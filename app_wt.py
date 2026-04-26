import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from datetime import datetime
import plotly.express as px

# --- CONFIGURAÇÃO DE INTERFACE ---
st.set_page_config(page_title="FT20 - Wise Talon", page_icon="🦅", layout="wide")

# Estilo CSS para o Painel
st.markdown("""
    <style>
    .stApp { background-color: #0b0d11; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        border-radius: 8px;
    }
    h1, h2, h3 { color: #ff4b4b !important; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE EXTRAÇÃO DE DADOS (PARSER ROBUSTO) ---
def extrair_dados_sesp(file):
    # Lendo o conteúdo bruto do arquivo
    content = file.read().decode('utf-8', errors='ignore')
    
    # Divide o texto em blocos baseando-se no campo "Placa"
    blocks = re.split(r'"Placa\s+', content)
    records = []
    
    for block in blocks[1:]:
        data = {}
        # Extração de Placa (considerando formatos com ou sem hífen)
        placa_match = re.search(r'^([A-Z0-9-]{7,8})"', block)
        data['Placa'] = placa_match.group(1).strip() if placa_match else "N/I"
        
        # Extração de Data/Hora
        dt_match = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
        if dt_match:
            try:
                dt_str = dt_match.group(1).strip()
                data['Data_Hora'] = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                data['Hora'] = data['Data_Hora'].hour
            except:
                data['Data_Hora'], data['Hora'] = None, None
        
        # Extração de Coordenadas
        coord_match = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
        if coord_match:
            data['Lat'] = float(coord_match.group(1))
            data['Lon'] = float(coord_match.group(2))
        else:
            data['Lat'], data['Lon'] = None, None
            
        # Extração de Local e Cidade
        local_match = re.search(r'"([^"]+)"\s+"Local"', block)
        if local_match:
            local_full = local_match.group(1).strip()
            data['Local'] = local_full
            # Tenta extrair a cidade (assume-se que a cidade vem antes do primeiro hífen)
            data['Cidade'] = local_full.split('-')[0].strip()
        else:
            data['Local'] = "Ponto não identificado"
            data['Cidade'] = "N/I"
        
        records.append(data)
    
    return pd.DataFrame(records)

# --- INTERFACE DO SISTEMA ---
st.title("🦅 FT20 - WISE TALON")
st.subheader("SISTEMA DE ANÁLISE DE FLUXOS")

arquivos = st.file_uploader("📂 INGERIR RELATÓRIOS (CSV SESP)", type=["csv"], accept_multiple_files=True)

if arquivos:
    # Processamento dos arquivos carregados
    lista_dfs = []
    for arq in arquivos:
        df_individual = extrair_dados_sesp(arq)
        if not df_individual.empty:
            lista_dfs.append(df_individual)
    
    if lista_dfs:
        df_total = pd.concat(lista_dfs).sort_values(by='Data_Hora', ascending=False)
        
        # --- PAINEL DE MÉTRICAS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("PASSAGENS", len(df_total))
        m2.metric("ALVOS ÚNICOS", df_total['Placa'].nunique())
        m3.metric("COORDENADAS GPS", df_total['Lat'].notna().sum())
        m4.metric("CIDADES", df_total['Cidade'].nunique())

        st.markdown("---")

        # Colunas de Visualização
        col_grafico, col_mapa = st.columns([1, 1.2])

        with col_grafico:
            st.subheader("📈 Padrão de Horários")
            df_hora = df_total['Hora'].value_counts().sort_index().reset_index()
            df_hora.columns = ['Hora', 'Frequência']
            fig = px.bar(df_hora, x='Hora', y='Frequência', color_discrete_sequence=['#ff4b4b'])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
            st.plotly_chart(fig, use_container_width=True)

        with col_mapa:
            st.subheader("🗺️ Mapa de Calor")
            df_mapa = df_total.dropna(subset=['Lat', 'Lon'])
            if not df_mapa.empty:
                centro = [df_mapa['Lat'].mean(), df_mapa['Lon'].mean()]
                mapa = folium.Map(location=centro, zoom_start=13, tiles="cartodbpositron")
                HeatMap([[r['Lat'], r['Lon']] for _, r in df_mapa.iterrows()], radius=15).add_to(mapa)
                st_folium(mapa, width="100%", height=400)
            else:
                st.warning("Dados de localização indisponíveis nos arquivos.")

        # Tabela Detalhada
        st.subheader("📋 Relatório Consolidado")
        st.dataframe(df_total[['Placa', 'Data_Hora', 'Cidade', 'Local']], use_container_width=True)
    else:
        st.error("Não foi possível extrair dados dos arquivos enviados.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Filtros")
    filtro_placa = st.text_input("Filtrar Placa", "").upper()
    if filtro_placa and 'df_total' in locals():
        df_total = df_total[df_total['Placa'].str.contains(filtro_placa)]
    st.divider()
    st.caption("FT20 - Unidade de Inteligência")
    
