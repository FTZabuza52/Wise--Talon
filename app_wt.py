import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import io

# --- TENTATIVA DE IMPORTS (MODO PROTEGIDO) ---
try:
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# --- 1. PROTOCOLO DE SEGURANÇA ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "ft20+52":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='color: #ff4b4b; text-align: center;'>🦅 FT20 - ACESSO RESTRITO</h1>", unsafe_allow_html=True)
        st.text_input("Insira a Credencial Tática", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("<h1 style='color: #ff4b4b; text-align: center;'>🦅 FT20 - ACESSO RESTRITO</h1>", unsafe_allow_html=True)
        st.text_input("Insira a Credencial Tática", type="password", on_change=password_entered, key="password")
        st.error("❌ Senha incorreta.")
        return False
    return True

# --- 2. GEOLOCALIZAÇÃO (CIDADE) ---
@st.cache_data
def get_city_coords(cidade):
    if not GEOPY_AVAILABLE or not cidade or cidade == "N/I":
        return None, None
    try:
        geolocator = Nominatim(user_agent="wise_talon_safety")
        location = geolocator.geocode(f"{cidade}, Mato Grosso, Brazil", timeout=10)
        return (location.latitude, location.longitude) if location else (None, None)
    except:
        return None, None

# --- 3. MOTOR DE PROCESSAMENTO HÍBRIDO ---
@st.cache_data
def processar_arquivos(arquivos):
    all_records = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
        # Modelo 1 (Blocos com GPS)
        if '"Placa ' in content:
            blocks = re.split(r'"Placa\s+', content)
            for block in blocks[1:]:
                data = {}
                p_m = re.search(r'^([A-Z0-9-]{7,8})"', block)
                data['Placa'] = p_m.group(1).strip() if p_m else "N/I"
                dt_m = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
                if dt_m: data['Data_Hora'] = datetime.strptime(dt_m.group(1).strip(), '%d/%m/%Y %H:%M:%S')
                c_m = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
                data['Lat'], data['Lon'] = (float(c_m.group(1)), float(c_m.group(2))) if c_m else (None, None)
                l_m = re.search(r'"([^"]+)"\s+"Local"', block)
                data['Local'] = l_m.group(1).strip() if l_m else "N/I"
                data['Cidade'] = data['Local'].split('-')[0].strip() if '-' in data['Local'] else data['Local']
                data['Hora'] = data['Data_Hora'].hour
                data['Is_City'] = False
                all_records.append(data)
        # Modelo 2 (Listas SESP)
        else:
            lines = [l.strip().replace('"', '') for l in content.split('\n') if l.strip()]
            for i in range(len(lines)):
                match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', lines[i])
                if match:
                    dt_s, placa = match.group(1), match.group(2)
                    local = lines[i-1] if i > 0 else "N/I"
                    dt_o = datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S')
                    cid = local.split(' KM ')[0].split(' Sentido:')[0].strip()
                    lat_c, lon_c = get_city_coords(cid)
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_o, 'Hora': dt_o.hour,
                        'Local': local, 'Cidade': cid, 'Lat': lat_c, 'Lon': lon_c, 'Is_City': True
                    })
    return pd.DataFrame(all_records).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 4. INTERFACE V4.0 ---
if check_password():
    st.set_page_config(page_title="Wise Talon v4.0", layout="wide", page_icon="🦅")
    
    st.markdown("""
        <style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] { background-color: #161b22; border-radius: 4px; padding: 10px 20px; border: 1px solid #30363d; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; border-color: #ff4b4b !important; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', monospace; }
        .stSidebar { background-color: #0d1117; border-right: 1px solid #30363d; }
        </style>
        """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🦅 WISE TALON")
        st.subheader("Painel de Controle")
        arquivos = st.file_uploader("Ingerir Dados (CSV)", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Resetar Sessão"): st.session_state.clear(); st.rerun()
        st.divider()
        st.caption("Status de Bibliotecas:")
        st.write(f"🗺️ Geo-Engine: {'✅' if GEOPY_AVAILABLE else '❌'}")
        st.write(f"📄 PDF-Engine: {'✅' if FPDF_AVAILABLE else '❌'}")

    if arquivos:
        df_total = processar_arquivos(arquivos)
        tab_dash, tab_invest, tab_risk = st.tabs(["📊 DASHBOARD", "🔎 INVESTIGAÇÃO", "🚩 ALVOS DE RISCO"])

        with tab_dash:
            # Métricas em Grid
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("REGISTROS", len(df_total))
            m2.metric("PLACAS", df_total['Placa'].nunique())
            m3.metric("CIDADES", df_total['Cidade'].nunique())
            m4.metric("PERÍODO (DIAS)", (df_total['Data_Hora'].max() - df_total['Data_Hora'].min()).days + 1)
            
            st.divider()
            c_left, c_right = st.columns(2)
            with c_left:
                fig_pie = px.pie(df_total, names='Cidade', hole=0.4, title="Concentração Geográfica", color_discrete_sequence=px.colors.sequential.Reds_r)
                st.plotly_chart(fig_pie, use_container_width=True)
            with c_right:
                fig_bar = px.histogram(df_total, x='Hora', title="Fluxo por Horário", color_discrete_sequence=['#ff4b4b'])
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_risk:
            st.subheader("🚩 Identificação de Deslocamento Intermunicipal")
            city_counts = df_total.groupby('Placa')['Cidade'].nunique()
            riscos = city_counts[city_counts > 1].index.tolist()
            if riscos:
                st.warning(f"Foram detectados {len(riscos)} alvos transitando entre diferentes cidades.")
                # Tabela de alvos de risco
                df_risco = df_total[df_total['Placa'].isin(riscos)].sort_values(['Placa', 'Data_Hora'])
                st.dataframe(df_risco[['Placa', 'Cidade', 'Data_Hora', 'Local']], use_container_width=True)
            else:
                st.success("Nenhum deslocamento suspeito identificado na base atual.")

        with tab_invest:
            target = st.text_input("DIGITE A PLACA PARA ANÁLISE DETALHADA", "").upper().strip()
            if target:
                df_alvo = df_total[df_total['Placa'].str.contains(target)]
                if not df_alvo.empty:
                    col_info, col_map = st.columns([1, 1.2])
                    with col_info:
                        st.markdown("### 📝 Itinerário Cronológico")
                        txt = f"RELATORIO OPERACIONAL - ALVO {target}\n"
                        txt += f"Cidades: {', '.join(df_alvo['Cidade'].unique())}\n\n"
                        for _, r in df_alvo.head(20).iterrows():
                            txt += f"[{r['Data_Hora'].strftime('%d/%m %H:%M')}] {r['Cidade']} -> {r['Local']}\n"
                        st.text_area("REGISTROS", txt, height=400)
                        
                        # Botão PDF (com proteção)
                        if FPDF_AVAILABLE:
                            try:
                                pdf = FPDF()
                                pdf.add_page()
                                pdf.set_font("helvetica", "B", 16)
                                pdf.cell(0, 10, f"RELATORIO TÁTICO: {target}", ln=True)
                                pdf.set_font("helvetica", "", 12)
                                pdf.multi_cell(0, 8, txt.encode('latin-1', 'replace').decode('latin-1'))
                                pdf_bytes = bytes(pdf.output())
                                st.download_button("📥 BAIXAR RELATÓRIO PDF", data=pdf_bytes, file_name=f"Alvo_{target}.pdf")
                            except: st.error("Erro ao gerar PDF.")

                    with col_map:
                        st.markdown("### 🗺️ Trajetória Geográfica")
                        df_m = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                        if not df_m.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            pts = [[r['Lat'], r['Lon']] for _, r in df_m.iterrows()]
                            folium.PolyLine(pts, color="#ff4b4b", weight=4, opacity=0.8).add_to(m)
                            for _, row in df_m.iterrows():
                                ic = 'orange' if row.get('Is_City') else 'blue'
                                folium.CircleMarker([row['Lat'], row['Lon']], radius=6, color=ic, fill=True).add_to(m)
                            m.fit_bounds(pts)
                            st_folium(m, width="100%", height=550)
                        else:
                            st.info("Sem dados geográficos para mapeamento.")
                else:
                    st.error("Placa não encontrada nos registros.")
