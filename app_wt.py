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
    # Suporte a acentos e quebra automática de linha
    pdf.multi_cell(0, 8, texto.encode('latin-1', 'replace').decode('latin-1'))
    
    return pdf.output()

# --- 3. MOTOR DE PROCESSAMENTO (REGEX + CACHE) ---
@st.cache_data
def processar_dados_sesp(arquivos):
    dfs = []
    for arq in arquivos:
        try:
            content = arq.read().decode('utf-8', errors='ignore')
            blocks = re.split(r'"Placa\s+', content)
            records = []
            for block in blocks[1:]:
                data = {}
                placa_match = re.search(r'^([A-Z0-9-]{7,8})"', block)
                data['Placa'] = placa_match.group(1).strip() if placa_match else "N/I"
                
                dt_match = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
                if dt_match:
                    dt_str = dt_match.group(1).strip()
                    data['Data_Hora'] = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                    data['Hora'] = data['Data_Hora'].hour
                    data['Dia_Semana'] = data['Data_Hora'].strftime('%A')
                
                coord_match = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
                if coord_match:
                    data['Lat'], data['Lon'] = float(coord_match.group(1)), float(coord_match.group(2))
                else:
                    data['Lat'], data['Lon'] = None, None
                
                local_match = re.search(r'"([^"]+)"\s+"Local"', block)
                if local_match:
                    local_full = local_match.group(1).strip()
                    data['Local'] = local_full
                    data['Cidade'] = local_full.split('-')[0].strip()
                else:
                    data['Local'], data['Cidade'] = "Não identificado", "N/I"
                
                records.append(data)
            dfs.append(pd.DataFrame(records))
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")
    
    if not dfs: return pd.DataFrame()
    return pd.concat(dfs).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

# --- 4. GERADOR DE NARRATIVA ---
def gerar_narrativa(df_alvo, placa):
    total = len(df_alvo)
    ponto_f = df_alvo['Local'].value_counts().index[0]
    cidades = ", ".join(df_alvo['Cidade'].unique())
    
    m = len(df_alvo[(df_alvo['Hora'] >= 6) & (df_alvo['Hora'] < 12)])
    t = len(df_alvo[(df_alvo['Hora'] >= 12) & (df_alvo['Hora'] < 18)])
    n = len(df_alvo[(df_alvo['Hora'] >= 18) | (df_alvo['Hora'] < 6)])
    perfil = "MATUTINO" if m > t and m > n else "VESPERTINO" if t > n else "NOTURNO"
    
    return f"""RELATORIO CIRCUNSTANCIADO - ALVO {placa}
EMISSAO: {datetime.now().strftime('%d/%m/%Y %H:%M')}

1. RESUMO:
O veiculo foi detectado {total} vezes.
O comportamento sugere perfil de circulacao {perfil}.

2. GEOGRAFIA:
Municipios detectados: {cidades}.
Ponto critico de passagem: {ponto_f}.

3. HISTOGRAMA TEMPORAL:
- Manha: {m} passagens.
- Tarde: {t} passagens.
- Noite/Madrugada: {n} passagens.

4. DIRETRIZ:
Sugere-se monitoramento preventivo nos horários identificados como de maior calor no grafico de rotina."""

# --- 5. INTERFACE (STREAMLIT) ---
if check_password():
    st.set_page_config(page_title="Wise Talon - FT20", page_icon="🦅", layout="wide")
    
    # Custom CSS para tema tático
    st.markdown("""
        <style>
        .stApp { background-color: #0b0d11; color: #e0e0e0; }
        div[data-testid="stMetric"] { background-color: #161b22; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; }
        h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', Courier, monospace; }
        .stTextArea textarea { background-color: #161b22; color: white !important; }
        </style>
        """, unsafe_allow_html=True)

    st.title("🦅 WISE TALON - ANÁLISE DE ROTAS")

    with st.sidebar:
        st.header("📂 ENTRADA DE DADOS")
        arquivos = st.file_uploader("Subir CSVs do SESP", type=["csv"], accept_multiple_files=True)
        if st.button("🔄 Reiniciar Sistema"):
            st.session_state.clear()
            st.rerun()
        st.caption("FT20 - v3.0 | 2026")

    if arquivos:
        df_total = processar_dados_sesp(arquivos)

        # Dashboard Geral (Resumo da Carga)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("REGISTROS TOTAIS", len(df_total))
        c2.metric("VEÍCULOS ÚNICOS", df_total['Placa'].nunique())
        c3.metric("COORDENADAS ATIVAS", df_total['Lat'].notna().sum())
        c4.metric("CIDADES NA BASE", df_total['Cidade'].nunique())

        st.divider()

        # --- BUSCA POR ALVO ---
        st.subheader("🔎 INVESTIGAÇÃO DE ALVO")
        placa_alvo = st.text_input("INSIRA A PLACA PARA LIBERAR O MAPA E RELATÓRIO", "").upper().strip()

        if placa_alvo:
            df_selecionado = df_total[df_total['Placa'].str.contains(placa_alvo)]
            
            if not df_selecionado.empty:
                col_info, col_mapa = st.columns([1, 1.2])

                with col_info:
                    st.markdown("### 📄 Relatório de Inteligência")
                    relatorio_texto = gerar_narrativa(df_selecionado, placa_alvo)
                    st.text_area("CONTEÚDO", relatorio_texto, height=280)
                    
                    pdf_data = exportar_pdf(relatorio_texto, placa_alvo)
                    st.download_button("📥 BAIXAR PDF TÁTICO", data=pdf_data, file_name=f"Relatorio_{placa_alvo}.pdf", mime="application/pdf")

                    st.divider()
                    
                    # INSIGHT DE ROTINA (Heatmap Dia x Hora)
                    st.markdown("### 📅 Matriz de Rotina")
                    dias_ordem = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    pivot_routine = df_selecionado.pivot_table(index='Hora', columns='Dia_Semana', values='Placa', aggfunc='count').fillna(0)
                    pivot_routine = pivot_routine.reindex(columns=[d for d in dias_ordem if d in pivot_routine.columns])
                    
                    fig_heat = px.imshow(pivot_routine, color_continuous_scale='Reds', labels=dict(x="Dia", y="Hora", color="Frequência"))
                    fig_heat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=250, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_heat, use_container_width=True)

                with col_mapa:
                    st.markdown(f"### 🗺️ Trajetória do Alvo: {placa_alvo}")
                    df_gps = df_selecionado.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                    
                    if not df_gps.empty:
                        # Criando o mapa folium
                        m = folium.Map(tiles="cartodbpositron")
                        coords = [[r['Lat'], r['Lon']] for _, r in df_gps.iterrows()]
                        
                        # Linha do rastro
                        folium.PolyLine(coords, color="#ff4b4b", weight=5, opacity=0.7).add_to(m)
                        
                        # Marcadores de Início e Fim
                        folium.Marker(coords[0], tooltip="INÍCIO DO RASTRO", icon=folium.Icon(color='green', icon='play')).add_to(m)
                        folium.Marker(coords[-1], tooltip="ÚLTIMA LOCALIZAÇÃO", icon=folium.Icon(color='red', icon='stop')).add_to(m)
                        
                        m.fit_bounds(coords) # Zoom automático no trajeto
                        st_folium(m, width="100%", height=580)
                    else:
                        st.error("Este veículo não possui dados de GPS para gerar o mapa.")
            else:
                st.warning("Nenhum registro encontrado para esta placa.")
        else:
            st.info("Aguardando inserção de placa para processar rota e mapa...")
    else:
        st.write("---")
        st.info("⬆️ Por favor, carregue os arquivos CSV no menu lateral para começar.")
