import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
import io
import time

# --- PROTEÇÃO E CARREGAMENTO DE BIBLIOTECAS ---
try:
    from geopy.geocoders import Nominatim
    GEOPY_INSTALLED = True
except ImportError:
    GEOPY_INSTALLED = False

try:
    from fpdf import FPDF
    FPDF_INSTALLED = True
except ImportError:
    FPDF_INSTALLED = False

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

# --- 2. MOTOR DE GEOLOCALIZAÇÃO (LIMPEZA ULTRA) ---
@st.cache_data
def get_city_coords(texto_bruto):
    if not GEOPY_INSTALLED or not texto_bruto:
        return None, None
    
    # LÓGICA DE LIMPEZA: Isolar apenas o nome da cidade
    # 1. Remove "BR" e números da rodovia
    temp = re.sub(r'BR\s*\d+', '', texto_bruto, flags=re.I)
    # 2. Remove "KM" e as quilometragens (ex: 636+600)
    temp = re.sub(r'KM\s*[\d+.,/]+', '', temp, flags=re.I)
    # 3. Remove tudo o que vier após "Sentido:"
    temp = re.sub(r'Sentido:.*', '', temp, flags=re.I)
    # 4. Remove caracteres especiais remanescentes e IDs
    temp = re.sub(r'ID:.*', '', temp, flags=re.I)
    temp = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', temp)
    
    cidade = temp.strip()
    
    # Se a limpeza resultar em algo vazio ou muito curto, aborta
    if len(cidade) < 3:
        return None, None

    try:
        # User_agent único com timestamp para evitar bloqueio por ConfigurationError
        ua = f"WiseTalon_MT_Analytics_{int(time.time())}"
        geolocator = Nominatim(user_agent=ua)
        
        # Busca focada em Mato Grosso
        query = f"{cidade}, Mato Grosso, Brasil"
        location = geolocator.geocode(query, timeout=10)
        
        # Pausa obrigatória de 1 segundo para respeitar o limite do servidor gratuito
        time.sleep(1) 
        
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

# --- 3. PROCESSAMENTO DE DADOS ---
@st.cache_data
def processar_arquivos(arquivos):
    all_records = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
        
        # MODELO 1: COM GPS NO CSV (Formato Bloco)
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
                data['Estimado'] = False
                all_records.append(data)
        
        # MODELO 2: LISTA SESP (Pesquisa por nome da cidade)
        else:
            lines = [l.strip().replace('"', '') for l in content.split('\n') if l.strip()]
            for i in range(len(lines)):
                match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', lines[i])
                if match:
                    dt_s, placa = match.group(1), match.group(2)
                    local_bruto = lines[i-1] if i > 0 else "N/I"
                    dt_o = datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S')
                    
                    # Tenta buscar a latitude/longitude pelo nome da cidade limpo
                    lat_e, lon_e = get_city_coords(local_bruto)
                    
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_o, 'Hora': dt_o.hour,
                        'Local': local_bruto, 'Cidade': local_bruto,
                        'Lat': lat_e, 'Lon': lon_e, 'Estimado': True
                    })
    return pd.DataFrame(all_records).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 4. INTERFACE ---
if check_password():
    st.set_page_config(page_title="Wise Talon v4.3", layout="wide")
    st.markdown("""<style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', monospace; }
        </style>""", unsafe_allow_html=True)

    with st.sidebar:
        st.title("🦅 WISE TALON")
        arquivos = st.file_uploader("Upload CSV SESP", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Reiniciar Sistema"): st.session_state.clear(); st.rerun()

    if arquivos:
        df_total = processar_arquivos(arquivos)
        tab1, tab2, tab3 = st.tabs(["📊 DASHBOARD", "🔎 INVESTIGAÇÃO", "🚩 RISCO"])

        with tab1:
            c1, c2, c3 = st.columns(3)
            c1.metric("REGISTROS", len(df_total))
            c2.metric("PLACAS ÚNICAS", df_total['Placa'].nunique())
            c3.metric("MAPEADOS", df_total['Lat'].notna().sum())
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.plotly_chart(px.pie(df_total, names='Local', hole=0.4, title="Locais de Passagem", color_discrete_sequence=px.colors.sequential.Reds_r), use_container_width=True)
            with col_b:
                st.plotly_chart(px.histogram(df_total, x='Hora', title="Fluxo por Hora", color_discrete_sequence=['#ff4b4b']), use_container_width=True)

        with tab2:
            busca = st.text_input("INSIRA A PLACA PARA VER O TRAJETÓRIA", "").upper().strip()
            if busca:
                df_alvo = df_total[df_total['Placa'].str.contains(busca)]
                if not df_alvo.empty:
                    c_inf, c_map = st.columns([1, 1.5])
                    with c_inf:
                        st.markdown(f"### 📋 Itinerário de {busca}")
                        st.dataframe(df_alvo[['Data_Hora', 'Local']], height=400)
                    with c_map:
                        st.markdown("### 🗺️ Mapa Operacional")
                        df_m = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                        if not df_m.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            pts = [[r['Lat'], r['Lon']] for _, r in df_m.iterrows()]
                            folium.PolyLine(pts, color="#ff4b4b", weight=5).add_to(m)
                            for _, r in df_m.iterrows():
                                cor = 'orange' if r['Estimado'] else 'blue'
                                folium.Marker([r['Lat'], r['Lon']], popup=r['Local'], icon=folium.Icon(color=cor)).add_to(m)
                            m.fit_bounds(pts)
                            st_folium(m, width="100%", height=550)
                        else:
                            st.warning("Não há coordenadas ou cidades identificáveis para esta placa.")
