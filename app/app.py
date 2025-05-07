import sys
import os
import streamlit as st
import pandas as pd
import requests
sys.dont_write_bytecode = True

st.set_page_config(page_title="Wazelog", layout="wide")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Primeiro inicializa o banco de dados
from database import init_db
init_db()

# Depois importa as páginas que podem acessá-lo
from dashboard_page import show as show_dashboard
from frota_page import show as show_frota
from pedidos_page import show as show_pedidos
from roteirizacao_page import show as show_roteirizacao
from mapas_page import show as show_mapas
from cnpj_page import show as show_cnpj

# Material Design aprimorado com cabeçalho e menu lateral com ícones
st.markdown('''

    <style>
    .main-header {
        background: linear-gradient(90deg, #1976d2 0%, #2196f3 100%);
        color: #fff;
        padding: 1.2rem 2rem 1.2rem 2rem;
        border-radius: 0 0 18px 18px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .main-header h1 {
        font-family: 'Roboto', sans-serif;
        font-size: 2.2rem;
        margin: 0;
        letter-spacing: 1px;
    }
    .main-header img {
        height: 48px;
        margin-right: 10px;
    }
    .stSidebar {
        background: #fff;
        border-radius: 16px;
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.06);
        padding-top: 1.5rem;
    }
    .stButton>button { /* Estilo base para botões */
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(25, 118, 210, 0.08);
    }
    </style>
''', unsafe_allow_html=True)

# Cabeçalho fixo (HTML corrigido)
st.markdown(
    '''<div class="main-header">
        <img src="https://img.icons8.com/color/96/000000/route.png" alt="logo" />
        <h1>Wazelog - Roteirizador de Entregas</h1>
    </div>''',
    unsafe_allow_html=True
)

# Menu lateral customizado com design premium
st.markdown('''
<style>
.sidebar-menu-premium {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    margin-top: 1.5rem;
}
.menu-item-premium { /* Estilo para o DIV do item selecionado */
    display: flex;
    align-items: center;
    gap: 1.1rem;
    padding: 0.8rem 1.2rem; /* Padding original */
    border-radius: 10px;
    font-size: 1.05rem;
    font-weight: 500;
    color: #31333F;
    background: #fff;
    border: 1px solid transparent;
    transition: background 0.18s, color 0.18s, border 0.18s, box-shadow 0.18s;
    cursor: pointer;
    position: relative;
}
/* Estilo para o botão Streamlit usado como item de menu */
.stButton>button[kind="secondary"][data-testid="baseButton-secondary"] {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    padding: 0.8rem 1.2rem !important; /* Padding original */
    border-radius: 10px !important;
    font-size: 1.05rem !important;
    font-weight: 500 !important;
    color: #31333F !important;
    background: #fff !important;
    border: 1px solid transparent !important;
    box-shadow: none !important;
    width: 100%;
    justify-content: flex-start;
    margin-bottom: 0;
    transition: background 0.18s, color 0.18s, border 0.18s;
}
.menu-item-premium.selected { /* Aplicado ao DIV */
    background: linear-gradient(90deg, #e3f2fd 0%, #f0f7ff 100%);
    color: #1565c0;
    font-weight: 600;
    border: 1px solid #bbdefb;
}
.stButton>button[kind="secondary"][data-testid="baseButton-secondary"]:hover { /* Hover para botão */
    background: #e3f2fd !important;
    color: #1565c0 !important;
    border: 1px solid #90caf9 !important;
}
.menu-icon-premium {
    font-size: 1.5rem;
    margin-right: 0.2rem;
    color: #1976d2;
}
.menu-item-premium.selected .menu-icon-premium {
     color: #1565c0;
}
.stButton>button[kind="secondary"][data-testid="baseButton-secondary"]:hover .menu-icon-premium {
     color: #1565c0 !important;
}
.menu-title-premium {
    font-size: 1.4rem;
    font-weight: 800;
    color: #1976d2;
    margin-bottom: 1.2rem;
    letter-spacing: 1px;
    text-align: left;
    padding-left: 0.2rem; /* Padding original do título */
}
.menu-divider-premium {
    height: 1px;
    background: linear-gradient(90deg, #1976d2 0%, #64b5f6 100%);
    margin: 0.7rem 0 0.7rem 0;
    border: none;
}
</style>
''', unsafe_allow_html=True)

# CSS aprimorado para modo claro e escuro (dark 100% escuro)
st.markdown('''
<style>
body[data-theme="dark"], .stApp[data-theme="dark"] {
    --card-bg: #181a1b !important;
    --card-fg: #f5f7fa !important;
    --section-title: #90caf9 !important;
    --table-bg: #181a1b !important;
    --table-fg: #f5f7fa !important;
    --container-bg: #181a1b !important;
    background: #181a1b !important;
    color: #f5f7fa !important;
}
body[data-theme="dark"] .kpi-card, .stApp[data-theme="dark"] .kpi-card,
body[data-theme="dark"] .stMetric, .stApp[data-theme="dark"] .stMetric,
body[data-theme="dark"] .stContainer, .stApp[data-theme="dark"] .stContainer {
    background: var(--card-bg, #181a1b) !important;
    color: var(--card-fg, #f5f7fa) !important;
    box-shadow: 0 2px 16px rgba(25, 118, 210, 0.18);
    border: 1px solid #23272b !important;
    border-radius: 10px;
}
body[data-theme="dark"] .section-title, .stApp[data-theme="dark"] .section-title {
    color: var(--section-title, #90caf9) !important;
}
body[data-theme="dark"] .stDataFrame, .stApp[data-theme="dark"] .stDataFrame,
body[data-theme="dark"] .stDataEditor, .stApp[data-theme="dark"] .stDataEditor {
    background: var(--table-bg, #181a1b) !important;
    color: var(--table-fg, #f5f7fa) !important;
    border-radius: 10px !important;
    border: 1px solid #23272b !important;
}
body[data-theme="dark"] div[data-testid="stDataFrameResizable"] > div > div > div > div > div[role="columnheader"] {
    background-color: #262C35 !important;
    color: #CDCDCD !important;
}
body[data-theme="dark"] div[data-testid="stDataFrameResizable"] > div > div > div > div > div[role="gridcell"] {
     background-color: #1E222A !important;
     color: #CDCDCD !important;
     border-color: #30363F !important;
}
body[data-theme="dark"] .stButton>button:not([data-testid="baseButton-secondary"]),
body[data-theme="dark"] .stDownloadButton>button {
    background: #23272b !important;
    color: #90caf9 !important;
    border: 1px solid #1976d2 !important;
}
body[data-theme="dark"] .stButton>button:not([data-testid="baseButton-secondary"]):hover,
body[data-theme="dark"] .stDownloadButton>button:hover {
    background: #1976d2 !important;
    color: #fff !important;
}
body[data-theme="dark"] .main-header {
    background: linear-gradient(90deg, #181a1b 0%, #23272b 100%) !important;
    color: #f5f7fa !important;
}

/* Ensure Sidebar MAIN container is dark */
body[data-theme="dark"] section[data-testid="stSidebar"] {
    background-color: #181a1b !important;
    border-right: 1px solid #23272b !important;
}

/* Ensure the direct child div also gets the background */
body[data-theme="dark"] section[data-testid="stSidebar"] > div:first-child {
    background-color: transparent !important; /* Inherit from parent */
    color: #f5f7fa !important;
}

/* Ensure the menu container itself is transparent in dark mode */
body[data-theme="dark"] .sidebar-menu-premium {
    background-color: transparent !important;
}

/* NEW: Target ANY direct div child of the menu container */
body[data-theme="dark"] .sidebar-menu-premium > div {
    background-color: transparent !important;
}

/* Style for NON-SELECTED menu buttons in dark mode */
body[data-theme="dark"] .stButton>button[kind="secondary"][data-testid="baseButton-secondary"] {
    background: transparent !important; /* Transparent background */
    color: #90caf9 !important;
    border: 1px solid transparent !important;
    width: 100%; /* Ensure button takes full width */
}

body[data-theme="dark"] .menu-item-premium { /* DIV dark */
    background: #23272b !important;
    color: #90caf9 !important;
    border: 1px solid #23272b !important;
}
body[data-theme="dark"] .stButton>button[kind="secondary"][data-testid="baseButton-secondary"] { /* Botão dark */
    background: transparent !important; /* Make button background transparent */
    color: #90caf9 !important;
    border: 1px solid transparent !important;
}
body[data-theme="dark"] .menu-item-premium.selected { /* DIV selecionado dark */
    background: linear-gradient(90deg, #1976d2 0%, #23272b 100%) !important;
    color: #fff !important;
    border: 1px solid #1976d2 !important;
}
body[data-theme="dark"] .stButton>button[kind="secondary"][data-testid="baseButton-secondary"]:hover { /* Hover botão dark */
    background: #263238 !important;
    color: #90caf9 !important;
    border: 1.5px solid #90caf9 !important;
}
body[data-theme="dark"] .menu-icon-premium {
    color: #64b5f6;
}
body[data-theme="dark"] .menu-item-premium.selected .menu-icon-premium {
     color: #fff;
}
body[data-theme="dark"] .stButton>button[kind="secondary"][data-testid="baseButton-secondary"]:hover .menu-icon-premium {
     color: #90caf9 !important;
}
body[data-theme="dark"] .stSidebar {
    background: #181a1b !important;
    color: #f5f7fa !important;
    border: 1px solid #23272b !important;
    border-radius: 16px;
}
body[data-theme="dark"] .menu-title-premium {
    color: #64b5f6 !important; /* Title color in dark */
}
body[data-theme="dark"] .menu-divider-premium {
    background: #30363F;
}
</style>
''', unsafe_allow_html=True)

menu_itens = [
    ("Dashboard", "🏠"),
    ("Frota", "🚚"),
    ("Pedidos", "📦"),
    ("Roteirização", "🗺️"),
    ("Mapas", "🗾"),
    ("Busca CNPJ", "🔎")
]

with st.sidebar:
    st.markdown("<div class='menu-title-premium'>✨ Menu Principal</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-menu-premium'>", unsafe_allow_html=True)
    pagina = None # Será definido dentro do loop
    pagina_selecionada = st.session_state.get('pagina_selecionada', 'Dashboard')

    for nome, icone in menu_itens:
        selected = pagina_selecionada == nome
        if selected:
            st.markdown(
                f"""<div class='menu-item-premium selected'>
                       <span class='menu-icon-premium'>{icone}</span> {nome}
                   </div>""",
                unsafe_allow_html=True
            )
            pagina = nome
        else:
            if st.button(f"{icone} {nome}", key=f"menu_{nome}", use_container_width=True):
                st.session_state['pagina_selecionada'] = nome
                st.rerun()

    if pagina is None:
        pagina = 'Dashboard'
        if 'pagina_selecionada' not in st.session_state:
             st.session_state['pagina_selecionada'] = 'Dashboard'

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='menu-divider-premium'>", unsafe_allow_html=True)

    if "modo_escuro" not in st.session_state:
        st.session_state["modo_escuro"] = False
    modo_escuro = st.toggle("🌙 Modo escuro", value=st.session_state["modo_escuro"], key="modo_escuro_toggle")
    if modo_escuro != st.session_state["modo_escuro"]:
        st.session_state["modo_escuro"] = modo_escuro
        st.rerun()

# Renderiza página selecionada
if pagina == "Dashboard":
    show_dashboard()
elif pagina == "Frota":
    show_frota()
elif pagina == "Pedidos":
    show_pedidos()
elif pagina == "Roteirização":
    show_roteirizacao()
elif pagina == "Mapas":
    show_mapas()
elif pagina == "Busca CNPJ":
    show_cnpj()
else:
    show_dashboard()
