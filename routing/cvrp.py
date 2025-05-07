from routing.utils import get_logger, validar_dataframe, validar_matriz

def solver_cvrp(pedidos, frota, matriz_distancias, pos_processamento=False, tipo_heuristica='2opt', kwargs_heuristica=None, ajuste_capacidade_pct=100):
    """
    Capacitated VRP: considera a capacidade máxima de carga dos veículos além da roteirização.
    Se pos_processamento=True, aplica heurística ('2opt', 'merge', 'split') automaticamente nas rotas geradas.
    ajuste_capacidade_pct: percentual de ajuste da capacidade dos veículos (default=100, pode ser até 120).
    """
    import pandas as pd
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    import numpy as np
    from routing import pos_processamento

    logger = get_logger(__name__)

    if kwargs_heuristica is None:
        kwargs_heuristica = {}

    ok_ped, msg_ped = validar_dataframe(pedidos, ['Peso dos Itens'], 'Pedidos')
    ok_frota, msg_frota = validar_dataframe(frota, ['Capacidade (Kg)'], 'Frota')
    ok_mat, msg_mat = validar_matriz(matriz_distancias)

    if not ok_ped:
        logger.warning(f"CVRP Solver: {msg_ped}")
        return pd.DataFrame() # Retorna DataFrame vazio
    if not ok_frota:
        logger.warning(f"CVRP Solver: {msg_frota}")
        return pd.DataFrame() # Retorna DataFrame vazio
    if not ok_mat:
        logger.error(f"CVRP Solver: {msg_mat}")
        return pd.DataFrame() # Retorna DataFrame vazio

    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)

    n_pedidos = len(pedidos)
    n_veiculos = len(frota)
    depot_index = 0 # Assumindo que o depósito é sempre o índice 0 na matriz_distancias

    # --- Preparação dos Dados para OR-Tools ---
    # Demanda (garantir que seja numérica e tratar NaNs)
    if 'Peso dos Itens' in pedidos.columns:
        demands_series = pd.to_numeric(pedidos['Peso dos Itens'], errors='coerce').fillna(1)
    elif 'Qtde. dos Itens' in pedidos.columns:
        demands_series = pd.to_numeric(pedidos['Qtde. dos Itens'], errors='coerce').fillna(1)
    else:
        logger.warning("CVRP Solver: Coluna de demanda ('Peso dos Itens' ou 'Qtde. dos Itens') não encontrada. Usando demanda 1 para todos.")
        demands_series = pd.Series([1] * n_pedidos)
    # Adiciona 0 para o depósito no início da lista de demandas
    demands = [0] + demands_series.astype(int).tolist()

    # Capacidade (garantir que seja numérica e tratar NaNs/zeros)
    ajuste = max(0, min(ajuste_capacidade_pct, 120)) / 100.0
    if 'Capacidade (Kg)' in frota.columns:
        capacities_series = pd.to_numeric(frota['Capacidade (Kg)'], errors='coerce').fillna(1) * ajuste
    elif 'Capacidade (Cx)' in frota.columns:
        capacities_series = pd.to_numeric(frota['Capacidade (Cx)'], errors='coerce').fillna(1) * ajuste
    else:
        logger.warning("CVRP Solver: Coluna de capacidade ('Capacidade (Kg)' ou 'Capacidade (Cx)') não encontrada. Usando capacidade 1000 para todos.")
        capacities_series = pd.Series([1000] * n_veiculos) * ajuste
    # Garante que capacidade seja pelo menos 1
    capacities = capacities_series.astype(int).clip(lower=1).tolist()

    # Matriz de distâncias (já deve incluir o depósito no índice 0)
    distance_matrix = np.array(matriz_distancias).astype(int).tolist() # Garante formato lista de listas de int
    num_locations = len(distance_matrix)

    if num_locations != n_pedidos + 1:
         logger.error(f"CVRP Solver: Inconsistência no tamanho da matriz de distâncias ({num_locations}) vs número de pedidos+depósito ({n_pedidos + 1}).")
         return pd.DataFrame()

    # --- Configuração do OR-Tools ---
    try:
        manager = pywrapcp.RoutingIndexManager(num_locations, n_veiculos, depot_index)
        routing = pywrapcp.RoutingModel(manager)

        # Callback de Distância
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # Validação de índices
            if 0 <= from_node < num_locations and 0 <= to_node < num_locations:
                return distance_matrix[from_node][to_node]
            else:
                logger.error(f"Índice fora dos limites no distance_callback: {from_node}, {to_node}")
                return 9999999 # Retorna um valor alto para penalizar rotas inválidas
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Callback de Demanda e Dimensão de Capacidade
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            # Validação de índices
            if 0 <= from_node < len(demands):
                return demands[from_node]
            else:
                 logger.error(f"Índice fora dos limites no demand_callback: {from_node}")
                 return 0 # Retorna 0 para evitar falhas, mas indica problema
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # Sem folga de capacidade
            capacities,  # Capacidades máximas dos veículos
            True,  # Começar cumulativo em zero
            'Capacity'
        )
        capacity_dimension = routing.GetDimensionOrDie('Capacity')

    except Exception as e:
        logger.error(f"Erro na configuração do OR-Tools: {e}")
        return pd.DataFrame()

    # --- Parâmetros de Busca ---
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 30 # Adiciona um limite de tempo

    # --- Resolução ---
    logger.info("Iniciando a resolução do CVRP com OR-Tools...")
    solution = routing.SolveWithParameters(search_parameters)
    logger.info("Resolução do CVRP concluída.")

    # --- Montagem do Resultado ---
    routes_data = []
    if solution:
        logger.info("Solução encontrada. Processando rotas...")
        total_distance_solution = 0
        pedidos_roteirizados_indices = set()
        rotas_por_veiculo = []  # Para pós-processamento

        for vehicle_id in range(n_veiculos):
            index = routing.Start(vehicle_id)
            sequence = 1 # Começa a sequência em 1 para o primeiro cliente
            vehicle_identifier = (
                frota['ID Veículo'].iloc[vehicle_id]
                if 'ID Veículo' in frota.columns and not frota.empty else
                frota['Placa'].iloc[vehicle_id] if 'Placa' in frota.columns and not frota.empty else f'veiculo_{vehicle_id+1}'
            )
            route_distance_vehicle = 0
            route_load_vehicle = 0
            rota_indices = [0]  # Começa no depósito

            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                load_var = capacity_dimension.CumulVar(index)
                current_load = solution.Value(load_var)

                if node_index != depot_index: # Não adiciona o depósito como uma parada na sequência
                    pedido_original_index = node_index - 1 # Ajusta para índice do DataFrame 'pedidos'
                    if 0 <= pedido_original_index < n_pedidos:
                        # Verifica se o pedido já foi roteirizado (não deveria acontecer com CVRP padrão)
                        if pedido_original_index in pedidos_roteirizados_indices:
                             logger.warning(f"Pedido {pedido_original_index} aparecendo em múltiplas rotas (Veículo {vehicle_identifier}). Verifique a lógica.")
                        else:
                            pedidos_roteirizados_indices.add(pedido_original_index)
                            pedido_info = pedidos.iloc[pedido_original_index]
                            routes_data.append({
                                'Veículo': vehicle_identifier,
                                'Sequencia': sequence,
                                'Node_Index_OR': node_index, # Índice do nó no OR-Tools (inclui depósito)
                                'Pedido_Index_DF': pedido_original_index, # Índice no DataFrame 'pedidos' original
                                'ID Pedido': pedido_info.get('ID Pedido', f'Pedido_{pedido_original_index}'),
                                'Cliente': pedido_info.get('Cliente', 'N/A'),
                                'Endereço': pedido_info.get('Endereço', 'N/A'),
                                'Demanda': demands[node_index],
                                'Carga_Acumulada': current_load,
                            })
                            sequence += 1
                            route_load_vehicle += demands[node_index] # Soma a demanda do nó atual
                            rota_indices.append(node_index)
                    else:
                         logger.warning(f"Índice de pedido inválido ({pedido_original_index}) encontrado na rota do veículo {vehicle_identifier}.")

                previous_index = index
                index = solution.Value(routing.NextVar(index))
                # Calcula a distância do arco
                arc_distance = routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
                route_distance_vehicle += arc_distance

            # Adiciona a distância do último nó de volta ao depósito (se houver rota)
            if routing.IsEnd(index) and manager.IndexToNode(previous_index) != depot_index:
                 end_node_index = routing.End(vehicle_id)
                 arc_distance = routing.GetArcCostForVehicle(previous_index, end_node_index, vehicle_id)
                 route_distance_vehicle += arc_distance

            if sequence > 1: # Se o veículo fez alguma entrega
                 logger.info(f"Veículo {vehicle_identifier}: {sequence-1} paradas, Carga={route_load_vehicle}, Dist={route_distance_vehicle/1000:.1f}km")
                 total_distance_solution += route_distance_vehicle
                 rota_indices.append(0)  # Fecha no depósito
                 rotas_por_veiculo.append(rota_indices)

        rotas_df = pd.DataFrame(routes_data)

        # --- Pós-processamento automático ---
        if pos_processamento and not rotas_df.empty and len(rotas_por_veiculo) > 0:
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
            # Opcional: atualizar rotas_df ou retornar as rotas otimizadas separadamente
            # Aqui apenas loga e retorna o DataFrame original para compatibilidade

        if rotas_df.empty:
             logger.warning("Solver CVRP encontrou uma solução, mas nenhuma rota válida foi gerada (talvez nenhum pedido atribuído).")
        else:
             logger.info(f"Total de {len(rotas_df)} paradas distribuídas.")
             logger.info(f"Distância total (solução OR-Tools): {total_distance_solution / 1000:.1f} km")
             # Verifica se todos os pedidos foram roteirizados
             pedidos_nao_roteirizados = n_pedidos - len(pedidos_roteirizados_indices)
             if pedidos_nao_roteirizados > 0:
                  logger.warning(f"{pedidos_nao_roteirizados} pedidos não foram incluídos nas rotas pela solução.")

        return rotas_df

    else:
        logger.warning("Solver CVRP não encontrou solução.")
        status_map = {
            routing.ROUTING_NOT_SOLVED: 'NOT_SOLVED',
            routing.ROUTING_FAIL: 'FAIL',
            routing.ROUTING_FAIL_TIMEOUT: 'FAIL_TIMEOUT',
            routing.ROUTING_INVALID: 'INVALID',
        }
        logger.warning(f"Status da solução: {routing.status()} ({status_map.get(routing.status(), 'UNKNOWN')})")
        # Tentar fornecer mais detalhes sobre a inviabilidade, se possível
        # (Ex: verificar se alguma demanda excede capacidade, etc. - já feito na página)
        return pd.DataFrame() # Retorna DataFrame vazio em caso de falha