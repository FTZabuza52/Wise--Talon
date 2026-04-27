import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io

# --- 1. SETUP DE INTERFACE (UX DESIGNER SPECS) ---
st.set_page_config(page_title="Wise Talon v5.1", layout="wide", page_icon="🦅")

def aplicar_design_sistema():
    st.markdown("""
        <style>
        /* Fundo e Texto Base */
        .stApp { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Roboto, sans-serif; }
        
        /* Headers Crimson Intelligence */
        h1, h2, h3 { 
            color: #ff4b4b !important; 
            font-weight: 700; 
            letter-spacing: -0.5px; 
            text-transform: uppercase;
            border-bottom: 1px solid #30363d;
            padding-bottom: 10px;
        }

        /* Cards de Métricas e Alvos */
        div[data-testid="stMetric"] {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 15px;
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover { border-color: #ff4b4b; transform: translateY(-2px); }

        /* Abas Operacionais */
        .stTabs [data-baseweb="tab-list"] { gap: 12px; }
        .stTabs [data-baseweb="tab"] {
            background-color: #161b22;
            border-radius: 8px 8px 0 0;
            color: #8b949e;
            padding: 10px 20px;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ff4b4b !important;
            color: white !important;
        }
        
        /* Inputs e Sidebar */
        .stTextInput input { background-color: #0d1117; border: 1px solid #30363d; color: white; }
        [data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #30363d; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. BASE TÁTICA GEOGRÁFICA ---
MAPA_TATICO_MT = {
    "CUIABA": (-15.6014, -56.0979), "VARZEA GRANDE": (-15.6461, -56.1325),
    "POCONE": (-16.2567, -56.6228), "PRIMAVERA DO LESTE": (-15.5594, -54.2961),
    "CACERES": (-16.0706, -57.6789), "RONDONOPOLIS": (-16.4678, -54.6361),
    "SINOP": (-11.8608, -55.5095), "SORRISO": (-12.5441, -55.7158),
    "BARRA DO GARCAS": (-15.8900, -52.2567), "CAMPO VERDE": (-15.5478, -55.1658),
    "ALTO GARCAS": (-16.9442, -53.5261), "ALTO ARAGUAIA": (-17.3150, -53.2158)
}

# --- 3. MOTOR DE INTELIGÊNCIA ---
@st.cache_data
def processar_inteligencia(arquivos):
    registros = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore').split('\n')
        for i, linha in enumerate(content):
            match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', linha)
            if match:
                dt_s, placa = match.group(1), match.group(2)
                local = content[i-1].strip() if i > 0 else "N/I"
                cid_ref = re.sub(r'BR\s*\d+|KM\s*[\d+.,/]+|Sentido:.*|ID:.*|[^a-zA-ZÀ-ÿ\s]', '', local, flags=re.I).strip().upper()
                coords = None
                for c, coord in MAPA_TATICO_MT.items():
                    if c in cid_ref: coords = coord; break
                
                registros.append({
                    'Placa': placa, 'Data_Hora': datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S'),
                    'Local': local, 'Cidade_Ref': cid_ref, 'Lat': coords[0] if coords else None, 
                    'Lon': coords[1] if coords else None
                })
    df = pd.DataFrame(registros)
    if not df.empty:
        df['Hora'] = df['Data_Hora'].dt.hour
    return df.sort_values('Data_Hora')

# --- 4. INTERFACE OPERACIONAL ---
aplicar_design_sistema()

# Protocolo de Acesso
if "auth" not in st.session_state:
    st.markdown("<h1 style='text-align: center; border:none;'>🦅⚡ WISE TALON</h1>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1,1.5,1])
    with col_c:
        st.info("Sistema de Triangulação de Rotas e Inteligência SESP")
        senha = st.text_input("Credencial Tática", type="password")
        if senha == "ft20+52":
            st.session_state["auth"] = True
            st.rerun()
    st.stop()

# Sidebar
with st.sidebar:
    st.markdown("### 🦅⚡ COMANDO")
    arqs = st.file_uploader("Upload Base SESP (CSV)", type=["csv"], accept_multiple_files=True)
    if st.button("🔄 Reiniciar"): st.session_state.clear(); st.rerun()
    st.divider()
    st.caption("v5.1 - Tactical Intelligence Unit")

if arqs:
    df = processar_inteligencia(arqs)
    
    # --- DETECÇÃO PRÉVIA DE ALVOS COMUNS (Insight Automático) ---
    st.markdown("## 🎯 ALVOS PRIORITÁRIOS (DETECTADOS EM MULTICIDADES)")
    city_counts = df.groupby('Placa')['Cidade_Ref'].nunique()
    alvos_comuns = city_counts[city_counts > 1].index.tolist()

    if alvos_comuns:
        # Layout de "Cards" para alvos detectados
        cols = st.columns(len(alvos_comuns) if len(alvos_comuns) < 5 else 5)
        for idx, p in enumerate(alvos_comuns[:15]): # Limite de 15 cards por performance
            cidades = df[df['Placa'] == p]['Cidade_Ref'].unique()
            cols[idx % 5].metric(label=f"🎯 {p}", value=f"{len(cidades)} Cidades", delta="Deslocamento")
    else:
        st.success("Nenhum deslocamento intermunicipal detectado no carregamento inicial.")

    st.divider()

    # ABAS
    tab_dash, tab_invest = st.tabs(["📊 DASHBOARD GERAL", "🔎 INVESTIGAÇÃO DETALHADA"])

    with tab_dash:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("VOLUME TOTAL", len(df))
        c2.metric("PLACAS ÚNICAS", df['Placa'].nunique())
        c3.metric("CIDADES ATIVAS", df['Cidade_Ref'].nunique())
        c4.metric("PERÍODO (DIAS)", (df['Data_Hora'].max() - df['Data_Hora'].min()).days + 1)
        
        st.divider()
        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(px.pie(df, names='Cidade_Ref', title="Concentração Geográfica", hole=0.5, 
                                  color_discrete_sequence=px.colors.sequential.Reds_r), use_container_width=True)
        with col_r:
            st.plotly_chart(px.histogram(df, x='Hora', title="Pico de Fluxo por Horário", color_discrete_sequence=['#ff4b4b']), use_container_width=True)

    with tab_invest:
        st.markdown("### 🔎 Análise de Trajetória e Perfil de Alvo")
        busca = st.text_input("DIGITE A PLACA DO ALVO", "").upper().strip()
        
        if busca:
            df_alvo = df[df['Placa'].str.contains(busca)]
            if not df_alvo.empty:
                c_rel, c_map = st.columns([1, 1.5])
                with c_rel:
                    st.markdown(f"#### 📋 Itinerário: {busca}")
                    txt = f"RELATÓRIO TÁTICO: {busca}\n"
                    txt += f"Municípios: {', '.join(df_alvo['Cidade_Ref'].unique())}\n\nCRONOLOGIA:\n"
                    for _, r in df_alvo.head(20).iterrows():
                        txt += f"- [{r['Data_Hora'].strftime('%d/%m %H:%M')}] {r['Local']}\n"
                    st.text_area("CONTEÚDO", txt, height=350)
                    
                    # PDF Gerador
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("helvetica", "B", 16)
                    pdf.cell(0, 10, "WISE TALON - RELATORIO DE INTELIGENCIA", ln=True)
                    pdf.set_font("helvetica", "", 12)
                    pdf.multi_cell(0, 10, txt.encode('latin-1', 'replace').decode('latin-1'))
                    st.download_button("📥 Baixar PDF Operacional", data=bytes(pdf.output()), file_name=f"Inteligencia_{busca}.pdf")

                with c_map:
                    df_gps = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                    if not df_gps.empty:
                        m = folium.Map(location=[df_gps['Lat'].mean(), df_gps['Lon'].mean()], zoom_start=8, tiles="cartodbpositron")
                        folium.PolyLine(df_gps[['Lat', 'Lon']].values, color="#ff4b4b", weight=4).add_to(m)
                        for _, r in df_gps.iterrows():
                            folium.Marker([r['Lat'], r['Lon']], popup=r['Local'], icon=folium.Icon(color='red')).add_to(m)
                        st_folium(m, width="100%", height=550)
                    else:
                        st.warning("Dados sem coordenadas GPS exatas para mapeamento.")
            else: st.error("Placa não encontrada na base atual.")

else:
    # Standby UX
    st.markdown("""
        <div style='text-align: center; margin-top: 150px;'>
            <h1 style='font-size: 100px; border:none;'>🦅⚡</h1>
            <h2 style='border:none;'>WISE TALON v5.1</h2>
            <p style='color: #8b949e;'>Aguardando ingestão de dados para varredura de alvos prioritários.</p>
        </div>
    """, unsafe_allow_html=True)
