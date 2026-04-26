
import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from datetime import datetime
import plotly.express as px # Para os gráficos táticos

# --- 1. CONFIGURAÇÃO DE ELITE (ESTILO) ---
st.set_page_config(page_title="FT20 - Wise Talon", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    /* Forçar Fundo Escuro */
    .stApp { background-color: #0b0d11; color: #e0e0e0; }
    
    /* Cards de Métrica Táticos */
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        border-radius: 8px;
    }
    
    /* Ajuste de Títulos */
    h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', Courier, monospace; }
    
    /* Sidebar Estilizada */
    section[data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE EXTRAÇÃO (SESP) ---
def extrair_dados_sesp(file):
    content = file.read().decode('utf-8', errors='ignore')
    blocks = re.split(r'"Placa\s+', content)
    records = []
    for block in blocks[1:]:
        data = {}
        placa_match = re.search(r'^([A-Z0-9-]{7,8})"', block)
        data['Placa'] = placa_match.group(1) if placa_match else "IGNORADA"
        dt_match = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
        if dt_match:
            try:
                data['Data_Hora'] = datetime.strptime(dt_match.group(1).strip(), '%d/%m/%Y %H:%M:%S')
                data['Hora'] = data['Data_Hora'].hour # Extrai a hora para o gráfico
            except: data['Data_Hora'], data['Hora'] = None, None
        coord_match = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
        if coord_match:
            data['Lat'], data['Lon'] = float(coord_match.group(1)), float(coord_match.group(2))
        else: data['Lat'], data['Lon'] = None, None
        local_match = re.search(r'"([^"]+)"\s+"Local"', block)
        data['Local'] = local_match.group(1).strip() if local_match else "Ponto não identificado"
        records.append(data)
    return pd.DataFrame(records)

# --- 3. INTERFACE OPERACIONAL ---
st.title("🦅 FT20 - WISE TALON")
st.subheader("SISTEMA DE ANÁLISE DE FLUXOS")

arquivos = st.file_uploader("📂 INGERIR RELATÓRIOS SESP", type=["csv"], accept_multiple_files=True)

if arquivos:
    dfs = [extrair_dados_sesp(arq) for arq in arquivos]
    df_total = pd.concat(dfs).sort_values(by='Data_Hora', ascending=False)
    
    # --- DASHBOARD DE MÉTRICAS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PASSAGENS", len(df_total))
    c2.metric("ALVOS ÚNICOS", df_total['Placa'].nunique())
    c3.metric("COM GPS", df_total['Lat'].notna().sum())
    c4.metric("CIDADES", "1") # Barra do Garças

    st.markdown("---")

    col_esq, col_dir = st.columns([1, 1.2])

    with col_esq:
        st.subheader("📈 Padrão de Horários")
        # Gráfico de Horários de Pico
        if not df_total.empty:
            df_hora = df_total['Hora'].value_counts().sort_index().reset_index()
            df_hora.columns = ['Hora', 'Frequência']
            fig = px.bar(df_hora, x='Hora', y='Frequência', color_discrete_sequence=['#ff4b4b'])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
            st.plotly_chart(fig, use_container_width=True)

    with col_dir:
        st.subheader("🗺️ Inteligência Geoespacial")
        df_mapa = df_total.dropna(subset=['Lat', 'Lon'])
        if not df_mapa.empty:
            centro = [df_mapa['Lat'].mean(), df_mapa['Lon'].mean()]
            m = folium.Map(location=centro, zoom_start=13, tiles="cartodbpositron")
            HeatMap([[r['Lat'], r['Lon']] for _, r in df_mapa.iterrows()], radius=15).add_to(m)
            st_folium(m, width=800, height=400)

    st.subheader("📋 Relatório de Passagens")
    st.dataframe(df_total[['Placa', 'Data_Hora', 'Local']], use_container_width=True)
    
