import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from datetime import datetime
import io

# --- CONFIGURAÇÃO DE AMBIENTE ---
st.set_page_config(page_title="FT20 - Wise Talon", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { border-left: 5px solid #ff4b4b; background-color: #1f2937; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- O CÉREBRO DA CORUJA (PARSER) ---
def extrair_dados_sesp(file):
    # Lendo o arquivo ignorando erros de formatação comuns em CSVs de sistema
    content = file.read().decode('utf-8', errors='ignore')
    
    # Cada registro começa com a palavra "Placa"
    blocos = re.split(r'"Placa\s+', content)
    registros = []
    
    for bloco in blocos[1:]:
        dados = {}
        
        # Extração de Placa (7 ou 8 caracteres)
        placa = re.search(r'^([A-Z0-9-]{7,8})"', bloco)
        dados['Placa'] = placa.group(1) if placa else "N/I"
        
        # Extração de Data e Hora
        data_hora = re.search(r'Data/Hora\s+([0-9/:\s]+)"', bloco)
        if data_hora:
            try:
                dados['Data_Hora'] = datetime.strptime(data_hora.group(1).strip(), '%d/%m/%Y %H:%M:%S')
            except: dados['Data_Hora'] = None
        
        # Extração de Coordenadas (Latitude & Longitude)
        coords = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', bloco)
        if coords:
            dados['Lat'] = float(coords.group(1))
            dados['Lon'] = float(coords.group(2))
        else:
            dados['Lat'], dados['Lon'] = None, None
            
        # Extração do Local
        local = re.search(r'"([^"]+)"\s+"Local"', bloco)
        dados['Local'] = local.group(1).strip() if local
        
        registros.append(dados)
    
    return pd.DataFrame(registros)

# --- INTERFACE OPERACIONAL ---
st.title("🦅 FT20 - Wise Talon | Analista de Rotas")
st.write("Processamento tático de relatórios SESP/MT.")

# Upload
arquivos = st.file_uploader("Arraste os CSVs da SESP aqui (Máximo 3)", type=["csv"], accept_multiple_files=True)

if arquivos:
    lista_dfs = []
    for f in arquivos:
        df_individual = extrair_dados_sesp(f)
        lista_dfs.append(df_individual)
    
    # Consolidação e limpeza
    df_final = pd.concat(lista_dfs).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)
    
    # --- PAINEL DE MÉTRICAS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Total de Passagens", len(df_final))
    m2.metric("Veículos Únicos", df_final['Placa'].nunique())
    m3.metric("Pontos com GPS", df_final['Lat'].notna().sum())

    # --- VISUALIZAÇÃO ---
    tab1, tab2 = st.tabs(["📊 Tabela de Inteligência", "🗺️ Mapa de Calor"])
    
    with tab1:
        st.dataframe(df_final, use_container_width=True)
        
        # Opção de exportar o "Milho Debulhado"
        csv_limpo = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar CSV Padronizado FT20", csv_limpo, "rotas_identificadas.csv", "text/csv")

    with tab2:
        df_mapa = df_final.dropna(subset=['Lat', 'Lon'])
        if not df_mapa.empty:
            centro = [df_mapa['Lat'].mean(), df_mapa['Lon'].mean()]
            mapa = folium.Map(location=centro, zoom_start=13, tiles="cartodbpositron")
            
            # Adicionando a "Mancha" de calor
            heat_data = [[row['Lat'], row['Lon']] for _, row in df_mapa.iterrows()]
            HeatMap(heat_data, radius=15, blur=10).add_to(mapa)
            
            # Marcadores individuais para os últimos 20 registros
            for _, row in df_mapa.head(20).iterrows():
                folium.Marker(
                    location=[row['Lat'], row['Lon']],
                    popup=f"Placa: {row['Placa']}<br>{row['Data_Hora']}",
                    icon=folium.Icon(color='red', icon='info-sign')
                ).add_to(mapa)
                
            st_folium(mapa, width="100%", height=500)
        else:
            st.warning("Nenhuma coordenada GPS encontrada nos arquivos para gerar o mapa.")

# --- FOOTER ---
st.markdown("---")
st.caption("FT20 - Sistema de Apoio à Decisão | Unidade Raio Imortal Vermelho")
