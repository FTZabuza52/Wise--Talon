
import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from datetime import datetime

# --- CONFIGURAÇÃO DE ELITE ---
st.set_page_config(page_title="FT20 - Wise Talon", page_icon="🦅", layout="wide")

# Estilo para o Painel Tático
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1f2937; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO DE TRADUÇÃO (PARSER SESP) ---
def extrair_dados_sesp(file):
    content = file.read().decode('utf-8', errors='ignore')
    # Divide o arquivo por "Placa" que é o início de cada registro
    blocks = re.split(r'"Placa\s+', content)
    records = []
    
    for block in blocks[1:]:
        data = {}
        # 1. Extrair Placa
        placa_match = re.search(r'^([A-Z0-9-]{7,8})"', block)
        data['Placa'] = placa_match.group(1) if placa_match else "IGNORADA"
        
        # 2. Extrair Data/Hora
        dt_match = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
        if dt_match:
            try:
                dt_str = dt_match.group(1).strip()
                data['Data_Hora'] = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
            except:
                data['Data_Hora'] = None
        
        # 3. Extrair Coordenadas (Latitude & Longitude)
        coord_match = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
        if coord_match:
            data['Lat'] = float(coord_match.group(1))
            data['Lon'] = float(coord_match.group(2))
        else:
            data['Lat'], data['Lon'] = None, None
            
        # 4. Extrair Local (Descrição) - LINHA CORRIGIDA AQUI
        local_match = re.search(r'"([^"]+)"\s+"Local"', block)
        data['Local'] = local_match.group(1).strip() if local_match else "Ponto não identificado"
        
        records.append(data)
    
    return pd.DataFrame(records)

# --- INTERFACE ---
st.title("🦅 FT20 - Wise Talon | Analista de Rotas")
st.info("Sistema de análise de fluxos e padrões de veículos através de relatórios SESP.")

with st.sidebar:
    st.header("⚙️ Filtros Táticos")
    usar_gps = st.toggle("Habilitar Mapeamento GPS", value=True)
    filtro_placa = st.text_input("Filtrar Placa Específica", "").upper()
    st.divider()
    st.markdown("© Unidade Raio Imortal Vermelho")

# Upload de Arquivos
arquivos = st.file_uploader("Subir Relatórios (CSV SESP) - Máx 3", type=["csv"], accept_multiple_files=True)

if arquivos:
    dfs = []
    for arq in arquivos:
        df_parsed = extrair_dados_sesp(arq)
        dfs.append(df_parsed)
    
    if dfs:
        df_total = pd.concat(dfs).sort_values(by='Data_Hora', ascending=False)
        
        if filtro_placa:
            df_total = df_total[df_total['Placa'].str.contains(filtro_placa)]

        # --- DASHBOARD ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Passagens", len(df_total))
        col2.metric("Veículos Únicos", df_total['Placa'].nunique())
        col3.metric("Pontos com GPS", df_total['Lat'].notna().sum())

        st.divider()

        c1, c2 = st.columns([1, 1])

        with c1:
            st.subheader("📋 Log de Passagens")
            st.dataframe(df_total[['Placa', 'Data_Hora', 'Local']], use_container_width=True, height=450)

        with c2:
            st.subheader("🗺️ Mapa de Calor de Rotas")
            df_mapa = df_total.dropna(subset=['Lat', 'Lon'])
            
            if usar_gps and not df_mapa.empty:
                centro = [df_mapa['Lat'].mean(), df_mapa['Lon'].mean()]
                m = folium.Map(location=centro, zoom_start=13, tiles="cartodbpositron")
                
                heat_data = [[row['Lat'], row['Lon']] for index, row in df_mapa.iterrows()]
                HeatMap(heat_data, radius=15).add_to(m)
                
                for _, row in df_mapa.head(30).iterrows():
                    folium.CircleMarker(
                        location=[row['Lat'], row['Lon']],
                        radius=5,
                        popup=f"Placa: {row['Placa']}<br>Hora: {row['Data_Hora']}",
                        color="red",
                        fill=True
                    ).add_to(m)
                
                st_folium(m, width=700, height=450)
            else:
                st.warning("Sem coordenadas para exibir no mapa.")
