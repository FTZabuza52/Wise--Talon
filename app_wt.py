import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from datetime import datetime
import plotly.express as px
from fpdf import FPDF
import io

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

# --- 2. GERADOR DE PDF ---
def exportar_pdf(texto, placa):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(255, 0, 0)
    pdf.cell(0, 10, "RELATORIO DE INTELIGENCIA - FT20", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("helvetica", "", 12)
    pdf.set_text_color(0, 0, 0)
    # Limpeza para evitar erros de caracteres no PDF
    texto_limpo = texto.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, texto_limpo)
    return pdf.output()

# --- 3. MOTOR DE PROCESSAMENTO HÍBRIDO (DETECTA MODELO 1 E 2) ---
@st.cache_data
def processar_dados_sesp(arquivos):
    all_records = []
    
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
        
        # --- VERIFICAÇÃO DE MODELO ---
        # Modelo 1: Tem a palavra '"Placa ' (Formato Bloco)
        # Modelo 2: Tem cabeçalhos de Data/Hora (Formato Relatório de Passagem)
        
        if '"Placa ' in content:
            # PROCESSAMENTO MODELO 1 (COM GPS)
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
                if coord_m:
                    data['Lat'], data['Lon'] = float(coord_m.group(1)), float(coord_m.group(2))
                else: data['Lat'], data['Lon'] = None, None
                
                local_m = re.search(r'"([^"]+)"\s+"Local"', block)
                data['Local'] = local_m.group(1).strip() if local_m else "N/I"
                data['Cidade'] = data['Local'].split('-')[0].strip() if '-' in data['Local'] else "N/I"
                data['Sentido'] = "N/I"
                data['Hora'] = data['Data_Hora'].hour
                data['Dia_Semana'] = data['Data_Hora'].strftime('%A')
                all_records.append(data)
                
        else:
            # PROCESSAMENTO MODELO 2 (NOVO FORMATO - SEM GPS)
            lines = [l.strip().replace('"', '') for l in content.split('\n') if l.strip()]
            for i in range(len(lines)):
                match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\s+([A-Z0-9-]{7,8})', lines[i])
                if match:
                    dt_str, placa = match.group(1), match.group(2)
                    local = lines[i-1] if i > 0 else "N/I"
                    sentido = "N/I"
                    if "Sentido:" in lines[i]: sentido = lines[i].split("Sentido:")[-1].strip()
                    elif "Sentido:" in lines[i-1]: sentido = lines[i-1].split("Sentido:")[-1].strip()
                    
                    dt_obj = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                    
                    # Tenta extrair cidade do nome do local
                    cidade = "N/I"
                    if "PRIMAVERA" in local.upper(): cidade = "Primavera do Leste"
                    elif "POCONE" in local.upper(): cidade = "Poconé"
                    elif "CUIABA" in local.upper(): cidade = "Cuiabá"
                    elif "CACERES" in local.upper(): cidade = "Cáceres"
                    
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_obj, 'Hora': dt_obj.hour,
                        'Dia_Semana': dt_obj.strftime('%A'), 'Local': local,
                        'Cidade': cidade, 'Sentido': sentido, 'Lat': None, 'Lon': None
                    })

    return pd.DataFrame(all_records).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 4. INTERFACE ---
if check_password():
    st.set_page_config(page_title="Wise Talon - FT20", layout="wide")
    st.markdown("""<style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', Courier, monospace; }
        </style>""", unsafe_allow_html=True)

    st.title("🦅 WISE TALON - ANÁLISE DE ROTAS")

    with st.sidebar:
        st.header("📂 CARGA DE DADOS")
        arquivos = st.file_uploader("Suba qualquer CSV do SESP", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Reiniciar"):
            st.session_state.clear()
            st.rerun()

    if arquivos:
        df_total = processar_dados_sesp(arquivos)
        if not df_total.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("PASSAGENS", len(df_total))
            c2.metric("ALVOS", df_total['Placa'].nunique())
            c3.metric("CIDADES", df_total['Cidade'].nunique())
            c4.metric("GPS ATIVO", df_total['Lat'].notna().sum())

            st.divider()
            st.subheader("🔎 INVESTIGAÇÃO DE ALVO")
            placa_alvo = st.text_input("DIGITE A PLACA DO VEÍCULO", "").upper().strip()

            if placa_alvo:
                df_alvo = df_total[df_total['Placa'].str.contains(placa_alvo)]
                if not df_alvo.empty:
                    col1, col2 = st.columns([1, 1.2])
                    with col1:
                        st.markdown("### 📄 Relatório Operacional")
                        txt = f"RELATORIO DE BUSCA - ALVO: {placa_alvo}\n"
                        txt += f"Total de passagens: {len(df_alvo)}\n"
                        txt += f"Ultima localizacao: {df_alvo.iloc[0]['Local']}\n"
                        txt += f"Cidades: {', '.join(df_alvo['Cidade'].unique())}\n\nHISTORICO:\n"
                        for _, r in df_alvo.head(10).iterrows():
                            txt += f"- {r['Data_Hora'].strftime('%d/%m %H:%M')}: {r['Local']}\n"
                        
                        st.text_area("CONTEÚDO", txt, height=300)
                        st.download_button("📥 BAIXAR PDF", data=exportar_pdf(txt, placa_alvo), file_name=f"Alvo_{placa_alvo}.pdf")
                        
                        st.markdown("### 📅 Padrão de Horários")
                        fig = px.bar(df_alvo.groupby('Hora').size().reset_index(name='Qtd'), x='Hora', y='Qtd', color_discrete_sequence=['#ff4b4b'])
                        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=200)
                        st.plotly_chart(fig, use_container_width=True)

                    with col2:
                        st.markdown("### 🗺️ Localização e Rotas")
                        df_gps = df_alvo.dropna(subset=['Lat', 'Lon'])
                        
                        if not df_gps.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            coords = [[r['Lat'], r['Lon']] for _, r in df_gps.iterrows()]
                            folium.PolyLine(coords, color="#ff4b4b", weight=5).add_to(m)
                            folium.Marker(coords[0], icon=folium.Icon(color='green')).add_to(m)
                            folium.Marker(coords[-1], icon=folium.Icon(color='red')).add_to(m)
                            m.fit_bounds(coords)
                            st_folium(m, width="100%", height=500)
                        else:
                            st.warning("⚠️ Este arquivo não possui coordenadas GPS. Veja abaixo a lista de passagens:")
                            st.table(df_alvo[['Data_Hora', 'Local', 'Sentido']].head(15))
                else:
                    st.error("Placa não encontrada.")
        else:
            st.error("Erro ao ler os arquivos.")
    else:
        st.info("Aguardando upload de arquivos...")
