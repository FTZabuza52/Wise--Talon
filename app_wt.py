import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import io
import time

# --- 1. BASE DE DADOS TÁTICA AMPLIADA (MATO GROSSO) ---
# Adicionadas: Alto Garças e Alto Araguaia
MAPA_TATICO_MT = {
    "CUIABA": (-15.6014, -56.0979), "VARZEA GRANDE": (-15.6461, -56.1325),
    "POCONE": (-16.2567, -56.6228), "PRIMAVERA DO LESTE": (-15.5594, -54.2961),
    "CACERES": (-16.0706, -57.6789), "RONDONOPOLIS": (-16.4678, -54.6361),
    "SINOP": (-11.8608, -55.5095), "SORRISO": (-12.5441, -55.7158),
    "BARRA DO GARCAS": (-15.8900, -52.2567), "CAMPO VERDE": (-15.5478, -55.1658),
    "NOVA MUTUM": (-13.8306, -56.0819), "LUCAS DO RIO VERDE": (-13.0642, -55.9103),
    "TANGARA DA SERRA": (-14.6189, -57.4847), "PONTES E LACERDA": (-15.2261, -59.3353),
    "DIAMANTINO": (-14.4086, -56.4461), "BARRA DO BUGRES": (-15.0733, -57.1811),
    "JUINA": (-11.4147, -58.7458), "COLIDER": (-10.8147, -55.4547),
    "ALTA FLORESTA": (-9.8753, -56.0861), "JUARA": (-11.2547, -57.5189),
    "PEIXOTO DE AZEVEDO": (-10.2222, -54.9806), "GUARANTA DO NORTE": (-9.7878, -54.9111),
    "POXOREU": (-15.8372, -54.3892), "JACIARA": (-15.9653, -54.9683),
    "MIRASSOL DO OESTE": (-15.6767, -58.0958), "SAPEZAL": (-13.5422, -58.8167),
    "VILA RICA": (-10.0103, -51.1378), "CONFRESA": (-10.6433, -51.3931),
    "CAMPO NOVO DO PARECIS": (-13.6739, -57.8875), "QUERENCIA": (-12.6056, -52.1889),
    "ARIPUANA": (-10.1667, -59.4667), "CAMPOS DE JULIO": (-13.8967, -59.1467),
    "ALTO GARCAS": (-16.9442, -53.5261), "ALTO ARAGUAIA": (-17.3150, -53.2158)
}

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

# --- 3. MOTOR GEOGRÁFICO ---
@st.cache_data
def buscar_coordenadas(texto_local):
    if not texto_local: return None, None
    # Limpeza para identificar apenas o nome da cidade
    limpo = re.sub(r'BR\s*\d+|KM\s*[\d+.,/]+|Sentido:.*|ID:.*|[^a-zA-ZÀ-ÿ\s]', '', texto_local, flags=re.I).strip().upper()
    for cidade, coords in MAPA_TATICO_MT.items():
        if cidade in limpo: return coords
    return None, None

def exportar_pdf(texto, placa, mapa_img=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(255, 0, 0)
    pdf.cell(0, 10, "RELATORIO DE INTELIGENCIA - FT20", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("helvetica", "", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 8, texto.encode('latin-1', 'replace').decode('latin-1'))
    if mapa_img:
        pdf.ln(10)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "ANEXO: VETOR DE DESLOCAMENTO", ln=True)
        img_buffer = io.BytesIO(mapa_img)
        pdf.image(img_buffer, x=10, w=190)
    return bytes(pdf.output())

# --- 4. MOTOR DE PROCESSAMENTO ---
@st.cache_data
def processar_arquivos(arquivos):
    all_records = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
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
                data['Metodo'] = "GPS"
                all_records.append(data)
        else:
            lines = [l.strip().replace('"', '') for l in content.split('\n') if l.strip()]
            for i in range(len(lines)):
                match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', lines[i])
                if match:
                    dt_s, placa = match.group(1), match.group(2)
                    local_bruto = lines[i-1] if i > 0 else "N/I"
                    dt_o = datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S')
                    lat, lon = buscar_coordenadas(local_bruto)
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_o, 'Local': local_bruto,
                        'Lat': lat, 'Lon': lon, 'Metodo': "CIDADE"
                    })
    df = pd.DataFrame(all_records)
    if not df.empty:
        df['Hora'] = df['Data_Hora'].dt.hour
        # Limpeza para exibir a cidade no Dashboard
        df['Cidade_Ref'] = df['Local'].apply(lambda x: re.sub(r'BR\s*\d+|KM\s*[\d+.,/]+|Sentido:.*|ID:.*|[^a-zA-ZÀ-ÿ\s]', '', str(x), flags=re.I).strip().upper())
    return df.sort_values(by='Data_Hora', ascending=False).reset_
