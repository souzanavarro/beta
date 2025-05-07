import logging
import pandas as pd
import numpy as np

def get_logger(name=__name__):
    """Retorna logger padronizado para o projeto."""
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logger

def validar_dataframe(df, colunas_obrigatorias=None, nome_df='DataFrame'):
    """Valida se o DataFrame possui as colunas obrigatórias e não está vazio."""
    if df is None or df.empty:
        return False, f"{nome_df} está vazio ou não foi carregado."
    if colunas_obrigatorias:
        faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
        if faltantes:
            return False, f"Colunas obrigatórias ausentes em {nome_df}: {faltantes}"
    return True, "OK"

def validar_matriz(matriz, tamanho_esperado=None):
    """Valida se a matriz é um array/lista quadrada e, se fornecido, do tamanho esperado."""
    if matriz is None:
        return False, "Matriz não fornecida."
    arr = np.array(matriz)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        return False, f"Matriz não é quadrada: shape={arr.shape}"
    if tamanho_esperado and arr.shape[0] != tamanho_esperado:
        return False, f"Matriz tem tamanho {arr.shape[0]}, esperado {tamanho_esperado}"
    return True, "OK"

def clusterizar_pedidos_por_regiao_ou_kmeans(pedidos, n_clusters):
    """
    Agrupa pedidos por KMeans nas coordenadas (Latitude, Longitude), ignorando a coluna 'Região'.
    Retorna um array de labels (um para cada pedido).
    """
    import numpy as np
    from sklearn.cluster import KMeans
    # Garante que as colunas estejam no padrão correto
    if 'Latitude' not in pedidos.columns or 'Longitude' not in pedidos.columns:
        raise ValueError("DataFrame deve conter colunas 'Latitude' e 'Longitude' para clusterização.")
    coords = pedidos[['Latitude', 'Longitude']].dropna()
    if coords.empty:
        return np.zeros(len(pedidos), dtype=int)  # Todos no mesmo cluster se não houver coordenadas
    n_clusters = min(n_clusters, len(coords))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
    labels = kmeans.fit_predict(coords)
    # Cria um array de labels para todos os pedidos (mesmo os sem coordenada)
    full_labels = np.full(len(pedidos), -1, dtype=int)
    full_labels[coords.index] = labels
    return full_labels
