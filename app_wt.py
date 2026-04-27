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

# --- 1. CONFIGURAÇÃO E BIBLIOTECAS ---
st.set_page_config(page_title="Wise Talon v4.9", layout="wide", page_icon="🦅")

try:
    from fpdf import FPDF
    FPDF_OK = True
except: FPDF_OK = False

# BASE TÁTICA AMPLIADA (Incluindo Alto Garças e Alto Araguaia)
MAPA_TATICO_MT = {
    "CUIABA": (-15.6014, -56.0979), "VARZEA GRANDE": (-15.6461, -56.1325),
    "POCONE": (-16.2567, -56.6228), "PRIMAVERA DO LESTE": (-15.5594, -54.2961),
    "CACERES": (-16.0706, -57.6789), "RONDONOPOLIS": (-16.4678, -54.6361),
    "SINOP": (-11.8608, -55.5095), "SORRISO": (-12.5441, -55.7158),
    "BARRA DO GARCAS": (-15.8900, -52.2567), "CAMPO VERDE": (-15.5478, -55.1658),
    "ALTO GARCAS": (-16.9442, -53.5261), "ALTO ARAGUAIA": (-17.3150, -53.2158),
    "PONTES E LACERDA": (-15.2261, -59.3353), "TANGARA DA SERRA": (-14.6189, -57.4847)
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

# --- 3. MOTORES DE INTELIGÊNCIA ---
@st.cache_data
def limpar_cidade(texto):
    if not texto: return "N/I"
    # Isola o nome da cidade removendo BR, KM e Sentidos
    limpo = re.sub(r'BR\s*\d+|KM\s*[\d+.,/]+|Sentido:.*|ID:.*|[^a-zA-ZÀ-ÿ\s]', '', str(texto), flags=re.I).strip().upper()
    return limpo if limpo else "N/I"

@st.cache_data
def buscar_coords(cidade_limpa):
    for cidade, coords in MAPA_TATICO_MT.items():
        if cidade in cidade_limpa: return coords
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
                cid_ref = limpar_cidade(local)
                lat, lon = buscar_coords(cid_ref)
                all_data.append({
                    'Placa': placa, 'Data_Hora': datetime.strptime(dt_s, '%d/%m/%Y %H:%M:%S'),
                    'Local': local, 'Cidade_Ref': cid_ref, 'Lat': lat, 'Lon': lon
                })
    df = pd.DataFrame(all_data)
    if not df.empty:
        df['Hora'] = df['Data_Hora'].dt.hour
    return df.sort_values('Data_Hora', ascending=False)

def gerar_pdf(texto, placa, mapa_img=None):
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
        img_buffer = io.BytesIO(mapa_img)
        pdf.image(img_buffer, x=10, w=190)
    return bytes(pdf.output())

# --- 4. INTERFACE ---
if check_password():
    st.markdown("""<style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        h1, h2, h3 { color: #ff4b4b !important; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; }
        </style>""", unsafe_allow_html=True)

    with st.sidebar:
        st.title("🦅 WISE TALON")
        arquivos = st.file_uploader("📂 INGERIR DADOS", type=["csv"], accept_multiple_files=True)
        if st.button("Limpar Tudo"):
            st.session_state.clear()
            st.rerun()

    if arquivos:
        df_total = processar_arquivos(arquivos)
        tab_risk, tab_invest, tab_dash = st.tabs(["🚩 ALVOS DE RISCO", "🔎 INVESTIGAÇÃO", "📊 DASHBOARD"])

        with tab_risk:
            st.subheader("Veículos detectados em múltiplas cidades")
            # Agrupar e encontrar placas que cruzaram cidades
            check_risk = df_total.groupby('Placa')['Cidade_Ref'].nunique()
            multi_city = check_risk[check_risk > 1].index.tolist()
            
            if multi_city:
                st.warning(f"Foram identificados {len(multi_city)} alvos com deslocamento intermunicipal.")
                for p in multi_city:
                    cidades = df_total[df_total['Placa'] == p]['Cidade_Ref'].unique()
                    st.code(f"PLACA: {p} | CIDADES: {', '.join(cidades)}")
                
                st.divider()
                st.dataframe(df_total[df_total['Placa'].isin(multi_city)][['Placa', 'Data_Hora', 'Cidade_Ref', 'Local']], use_container_width=True)
            else:
                st.success("Nenhum deslocamento suspeito detectado.")

        with tab_invest:
            busca = st.text_input("PESQUISAR PLACA ESPECÍFICA", "").upper().strip()
            if busca:
                df_alvo = df_total[df_total['Placa'].str.contains(busca)]
                if not df_alvo.empty:
                    c1, c2 = st.columns([1, 1.5])
                    
                    # Preparar imagem do mapa para o PDF (Plotly)
                    mapa_png = None
                    df_m = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                    if not df_m.empty:
                        try:
                            fig_st = px.scatter_mapbox(df_m, lat="Lat", lon="Lon", zoom=7)
                            fig_st.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
                            mapa_png = fig_st.to_image(format="png")
                        except: pass

                    with c1:
                        txt_rel = f"RELATORIO ALVO: {busca}\nCidades: {', '.join(df_alvo['Cidade_Ref'].unique())}\n\n"
                        for _, r in df_alvo.head(15).iterrows():
                            txt_rel += f"[{r['Data_Hora'].strftime('%d/%m %H:%M')}] {r['Local']}\n"
                        st.text_area("Histórico", txt_rel, height=300)
                        
                        if FPDF_OK:
                            pdf_bytes = gerar_pdf(txt_rel, busca, mapa_png)
                            st.download_button("📥 BAIXAR RELATÓRIO PDF", data=pdf_bytes, file_name=f"Alvo_{busca}.pdf")

                    with c2:
                        if not df_m.empty:
                            m = folium.Map(location=[df_m['Lat'].mean(), df_m['Lon'].mean()], zoom_start=8)
                            coords = df_m[['Lat', 'Lon']].values.tolist()
                            folium.PolyLine(coords, color="red", weight=5, tooltip="Vetor de Deslocamento").add_to(m)
                            for _, r in df_m.iterrows():
                                folium.Marker([r['Lat'], r['Lon']], popup=f"{r['Data_Hora']}").add_to(m)
                            st_folium(m, width="100%", height=500)
                else: st.error("Placa não encontrada.")

        with tab_dash:
            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(df_total, names='Cidade_Ref', title="Concentração por Cidade"), use_container_width=True)
            c2.plotly_chart(px.histogram(df_total, x='Hora', title="Fluxo por Hora"), use_container_width=True)

    else:
        st.markdown("<div style='text-align: center; margin-top: 100px;'><h1>🦅</h1><h3>Aguardando arquivos para análise...</h3></div>", unsafe_allow_html=True)
