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
    "ARIPUANA": (-10.1667, -59.4667), "CAMPOS DE JULIO": (-13.8967, -59.1467)
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
        df['Cidade_Ref'] = df['Local'].apply(lambda x: re.sub(r'BR\s*\d+|KM\s*[\d+.,/]+|Sentido:.*|ID:.*|[^a-zA-ZÀ-ÿ\s]', '', str(x), flags=re.I).strip().upper())
    return df.sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 5. UI V4.5 ---
if check_password():
    st.set_page_config(page_title="Wise Talon v4.5", layout="wide")
    st.markdown("""<style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', monospace; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; }
        </style>""", unsafe_allow_html=True)

    with st.sidebar:
        st.title("🦅 WISE TALON")
        arquivos = st.file_uploader("Upload CSV SESP", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Reiniciar"): st.session_state.clear(); st.rerun()

    if arquivos:
        df_total = processar_arquivos(arquivos)
        tab1, tab2, tab3 = st.tabs(["📊 DASHBOARD", "🔎 INVESTIGAÇÃO", "🚩 ALVOS DE RISCO"])

        with tab1:
            m1, m2, m3 = st.columns(3)
            m1.metric("PASSAGENS", len(df_total))
            m2.metric("PLACAS ÚNICAS", df_total['Placa'].nunique())
            m3.metric("MAPEADOS", df_total['Lat'].notna().sum())
            st.divider()
            c_a, c_b = st.columns(2)
            with c_a: st.plotly_chart(px.pie(df_total, names='Cidade_Ref', title="Distribuição Geográfica", hole=0.4, color_discrete_sequence=px.colors.sequential.Reds_r), use_container_width=True)
            with c_b: st.plotly_chart(px.histogram(df_total, x='Hora', title="Fluxo por Horário", color_discrete_sequence=['#ff4b4b']), use_container_width=True)

        with tab3:
            st.subheader("🚩 Detecção de Deslocamento Intermunicipal")
            deslocamentos = df_total.groupby('Placa')['Cidade_Ref'].nunique()
            alvos_risco = deslocamentos[deslocamentos > 1].index.tolist()
            if alvos_risco:
                st.warning(f"Foram identificados {len(alvos_risco)} veículos transitando em múltiplas cidades.")
                st.dataframe(df_total[df_total['Placa'].isin(alvos_risco)][['Placa', 'Data_Hora', 'Cidade_Ref', 'Local']], use_container_width=True)
            else: st.success("Nenhum deslocamento intermunicipal detectado.")

        with tab2:
            placa = st.text_input("PESQUISAR PLACA", "").upper().strip()
            if placa:
                df_alvo = df_total[df_total['Placa'].str.contains(placa)]
                if not df_alvo.empty:
                    c_rel, c_map = st.columns([1, 1.5])
                    
                    # Preparação da Imagem para o PDF
                    mapa_png = None
                    df_gps = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                    if not df_gps.empty:
                        try:
                            # Criamos um mapa estático com Plotly para "tirar a foto"
                            fig_stat = px.scatter_mapbox(df_gps, lat="Lat", lon="Lon", zoom=7)
                            fig_stat.update_traces(marker=dict(size=12, color='red'))
                            fig_stat.update_layout(mapbox_style="stamen-terrain", mapbox_accesstoken=None, margin={"r":0,"t":0,"l":0,"b":0})
                            mapa_png = fig_stat.to_image(format="png")
                        except: mapa_png = None

                    with c_rel:
                        st.markdown(f"### 📋 Histórico de {placa}")
                        txt = f"RELATORIO OPERACIONAL - ALVO {placa}\nCidades: {', '.join(df_alvo['Cidade_Ref'].unique())}\n\n"
                        for _, r in df_alvo.head(20).iterrows():
                            txt += f"[{r['Data_Hora'].strftime('%d/%m %H:%M')}] {r['Local']}\n"
                        st.text_area("REGISTROS", txt, height=350)
                        
                        pdf_bytes = exportar_pdf(txt, placa, mapa_png)
                        st.download_button("📥 BAIXAR RELATÓRIO PDF (COM MAPA)", data=pdf_bytes, file_name=f"Relatorio_{placa}.pdf")

                    with c_map:
                        st.markdown("### 🧭 Vetor Tático de Deslocamento")
                        if not df_gps.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            coords = [[r['Lat'], r['Lon']] for _, r in df_gps.iterrows()]
                            # LINHA DE ROTA CRONOLÓGICA
                            folium.PolyLine(coords, color="#ff4b4b", weight=5, opacity=0.8, tooltip="Trajetória Provável").add_to(m)
                            for _, r in df_gps.iterrows():
                                cor = 'orange' if r['Metodo'] == "CIDADE" else 'blue'
                                folium.Marker([r['Lat'], r['Lon']], popup=f"{r['Data_Hora'].strftime('%H:%M')} - {r['Local']}", icon=folium.Icon(color=cor)).add_to(m)
                            m.fit_bounds(coords)
                            st_folium(m, width="100%", height=550)
                        else: st.error("Sem dados geográficos para este alvo.")
