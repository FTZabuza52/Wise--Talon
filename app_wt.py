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
    texto_limpo = texto.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, texto_limpo)
    return pdf.output()

# --- 3. MOTOR DE PROCESSAMENTO HÍBRIDO ---
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
                    sentido = "N/I"
                    if "Sentido:" in lines[i]: sentido = lines[i].split("Sentido:")[-1].strip()
                    dt_obj = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                    # Tenta limpar o nome da cidade de forma mais inteligente
                    cidade = local.split(' KM ')[0] if ' KM ' in local else local
                    if ' Sentido:' in cidade: cidade = cidade.split(' Sentido:')[0]
                    
                    all_records.append({
                        'Placa': placa, 'Data_Hora': dt_obj, 'Hora': dt_obj.hour,
                        'Dia_Semana': dt_obj.strftime('%A'), 'Local': local,
                        'Cidade': cidade.strip(), 'Sentido': sentido, 'Lat': None, 'Lon': None
                    })
    return pd.DataFrame(all_records).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 4. INTERFACE ---
if check_password():
    st.set_page_config(page_title="Wise Talon - FT20", layout="wide")
    st.markdown("""<style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', Courier, monospace; }
        .stAlert { background-color: #161b22; color: white; border: 1px solid #ff4b4b; }
        </style>""", unsafe_allow_html=True)

    st.title("🦅 WISE TALON - ANÁLISE DE DESLOCAMENTO")

    with st.sidebar:
        st.header("📂 CARGA DE DADOS")
        arquivos = st.file_uploader("Suba os arquivos CSV", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Reiniciar Sistema"):
            st.session_state.clear()
            st.rerun()

    if arquivos:
        df_total = processar_dados_sesp(arquivos)
        if not df_total.empty:
            # MÉTRICAS TOTAIS
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("PASSAGENS", len(df_total))
            m2.metric("VEÍCULOS ÚNICOS", df_total['Placa'].nunique())
            m3.metric("CIDADES", df_total['Cidade'].nunique())
            m4.metric("GPS DISPONÍVEL", df_total['Lat'].notna().sum())

            st.divider()

            # --- NOVO: IDENTIFICAÇÃO DE ALVOS EM MÚLTIPLAS CIDADES ---
            st.subheader("🚩 ALVOS DE INTERESSE (DESLOCAMENTO)")
            # Agrupa por placa e conta quantas cidades únicas cada uma possui
            plates_by_city = df_total.groupby('Placa')['Cidade'].nunique()
            multi_city_targets = plates_by_city[plates_by_city > 1].index.tolist()

            if multi_city_targets:
                st.warning(f"🔍 **DETECTADO:** {len(multi_city_targets)} veículos aparecem em mais de uma cidade.")
                cols = st.columns(5) # Divide a lista em colunas para não ficar gigante
                for idx, p in enumerate(multi_city_targets):
                    # Mostra a placa e em quantas cidades ela apareceu
                    cidades_alvo = df_total[df_total['Placa'] == p]['Cidade'].unique()
                    cols[idx % 5].code(f"{p} ({len(cidades_alvo)} Cidades)")
            else:
                st.info("Nenhum veículo detectado em múltiplas cidades nesta base de dados.")

            st.divider()

            # --- BUSCA POR ALVO ---
            st.subheader("🔎 INVESTIGAÇÃO DETALHADA")
            placa_alvo = st.text_input("DIGITE A PLACA ACIMA PARA ANALISAR", "").upper().strip()

            if placa_alvo:
                df_alvo = df_total[df_total['Placa'].str.contains(placa_alvo)]
                if not df_alvo.empty:
                    col1, col2 = st.columns([1, 1.2])
                    with col1:
                        st.markdown("### 📄 Relatório de Itinerário")
                        txt = f"RELATORIO DE BUSCA - ALVO: {placa_alvo}\n"
                        txt += f"Cidades detectadas: {', '.join(df_alvo['Cidade'].unique())}\n"
                        txt += f"Total de registros: {len(df_alvo)}\n\nCRONOLOGIA:\n"
                        for _, r in df_alvo.head(15).iterrows():
                            txt += f"- {r['Data_Hora'].strftime('%d/%m %H:%M')} | {r['Cidade']} | {r['Local']}\n"
                        
                        st.text_area("REGISTROS", txt, height=350)
                        st.download_button("📥 BAIXAR PDF", data=exportar_pdf(txt, placa_alvo), file_name=f"Relatorio_{placa_alvo}.pdf")

                    with col2:
                        st.markdown("### 🧭 Análise de Movimentação")
                        df_gps = df_alvo.dropna(subset=['Lat', 'Lon'])
                        if not df_gps.empty:
                            m = folium.Map(tiles="cartodbpositron")
                            coords = [[r['Lat'], r['Lon']] for _, r in df_gps.iterrows()]
                            folium.PolyLine(coords, color="#ff4b4b", weight=5).add_to(m)
                            folium.Marker(coords[0], tooltip="Início", icon=folium.Icon(color='green')).add_to(m)
                            folium.Marker(coords[-1], tooltip="Último", icon=folium.Icon(color='red')).add_to(m)
                            m.fit_bounds(coords)
                            st_folium(m, width="100%", height=500)
                        else:
                            # Se não tem GPS, mostra gráfico de cidades
                            fig_city = px.pie(df_alvo, names='Cidade', title=f"Distribuição Geográfica de {placa_alvo}", color_discrete_sequence=px.colors.sequential.Reds_r)
                            fig_city.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color="white")
                            st.plotly_chart(fig_city, use_container_width=True)
                            
                            st.write("**Histórico de Passagens:**")
                            st.dataframe(df_alvo[['Data_Hora', 'Cidade', 'Local', 'Sentido']], use_container_width=True)
                else:
                    st.error("Placa não encontrada nos arquivos carregados.")
            else:
                st.info("Insira uma placa para gerar os detalhes da rota.")
