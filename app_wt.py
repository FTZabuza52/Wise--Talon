import streamlit as st
import pandas as pd
import re
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from datetime import datetime
import plotly.express as px
import io

# --- 1. CONFIGURAÇÃO DE INTERFACE E ESTILO (PADRÃO FT20) ---
st.set_page_config(page_title="FT20 - Wise Talon", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    /* Fundo Dark e Texto Claro */
    .stApp { background-color: #0b0d11; color: #e0e0e0; }
    
    /* Cards de Métrica com Borda Vermelha */
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        border-radius: 8px;
    }
    
    /* Títulos em Vermelho Tático */
    h1, h2, h3 { color: #ff4b4b !important; font-family: 'Courier New', Courier, monospace; }
    
    /* Ajuste de Tabelas e Sidebar */
    section[data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #30363d; }
    .stDataFrame { background-color: #161b22; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE INTELIGÊNCIA (PARSER SESP) ---
def extrair_dados_sesp(file):
    content = file.read().decode('utf-8', errors='ignore')
    blocks = re.split(r'"Placa\s+', content)
    records = []
    
    for block in blocks[1:]:
        data = {}
        # Extração de Placa
        placa_match = re.search(r'^([A-Z0-9-]{7,8})"', block)
        data['Placa'] = placa_match.group(1).strip() if placa_match else "N/I"
        
        # Extração de Data/Hora e Faixa Horária
        dt_match = re.search(r'Data/Hora\s+([0-9/:\s]+)"', block)
        if dt_match:
            try:
                dt_str = dt_match.group(1).strip()
                data['Data_Hora'] = datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                data['Hora'] = data['Data_Hora'].hour
            except:
                data['Data_Hora'], data['Hora'] = None, None
        
        # Extração de Coordenadas GPS
        coord_match = re.search(r'Coordenadas do local\s+([-0-9.]+)\s+&\s+([-0-9.]+)"', block)
        if coord_match:
            data['Lat'], data['Lon'] = float(coord_match.group(1)), float(coord_match.group(2))
        else:
            data['Lat'], data['Lon'] = None, None
            
        # Extração de Local e Cidade
        local_match = re.search(r'"([^"]+)"\s+"Local"', block)
        if local_match:
            local_full = local_match.group(1).strip()
            data['Local'] = local_full
            data['Cidade'] = local_full.split('-')[0].strip()
        else:
            data['Local'], data['Cidade'] = "Ponto não identificado", "N/I"
        
        records.append(data)
    
    return pd.DataFrame(records)

# --- 3. GERADOR DE NARRATIVA PARA RELATÓRIO ---
def gerar_relatorio_texto(df_alvo, placa):
    total = len(df_alvo)
    primeira = df_alvo['Data_Hora'].min()
    ultima = df_alvo['Data_Hora'].max()
    ponto_frequente = df_alvo['Local'].value_counts().index[0]
    freq_ponto = df_alvo['Local'].value_counts().values[0]
    
    m_count = len(df_alvo[(df_alvo['Hora'] >= 6) & (df_alvo['Hora'] < 12)])
    t_count = len(df_alvo[(df_alvo['Hora'] >= 12) & (df_alvo['Hora'] < 18)])
    n_count = len(df_alvo[(df_alvo['Hora'] >= 18) | (df_alvo['Hora'] < 6)])
    perfil = "MATUTINO" if m_count > t_count and m_count > n_count else "VESPERTINO" if t_count > n_count else "NOTURNO"

    txt = f"""=== RELATÓRIO DE INTELIGÊNCIA TÁTICA - FT20 ===
GERADO EM: {datetime.now().strftime('%d/%m/%Y %H:%M')}

ALVO ANALISADO: VEÍCULO PLACA {placa}
--------------------------------------------------

1. RESUMO DE PASSAGENS:
Total de registros detectados: {total}
Início do rastro: {primeira.strftime('%d/%m/%Y às %H:%M')}
Último rastro: {ultima.strftime('%d/%m/%Y às %H:%M')}

2. ANÁLISE DE MODUS OPERANDI (TEMPORAL):
O veículo apresenta um perfil de circulação predominantemente {perfil}.
- Manhã: {m_count} passagens
- Tarde: {t_count} passagens
- Noite/Madrugada: {n_count} passagens

3. ANÁLISE GEOESPACIAL:
Ponto de maior interesse: {ponto_frequente}
Frequência no ponto: {freq_ponto} passagens.

4. CONCLUSÃO PRELIMINAR:
A recorrência de passagens no sensor {ponto_frequente} indica possível zona de 
influência ou residência do condutor. Recomenda-se vigilância no período {perfil}.
--------------------------------------------------
WISE TALON - UNIDADE RAIO IMORTAL VERMELHO"""
    return txt

# --- 4. INTERFACE PRINCIPAL ---
st.title("🦅 FT20 - WISE TALON")
st.subheader("ANALISTA DE ROTAS E PADRÕES")

arquivos = st.file_uploader("📂 INGERIR RELATÓRIOS SESP (CSV)", type=["csv"], accept_multiple_files=True)

if arquivos:
    lista_dfs = [extrair_dados_sesp(arq) for arq in arquivos]
    df_total = pd.concat(lista_dfs).sort_values(by='Data_Hora', ascending=False).reset_index(drop=True)

    # Métricas Superiores
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("TOTAL PASSAGENS", len(df_total))
    m2.metric("ALVOS ÚNICOS", df_total['Placa'].nunique())
    m3.metric("COORDENADAS GPS", df_total['Lat'].notna().sum())
    m4.metric("CIDADES ATIVAS", df_total['Cidade'].nunique())

    st.divider()

    # Dashboard Principal: Gráfico e Mapa
    col_g, col_m = st.columns([1, 1.2])

    with col_g:
        st.subheader("📈 Padrão de Horários")
        df_hora = df_total['Hora'].value_counts().sort_index().reset_index()
        df_hora.columns = ['Hora', 'Frequência']
        fig = px.bar(df_hora, x='Hora', y='Frequência', color_discrete_sequence=['#ff4b4b'])
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col_m:
        st.subheader("🗺️ Mancha Térmica (Rotas)")
        df_mapa = df_total.dropna(subset=['Lat', 'Lon'])
        if not df_mapa.empty:
            centro = [df_mapa['Lat'].mean(), df_mapa['Lon'].mean()]
            mapa = folium.Map(location=centro, zoom_start=13, tiles="cartodbpositron")
            HeatMap([[r['Lat'], r['Lon']] for _, r in df_mapa.iterrows()], radius=15).add_to(mapa)
            st_folium(mapa, width="100%", height=350)

    # --- SEÇÃO DE INTELIGÊNCIA DE ALVO ---
    st.divider()
    st.subheader("🕵️‍♂️ INVESTIGAÇÃO DE ALVO ESPECÍFICO")
    
    placa_busca = st.text_input("INSIRA A PLACA PARA ANÁLISE DETALHADA", "").upper()
    
    if placa_busca:
        df_alvo = df_total[df_total['Placa'].str.contains(placa_busca)]
        
        if not df_alvo.empty:
            c_rel, c_map = st.columns([1, 1.2])
            
            with c_rel:
                rel_txt = gerar_relatorio_texto(df_alvo, placa_busca)
                st.text_area("RELATÓRIO CIRCUNSTANCIADO", rel_txt, height=350)
                st.download_button("📥 BAIXAR RELATÓRIO (.TXT)", rel_txt, file_name=f"Relatorio_{placa_busca}.txt")
            
            with c_map:
                st.write("**TRAJETÓRIA CRONOLÓGICA DO ALVO**")
                df_alvo_gps = df_alvo.dropna(subset=['Lat', 'Lon']).sort_values('Data_Hora')
                if not df_alvo_gps.empty:
                    m_alvo = folium.Map(location=[df_alvo_gps['Lat'].mean(), df_alvo_gps['Lon'].mean()], zoom_start=14)
                    pontos = [[r['Lat'], r['Lon']] for _, r in df_alvo_gps.iterrows()]
                    folium.PolyLine(pontos, color="red", weight=3, opacity=0.8).add_to(m_alvo)
                    for _, r in df_alvo_gps.tail(5).iterrows(): # Marcadores nos últimos 5 pontos
                        folium.Marker([r['Lat'], r['Lon']], popup=f"{r['Data_Hora']}").add_to(m_alvo)
                    st_folium(m_alvo, width="100%", height=350)
        else:
            st.error("PLACA NÃO ENCONTRADA NA BASE DE DADOS CARREGADA.")

    # Tabela Bruta
    st.divider()
    st.subheader("📋 LOG COMPLETO DE DADOS")
    st.dataframe(df_total[['Placa', 'Data_Hora', 'Cidade', 'Local']], use_container_width=True)

else:
    st.warning("AGUARDANDO CARREGAMENTO DE RELATÓRIO CSV PARA INICIAR ANÁLISE.")
    
