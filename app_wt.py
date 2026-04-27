import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from datetime import datetime
import plotly.express as px
from fpdf import FPDF
import io

# --- 1. PROTOCOLO DE SEGURANÇA (LOGIN) ---
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
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(255, 0, 0)
    pdf.cell(0, 10, "RELATÓRIO DE INTELIGÊNCIA - FT20", ln=True, align='C')
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    
    # Tratamento simples para caracteres especiais no PDF
    texto_limpo = texto.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, texto_limpo)
    
    return pdf.output()

if check_password():
    # --- CONFIGURAÇÕES VISUAIS ---
    st.set_page_config(page_title="FT20 - Wise Talon", page_icon="🦅", layout="wide")
    st.markdown("""
        <style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', Courier, monospace; }
        </style>
        """, unsafe_allow_html=True)

    # --- MOTOR SESP ---
    def extrair_dados_sesp(file):
        content = file.read().decode('utf-8', errors='ignore')
        blocks = re.split(r'"Placa\s+', content)
        records = []
        for block in blocks[1:]:
            data = {}
            placa_match = re.search(r'^([A-Z0-9-]{7,8})"', block)
            data['Placa'] = placa_match.group(1).strip() if placa_match else "N/I"
            dt_match = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
            if dt_match:
                try:
                    dt_str = dt_match.group(1).strip()
                    data['Data_Hora'] = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                    data['Hora'] = data['Data_Hora'].hour
                except: data['Data_Hora'], data['Hora'] = None, None
            coord_match = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
            if coord_match:
                data['Lat'], data['Lon'] = float(coord_match.group(1)), float(coord_match.group(2))
            else: data['Lat'], data['Lon'] = None, None
            local_match = re.search(r'"([^"]+)"\s+"Local"', block)
            if local_match:
                local_full = local_match.group(1).strip()
                data['Local'] = local_full
                data['Cidade'] = local_full.split('-')[0].strip()
            else: data['Local'], data['Cidade'] = "Ponto não identificado", "N/I"
            records.append(data)
        return pd.DataFrame(records)

    # --- RELATÓRIO NARRATIVO ---
    def gerar_narrativa(df_alvo, placa):
        total = len(df_alvo)
        ponto_f = df_alvo['Local'].value_counts().index[0]
        m = len(df_alvo[(df_alvo['Hora'] >= 6) & (df_alvo['Hora'] < 12)])
        t = len(df_alvo[(df_alvo['Hora'] >= 12) & (df_alvo['Hora'] < 18)])
        n = len(df_alvo[(df_alvo['Hora'] >= 18) | (df_alvo['Hora'] < 6)])
        perfil = "MATUTINO" if m > t and m > n else "VESPERTINO" if t > n else "NOTURNO"
        return f"""RELATÓRIO CIRCUNSTANCIADO - VEÍCULO {placa}
DATA: {datetime.now().strftime('%d/%m/%Y')}

1. RESUMO: {total} passagens detectadas.
2. PERÍODO: {perfil} (M:{m}, T:{t}, N:{n}).
3. LOCAL PRINCIPAL: {ponto_f}.
4. CONCLUSÃO: Sugere-se monitoramento estratégico no ponto citado."""

    # --- UI PRINCIPAL ---
    st.title("🦅 FT20 - WISE TALON")
    arquivos = st.file_uploader("📂 INGERIR CSV SESP", type=["csv"], accept_multiple_files=True)

    if arquivos:
        df_total = pd.concat([extrair_dados_sesp(arq) for arq in arquivos]).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("PASSAGENS", len(df_total))
        m2.metric("ALVOS ÚNICOS", df_total['Placa'].nunique())
        m3.metric("GPS ATIVO", df_total['Lat'].notna().sum())
        m4.metric("CIDADES", df_total['Cidade'].nunique())

        st.divider()
        c_g, c_m = st.columns([1, 1.2])

        with c_g:
            st.subheader("📈 Padrão de Horários")
            df_hora = df_total['Hora'].value_counts().sort_index().reset_index()
            df_hora.columns = ['Hora', 'Frequência']
            fig = px.bar(df_hora, x='Hora', y='Frequência', color_discrete_sequence=['#ff4b4b'])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=300)
            st.plotly_chart(fig, use_container_width=True)

        with c_m:
            st.subheader("🗺️ Mancha Térmica")
            df_mapa = df_total.dropna(subset=['Lat', 'Lon'])
            if not df_mapa.empty:
                m_calor = folium.Map(location=[df_mapa['Lat'].mean(), df_mapa['Lon'].mean()], zoom_start=12, tiles="cartodbpositron")
                HeatMap([[r['Lat'], r['Lon']] for _, r in df_mapa.iterrows()], radius=15).add_to(m_calor)
                st_folium(m_calor, width="100%", height=300)

        st.divider()
        st.subheader("🕵️‍♂️ INVESTIGAÇÃO DE ALVO")
        placa_b = st.text_input("PLACA PARA ANÁLISE", "").upper()

        if placa_b:
            df_alvo = df_total[df_total['Placa'].str.contains(placa_b)]
            if not df_alvo.empty:
                col_rel, col_map = st.columns([1, 1.2])
                with col_rel:
                    texto_rel = gerar_narrativa(df_alvo, placa_b)
                    st.text_area("CONTEÚDO DO RELATÓRIO", texto_rel, height=300)
                    # Geração do PDF
                    pdf_bytes = exportar_pdf(texto_rel, placa_b)
                    st.download_button("📥 BAIXAR RELATÓRIO (PDF)", data=bytes(pdf_bytes), file_name=f"Relatorio_{placa_b}.pdf", mime="application/pdf")
                
                with col_map:
                    st.write("**TRAJETÓRIA (ZOOM AJUSTADO)**")
                    df_alvo_gps = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                    if not df_alvo_gps.empty:
                        m_alvo = folium.Map(tiles="cartodbpositron")
                        pontos = [[r['Lat'], r['Lon']] for _, r in df_alvo_gps.iterrows()]
                        folium.PolyLine(pontos, color="red", weight=3, opacity=0.8).add_to(m_alvo)
                        # O SEGREDO DO ZOOM: fit_bounds
                        m_alvo.fit_bounds(pontos) 
                        st_folium(m_alvo, width="100%", height=350)
            else: st.error("PLACA NÃO ENCONTRADA.")

    with st.sidebar:
        st.button("Sair", on_click=lambda: st.session_state.clear())
        st.caption("FT20 WISE TALON v2.0")
    
