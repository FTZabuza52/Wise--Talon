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

# --- 2. GERADOR DE PDF (fpdf2) ---
def exportar_pdf(texto, placa):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(255, 0, 0)
    pdf.cell(0, 10, "RELATÓRIO DE INTELIGÊNCIA - FT20", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("helvetica", "", 12)
    pdf.set_text_color(0, 0, 0)
    # fpdf2 suporta UTF-8 nativamente em muitos casos
    pdf.multi_cell(0, 10, texto)
    
    return pdf.output()

# --- 3. MOTOR DE DADOS COM CACHE ---
@st.cache_data
def processar_arquivos(arquivos):
    dfs = []
    for arq in arquivos:
        content = arq.read().decode('utf-8', errors='ignore')
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
                    data['Dia_Semana'] = data['Data_Hora'].strftime('%A')
                except: continue
            
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
        dfs.append(pd.DataFrame(records))
    
    if not dfs: return pd.DataFrame()
    return pd.concat(dfs).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 4. RELATÓRIO NARRATIVO AVANÇADO ---
def gerar_narrativa(df_alvo, placa):
    total = len(df_alvo)
    ponto_f = df_alvo['Local'].value_counts().index[0]
    cidades = df_alvo['Cidade'].unique()
    
    m = len(df_alvo[(df_alvo['Hora'] >= 6) & (df_alvo['Hora'] < 12)])
    t = len(df_alvo[(df_alvo['Hora'] >= 12) & (df_alvo['Hora'] < 18)])
    n = len(df_alvo[(df_alvo['Hora'] >= 18) | (df_alvo['Hora'] < 6)])
    perfil = "MATUTINO" if m > t and m > n else "VESPERTINO" if t > n else "NOTURNO"
    
    texto = f"""RELATÓRIO CIRCUNSTANCIADO - VEÍCULO {placa}
GERADO EM: {datetime.now().strftime('%d/%m/%Y %H:%M')}

1. RESUMO OPERACIONAL:
Detectadas {total} passagens no período analisado.
O veículo demonstra um perfil predominantemente {perfil}.

2. FLUXO GEOGRÁFICO:
Cidades detectadas: {', '.join(cidades)}.
Ponto de maior incidência: {ponto_f}.

3. ANÁLISE COMPORTAMENTAL:
- Período Matutino: {m} registros.
- Período Vespertino: {t} registros.
- Período Noturno: {n} registros.

4. CONCLUSÃO TÁTICA:
A análise de rota sugere padrões de rotina consistentes. Recomenda-se cerco inteligente nos horários de maior frequência identificados no gráfico de calor."""
    return texto

# --- 5. UI PRINCIPAL ---
if check_password():
    st.set_page_config(page_title="FT20 - Wise Talon", page_icon="🦅", layout="wide")
    st.markdown("""
        <style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', Courier, monospace; }
        .stTextArea textarea { background-color: #161b22; color: #white; border: 1px solid #ff4b4b; }
        </style>
        """, unsafe_allow_html=True)

    st.title("🦅 FT20 - WISE TALON")
    
    with st.sidebar:
        st.header("⚙️ CONFIGURAÇÃO")
        arquivos = st.file_uploader("INGERIR CSV SESP", type=["csv"], accept_multiple_files=True)
        if st.button("Limpar Sistema"):
            st.session_state.clear()
            st.rerun()
        st.caption("v3.0 - Intelligence & Route Analysis")

    if arquivos:
        df_total = processar_arquivos(arquivos)
        
        # Dashboard Inicial (Métricas Globais)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("TOTAL PASSAGENS", len(df_total))
        m2.metric("ALVOS ÚNICOS", df_total['Placa'].nunique())
        m3.metric("GPS DISPONÍVEL", df_total['Lat'].notna().sum())
        m4.metric("MUNICÍPIOS", df_total['Cidade'].nunique())

        st.divider()
        
        # --- INVESTIGAÇÃO DE ALVO ---
        st.subheader("🕵️‍♂️ ANÁLISE DE ROTA ESPECÍFICA")
        placa_b = st.text_input("DIGITE A PLACA PARA LIBERAR O MAPA", "").upper()

        if placa_b:
            df_alvo = df_total[df_total['Placa'].str.contains(placa_b)]
            
            if not df_alvo.empty:
                col_rel, col_map = st.columns([1, 1.2])
                
                with col_rel:
                    texto_rel = gerar_narrativa(df_alvo, placa_b)
                    st.text_area("INTELIGÊNCIA NARRATIVA", texto_rel, height=300)
                    pdf_bytes = exportar_pdf(texto_rel, placa_b)
                    st.download_button("📥 EXPORTAR PDF", data=bytes(pdf_bytes), file_name=f"Alvo_{placa_b}.pdf")

                    # INSIGHT DE ROTINA (Heatmap Dia x Hora)
                    st.subheader("📅 Padrão de Rotina")
                    pivot_rotina = df_alvo.pivot_table(index='Hora', columns='Dia_Semana', values='Placa', aggfunc='count').fillna(0)
                    # Reordenar dias da semana
                    dias = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    pivot_rotina = pivot_rotina.reindex(columns=[d for d in dias if d in pivot_rotina.columns])
                    
                    fig_heat = px.imshow(pivot_rotina, color_continuous_scale='Reds', aspect="auto")
                    fig_heat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=250)
                    st.plotly_chart(fig_heat, use_container_width=True)

                with col_map:
                    st.subheader(f"🗺️ TRAJETÓRIA TÁTICA: {placa_b}")
                    df_alvo_gps = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                    
                    if not df_alvo_gps.empty:
                        # Criar Mapa
                        m_alvo = folium.Map(tiles="cartodbpositron")
                        pontos = [[r['Lat'], r['Lon']] for _, r in df_alvo_gps.iterrows()]
                        
                        # Linha da Rota
                        folium.PolyLine(pontos, color="#ff4b4b", weight=4, opacity=0.8, tooltip="Trajetória").add_to(m_alvo)
                        
                        # Marcadores de Início e Fim
                        folium.Marker(pontos[0], popup="INÍCIO", icon=folium.Icon(color='green', icon='play')).add_to(m_alvo)
                        folium.Marker(pontos[-1], popup="ÚLTIMA POSIÇÃO", icon=folium.Icon(color='red', icon='stop')).add_to(m_alvo)
                        
                        m_alvo.fit_bounds(pontos)
                        st_folium(m_alvo, width="100%", height=550)
                    else:
                        st.warning("⚠️ Este alvo não possui coordenadas GPS válidas para mapeamento.")
            else:
                st.error("❌ Placa não encontrada na base de dados atual.")
        else:
            st.info("💡 Insira uma placa acima para carregar os mapas e as análises comportamentais.")
    
