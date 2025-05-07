import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import numpy as np
import time
import logging
from routing import pos_processamento
from routing.utils import get_logger, validar_dataframe, validar_matriz

def solver_cvrp_flex(pedidos, frota, matriz_distancias, depot_index=0, ajuste_capacidade_pct=100, cenarios=None, diagnostico=False, metricas=False, pos_processamento=False, tipo_heuristica='2opt', kwargs_heuristica=None):
    """
    Resolve o problema CVRP permitindo ajuste percentual da capacidade dos veículos.
    Suporta simulação de cenários, diagnóstico de inviabilidade e retorno de métricas detalhadas.
    Se pos_processamento=True, aplica heurística ('2opt', 'merge', 'split') automaticamente nas rotas geradas.
    Exemplo de uso:
        resultado = solver_cvrp_flex(pedidos, frota, matriz_distancias, pos_processamento=True, tipo_heuristica='merge')
    
    Args:
        pedidos (pd.DataFrame): DataFrame dos pedidos, deve conter 'Peso dos Itens'.
        frota (pd.DataFrame): DataFrame da frota, deve conter 'Capacidade (Kg)'.
        matriz_distancias (np.ndarray or list): Matriz de distâncias entre todos os pontos (depósito + clientes).
        depot_index (int): Índice do depósito na matriz de distâncias (default=0).
        ajuste_capacidade_pct (int): Percentual de ajuste da capacidade dos veículos (default=100, pode ser até 120).
        cenarios (list): Lista de dicionários com parâmetros para simulação de cenários.
        diagnostico (bool): Se True, retorna diagnóstico detalhado em caso de inviabilidade.
        metricas (bool): Se True, retorna métricas detalhadas da solução.
        pos_processamento (bool): Se True, aplica heurística de pós-processamento nas rotas geradas.
        tipo_heuristica (str): Tipo de heurística de pós-processamento ('2opt', 'merge', 'split').
        kwargs_heuristica (dict): Parâmetros adicionais para a heurística de pós-processamento.
    
    Returns:
        dict: Resultados por cenário, incluindo solução, diagnóstico e métricas.
    """
    logger = get_logger(__name__)
    if kwargs_heuristica is None:
        kwargs_heuristica = {}
    ok_ped, msg_ped = validar_dataframe(pedidos, ['Peso dos Itens'], 'Pedidos')
    ok_frota, msg_frota = validar_dataframe(frota, ['Capacidade (Kg)'], 'Frota')
    ok_mat, msg_mat = validar_matriz(matriz_distancias)
    if not ok_ped:
        logger.warning(f"CVRP Flex: {msg_ped}")
        return {'diagnostico': msg_ped}
    if not ok_frota:
        logger.warning(f"CVRP Flex: {msg_frota}")
        return {'diagnostico': msg_frota}
    if not ok_mat:
        logger.error(f"CVRP Flex: {msg_mat}")
        return {'diagnostico': msg_mat}

    def run_solver(pedidos, frota, matriz_distancias, depot_index, ajuste_capacidade_pct):
        start_time = time.time()
        resultado = {
            'pedidos_result': None,
            'diagnostico': None,
            'metricas': None
        }
        if pedidos is None or pedidos.empty or frota is None or frota.empty or matriz_distancias is None:
            resultado['diagnostico'] = 'Dados de entrada ausentes ou vazios.'
            return resultado

        num_vehicles = len(frota)
        num_nodes = len(matriz_distancias)
        if num_nodes < 2 or num_vehicles < 1:
            resultado['diagnostico'] = 'Frota ou matriz de distâncias insuficiente.'
            return resultado

        demanda_total = pedidos['Peso dos Itens'].fillna(0).sum()
        ajuste = max(0, min(ajuste_capacidade_pct, 120)) / 100.0
        capacidade_total = (frota['Capacidade (Kg)'].fillna(0).astype(float) * ajuste).sum()
        if capacidade_total < demanda_total:
            resultado['diagnostico'] = f"Demanda total ({demanda_total}) excede capacidade total da frota ({capacidade_total})."
            return resultado

        manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, depot_index)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(matriz_distancias[from_node][to_node])

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        demands = [0] + pedidos['Peso dos Itens'].fillna(0).astype(int).tolist()
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return demands[from_node]
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)

        capacities = (frota['Capacidade (Kg)'].fillna(0).astype(float) * ajuste).astype(int).tolist()
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            capacities,
            True,
            'Capacity')

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        search_parameters.time_limit.seconds = 60

        solution = routing.SolveWithParameters(search_parameters)

        pedidos_result = pedidos.copy()
        pedidos_result['Veículo'] = None
        pedidos_result['Sequencia'] = None
        pedidos_result['Node_Index_OR'] = None
        pedidos_result['distancia'] = None
        total_dist = 0
        veiculos_usados = 0
        pedidos_atendidos = set()
        rotas_por_veiculo = []  # Para pós-processamento

        if solution:
            for vehicle_id in range(num_vehicles):
                index = routing.Start(vehicle_id)
                seq = 1
                placa = frota.iloc[vehicle_id]['Placa'] if 'Placa' in frota.columns and vehicle_id < len(frota) else str(vehicle_id)
                route_dist = 0
                used = False
                rota_indices = [depot_index]
                while not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    if node_index != depot_index and node_index-1 < len(pedidos):
                        pedidos_result.at[node_index-1, 'Veículo'] = placa
                        pedidos_result.at[node_index-1, 'Sequencia'] = seq
                        pedidos_result.at[node_index-1, 'Node_Index_OR'] = node_index
                        next_index = solution.Value(routing.NextVar(index))
                        dist = matriz_distancias[node_index][manager.IndexToNode(next_index)]
                        pedidos_result.at[node_index-1, 'distancia'] = dist
                        route_dist += dist
                        seq += 1
                        pedidos_atendidos.add(node_index-1)
                        used = True
                        rota_indices.append(node_index)
                    index = solution.Value(routing.NextVar(index))
                if used:
                    veiculos_usados += 1
                    total_dist += route_dist
                    rota_indices.append(depot_index)
                    rotas_por_veiculo.append(rota_indices)
            pedidos_result['Pedido_Index_DF'] = pedidos_result.index
            # --- Pós-processamento automático ---
            if pos_processamento and len(rotas_por_veiculo) > 0:
                logger.info(f"Aplicando pós-processamento '{tipo_heuristica}' nas rotas...")
                matriz_np = np.array(matriz_distancias)
                rotas_otimizadas = []
                if tipo_heuristica == '2opt':
                    for rota in rotas_por_veiculo:
                        if len(rota) > 3:
                            rota_opt = pos_processamento.heuristica_2opt(rota, matriz_np)
                            rotas_otimizadas.append(rota_opt)
                        else:
                            rotas_otimizadas.append(rota)
                elif tipo_heuristica == 'merge':
                    rotas_otimizadas = pos_processamento.merge(rotas_por_veiculo, matriz_np, **kwargs_heuristica)
                elif tipo_heuristica == 'split':
                    max_paradas = kwargs_heuristica.get('max_paradas_por_subrota', 5)
                    for rota in rotas_por_veiculo:
                        rotas_otimizadas.extend(pos_processamento.split(rota, max_paradas))
                else:
                    logger.warning(f"Tipo de heurística '{tipo_heuristica}' não reconhecido. Nenhum pós-processamento aplicado.")
                    rotas_otimizadas = rotas_por_veiculo
                logger.info(f"Rotas após pós-processamento: {rotas_otimizadas}")
                # Opcional: atualizar pedidos_result ou retornar as rotas otimizadas separadamente
        else:
            resultado['diagnostico'] = 'Não foi encontrada solução viável para o cenário.'
            if diagnostico:
                resultado['diagnostico'] += f' Demanda total: {demanda_total}, Capacidade total: {capacidade_total}, Veículos: {num_vehicles}'
        return resultado

    resultados = {}
    if cenarios:
        for i, cenario in enumerate(cenarios):
            params = {
                'pedidos': cenario.get('pedidos', pedidos),
                'frota': cenario.get('frota', frota),
                'matriz_distancias': cenario.get('matriz_distancias', matriz_distancias),
                'depot_index': cenario.get('depot_index', depot_index),
                'ajuste_capacidade_pct': cenario.get('ajuste_capacidade_pct', ajuste_capacidade_pct)
            }
            resultados[f'Cenário_{i+1}'] = run_solver(**params)
    else:
        resultados['Cenário_1'] = run_solver(pedidos, frota, matriz_distancias, depot_index, ajuste_capacidade_pct)
    return resultados
