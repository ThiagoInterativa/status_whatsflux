import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import unicodedata
import altair as alt  
import json
import os

# ==============================
# CONFIG
# ==============================
st.set_page_config(layout="wide", page_title="NOC Call Center")

LOGIN_URL = "https://pabx.evence.com.br/login"
MONITOR_URL = "https://pabx.evence.com.br/callcenter/monitoramentoAgentes/detalhes?agentes=46,47,49,50,52,53"

EMAIL = st.secrets["EMAIL"]
SENHA = st.secrets["SENHA"]


# ==============================
# CONTROLE DE ATUALIZAÇÃO (BARRA LATERAL)
# ==============================
st.sidebar.header("⚙️ Configurações")
refresh_rate = st.sidebar.slider(
    "Tempo de atualização (segundos)", 
    min_value=10, 
    max_value=300, 
    value=30, 
    step=5
)

# ==============================
# CSS NOC (VISUAL PROFISSIONAL)
# ==============================
st.markdown("""
<style>
body {
    background-color: #0e1117;
    color: white;
}

/* CARD  */
.small-card {
    padding: 26px;
    border-radius: 8px;
    text-align: center;
    font-size: 20px;
    font-weight: bold;
    line-height: 1.2;
}

.green { background-color: #16a34a; }
.red { background-color: #dc2626; }
.yellow { background-color: #eab308; }

.title {
    text-align: center;
    font-size: 32px;
    font-weight: bold;
    margin-bottom: 20px;
}

/* CONTAINER DE TAREFA ESTILIZADO */
.kanban-box {
    background-color: #1e293b;
    border-left: 5px solid #2563eb;
    padding: 12px 18px;
    border-radius: 6px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# ==============================
# FUNÇÕES AUXILIARES E SCRAPING
# ==============================
def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def login():
    session = requests.Session()
    try:
        r = session.get(LOGIN_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        token = soup.find("input", {"name": "_token"})["value"]

        payload = {
            "login": EMAIL,
            "senha": SENHA,
            "_token": token
        }
        res = session.post(LOGIN_URL, data=payload)
        return session if res.url != LOGIN_URL else None
    except Exception:
        return None

def get_agentes(session):
    try:
        r = session.get(MONITOR_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        tabela = soup.find("table")
        agentes = []

        if not tabela:
            return []

        for linha in tabela.find_all("tr"):
            cols = linha.find_all("td")
            if len(cols) >= 3:
                nome = cols[0].get_text(" ", strip=True).split("Última chamada")[0].strip()
                status_txt = remover_acentos(cols[2].get_text(strip=True).lower())

                if "pausa" in status_txt:
                    status = "pausa"
                elif "ocupado" in status_txt or "falando" in status_txt:
                    status = "ocupado"
                elif "livre" in status_txt:
                    status = "livre"
                elif "indisponivel" in status_txt:
                    status = "offline"
                else:
                    status = "offline"

                if nome:
                    agentes.append((nome, status))
        return agentes
    except Exception:
        return []
def login_e_get_status_whatsflux():
    login_api_url = "https://api.whatsflux.com.br/auth/login"
    users_api_url = "https://api.whatsflux.com.br/users"
    
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": "https://app.whatsflux.com.br/login",
        "Origin": "https://app.whatsflux.com.br"
    }
    session.headers.update(headers)
    
    tecnicos_alvo = ["Leonardo", "Matheus", "Gabriel", "Ramon", "Thiago", "Vinicius"]
    status_tecnicos = {nome: "offline" for nome in tecnicos_alvo}
    
    try:
        email_whats = st.secrets["WHATSFLUX_EMAIL"]
        senha_whats = st.secrets["WHATSFLUX_SENHA"]
    except KeyError:
        return "Configure o Secrets (WHATSFLUX_EMAIL / WHATSFLUX_SENHA)", {}, []

    try:
        payload = {
            "email": email_whats,
            "password": senha_whats
        }
        res_login = session.post(login_api_url, json=payload, timeout=10)
        
        if res_login.status_code not in [200, 201, 302]:
            return f"Falha Auth (HTTP {res_login.status_code})", {}, []

        try:
            dados_resposta = res_login.json()
            token = dados_resposta.get("token") or dados_resposta.get("access_token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        except Exception:
            pass

        # Busca a lista de usuários autenticada
        res_users = session.get(users_api_url, timeout=10)
        if res_users.status_code != 200:
            return f"Erro API Users ({res_users.status_code})", {}, []
            
        resposta_json = res_users.json()
        
        # Como o JSON vem envelopado em {"users": [...]}, extraímos a lista de usuários
        dados_usuarios = resposta_json.get("users", [])
        
        if not isinstance(dados_usuarios, list):
            dados_usuarios = [dados_usuarios]

        nomes_encontrados_na_api = []

        def normalizar(texto):
            if not texto: return ""
            texto_normalizado = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
            return texto_normalizado.lower().strip()

        # Varre a lista de usuários retornada pelo WhatsFlux
        for usuario in dados_usuarios:
            nome_usuario = usuario.get("name", "")
            is_online = usuario.get("online", False) # Retorna True ou False
            
            status_txt = "ONLINE" if is_online else "OFFLINE"
            nomes_encontrados_na_api.append(f"{nome_usuario} (Status: {status_txt})")
            
            nome_usuario_limpo = normalizar(nome_usuario)
            
            # Compara com a nossa lista de técnicos alvo
            for tecnico in tecnicos_alvo:
                tecnico_limpo = normalizar(tecnico)
                
                if tecnico_limpo in nome_usuario_limpo:
                    if is_online:
                        status_tecnicos[tecnico] = "online"

        return "OK", status_tecnicos, nomes_encontrados_na_api

    except Exception as e:
        return f"Erro de Conexão ({str(e)[:20]})", {}, []
        
        def normalizar(texto):
            if not texto: return ""
            texto_normalizado = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
            return texto_normalizado.lower().strip()

        for conexao in dados_conexoes:
            nome_conexao = conexao.get("name", "")
            status_conexao = str(conexao.get("status", "")).upper()
            
            nomes_encontrados_na_api.append(f"{nome_conexao} (Status: {status_conexao})")
            
            nome_conexao_limpo = normalizar(nome_conexao)
            
            for tecnico in tecnicos_alvo:
                tecnico_limpo = normalizar(tecnico)
                
                if tecnico_limpo in nome_conexao_limpo:
                    if status_conexao in ["CONNECTED", "ONLINE", "ATIVO"]:
                        status_tecnicos[tecnico] = "online"

        return "OK", status_tecnicos, nomes_encontrados_na_api

    except Exception as e:
        return f"Erro de Conexão ({str(e)[:20]})", {}, []

# ==============================
# TESTE TEMPORÁRIO CORRIGIDO DE ROTAS
# ==============================
if st.sidebar.checkbox("🔍 Executar Teste de Rotas (Autenticado)"):
    st.write("### 🛠️ Diagnóstico de Endpoints WhatsFlux")
    
    login_api_url = "https://api.whatsflux.com.br/auth/login"
    rotas_para_testar = [
        "https://api.whatsflux.com.br/users",
        "https://api.whatsflux.com.br/users/"
    ]
    
    try:
        email_whats = st.secrets["WHATSFLUX_EMAIL"]
        senha_whats = st.secrets["WHATSFLUX_SENHA"]
        
        # 1. Cria uma nova sessão limpa para o WhatsFlux
        s_whats = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": "https://app.whatsflux.com.br/login",
            "Origin": "https://app.whatsflux.com.br"
        }
        s_whats.headers.update(headers)
        
        # 2. Faz o login para pegar o Token
        payload = {"email": email_whats, "password": senha_whats}
        res_login = s_whats.post(login_api_url, json=payload, timeout=10)
        
        if res_login.status_code in [200, 201]:
            dados_resposta = res_login.json()
            token = dados_resposta.get("token") or dados_resposta.get("access_token")
            
            if token:
                # 3. Aplica o Token Bearer estritamente necessário para sair do 401
                s_whats.headers.update({"Authorization": f"Bearer {token}"})
                st.success("🔑 Autenticação no WhatsFlux realizada com sucesso!")
                
                # 4. Testa os endpoints agora autenticado
                for url in rotas_para_testar:
                    res = s_whats.get(url, timeout=5)
                    st.write(f"**Rota:** `{url}` | **Status:** `{res.status_code}`")
                    if res.status_code == 200:
                        st.json(res.json()[:3] if isinstance(res.json(), list) else res.json())
            else:
                st.error("Token não encontrado na resposta de login.")
        else:
            st.error(f"Falha no login de teste. Status: {res_login.status_code}")
            
    except Exception as e:
        st.error(f"Erro no teste: {e}")


# ==============================
# INICIALIZAÇÃO DE VARIÁVEIS DO ESTADO
# ==============================
st.markdown('<div class="title">📡 Gestor de Call Center - Intercom</div>', unsafe_allow_html=True)

if "historico" not in st.session_state:
    st.session_state.historico = []

if "play_alert" not in st.session_state:
    st.session_state.play_alert = False

# Logins automáticos/Persistidos
if "session" not in st.session_state or not st.session_state.session:
    st.session_state.session = login()

session = st.session_state.session

if not session:
    st.error("Erro no login do PABX")
    st.stop()

# Busca e atualiza as APIs
agentes = get_agentes(session)

# Contagem
livres = sum(1 for _, s in agentes if s == "livre")
ocupados = sum(1 for _, s in agentes if s == "ocupado")
pausa = sum(1 for _, s in agentes if s == "pausa")

agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))

# Salva histórico de NOC
registro = {
    "time": agora_br,
    "livres": int(livres),
    "ocupados": int(ocupados),
    "pausa": int(pausa)
}
st.session_state.historico.append(registro)

# ==============================
# 1. CARDS REDUZIDOS (TOPO)
# ==============================
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f'<div class="small-card green">🟢 {livres}<br>Livres</div>', unsafe_allow_html=True)

with col2:
    st.markdown(f'<div class="small-card red">🔴 {ocupados}<br>Ocupados</div>', unsafe_allow_html=True)

with col3:
    st.markdown(f'<div class="small-card yellow">🟡 {pausa}<br>Pausa</div>', unsafe_allow_html=True)

st.write("")  # Espaçador

# ==============================
# 2. GRÁFICO (CENTRO)
# ==============================
df_hist = pd.DataFrame(st.session_state.historico)

if not df_hist.empty:
    df_hist["time"] = pd.to_datetime(df_hist["time"], errors="coerce")
    df_hist = df_hist.dropna(subset=["time"]).sort_values("time")
    
    for col in ["livres", "ocupados", "pausa"]:
        if col not in df_hist.columns:
            df_hist[col] = 0
            
    df_hist[["livres", "ocupados", "pausa"]] = df_hist[["livres", "ocupados", "pausa"]].fillna(0).astype(int)

    series = ["livres", "ocupados"]
    if df_hist["pausa"].sum() > 0:
        series.append("pausa")

    df_plot = df_hist.copy()
    for col in ["livres", "ocupados"]:
        df_plot[col] = df_plot[col].replace(0, None)

    df_melt = df_plot.melt(id_vars=["time"], value_vars=series, var_name="Status", value_name="Quantidade")
    
    color_map = {"livres": "#22c55e", "ocupados": "#ef4444", "pausa": "#eab308"}
    color_scale = alt.Scale(domain=list(color_map.keys()), range=list(color_map.values()))

    chart = alt.Chart(df_melt).mark_line(point=True).encode(
        x=alt.X("time:T", axis=alt.Axis(format="%H:%M"), title="Horário (Brasil)"),
        y=alt.Y("Quantidade:Q", scale=alt.Scale(domain=[0, 9]), axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("Status:N", scale=color_scale),
        tooltip=["time:T", "Status", "Quantidade"]
    ).properties(height=320)

    st.altair_chart(chart, use_container_width=True)


# ==============================
# 3. 🟢 INTEGRAÇÃO WHATSFLUX (TECNICOS LOGADOS)
# ==============================
st.write("---")
msg_retorno, status_whats, lista_debug = login_e_get_status_whatsflux()

st.subheader("👥 Status do Suporte Técnico (WhatsFlux)")

if "OK" in msg_retorno:
    colunas_tecnicos = st.columns(len(status_whats))
    
    for col, (tecnico, status) in zip(colunas_tecnicos, status_whats.items()):
        with col:
            if status == "online":
                badge = '<span style="color: #4ade80; font-weight: bold;">🟢 ONLINE</span>'
            else:
                badge = '<span style="color: #f87171; font-weight: bold;">🔴 OFFLINE</span>'
                
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 12px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
                <div style="font-weight: bold; margin-bottom: 8px; font-size: 15px; color: #f8fafc;">{tecnico}</div>
                <div>{badge}</div>
            </div>
            """, unsafe_allow_html=True)
            
    # Painel de Depuração oculto por padrão
    with st.expander("🔍 Ver conexões detectadas na API (Diagnóstico)"):
        st.write("A API do WhatsFlux retornou as seguintes conexões:")
        for item in lista_debug:
            st.code(item)
else:
    st.error(f"Erro ao buscar status do WhatsFlux: {msg_retorno}")


# ==============================
# 4. TABELA DE AGENTES
# ==============================
st.write("---")
st.subheader("👨‍💻 Agentes de Plantão")

df_agentes = pd.DataFrame(agentes, columns=["Nome", "Status"])
st.dataframe(df_agentes, use_container_width=True)


# ==============================
# AUTO ATUALIZAR CONFIGURÁVEL
# ==============================
placeholder = st.empty()

# Espera o tempo configurado antes de recarregar a tela
time.sleep(refresh_rate)
st.rerun()
