import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
from fpdf import FPDF
import io
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

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

# --- 2. MOTOR DE GEOLOCALIZAÇÃO (Busca de Cidades) ---
@st.cache_data
def get_city_coords(cidade):
    """Transforma o nome da cidade em coordenadas reais"""
    if not cidade or cidade == "N/I":
        return None, None
    try:
        geolocator = Nominatim(user_agent="wise_talon_safety")
        # Refinamos a busca para MT para ser mais preciso
        location = geolocator.geocode(f"{cidade}, Mato Grosso, Brazil")
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

# --- 3. GERADOR DE PDF ---
def exportar_pdf(texto, placa, mapa_img=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(255, 0, 0)
    pdf.cell(0, 10, "RELATORIO DE INTELIGENCIA - FT20", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("helvetica", "", 12)
    texto_limpo = texto.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, texto_limpo)
    
    if mapa_img:
        pdf.ln(10)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "ANEXO: MAPA DE TRAJETORIA", ln=True)
        img_buffer = io.BytesIO(mapa_img)
        pdf.image(img_buffer, x=10, w=190)
    return bytes(pdf.output())

# --- 4. MOTOR DE PROCESSAMENTO ---
@st.cache_data
def processar_dados_sesp(arquivos):
    all_records = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
        if '"Placa ' in content:
            blocks = re.split(r'"Placa\s+', content)
            for block in blocks[1:]:
                data = {}
                placa_m = re.search(r'^([A-Z0-9-]{7,8})"', block)
                data['Placa'] = placa_m.group(1).strip() if placa_m else "N/I"
                dt_m = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
                if dt_m:
                    dt_str = dt_m.group(1).strip()
                    data['Data_Hora'] = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                coord_m = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
                data['Lat'], data['Lon'] = (float(coord_m.group(1)), float(coord_m.group(2))) if coord_m else (None, None)
                local_m = re.search(r'"([^"]+)"\s+"Local"', block)
                data['Local'] = local_m.group(1).strip() if local_m else "N/I"
                data['Cidade'] = data['Local'].split('-')[0].strip() if '-' in data['Local'] else data['Local']
                data['Sentido'] = "N/I"
                data['Hora'] = data['Data_Hora'].hour
                data['Dia_Semana'] = data['Data_Hora'].strftime('%A')
                all_records.append(data)
        else:
            lines = [l.strip().replace('"', '') for l in content.split('\n') if l.strip()]
            for i in range(len(lines)):
                match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', lines[i])
                if match:
                    dt_str, placa = match.group(1), match.group(2)
                    local = lines[i-1] if i > 0 else "N/I"
                    dt_obj = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                    cidade = local.split(' KM ')[0] if ' KM ' in local else local
                    if ' Sentido:' in cidade: cidade = cidade.split(' Sentido:')[0]
                    
                    # Tenta pegar coordenada da cidade se não houver GPS
                    lat_city, lon_city = get_city_coords(cidade.strip())
                    
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_obj, 'Hora': dt_obj.hour,
                        'Dia_Semana': dt_obj.strftime('%A'), 'Local': local,
                        'Cidade': cidade.strip(), 'Sentido': "N/I", 
                        'Lat': lat_city, 'Lon': lon_city, 'Is_City_Center': True
                    })
    return pd.DataFrame(all_records).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 5. UI ---
if check_password():
    st.set_page_config(page_title="Wise Talon - FT20", layout="wide")
    st.markdown("<style>.stApp { background-color: #0b0d11; color: #e0e0e0; } h1, h2, h3 { color: #ff4b4b !important; }</style>", unsafe_allow_html=True)
    st.title("🦅 WISE TALON - GEO-INTELIGÊNCIA")

    with st.sidebar:
        arquivos = st.file_uploader("Suba os arquivos CSV", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Reiniciar"): st.session_state.clear(); st.rerun()

    if arquivos:
        df_total = processar_dados_sesp(arquivos)
        if not df_total.empty:
            # --- DETECÇÃO DE DESLOCAMENTO ---
            st.subheader("🚩 ALVOS EM MÚLTIPLAS CIDADES")
            plates_by_city = df_total.groupby('Placa')['Cidade'].nunique()
            multi_city_targets = plates_by_city[plates_by_city > 1].index.tolist()
            if multi_city_targets:
                cols = st.columns(5)
                for idx, p in enumerate(multi_city_targets): cols[idx % 5].code(f"{p}")

            st.divider()
            placa_alvo = st.text_input("DIGITE A PLACA PARA ANÁLISE", "").upper().strip()

            if placa_alvo:
                df_alvo = df_total[df_total['Placa'].str.contains(placa_alvo)]
                if not df_alvo.empty:
                    col1, col2 = st.columns([1, 1.2])
                    
                    with col1:
                        st.markdown("### 📄 Itinerário")
                        txt = f"RELATORIO ALVO: {placa_alvo}\nCidades: {', '.join(df_alvo['Cidade'].unique())}\n\nCRONOLOGIA:\n"
                        for _, r in df_alvo.head(15).iterrows():
                            txt += f"- {r['Data_Hora'].strftime('%d/%m %H:%M')} | {r['Cidade']}\n"
                        st.text_area("REGISTROS", txt, height=350)
                        
                        # Preparar imagem do mapa para o PDF
                        mapa_png = None
                        df_gps = df_alvo.dropna(subset=['Lat', 'Lon'])
                        if not df_gps.empty:
                            try:
                                fig = px.scatter_mapbox(df_gps, lat="Lat", lon="Lon", zoom=8)
                                fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
                                mapa_png = fig.to_image(format="png")
                            except: mapa_png = None
                        
                        st.download_button("📥 BAIXAR PDF COM MAPA", data=exportar_pdf(txt, placa_alvo, mapa_png), file_name=f"Relatorio_{placa_alvo}.pdf")

                    with col2:
                        st.markdown("### 🧭 Mapa de Movimentação")
                        df_mapa = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                        if not df_mapa.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            coords = [[r['Lat'], r['Lon']] for _, r in df_mapa.iterrows()]
                            folium.PolyLine(coords, color="#ff4b4b", weight=5).add_to(m)
                            
                            # Marcadores diferenciados
                            for idx, row in df_mapa.iterrows():
                                color = 'blue'
                                if row.get('Is_City_Center'): color = 'orange' # Laranja para centro da cidade
                                folium.CircleMarker([row['Lat'], row['Lon']], radius=6, color=color, fill=True, popup=row['Local']).add_to(m)
                            
                            m.fit_bounds(coords)
                            st_folium(m, width="100%", height=550)
                        else:
                            st.error("Sem dados geográficos para este alvo.")
