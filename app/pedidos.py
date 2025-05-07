import pandas as pd
import requests
import os
import sqlite3
import itertools
import streamlit as st
import threading
import time

OPENCAGE_KEYS = [
    "5161dbd006cf4c43a7f7dd789ee1a3da",
    "6f522c67add14152926990afbe127384",
    "6c2d02cafb2e4b49aa3485a62262e54b"
]
key_cycle = itertools.cycle(OPENCAGE_KEYS)

def definir_regiao(row):
    cidade = str(row.get("Cidade de Entrega", "")).strip()
    bairro = str(row.get("Bairro de Entrega", "")).strip()
    if cidade.lower() == "são paulo" and bairro:
        return f"{bairro} - São Paulo"
    elif cidade:
        return cidade
    # fallback: tenta extrair do endereço completo
    endereco = str(row.get("Endereço Completo", ""))
    partes = [p.strip() for p in endereco.split(",") if p.strip()]
    if len(partes) >= 2:
        if "são paulo" in partes[-2].lower() and len(partes) >= 3:
            return f"{partes[-3]} - São Paulo"
        return partes[-2]
    return "N/A"

def obter_coordenadas_opencage(endereco):
    key = next(key_cycle)
    url = f"https://api.opencagedata.com/geocode/v1/json?q={requests.utils.quote(str(endereco or ''))}&key={key}&language=pt&countrycode=br&limit=1"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results")
            if results:
                geometry = results[0]["geometry"]
                return geometry["lat"], geometry["lng"]
    except Exception:
        pass
    return None, None

def obter_coordenadas_nominatim(endereco):
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={requests.utils.quote(endereco)}&addressdetails=0&limit=1"
        headers = {"User-Agent": "roteirizador_entregas"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            results = resp.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None, None

def carregar_coordenadas_salvas():
    # Agora carrega de um CSV simples
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'coordenadas.csv')
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path, dtype=str)
        return {(str(row['CNPJ']) + '|' + str(row['Endereço Completo'])): (float(row['Latitude']), float(row['Longitude']))
                for _, row in df.iterrows() if pd.notnull(row['Latitude']) and pd.notnull(row['Longitude'])}
    except Exception:
        return {}

def buscar_coordenadas_no_dict(endereco, coord_dict):
    # Agora a chave é CNPJ|Endereço Completo
    cnpj = None
    endereco_completo = None
    if isinstance(endereco, dict):
        cnpj = endereco.get('CNPJ', '')
        endereco_completo = endereco.get('Endereço Completo', '')
    else:
        # Para compatibilidade, assume que endereco é o endereço completo e CNPJ não está disponível
        endereco_completo = endereco
    for key in coord_dict:
        if cnpj and key.startswith(str(cnpj)+'|') and key.endswith(endereco_completo):
            lat, lon = coord_dict[key]
            if pd.notnull(lat) and pd.notnull(lon):
                return lat, lon
        elif not cnpj and key.endswith(endereco_completo):
            lat, lon = coord_dict[key]
            if pd.notnull(lat) and pd.notnull(lon):
                return lat, lon
    return None, None

def obter_coordenadas(endereco):
    # Busca apenas em APIs externas, pois a busca no banco já é feita no fluxo principal
    cnpj = None
    if isinstance(endereco, dict):
        cnpj = endereco.get('CNPJ', None)
        endereco_completo = endereco.get('Endereço Completo', None)
    else:
        endereco_completo = endereco
    lat, lon = obter_coordenadas_opencage(endereco_completo)
    if lat is not None and lon is not None:
        salvar_coordenada_csv(cnpj, endereco_completo, lat, lon)
        return lat, lon
    lat, lon = obter_coordenadas_nominatim(endereco_completo)
    if lat is not None and lon is not None:
        salvar_coordenada_csv(cnpj, endereco_completo, lat, lon)
    return lat, lon

# Função para salvar coordenada no CSV
def salvar_coordenada_csv(cpf_cnpj, endereco_completo, latitude, longitude):
    import pandas as pd
    import os
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'coordenadas.csv')
    # Carrega ou cria DataFrame
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, dtype=str)
    else:
        df = pd.DataFrame(columns=['CNPJ', 'Endereço Completo', 'Latitude', 'Longitude'])
    # Remove duplicata se já existir
    mask = (df['CNPJ'] == str(cpf_cnpj)) & (df['Endereço Completo'] == str(endereco_completo))
    df = df[~mask]
    # Adiciona nova linha
    new_row = {
        'CNPJ': str(cpf_cnpj) if cpf_cnpj is not None else '',
        'Endereço Completo': str(endereco_completo),
        'Latitude': str(latitude),
        'Longitude': str(longitude)
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(csv_path, index=False)

def processar_pedidos(arquivo, max_linhas=None, tamanho_lote=50, delay_lote=0):
    nome = arquivo.name if hasattr(arquivo, 'name') else str(arquivo)
    ext = os.path.splitext(nome)[-1].lower()
    if ext in ['.xlsx', '.xlsm']:
        df = pd.read_excel(arquivo)
    elif ext == '.csv':
        # Tenta detectar o separador e encoding
        try:
            df = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8-sig') # Tenta UTF-8 com BOM
        except Exception:
            try:
                # Volta para o arquivo original se a primeira tentativa falhar
                if hasattr(arquivo, 'seek'):
                    arquivo.seek(0)
                df = pd.read_csv(arquivo, sep=None, engine='python') # Tenta detectar automaticamente
            except Exception as e:
                 raise ValueError(f"Erro ao ler CSV. Verifique o formato e encoding. Erro: {e}")
    elif ext == '.json':
        df = pd.read_json(arquivo)
    else:
        raise ValueError('Formato de arquivo não suportado.')

    # Garante que a coluna CNPJ exista e esteja formatada corretamente
    import re
    def formatar_cnpj(cnpj):
        if pd.isnull(cnpj):
            return ''
        cnpj_str = re.sub(r'\D', '', str(cnpj))
        if len(cnpj_str) == 14:
            return f"{cnpj_str[:2]}.{cnpj_str[2:5]}.{cnpj_str[5:8]}/{cnpj_str[8:12]}-{cnpj_str[12:]}"
        return cnpj

    if 'CNPJ' in df.columns:
        df['CNPJ'] = df['CNPJ'].apply(formatar_cnpj)

    # Padroniza CNPJ se existir
    if 'CNPJ' in df.columns:
        df['CNPJ'] = df['CNPJ'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(14)

    # Não é mais necessário remover a coluna CPF/CNPJ, pois ela não será criada
    # --- Lógica de Endereço Ajustada ---
    # --- Garante colunas essenciais ---
    # 1. Cria a coluna Região ANTES de Endereço Completo, usando as regras solicitadas
    if 'Cidade de Entrega' in df.columns:
        def definir_regiao(row):
            cidade = str(row.get('Cidade de Entrega', '')).strip()
            bairro = str(row.get('Bairro de Entrega', '')).strip()
            if cidade.lower() == 'são paulo' and bairro:
                return f"São Paulo - {bairro}"
            return cidade
        df['Região'] = df.apply(definir_regiao, axis=1)
    else:
        df['Região'] = ''
    # 2. Cria a coluna Endereço Completo (se não existir)
    if 'Endereço Completo' not in df.columns:
        colunas_endereco_necessarias = [
            'Endereço de Entrega', 'Bairro de Entrega', 'Cidade de Entrega', 'Estado de Entrega'
        ]
        colunas_faltantes = [col for col in colunas_endereco_necessarias if col not in df.columns]
        if not colunas_faltantes:
            df['Endereço Completo'] = (
                df['Endereço de Entrega'].fillna('').astype(str) + ', ' +
                df['Bairro de Entrega'].fillna('').astype(str) + ', ' +
                df['Cidade de Entrega'].fillna('').astype(str) + ', ' +
                df['Estado de Entrega'].fillna('').astype(str)
            )
            df['Endereço Completo'] = df['Endereço Completo'].str.replace(r'^,\s*|,?\s*,\s*$', '', regex=True).str.strip()
            df['Endereço Completo'] = df['Endereço Completo'].str.replace(r'\s*,\s*,', ',', regex=True)
            try:
                df = df.drop(colunas_endereco_necessarias, axis=1)
            except KeyError:
                st.warning("Não foi possível remover colunas de endereço originais após criar 'Endereço Completo'.")
        else:
            raise ValueError(
                f"Erro: Coluna 'Endereço Completo' não encontrada e colunas necessárias para criá-la ({', '.join(colunas_faltantes)}) também estão ausentes."
            )
    else:
        st.info("Coluna 'Endereço Completo' encontrada no arquivo. Usando-a diretamente.")
        df['Endereço Completo'] = df['Endereço Completo'].fillna('').astype(str)

    # --- Garante colunas de janela de tempo e tempo de serviço para VRPTW ---
    if 'Janela de Descarga' not in df.columns:
        df['Janela de Descarga'] = 30
    if 'Latitude' not in df.columns:
        df['Latitude'] = None
    if 'Longitude' not in df.columns:
        df['Longitude'] = None

    if 'Janela Início' not in df.columns:
        df['Janela Início'] = "06:00"
    else:
        df['Janela Início'] = df['Janela Início'].fillna('').replace('', '06:00')
    if 'Janela Fim' not in df.columns:
        df['Janela Fim'] = "20:00"
    else:
        df['Janela Fim'] = df['Janela Fim'].fillna('').replace('', '20:00')
    if 'Tempo de Serviço' not in df.columns:
        df['Tempo de Serviço'] = "00:30"
    else:
        df['Tempo de Serviço'] = df['Tempo de Serviço'].fillna('').replace('', '00:30')

    # --- Continua o processamento ---
    # Limitar número de linhas para teste, se max_linhas for fornecido
    if max_linhas is not None:
        df = df.head(max_linhas)

    n = len(df)
    if n == 0:
        st.error("A planilha está vazia após o processamento. Nenhum pedido a importar.")
        return df
    latitudes = [None] * n
    longitudes = [None] * n
    progress_bar = st.progress(0, text="Buscando coordenadas...")
    coord_dict = carregar_coordenadas_salvas()
    tempo_inicio = time.time()

    def buscar_coordenada_db(endereco):
        from app.database import buscar_coordenada
        return buscar_coordenada(endereco)
    def processar_linha(i, row):
        if i >= len(latitudes) or i >= len(longitudes):
            return  # Protege contra acesso fora do limite
        lat = row.get('Latitude') # Pega Latitude da linha (planilha)
        lon = row.get('Longitude') # Pega Longitude da linha (planilha)

        # Verifica se Latitude e Longitude da planilha são válidas
        if pd.notnull(lat) and pd.notnull(lon):
            # Se forem válidas, usa elas diretamente
            latitudes[i] = lat
            longitudes[i] = lon
        else:
            # SOMENTE SE NÃO forem válidas na planilha, busca no dict/db/api
            lat, lon = buscar_coordenadas_no_dict(row['Endereço Completo'], coord_dict)
            if lat is not None and lon is not None:
                latitudes[i] = lat
                longitudes[i] = lon
            else:
                lat, lon = buscar_coordenada_db(row['Endereço Completo'])
                if lat is not None and lon is not None:
                    latitudes[i] = lat
                    longitudes[i] = lon
                else:
                    lat, lon = obter_coordenadas(row['Endereço Completo'])
                    latitudes[i] = lat
                    longitudes[i] = lon
    # Processamento em lotes
    for inicio in range(0, n, tamanho_lote):
        fim = min(inicio + tamanho_lote, n)
        threads = []
        for i in range(inicio, fim):
            if i >= len(df):
                continue  # Protege contra acesso fora do limite
            row = df.iloc[i]
            t = threading.Thread(target=processar_linha, args=(i, row))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        progresso = (fim) / n
        tempo_decorrido = time.time() - tempo_inicio
        tempo_estimado = tempo_decorrido / progresso if progresso > 0 else 0
        tempo_restante = tempo_estimado - tempo_decorrido
        progress_bar.progress(progresso, text=f"Buscando coordenadas... ({fim}/{n}) | Tempo restante: {int(tempo_restante)}s")
        if fim < n:
            time.sleep(delay_lote)
    df['Latitude'] = latitudes
    df['Longitude'] = longitudes
    progress_bar.empty()

    # Normalização e detecção de anomalias
    df = df.drop_duplicates()
    # Garante que 'Nº Pedido' exista antes de usar no dropna
    colunas_essenciais_dropna = ['Endereço Completo']
    if 'Nº Pedido' in df.columns:
        colunas_essenciais_dropna.append('Nº Pedido')
    else:
        st.warning("Coluna 'Nº Pedido' não encontrada. Não será usada para remover linhas nulas.")

    df = df.dropna(subset=colunas_essenciais_dropna)

    # --- Agrupamento automático por KMeans nas coordenadas, por Região ---
    if 'Latitude' in df.columns and 'Longitude' in df.columns and 'Região' in df.columns:
        from routing.utils import clusterizar_pedidos_por_regiao_ou_kmeans
        clusters = []
        regioes_unicas = df['Região'].dropna().unique()
        for regiao in regioes_unicas:
            mask = df['Região'] == regiao
            n_clusters = 1
            if 'frota' in st.session_state and st.session_state['frota'] is not None:
                n_clusters = max(1, len(st.session_state['frota']))
            clusters_regiao = clusterizar_pedidos_por_regiao_ou_kmeans(df[mask], n_clusters=n_clusters)
            clusters_regiao = [int(c) if c != -1 else -1 for c in clusters_regiao]
            clusters.extend(list(zip(df[mask].index, clusters_regiao)))
        # Preenche a coluna Cluster com -1 por padrão
        df['Cluster'] = -1
        for idx, cluster in clusters:
            df.at[idx, 'Cluster'] = cluster

    # Reorganizar colunas na ordem desejada (adapta se colunas não existirem)
    colunas_ordem_base = [
        "Nº Pedido", "Cód. Cliente", "CNPJ", "Nome Cliente", "Grupo Cliente",
        "Região", "Endereço Completo", "Qtde. dos Itens", "Peso dos Itens",
        "Latitude", "Longitude", "Janela de Descarga", "Anomalia"
    ]
    colunas_presentes_ordenadas = [col for col in colunas_ordem_base if col in df.columns]
    # Adiciona quaisquer outras colunas que não estavam na lista base ao final
    outras_colunas = [col for col in df.columns if col not in colunas_presentes_ordenadas]
    df = df[colunas_presentes_ordenadas + outras_colunas]

    return df
