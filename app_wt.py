import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
import io

# --- PROTEÇÃO DE BIBLIOTECAS ---
try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
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

# --- 2. MOTOR DE GEOLOCALIZAÇÃO APERFEIÇOADO ---
@st.cache_data
def get_city_coords(cidade_suja):
    if not GEOPY_AVAILABLE or not cidade_suja:
        return None, None
    
    # Limpeza pesada do nome da cidade (remove BR, KM, Números e Sentidos)
    cidade_limpa = re.sub(r'BR\s?\d+', '', cidade_suja, flags=re.IGNORECASE)
    cidade_limpa = re.sub(r'KM\s?\d+[\+\d+]*', '', cidade_limpa, flags=re.IGNORECASE)
    cidade_limpa = re.sub(r'Sentido:.*', '', cidade_limpa, flags=re.IGNORECASE)
    cidade_limpa = re.sub(r'\(.*?\)', '', cidade_limpa)
    cidade_limpa = cidade_limpa.replace('-', ' ').strip()
    
    if len(cidade_limpa) < 3: return None, None

    try:
        geolocator = Nominatim(user_agent="wise_talon_mt_ops")
        # Forçamos a busca dentro de Mato Grosso para evitar cidades homônimas em outros estados
        query = f"{cidade_limpa}, Mato Grosso, Brasil"
        location = geolocator.geocode(query, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

# --- 3. PROCESSAMENTO HÍBRIDO ---
@st.cache_data
def processar_arquivos(arquivos):
    all_records = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
        
        # Modelo 1: Com GPS nativo
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
                data['Is_City_Center'] = False
                all_records.append(data)
        
        # Modelo 2: Lista SESP (Cáceres, Primavera, etc.)
        else:
            lines = [l.strip().replace('"', '') for l in content.split('\n') if l.strip()]
            for i in range(len(lines)):
                match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', lines[i])
                if match:
                    dt_s, placa = match.group(1), match.group(2)
                    local_original = lines[i-1] if i > 0 else "N/I"
                    dt_o = datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S')
                    
                    # Tenta pegar as coordenadas pelo nome da cidade no local
                    lat_c, lon_c = get_city_coords(local_original)
                    
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_o, 'Hora': dt_o.hour,
                        'Local': local_original, 'Cidade': local_original, # Guardamos o original para exibição
                        'Lat': lat_c, 'Lon': lon_c, 'Is_City_Center': True
                    })
    return pd.DataFrame(all_records).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 4. INTERFACE ---
if check_password():
    st.set_page_config(page_title="Wise Talon v4.1", layout="wide")
    
    st.markdown("""
        <style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', monospace; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; }
        </style>
        """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🦅 WISE TALON")
        arquivos = st.file_uploader("Subir CSVs", type=["csv"], accept_multiple_files=True)
        if st.button("Reiniciar"): st.session_state.clear(); st.rerun()
        st.divider()
        st.write(f"Geo-Engine: {'✅' if GEOPY_AVAILABLE else '❌'}")

    if arquivos:
        df_total = processar_arquivos(arquivos)
        tab1, tab2, tab3 = st.tabs(["📊 DASHBOARD", "🔎 INVESTIGAÇÃO", "🚩 ALVOS DE RISCO"])

        with tab1:
            c1, c2, c3 = st.columns(3)
            c1.metric("REGISTROS", len(df_total))
            c2.metric("PLACAS", df_total['Placa'].nunique())
            c3.metric("GPS/CIDADES", df_total['Lat'].notna().sum())
            
            st.divider()
            col_a, col_b = st.columns(2)
            with col_a:
                fig_city = px.pie(df_total, names='Cidade', hole=0.4, title="Fluxo Geográfico", color_discrete_sequence=px.colors.sequential.Reds_r)
                st.plotly_chart(fig_city, use_container_width=True)
            with col_b:
                fig_hour = px.histogram(df_total, x='Hora', title="Fluxo por Hora", color_discrete_sequence=['#ff4b4b'])
                st.plotly_chart(fig_hour, use_container_width=True)

        with tab3:
            # Lógica de detecção de múltiplas cidades
            st.subheader("🚩 Possíveis Deslocamentos Intermunicipais")
            # Para o dashboard de risco, limpamos o nome da cidade para agrupar
            df_total['Cidade_Ref'] = df_total['Cidade'].apply(lambda x: x.split('KM')[-1].strip() if 'KM' in str(x) else str(x))
            target_counts = df_total.groupby('Placa')['Cidade_Ref'].nunique()
            multi = target_counts[target_counts > 1].index.tolist()
            if multi:
                st.warning(f"Detectados {len(multi)} veículos em trânsito entre cidades.")
                st.dataframe(df_total[df_total['Placa'].isin(multi)][['Placa', 'Cidade', 'Data_Hora', 'Local']])
            else:
                st.success("Nenhum deslocamento suspeito.")

        with tab2:
            busca = st.text_input("DIGITE A PLACA PARA VER NO MAPA", "").upper().strip()
            if busca:
                df_alvo = df_total[df_total['Placa'].str.contains(busca)]
                if not df_alvo.empty:
                    c_info, c_map = st.columns([1, 1.5])
                    
                    with c_info:
                        st.markdown(f"### 📄 Histórico de {busca}")
                        st.dataframe(df_alvo[['Data_Hora', 'Local']], height=400)
                        
                    with c_map:
                        st.markdown("### 🗺️ Mapa de Itinerário")
                        df_mapa = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                        if not df_mapa.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            coords = [[r['Lat'], r['Lon']] for _, r in df_mapa.iterrows()]
                            folium.PolyLine(coords, color="#ff4b4b", weight=5, opacity=0.8).add_to(m)
                            
                            for _, row in df_mapa.iterrows():
                                # Laranja para cidade, Azul para radar exato
                                cor = 'orange' if row['Is_City_Center'] else 'blue'
                                folium.CircleMarker([row['Lat'], row['Lon']], radius=7, color=cor, fill=True, popup=row['Local']).add_to(m)
                            
                            m.fit_bounds(coords)
                            st_folium(m, width="100%", height=550)
                        else:
                            st.error("⚠️ Não foi possível geolocalizar as cidades deste arquivo automaticamente.")
                else:
                    st.error("Placa não encontrada.")
