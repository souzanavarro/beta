import pandas as pd
import os

PLACAS_PROIBIDAS = {"FLB1111", "FLB2222", "FLB3333", "FLB4444", "FLB5555", "FLB6666", "FLB7777", "FLB888", "FLB9999"}

def processar_frota(arquivo):
    # Detecta o formato do arquivo
    nome = arquivo.name if hasattr(arquivo, 'name') else str(arquivo)
    ext = os.path.splitext(nome)[-1].lower()
    if ext in ['.xlsx', '.xlsm']:
        df = pd.read_excel(arquivo)
    elif ext == '.csv':
        df = pd.read_csv(arquivo)
    elif ext == '.json':
        df = pd.read_json(arquivo)
    else:
        raise ValueError('Formato de arquivo não suportado.')
    # Geração de ID do veículo igual à Placa
    df['ID Veículo'] = df['Placa'].astype(str)
    # Garante colunas essenciais de janela de tempo
    if 'Janela Início' not in df.columns:
        df['Janela Início'] = '00:00'
    if 'Janela Fim' not in df.columns:
        df['Janela Fim'] = '23:59'
    # Normalização de capacidade
    df['Capacidade (Cx)'] = pd.to_numeric(df['Capacidade (Cx)'], errors='coerce').fillna(0)
    df['Capacidade (Kg)'] = pd.to_numeric(df['Capacidade (Kg)'], errors='coerce').fillna(0)
    # Remove placas proibidas
    df = df[~df['Placa'].astype(str).isin(PLACAS_PROIBIDAS)]
    # Verifica duplicidade de placas
    if df['Placa'].duplicated().any():
        placas_duplicadas = df[df['Placa'].duplicated(keep=False)]['Placa'].unique()
        raise ValueError(f"Placas duplicadas encontradas: {', '.join(placas_duplicadas)}")
    # Indicação de veículos disponíveis
    df['Disponível'] = df['Disponível'].astype(str).str.lower().isin(['sim', 'yes', '1', 'true'])
    # Reorganizar colunas na ordem desejada
    colunas_ordem = [
        "Placa", "Transportador", "Descrição", "Veículo",
        "Capacidade (Cx)", "Capacidade (Kg)", "Disponível"
    ]
    df = df[[col for col in colunas_ordem if col in df.columns]]
    return df
