import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
import io
import time

# --- 1. BASE DE DADOS TÁTICA (Coordenadas Fixas de MT) ---
# Isso garante que o mapa funcione mesmo se o serviço de busca falhar
MAPA_TATICO_MT = {
    "POCONE": (-16.2567, -56.6228),
    "PRIMAVERA DO LESTE": (-15.5594, -54.2961),
    "CUIABA": (-15.6014, -56.0979),
    "VARZEA GRANDE": (-15.6461, -56.1325),
    "CACERES": (-16.0706, -57.6789),
    "RONDONOPOLIS": (-16.4678, -54.6361),
    "SINOP": (-11.8608, -55.5095),
    "SORRISO": (-12.5441, -55.7158),
    "BARRA DO GARCAS": (-15.8900, -52.2567),
    "CAMPO VERDE": (-15.5478, -55.1658),
    "NOVA MUTUM": (-13.8306, -56.0819),
    "LUCAS DO RIO VERDE": (-13.0642, -55.9103),
    "TANGARA DA SERRA": (-14.6189, -57.4847),
    "PONTES E LACERDA": (-15.2261, -59.3353),
    "DIAMANTINO": (-14.4086, -56.4461),
}

# --- PROTEÇÃO DE BIBLIOTECAS ---
try:
    from geopy.geocoders import Nominatim
    GEOPY_INSTALLED = True
except:
    GEOPY_INSTALLED = False

# --- 2. PROTOCOLO DE SEGURANÇA ---
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

# --- 3. MOTOR DE GEOLOCALIZAÇÃO (HÍBRIDO) ---
@st.cache_data
def buscar_coordenadas(texto_local):
    if not texto_local: return None, None
    
    # LIMPEZA CIRÚRGICA: Isolar o nome da cidade
    # Remove Rodovias, KM, Sentidos e IDs
    limpo = re.sub(r'BR\s*\d+', '', texto_local, flags=re.I)
    limpo = re.sub(r'KM\s*[\d+.,/]+', '', limpo, flags=re.I)
    limpo = re.sub(r'Sentido:.*', '', limpo, flags=re.I)
    limpo = re.sub(r'ID:.*', '', limpo, flags=re.I)
    limpo = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', limpo)
    cidade_detectada = limpo.strip().upper()

    # 1. Tenta encontrar na nossa Base Tática Interna (Muito mais rápido e seguro)
    for cidade_chave, coords in MAPA_TATICO_MT.items():
        if cidade_chave in cidade_detectada:
            return coords

    # 2. Se não estiver no mapa tático, tenta buscar no Google/OSM (Requer Internet)
    if GEOPY_INSTALLED:
        try:
            # User_agent dinâmico para evitar bloqueio
            geolocator = Nominatim(user_agent=f"WiseTalon_MT_{int(time.time())}")
            location = geolocator.geocode(f"{cidade_detectada}, Mato Grosso, Brasil", timeout=10)
            time.sleep(1) # Delay de segurança
            if location:
                return (location.latitude, location.longitude)
        except:
            pass
            
    return None, None

# --- 4. PROCESSAMENTO DE ARQUIVOS ---
@st.cache_data
def processar_arquivos(arquivos):
    all_records = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
        
        # MODELO A: Formato com Coordenadas Diretas
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
                data['Hora'] = data['Data_Hora'].hour
                data['Metodo'] = "GPS"
                all_records.append(data)
        
        # MODELO B: Formato Lista SESP (PVA, Cáceres, etc.)
        else:
            lines = [l.strip().replace('"', '') for l in content.split('\n') if l.strip()]
            for i in range(len(lines)):
                match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', lines[i])
                if match:
                    dt_s, placa = match.group(1), match.group(2)
                    local_bruto = lines[i-1] if i > 0 else "N/I"
                    dt_o = datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S')
                    
                    # Busca inteligência de localização
                    lat, lon = buscar_coordenadas(local_bruto)
                    
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_o, 'Hora': dt_o.hour,
                        'Local': local_bruto, 'Lat': lat, 'Lon': lon, 'Metodo': "CIDADE"
                    })
    return pd.DataFrame(all_records).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 5. UI PRINCIPAL ---
if check_password():
    st.set_page_config(page_title="Wise Talon v4.4", layout="wide")
    st.markdown("""<style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', monospace; }
        </style>""", unsafe_allow_html=True)

    st.title("🦅 WISE TALON - INTELIGÊNCIA OPERACIONAL")

    with st.sidebar:
        arquivos = st.file_uploader("Upload CSV SESP", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Reiniciar"): st.session_state.clear(); st.rerun()

    if arquivos:
        df_total = processar_arquivos(arquivos)
        tab1, tab2, tab3 = st.tabs(["📊 DASHBOARD", "🔎 INVESTIGAÇÃO", "🚩 ALVOS DE RISCO"])

        with tab1:
            c1, c2, c3 = st.columns(3)
            c1.metric("REGISTROS", len(df_total))
            c2.metric("VEÍCULOS", df_total['Placa'].nunique())
            c3.metric("MAPEADOS", df_total['Lat'].notna().sum())
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.plotly_chart(px.pie(df_total, names='Local', title="Distribuição Geográfica", hole=0.4, color_discrete_sequence=px.colors.sequential.Reds_r), use_container_width=True)
            with col_b:
                st.plotly_chart(px.histogram(df_total, x='Hora', title="Fluxo por Horário", color_discrete_sequence=['#ff4b4b']), use_container_width=True)

        with tab2:
            placa = st.text_input("BUSCAR PLACA", "").upper().strip()
            if placa:
                df_alvo = df_total[df_total['Placa'].str.contains(placa)]
                if not df_alvo.empty:
                    c_rel, c_map = st.columns([1, 1.5])
                    with c_rel:
                        st.markdown("### 📋 Histórico")
                        st.dataframe(df_alvo[['Data_Hora', 'Local']], height=400)
                    with c_map:
                        st.markdown("### 🗺️ Mapa de Trajetória")
                        df_m = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                        if not df_m.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            pts = [[r['Lat'], r['Lon']] for _, r in df_m.iterrows()]
                            folium.PolyLine(pts, color="#ff4b4b", weight=5).add_to(m)
                            for _, r in df_m.iterrows():
                                cor = 'orange' if r['Metodo'] == "CIDADE" else 'blue'
                                folium.Marker([r['Lat'], r['Lon']], popup=r['Local'], icon=folium.Icon(color=cor)).add_to(m)
                            m.fit_bounds(pts)
                            st_folium(m, width="100%", height=550)
                        else:
                            st.warning("Sem dados de localização para esta placa.")

        with tab3:
            # Lógica de deslocamento intermunicipal
            df_total['Cidade_Ref'] = df_total['Local'].apply(lambda x: x.split(' ')[-1] if ' ' in str(x) else str(x))
            target_counts = df_total.groupby('Placa')['Cidade_Ref'].nunique()
            multi = target_counts[target_counts > 1].index.tolist()
            if multi:
                st.warning(f"Detectados {len(multi)} veículos transitando entre cidades.")
                st.dataframe(df_total[df_total['Placa'].isin(multi)][['Placa', 'Data_Hora', 'Local']])
