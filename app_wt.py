import streamlit as st
import pandas as pd
import numpy as np
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import io

# --- 1. CONFIGURAÇÃO DE DESIGN (UX EXPERT) ---
st.set_page_config(page_title="Wise Talon v5.0", layout="wide", page_icon="🦅")

def aplicar_estilo_ux():
    st.markdown("""
        <style>
        /* Estilização Geral - Dark Slate Theme */
        .stApp {
            background-color: #0f1116;
            color: #afb1b6;
        }
        /* Títulos e Headers */
        h1, h2, h3 {
            color: #e63946 !important;
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            letter-spacing: -1px;
        }
        /* Tabs Personalizadas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: #0f1116;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            background-color: #1a1d24;
            border-radius: 8px 8px 0px 0px;
            color: #afb1b6;
            border: none;
            padding: 0px 25px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #e63946 !important;
            color: white !important;
        }
        /* Metrics Cards */
        div[data-testid="stMetric"] {
            background-color: #1a1d24;
            border: 1px solid #2d3139;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        /* Sidebar Estilizada */
        [data-testid="stSidebar"] {
            background-color: #16191f;
            border-right: 1px solid #2d3139;
        }
        </style>
    """, unsafe_allow_html=True)

# --- 2. BASE TÁTICA (EXPANDIDA) ---
MAPA_TATICO_MT = {
    "CUIABA": (-15.6014, -56.0979), "VARZEA GRANDE": (-15.6461, -56.1325),
    "POCONE": (-16.2567, -56.6228), "PRIMAVERA DO LESTE": (-15.5594, -54.2961),
    "CACERES": (-16.0706, -57.6789), "RONDONOPOLIS": (-16.4678, -54.6361),
    "SINOP": (-11.8608, -55.5095), "SORRISO": (-12.5441, -55.7158),
    "BARRA DO GARCAS": (-15.8900, -52.2567), "ALTO GARCAS": (-16.9442, -53.5261),
    "ALTO ARAGUAIA": (-17.3150, -53.2158), "CAMPO VERDE": (-15.5478, -55.1658)
}

# --- 3. MOTORES DE ANÁLISE AVANÇADA ---
@st.cache_data
def analisar_comboios(df, placa_alvo, janela_segundos=60):
    """Detecta veículos que passaram nos mesmos pontos que o alvo no mesmo minuto"""
    passagens_alvo = df[df['Placa'] == placa_alvo]
    comboio_lista = []
    
    for _, p in passagens_alvo.iterrows():
        outros = df[
            (df['Local'] == p['Local']) & 
            (df['Placa'] != placa_alvo) &
            (df['Data_Hora'] >= p['Data_Hora'] - timedelta(seconds=janela_segundos)) &
            (df['Data_Hora'] <= p['Data_Hora'] + timedelta(seconds=janela_segundos))
        ]
        comboio_lista.extend(outros['Placa'].tolist())
    
    # Retorna os que mais aparecem perto do alvo
    return pd.Series(comboio_lista).value_counts().head(5)

@st.cache_data
def processar_inteligencia(arquivos):
    all_data = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore').split('\n')
        for i, linha in enumerate(content):
            match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', linha)
            if match:
                dt_s, placa = match.group(1), match.group(2)
                local = content[i-1].strip() if i > 0 else "N/I"
                # Limpeza de cidade
                cid = re.sub(r'BR\s*\d+|KM\s*[\d+.,/]+|Sentido:.*|ID:.*|[^a-zA-ZÀ-ÿ\s]', '', local, flags=re.I).strip().upper()
                coords = None
                for c, coord in MAPA_TATICO_MT.items():
                    if c in cid: coords = coord; break
                
                all_data.append({
                    'Placa': placa, 'Data_Hora': datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S'),
                    'Local': local, 'Cidade': cid, 'Lat': coords[0] if coords else None, 
                    'Lon': coords[1] if coords else None
                })
    return pd.DataFrame(all_data).sort_values('Data_Hora')

# --- 4. INTERFACE ---
aplicar_estilo_ux()

# LOGIN
if "auth" not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>🦅⚡ WISE TALON</h1>", unsafe_allow_html=True)
    col_l, col_r = st.columns([1,1])
    with col_l:
        senha = st.text_input("Credencial Tática", type="password")
        if senha == "ft20+52":
            st.session_state["auth"] = True
            st.rerun()
    st.stop()

# SIDEBAR
with st.sidebar:
    st.markdown("## 🦅⚡ OPERAÇÕES")
    arqs = st.file_uploader("Ingerir Base SESP", type=["csv"], accept_multiple_files=True)
    if st.button("Limpar Cache"): st.session_state.clear(); st.rerun()

if arqs:
    df = processar_inteligencia(arqs)
    
    t_dash, t_invest, t_comboio = st.tabs(["📊 DASHBOARD", "🔎 INVESTIGAÇÃO", "🎯 ALVOS DE COMBOIO"])

    with t_dash:
        st.markdown("### 📊 Panorama de Inteligência")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("AVALIAÇÕES", len(df))
        c2.metric("PLACAS", df['Placa'].nunique())
        c3.metric("CIDADES", df['Cidade'].nunique())
        c4.metric("DENSIDADE", "Alta")
        
        st.divider()
        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(px.bar(df['Cidade'].value_counts().head(10), title="Top Cidades de Passagem", color_discrete_sequence=['#e63946']), use_container_width=True)
        with col_r:
            st.plotly_chart(px.line(df.groupby(df['Data_Hora'].dt.hour).size(), title="Volume por Hora (Fluxo)", color_discrete_sequence=['#e63946']), use_container_width=True)

    with t_invest:
        placa = st.text_input("PLACA ALVO", "").upper().strip()
        if placa:
            alvo_df = df[df['Placa'].str.contains(placa)]
            if not alvo_df.empty:
                st.markdown(f"### 🎯 Análise Estrutural: {placa}")
                c_rel, c_map = st.columns([1, 1.5])
                
                with c_rel:
                    txt = f"RELATÓRIO DE INTELIGÊNCIA: {placa}\n"
                    txt += f"Freq. de Passagens: {len(alvo_df)}\n"
                    txt += f"Cidades Detectadas: {', '.join(alvo_df['Cidade'].unique())}\n\n"
                    st.dataframe(alvo_df[['Data_Hora', 'Local']], height=300)
                    
                    # PDF Gerador
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, f"WISE TALON - RELATORIO {placa}", ln=True)
                    pdf.set_font("Arial", '', 12)
                    pdf.multi_cell(0, 10, txt.encode('latin-1', 'replace').decode('latin-1'))
                    st.download_button("📥 Exportar Relatório PDF", data=bytes(pdf.output()), file_name=f"Alvo_{placa}.pdf")

                with c_map:
                    df_m = alvo_df.dropna(subset=['Lat', 'Lon'])
                    if not df_m.empty:
                        m = folium.Map(location=[df_m['Lat'].mean(), df_m['Lon'].mean()], zoom_start=7, tiles="cartodbpositron")
                        folium.PolyLine(df_m[['Lat', 'Lon']].values, color="#e63946", weight=3).add_to(m)
                        for _, r in df_m.iterrows():
                            folium.Marker([r['Lat'], r['Lon']], popup=r['Local'], icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
                        st_folium(m, width="100%", height=500)
            else: st.error("Nenhum dado para esta placa.")

    with t_comboio:
        st.markdown("### 🎯 Detecção de Comboios e Batedores")
        placa_c = st.text_input("ANALISAR COMBOIO DA PLACA", "").upper().strip()
        if placa_c:
            comboios = analisar_comboios(df, placa_c)
            if not comboios.empty:
                st.warning(f"As seguintes placas acompanharam o alvo {placa_c} em momentos distintos:")
                for p, count in comboios.items():
                    st.write(f"🚜 **Placa: {p}** | Passagens em conjunto: {count}")
            else:
                st.success("Nenhum padrão de comboio detectado para este intervalo.")

else:
    st.markdown("""
        <div style='text-align: center; padding-top: 100px;'>
            <h1 style='font-size: 80px;'>🦅⚡</h1>
            <h2>AGUARDANDO DADOS SESP</h2>
            <p>Insira os arquivos para iniciar a triangulação de rotas.</p>
        </div>
    """, unsafe_allow_html=True)
