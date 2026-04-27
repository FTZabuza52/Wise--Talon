import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO INICIAL (DEVE SER A PRIMEIRA COISA) ---
st.set_page_config(page_title="Wise Talon v4.8", layout="wide", page_icon="🦅")

# --- TENTATIVA DE IMPORTS (MODO PROTEGIDO) ---
try:
    from geopy.geocoders import Nominatim
    GEOPY_OK = True
except: GEOPY_OK = False

try:
    from fpdf import FPDF
    FPDF_OK = True
except: FPDF_OK = False

# --- BASE TÁTICA DE CIDADES ---
MAPA_TATICO_MT = {
    "CUIABA": (-15.6014, -56.0979), "VARZEA GRANDE": (-15.6461, -56.1325),
    "POCONE": (-16.2567, -56.6228), "PRIMAVERA DO LESTE": (-15.5594, -54.2961),
    "CACERES": (-16.0706, -57.6789), "RONDONOPOLIS": (-16.4678, -54.6361),
    "SINOP": (-11.8608, -55.5095), "SORRISO": (-12.5441, -55.7158),
    "BARRA DO GARCAS": (-15.8900, -52.2567), "ALTO GARCAS": (-16.9442, -53.5261),
    "ALTO ARAGUAIA": (-17.3150, -53.2158), "CAMPO VERDE": (-15.5478, -55.1658)
}

# --- 2. PROTOCOLO DE SEGURANÇA ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='color: #ff4b4b; text-align: center;'>🦅 ACESSO RESTRITO - FT20</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            senha = st.text_input("Insira a Credencial Tática", type="password")
            if senha == "ft20+52":
                st.session_state["password_correct"] = True
                st.rerun()
        return False
    return True

# --- 3. MOTORES DE BUSCA E PROCESSAMENTO ---
@st.cache_data
def buscar_coords(local_bruto):
    if not local_bruto: return None, None
    limpo = re.sub(r'BR\s*\d+|KM\s*[\d+.,/]+|Sentido:.*|ID:.*|[^a-zA-ZÀ-ÿ\s]', '', str(local_bruto), flags=re.I).strip().upper()
    for cidade, coords in MAPA_TATICO_MT.items():
        if cidade in limpo: return coords
    return None, None

@st.cache_data
def processar_arquivos(arquivos):
    all_data = []
    for arq in arquivos:
        linhas = arq.read().decode('utf-8', errors='ignore').split('\n')
        for i, linha in enumerate(linhas):
            match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', linha)
            if match:
                dt_s, placa = match.group(1), match.group(2)
                local = linhas[i-1].strip() if i > 0 else "N/I"
                lat, lon = buscar_coords(local)
                all_data.append({
                    'Placa': placa, 
                    'Data_Hora': datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S'),
                    'Local': local, 'Lat': lat, 'Lon': lon
                })
    df = pd.DataFrame(all_data)
    if not df.empty:
        df['Hora'] = df['Data_Hora'].dt.hour
    return df.sort_values('Data_Hora', ascending=False)

# --- 4. INTERFACE PRINCIPAL ---
if check_password():
    # Estilo Dark Tático
    st.markdown("""<style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        h1, h2, h3 { color: #ff4b4b !important; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; }
        </style>""", unsafe_allow_html=True)

    with st.sidebar:
        st.title("🦅 WISE TALON")
        st.write(f"Status: Geo{'✅' if GEOPY_OK else '❌'} | PDF{'✅' if FPDF_OK else '❌'}")
        arquivos = st.file_uploader("📂 CARREGAR CSV SESP", type=["csv"], accept_multiple_files=True)
        if st.button("Limpar Sistema"):
            st.session_state.clear()
            st.rerun()

    if arquivos:
        df_total = processar_arquivos(arquivos)
        tab_invest, tab_dash = st.tabs(["🔎 INVESTIGAÇÃO", "📊 DASHBOARD"])

        with tab_invest:
            busca = st.text_input("PESQUISAR PLACA", "").upper().strip()
            if busca:
                df_alvo = df_total[df_total['Placa'].str.contains(busca)]
                if not df_alvo.empty:
                    c1, c2 = st.columns([1, 1.5])
                    with c1:
                        st.markdown(f"### Itinerário {busca}")
                        st.dataframe(df_alvo[['Data_Hora', 'Local']], height=400)
                    with c2:
                        st.markdown("### Mapa de Deslocamento")
                        df_gps = df_alvo.dropna(subset=['Lat', 'Lon'])
                        if not df_gps.empty:
                            m = folium.Map(location=[df_gps['Lat'].mean(), df_gps['Lon'].mean()], zoom_start=8)
                            folium.PolyLine(df_gps[['Lat', 'Lon']].values, color="red", weight=4).add_to(m)
                            for _, r in df_gps.iterrows():
                                folium.Marker([r['Lat'], r['Lon']], popup=r['Local']).add_to(m)
                            st_folium(m, width="100%", height=500)
                        else: st.warning("Sem coordenadas para esta placa.")
                else: st.error("Placa não encontrada.")
            else:
                st.info("💡 Digite uma placa acima para iniciar a busca no mapa.")

        with tab_dash:
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(df_total, names='Local', title="Locais de Passagem"), use_container_width=True)
            c2.plotly_chart(px.histogram(df_total, x='Hora', title="Fluxo por Horário"), use_container_width=True)
    
    else:
        # TELA DE STANDBY (Para evitar a tela branca)
        st.markdown("""
            <div style='text-align: center; margin-top: 100px;'>
                <h1 style='font-size: 50px;'>🦅</h1>
                <h2>WISE TALON PRONTO</h2>
                <p>Aguardando upload de arquivos CSV no menu lateral para processar inteligência.</p>
            </div>
        """, unsafe_allow_html=True)
