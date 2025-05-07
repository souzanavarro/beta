import streamlit as st
from frota import processar_frota
from database import carregar_frota, salvar_frota
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
    st.header("Gerenciar Frota", divider="rainbow")
    st.write("Importe, visualize, edite, adicione ou remova veículos da frota.")
    st.divider()
    if 'df_frota' not in st.session_state:
        st.session_state.df_frota = pd.DataFrame()
    # Garantir que não há índices duplicados
    st.session_state.df_frota = st.session_state.df_frota.reset_index(drop=True)
    arquivo = st.file_uploader("Upload da planilha da frota", type=["xlsx", "xlsm", "csv", "json"])
    if arquivo:
        try:
            df = processar_frota(arquivo)
            st.session_state.df_frota = df.copy()
            salvar_frota(df)
            st.success("Frota importada com sucesso!")
        except Exception as e:
            st.error(f"Erro ao processar a frota: {e}")
    df = st.session_state.df_frota
    if df.empty:
        df = carregar_frota()
        st.session_state.df_frota = df.copy()
    if not df.empty:
        df = df.loc[:, ~df.columns.duplicated()]
        df.columns = [str(col) if col else f"Coluna_{i}" for i, col in enumerate(df.columns)]
        # Remove colunas de janela de tempo se existirem
        for col in ['Janela Início', 'Janela Fim']:
            if col in df.columns:
                df = df.drop(columns=[col])
        # Garante a existência das colunas do cabeçalho
        colunas_cabecalho = [
            'Placa', 'Transportador', 'Descrição Veículo', 'Capacidade (Cx)',
            'Capacidade (Kg)', 'Disponível', 'Regiões Preferidas'
        ]
        for col in colunas_cabecalho:
            if col not in df.columns:
                df[col] = ''
        outras_colunas = [c for c in df.columns if c not in colunas_cabecalho]
        df = df[[*colunas_cabecalho, *outras_colunas]]
        # Campo para selecionar veículo
        placa_col = 'Placa' if 'Placa' in df.columns else None
        veiculo_sel = None
        if placa_col:
            placas = df[placa_col].dropna().unique().tolist()
            veiculo_sel = st.selectbox("Selecione o veículo para editar", ["Todos"] + placas)
            if veiculo_sel != "Todos":
                df = df[df[placa_col] == veiculo_sel]
        st.subheader("Editar Frota")
        colunas_editor = [c for c in df.columns if c not in ['Janela Início', 'Janela Fim']]
        df_editado = st.data_editor(df[colunas_editor], num_rows="dynamic", use_container_width=True, key="frota_editor")
        st.divider()
        st.subheader("Remover veículos")
        def format_option(x):
            placa = df_editado.loc[x, 'Placa'] if 'Placa' in df_editado.columns else str(x)
            descricao = df_editado.loc[x, 'Descrição'] if 'Descrição' in df_editado.columns else ''
            return f"{placa} - {descricao}" if descricao else f"{placa}"
        indices_remover = st.multiselect("Selecione as linhas para remover", df_editado.index, format_func=format_option)
        if st.button("Remover selecionados") and indices_remover:
            st.session_state.df_frota = df_editado.drop(indices_remover).reset_index(drop=True)
            salvar_frota(st.session_state.df_frota)
            st.success("Veículos removidos!")
            st.rerun()
    st.divider()
    st.subheader("Adicionar ou Editar veículo")
    # Novo: selectbox para selecionar placa para edição
    placas_existentes = st.session_state.df_frota['Placa'].dropna().unique().tolist() if not st.session_state.df_frota.empty else []
    placa_editar = st.selectbox("Selecione a placa para editar ou deixe em branco para adicionar novo", ["(Novo)"] + placas_existentes, key="placa_editar")
    # Preencher campos se for edição
    if placa_editar != "(Novo)" and placa_editar in st.session_state.df_frota['Placa'].values:
        veic_row = st.session_state.df_frota[st.session_state.df_frota['Placa'] == placa_editar].iloc[0]
        placa_val = veic_row['Placa']
        transportador_val = veic_row.get('Transportador', '')
        descricao_val = veic_row.get('Descrição', '')
        veiculo_val = veic_row.get('Veículo', '')
        capacidade_cx_val = veic_row.get('Capacidade (Cx)', 0)
        capacidade_kg_val = veic_row.get('Capacidade (Kg)', 0.0)
        disponivel_raw = veic_row.get('Disponível', True)
        if isinstance(disponivel_raw, (pd.Series, list)):
            disponivel_raw = disponivel_raw.iloc[0] if hasattr(disponivel_raw, 'iloc') else disponivel_raw[0]
        disponivel_val = "Sim" if bool(disponivel_raw) else "Não"
    else:
        placa_val = ""
        transportador_val = ""
        descricao_val = ""
        veiculo_val = ""
        capacidade_cx_val = 0
        capacidade_kg_val = 0.0
        disponivel_val = "Sim"
    with st.form("add_veiculo_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            placa = st.text_input("Placa", value=placa_val, key="placa_input")
            transportador = st.text_input("Transportador", value=transportador_val)
            descricao = st.text_input("Descrição", value=descricao_val)
        with col2:
            veiculo = st.text_input("Veículo", value=veiculo_val)
            capacidade_cx = st.number_input("Capacidade (Cx)", min_value=0, step=1, value=int(capacidade_cx_val))
            capacidade_kg = st.number_input("Capacidade (Kg)", min_value=0.0, step=1.0, format="%.2f", value=float(capacidade_kg_val))
        with col3:
            disponivel = st.selectbox("Disponível", ["Sim", "Não"], index=0 if disponivel_val=="Sim" else 1)
        if placa_editar == "(Novo)":
            submitted = st.form_submit_button("Adicionar veículo")
            if submitted and placa:
                novo = {
                    "Placa": placa,
                    "Transportador": transportador,
                    "Descrição": descricao,
                    "Veículo": veiculo,
                    "Capacidade (Cx)": capacidade_cx,
                    "Capacidade (Kg)": capacidade_kg,
                    "Disponível": disponivel.lower() == "sim",
                    "ID Veículo": placa
                }
                st.session_state.df_frota = pd.concat([st.session_state.df_frota, pd.DataFrame([novo])], ignore_index=True)
                salvar_frota(st.session_state.df_frota)
                st.success("Veículo adicionado!")
                st.rerun()
        else:
            submitted = st.form_submit_button("Atualizar veículo")
            if submitted and placa:
                # Remove duplicatas de índice e de placa antes de atualizar
                st.session_state.df_frota = st.session_state.df_frota.reset_index(drop=True)
                st.session_state.df_frota = st.session_state.df_frota.drop_duplicates(subset=['Placa'], keep='first').reset_index(drop=True)
                idxs = st.session_state.df_frota[st.session_state.df_frota['Placa'] == placa_editar].index
                if len(idxs) > 0:
                    idx = idxs[0]
                    st.session_state.df_frota.loc[idx, [
                        'Placa', 'Transportador', 'Descrição', 'Veículo', 'Capacidade (Cx)', 'Capacidade (Kg)', 'Disponível', 'ID Veículo']
                    ] = [placa, transportador, descricao, veiculo, capacidade_cx, capacidade_kg, disponivel.lower() == "sim", placa]
                    salvar_frota(st.session_state.df_frota)
                    st.success("Veículo atualizado!")
                    st.rerun()
    # Botão de limpar frota
    if st.button("Limpar Frota", type="primary"):
        from database import limpar_frota
        limpar_frota()
        st.session_state.df_frota = pd.DataFrame()
        st.success("Frota limpa com sucesso!")
        st.rerun()
