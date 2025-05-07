import streamlit as st
from pedidos import processar_pedidos, obter_coordenadas
from database import carregar_pedidos, salvar_pedidos
import pandas as pd

st.markdown("""
<style>
.kpi-card {
    background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
    display: flex;
    align-items: center;
    gap: 1.2rem;
}
.kpi-icon {
    font-size: 2.2rem;
    margin-right: 1rem;
}
.section-title {
    font-size: 1.3rem;
    font-weight: 700;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
    color: #1976d2;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.alert-info {
    background: #e3f2fd;
    color: #1565c0;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.alert-success {
    background: #e8f5e9;
    color: #388e3c;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.alert-warning {
    background: #fffde7;
    color: #fbc02d;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.alert-error {
    background: #ffebee;
    color: #c62828;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
</style>
""", unsafe_allow_html=True)

def show():
    st.header("Gerenciar Pedidos", divider="rainbow")
    st.write("Importe, visualize, edite, adicione ou remova pedidos de entrega.")
    st.divider()
    if 'df_pedidos' not in st.session_state:
        st.session_state.df_pedidos = pd.DataFrame()
    arquivo = st.file_uploader("Upload da planilha de pedidos", type=["xlsx", "xlsm", "csv", "json"])
    if arquivo:
        try:
            with st.spinner("Processando pedidos e buscando coordenadas, isso pode levar alguns minutos..."):
                df = processar_pedidos(arquivo)
            st.session_state.df_pedidos = df.copy()
            salvar_pedidos(df)
            st.success("Pedidos importados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao processar os pedidos: {e}")
    df = st.session_state.df_pedidos
    if df.empty:
        df = carregar_pedidos()
        st.session_state.df_pedidos = df.copy()
    if not df.empty:
        # Remove coluna de janela de tempo se existir
        if 'Janela de Descarga' in df.columns:
            df = df.drop(columns=['Janela de Descarga'])
        # --- Região baseada em coordenadas (agrupamento KMeans) ---
        if 'Latitude' in df.columns and 'Longitude' in df.columns:
            from routing.utils import clusterizar_pedidos_por_regiao_ou_kmeans
            n_clusters = 1
            if 'frota' in st.session_state and st.session_state['frota'] is not None:
                n_clusters = max(1, len(st.session_state['frota']))
            df['Região'] = clusterizar_pedidos_por_regiao_ou_kmeans(df, n_clusters=n_clusters)
        # Garantir que as colunas Regiao, Endereco Completo, Latitude e Longitude existam e estejam corretas
        if 'Endereço de Entrega' in df.columns and 'Bairro de Entrega' in df.columns and 'Cidade de Entrega' in df.columns:
            df['Endereço Completo'] = df['Endereço de Entrega'].astype(str) + ', ' + df['Bairro de Entrega'].astype(str) + ', ' + df['Cidade de Entrega'].astype(str)
        if 'Latitude' not in df.columns:
            df['Latitude'] = None
        if 'Longitude' not in df.columns:
            df['Longitude'] = None
        # Filtro para ordenar a planilha por coluna
        colunas_ordenaveis = [c for c in df.columns if c != 'Janela de Descarga']
        coluna_ordem = st.selectbox("Ordenar por", colunas_ordenaveis, index=0)
        if coluna_ordem:
            df = df.sort_values(by=coluna_ordem, key=lambda x: x.astype(str)).reset_index(drop=True)
        # Filtros avançados
        if 'Região' in df.columns:
            regioes = sorted([r for r in df['Região'].dropna().unique() if r and str(r).strip() and str(r).lower() != 'nan'])
        else:
            regioes = []
        regiao_filtro = st.selectbox("Filtrar por região", ["Todas"] + regioes)
        status_filtro = st.selectbox("Status de coordenadas", ["Todos", "Com coordenadas", "Sem coordenadas"])
        df_filtrado = df.copy()
        if regiao_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Região'] == regiao_filtro]
        if status_filtro == "Com coordenadas":
            df_filtrado = df_filtrado[df_filtrado['Latitude'].notnull() & df_filtrado['Longitude'].notnull()]
        elif status_filtro == "Sem coordenadas":
            df_filtrado = df_filtrado[df_filtrado['Latitude'].isnull() | df_filtrado['Longitude'].isnull()]
        # Remove filtro de janela de tempo
        filtro = st.text_input("Buscar pedidos (qualquer campo)")
        if filtro:
            filtro_lower = filtro.lower()
            df_filtrado = df_filtrado[df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(filtro_lower).any(), axis=1)]
        # Validação visual: destacar linhas com dados faltantes
        def get_row_style(row):
            falta_lat = 'Latitude' not in row or pd.isnull(row.get('Latitude'))
            falta_lon = 'Longitude' not in row or pd.isnull(row.get('Longitude'))
            if falta_lat or falta_lon:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)
        # Garante que as colunas de janela de tempo e tempo de serviço estejam visíveis
        for col in ["Janela Início", "Janela Fim", "Tempo de Serviço"]:
            if col not in df_filtrado.columns:
                df_filtrado[col] = ""  # valor vazio se não existir
        # Garante que as colunas estejam na ordem desejada
        # Garante que CNPJ sempre estará presente no DataFrame e na tabela editável
        if "CNPJ" not in df_filtrado.columns:
            df_filtrado["CNPJ"] = ""
        colunas_editor = [c for c in df_filtrado.columns if c != 'Janela de Descarga']
        if "CNPJ" not in colunas_editor:
            # Tenta inserir após Cód. Cliente, se existir, senão no início
            if "Cód. Cliente" in colunas_editor:
                idx = colunas_editor.index("Cód. Cliente") + 1
                colunas_editor.insert(idx, "CNPJ")
            else:
                colunas_editor.insert(0, "CNPJ")
        for col in ["Janela Início", "Janela Fim", "Tempo de Serviço"]:
            if col not in colunas_editor:
                colunas_editor.append(col)
        # Garante que a coluna Região seja string para evitar erro do Streamlit
        if "Região" in df_filtrado.columns:
            df_filtrado["Região"] = df_filtrado["Região"].astype(str)
        # Exibir apenas a planilha editável, sem duplicar visualização
        st.subheader("Editar Pedidos")
        df_editado = st.data_editor(
            df_filtrado[colunas_editor],
            num_rows="dynamic",
            use_container_width=True,
            key="pedidos_editor",
            column_config={
                "Latitude": st.column_config.NumberColumn(
                    "Latitude",
                    help="Latitude do endereço de entrega."
                ),
                "Longitude": st.column_config.NumberColumn(
                    "Longitude",
                    help="Longitude do endereço de entrega."
                ),
                "Região": st.column_config.TextColumn(
                    "Região",
                    help="Região agrupada automaticamente pelo sistema."
                ),
                "Endereço Completo": st.column_config.TextColumn(
                    "Endereço Completo",
                    help="Endereço completo gerado a partir dos campos de endereço, bairro e cidade."
                ),
                "Janela Início": st.column_config.TextColumn(
                    "Janela Início",
                    help="Horário de início da janela de atendimento (ex: 06:00)"
                ),
                "Janela Fim": st.column_config.TextColumn(
                    "Janela Fim",
                    help="Horário de fim da janela de atendimento (ex: 20:00)"
                ),
                "Tempo de Serviço": st.column_config.TextColumn(
                    "Tempo de Serviço",
                    help="Tempo de serviço no local (ex: 00:30)"
                ),
            },
            column_order=colunas_editor,
            hide_index=True
        )
        if not df_editado.equals(df_filtrado):
            # Atualiza o DataFrame original com as edições feitas no filtrado
            df_update = df.copy()
            df_update.update(df_editado)
            st.session_state.df_pedidos = df_update.copy()
            salvar_pedidos(st.session_state.df_pedidos)
        # Botão para reprocessar coordenadas
        if st.button("Reprocessar Coordenadas", type="primary"):
            with st.spinner("Reprocessando coordenadas apenas para pedidos sem coordenadas..."):
                df_pedidos = st.session_state.df_pedidos.copy()
                mask_sem_coord = df_pedidos['Latitude'].isnull() | df_pedidos['Longitude'].isnull()
                pedidos_sem_coord = df_pedidos[mask_sem_coord]
                n = len(pedidos_sem_coord)
                if n == 0:
                    st.success("Todos os pedidos já possuem coordenadas!")
                else:
                    latitudes = df_pedidos['Latitude'].tolist()
                    longitudes = df_pedidos['Longitude'].tolist()
                    progress_bar = st.progress(0, text="Buscando coordenadas...")
                    for idx, (i, row) in enumerate(pedidos_sem_coord.iterrows()):
                        lat, lon = obter_coordenadas(row['Endereço Completo'])
                        latitudes[i] = lat
                        longitudes[i] = lon
                        progress_bar.progress((idx + 1) / n, text=f"Buscando coordenadas... ({idx+1}/{n})")
                    df_pedidos['Latitude'] = latitudes
                    df_pedidos['Longitude'] = longitudes
                    progress_bar.empty()
                    salvar_pedidos(df_pedidos)
                    st.session_state.df_pedidos = df_pedidos.copy()
                    st.success("Coordenadas reprocessadas apenas para pedidos sem coordenadas!")
                    st.rerun()
        # Botão para calcular/regenerar Cluster por agrupamento KMeans (mantém Região original)
        if st.button("Gerar/Atualizar Cluster automaticamente", type="primary"):
            if 'Latitude' in df_filtrado.columns and 'Longitude' in df_filtrado.columns:
                from routing.utils import clusterizar_pedidos_por_regiao_ou_kmeans
                n_clusters = 1
                if 'frota' in st.session_state and st.session_state['frota'] is not None:
                    n_clusters = max(1, len(st.session_state['frota']))
                df_filtrado['Cluster'] = clusterizar_pedidos_por_regiao_ou_kmeans(df_filtrado, n_clusters=n_clusters)
                st.session_state.df_pedidos.update(df_filtrado)
                salvar_pedidos(st.session_state.df_pedidos)
                st.success("Cluster dos pedidos atualizado automaticamente!")
                st.rerun()
            else:
                st.warning("É necessário que os pedidos tenham Latitude e Longitude para gerar o Cluster automaticamente.")
        # Botão para atualizar janelas de tempo e tempo de serviço
        if st.button("Atualizar Janela de Início, Fim e Tempo de Serviço para todos", type="primary"):
            df['Janela Início'] = "06:00"
            df['Janela Fim'] = "20:00"
            df['Tempo de Serviço'] = "00:30"
            st.session_state.df_pedidos = df.copy()
            salvar_pedidos(df)
            st.success("Janelas de tempo e tempo de serviço atualizadas para todos os pedidos!")
        st.divider()
        st.subheader("Remover pedidos")
        # Remover pedidos selecionados
        def format_option(x):
            num = df_editado.loc[x, 'Nº Pedido'] if 'Nº Pedido' in df_editado.columns else str(x)
            cliente = df_editado.loc[x, 'Nome Cliente'] if 'Nome Cliente' in df_editado.columns else ''
            return f"{num} - {cliente}" if cliente else f"{num}"
        indices_remover = st.multiselect("Selecione os pedidos para remover", df_editado.index.tolist(), format_func=format_option)
        if st.button("Remover selecionados") and indices_remover:
            # Remover do DataFrame original com base no 'Nº Pedido' selecionado
            if 'Nº Pedido' in df_editado.columns and 'Nº Pedido' in st.session_state.df_pedidos.columns:
                pedidos_remover = df_editado.loc[indices_remover, 'Nº Pedido']
                st.session_state.df_pedidos = st.session_state.df_pedidos[~st.session_state.df_pedidos['Nº Pedido'].isin(pedidos_remover)].reset_index(drop=True)
            else:
                st.session_state.df_pedidos = st.session_state.df_pedidos.drop(indices_remover).reset_index(drop=True)
            salvar_pedidos(st.session_state.df_pedidos)
            st.success("Pedidos removidos!")
            st.rerun()
        # Botão para limpar todos os pedidos
        if st.button("Limpar todos os pedidos", type="primary"):
            st.session_state.df_pedidos = pd.DataFrame()
            salvar_pedidos(st.session_state.df_pedidos)
            st.success("Todos os pedidos foram removidos!")
            st.rerun()
    st.divider()
    st.subheader("Adicionar novo pedido")
    with st.form("add_pedido_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            numero = st.text_input("Nº Pedido")
            cod_cliente = st.text_input("Cód. Cliente")
            cnpj = st.text_input("CNPJ")
            nome_cliente = st.text_input("Nome Cliente")
            grupo_cliente = st.text_input("Grupo Cliente")
        with col2:
            endereco_entrega = st.text_input("Endereço de Entrega")
            bairro_entrega = st.text_input("Bairro de Entrega")
            cidade_entrega = st.text_input("Cidade de Entrega")
            estado_entrega = st.text_input("Estado de Entrega")
            qtde_itens = st.number_input("Qtde. dos Itens", min_value=0, step=1)
            peso_itens = st.number_input("Peso dos Itens", min_value=0.0, step=1.0, format="%.2f")
        with col3:
            latitude = st.number_input("Latitude", format="%.14f", value=-23.51689237191825)
            longitude = st.number_input("Longitude", format="%.14f", value=-46.48921155767101)
            anomalia = st.checkbox("Anomalia")
        # Endereço Completo gerado automaticamente
        endereco_completo_final = f"{endereco_entrega}, {bairro_entrega}, {cidade_entrega}, {estado_entrega}".strip(', ')
        regiao_final = f"{bairro_entrega} - São Paulo" if cidade_entrega.strip().lower() == "são paulo" and bairro_entrega else cidade_entrega
        submitted = st.form_submit_button("Adicionar pedido")
        if submitted and numero:
            novo = {
                "Nº Pedido": numero,
                "Cód. Cliente": cod_cliente,
                "CNPJ": cnpj,
                "Nome Cliente": nome_cliente,
                "Grupo Cliente": grupo_cliente,
                "Endereço de Entrega": endereco_entrega,
                "Bairro de Entrega": bairro_entrega,
                "Cidade de Entrega": cidade_entrega,
                "Estado de Entrega": estado_entrega,
                "Qtde. dos Itens": qtde_itens,
                "Peso dos Itens": peso_itens,
                "Endereço Completo": endereco_completo_final,
                "Região": regiao_final,
                "Latitude": latitude,
                "Longitude": longitude,
                "Anomalia": anomalia
            }
            st.session_state.df_pedidos = pd.concat([st.session_state.df_pedidos, pd.DataFrame([novo])], ignore_index=True)
            salvar_pedidos(st.session_state.df_pedidos)
            st.success("Pedido adicionado!")
            st.rerun()
    # Exportação de anomalias para CSV
    if 'df_filtrado' in locals():
        anomalias = df_filtrado[df_filtrado['Latitude'].isnull() | df_filtrado['Longitude'].isnull()]
        if not anomalias.empty:
            st.download_button(
                label="Exportar anomalias para CSV",
                data=anomalias.to_csv(index=False).encode('utf-8'),
                file_name=f"anomalias_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    # Visualização de pedidos no mapa (fora do formulário)
    if 'df_filtrado' in locals() and st.button("Visualizar pedidos no mapa"):
        if 'Latitude' in df_filtrado.columns and 'Longitude' in df_filtrado.columns:
            df_map = df_filtrado.dropna(subset=["Latitude", "Longitude"]).rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
            st.map(df_map)
        else:
            st.warning("Não há coordenadas suficientes para exibir no mapa.")
