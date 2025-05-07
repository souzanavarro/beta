import pandas as pd
import requests
import os
import sqlite3
import itertools
import streamlit as st
import threading
import time
import logging

logging.basicConfig(level=logging.INFO)

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

def processar_pedidos(arquivo, max_linhas=None):
    import logging
    logging.basicConfig(level=logging.INFO)
    nome = arquivo.name if hasattr(arquivo, 'name') else str(arquivo)
    ext = os.path.splitext(nome)[-1].lower()
    try:
        if ext in ['.xlsx', '.xlsm']:
            df = pd.read_excel(arquivo)
        elif ext == '.csv':
            df = pd.read_csv(arquivo, encoding='utf-8-sig')
        elif ext == '.json':
            df = pd.read_json(arquivo)
        else:
            raise ValueError('Formato de arquivo não suportado.')
    except Exception as e:
        logging.error(f"Erro ao ler arquivo: {e}")
        st.error(f"Erro ao ler arquivo: {e}")
        return pd.DataFrame()

    logging.info(f"Arquivo lido com {len(df)} linhas.")
    if max_linhas is not None:
        df = df.head(max_linhas)
    if df.empty:
        st.error("A planilha está vazia após o processamento.")
        return df

    # 1. Cria a coluna Região usando cidade/bairro conforme solicitado
    def definir_regiao(row):
        cidade = str(row.get('Cidade de Entrega', '')).strip()
        bairro = str(row.get('Bairro de Entrega', '')).strip()
        if cidade.lower() == 'são paulo' and bairro:
            return f"{bairro} - São Paulo"
        elif cidade:
            return cidade
        return ''

    # Garante que a coluna Região seja criada logo após o carregamento e após qualquer limpeza
    if 'Cidade de Entrega' in df.columns:
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

    # Garante colunas essenciais
    for col in ["Latitude", "Longitude", "Endereço Completo"]:
        if col not in df.columns:
            df[col] = None if col in ["Latitude", "Longitude"] else ""

    # Processa coordenadas diretamente no DataFrame
    coord_dict = carregar_coordenadas_salvas()
    for idx, row in df.iterrows():
        lat = row.get("Latitude")
        lon = row.get("Longitude")
        if pd.notnull(lat) and pd.notnull(lon):
            continue
        endereco = row.get("Endereço Completo", "")
        lat_db, lon_db = buscar_coordenadas_no_dict(endereco, coord_dict)
        if lat_db is not None and lon_db is not None:
            df.at[idx, "Latitude"] = lat_db
            df.at[idx, "Longitude"] = lon_db
            continue
        lat_api, lon_api = obter_coordenadas(endereco)
        df.at[idx, "Latitude"] = lat_api
        df.at[idx, "Longitude"] = lon_api
        logging.info(f"Coordenada processada para linha {idx}: {lat_api}, {lon_api}")

    # Remove duplicatas e linhas sem endereço
    df = df.drop_duplicates()
    if "Endereço Completo" in df.columns:
        df = df.dropna(subset=["Endereço Completo"])

    # Recalcula a coluna Região após limpeza para garantir consistência
    if 'Cidade de Entrega' in df.columns:
        df['Região'] = df.apply(definir_regiao, axis=1)
    else:
        df['Região'] = ''

    logging.info(f"Processamento finalizado. Linhas após limpeza: {len(df)}")
    return df
