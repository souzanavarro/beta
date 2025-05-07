import streamlit as st
import pandas as pd
import plotly.express as px

def show():
    st.header("Dashboard de Indicadores", divider="rainbow")
    st.write("Acompanhe os principais indicadores das últimas roteirizações.")
    cenarios = st.session_state.get('cenarios_roteirizacao', [])
    if not cenarios:
        st.info("Nenhum cenário de roteirização calculado ainda.")
        return
    df = pd.DataFrame([
        {
            'Data': c.get('data', ''),
            'Tipo': c.get('tipo', ''),
            'Pedidos': c.get('qtd_pedidos_roteirizados', 0),
            'Veículos Usados': c.get('qtd_veiculos_utilizados', 0),
            'Veículos Disponíveis': c.get('qtd_veiculos_disponiveis', 0),
            'Distância Total (km)': c.get('distancia_total_real_m', 0) / 1000 if c.get('distancia_total_real_m') else 0,
            'Peso Empenhado (Kg)': c.get('peso_total_empenhado_kg', 0),
            'Status': c.get('status_solver', ''),
        }
        for c in cenarios
    ])
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Pedidos", int(df['Pedidos'].sum()))
    with col2:
        st.metric("Veículos Usados", int(df['Veículos Usados'].sum()))
    with col3:
        st.metric("Distância Total (km)", f"{df['Distância Total (km)'].sum():,.1f}")
    with col4:
        st.metric("Peso Empenhado (Kg)", f"{df['Peso Empenhado (Kg)'].sum():,.1f}")
    st.divider()
    # Gráfico de evolução
    if len(df) > 1:
        fig = px.line(df, x='Data', y='Distância Total (km)', title='Evolução da Distância Total por Cenário')
        st.plotly_chart(fig, use_container_width=True)
    # Tabela detalhada
    st.subheader("Cenários Recentes")
    st.dataframe(df, use_container_width=True, hide_index=True)
