import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import unicodedata
import json
import os

st.set_page_config(layout="wide")

# ==============================
# CONFIG
# ==============================

LOGIN_URL = "https://pabx.evence.com.br/login"
MONITOR_URL = "https://pabx.evence.com.br/callcenter/monitoramentoAgentes/detalhes?agentes=46,47,49,50,52,53"

KANBAN_LOGIN_URL = "https://kanban.interativanet.com.br/?controller=AuthController&action=check"
KANBAN_URL = "https://kanban.interativanet.com.br/?controller=ProjectOverviewController&action=show&project_id=1&search=status%3Aopen"

EMAIL = st.secrets["EMAIL"]
SENHA = st.secrets["SENHA"]

KANBAN_USER = st.secrets["KANBAN_USER"]
KANBAN_PASS = st.secrets["KANBAN_PASS"]

RM_SHEET_URL = "https://docs.google.com/spreadsheets/d/1Gy-rZali0-GwjEMgcCY9TB4K0i-MXUnPN0LH6quj36Y/export?format=csv&gid=1341521358"

TAREFAS_FILE = "tarefas_pendentes.json"

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
    background: #1e293b;
    border-left: 5px solid #3b82f6;
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: white;
    font-size: 15px;
    min-height: 48px;
    box-sizing: border-box;
}

/* ESTILIZAÇÃO DOS BOTOES INTERNOS DO CARD */
.kanban-actions {
    display: flex;
    align-items: center;
    gap: 12px;
}

.btn-icon-action {
    background: transparent;
    border: none;
    color: white;
    font-size: 18px;
    cursor: pointer;
    padding: 0;
    margin: 0;
    line-height: 1;
    text-decoration: none;
    transition: transform 0.1s ease;
}

.btn-icon-action:hover {
    transform: scale(1.2);
}
</style>
""", unsafe_allow_html=True)

# ==============================
# SISTEMA DE ÁUDIO CORRIGIDO
# ==============================
def renderizar_botao_audio():
    audio_url = "https://notificationsounds.com/storage/sounds/file-sounds-1150-pristine.mp3"
    tocar_agora = "true" if st.session_state.get("play_alert", False) else "false"
    
    sound_html = f"""
    <div style="display: flex; justify-content: flex-end; align-items: center; height: 40px;">
        <button id="btn-ativar-som" onclick="testarEAtivarSom()" style="
            background:#2563eb;
            color:white;
            border:none;
            border-radius:8px;
            height:40px;
            font-weight:600;
            padding:0 18px;
            cursor:pointer;
        ">🔊 Ativar & Testar Som</button>
    </div>

    <audio id="notif-sound" src="{audio_url}" preload="auto"></audio>

    <script>
        var audio = document.getElementById('notif-sound');
        var deveTocarAutomatico = {tocar_agora};

        function testarEAtivarSom() {{
            if (audio) {{
                audio.volume = 1.0;
                audio.play()
                    .then(function() {{
                        alert("✅ Excelente! Som do painel ativado e autorizado com sucesso.");
                    }})
                    .catch(function(err) {{
                        alert("❌ Erro ao ativar o som. Verifique se o volume do computador está ligado.");
                    }});
            }}
        }}

        if (deveTocarAutomatico && audio) {{
            audio.volume = 1.0;
            audio.play().catch(function(e) {{
                console.log("Autoplay bloqueado pelo navegador.");
            }});
        }}
    </script>
    """
    st.components.v1.html(sound_html, height=50)

# ==============================
# PERSISTÊNCIA DAS TAREFAS
# ==============================
def carregar_tarefas_salvas():
    if os.path.exists(TAREFAS_FILE):
        try:
            with open(TAREFAS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_tarefas(tarefas):
    with open(TAREFAS_FILE, "w", encoding="utf-8") as f:
        json.dump(tarefas, f, indent=4, ensure_ascii=False)

# ==============================
# UTILS
# ==============================
def remover_acentos(txt):
    return ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    )

# ==============================
# LOGINS E SCRAPING
# ==============================
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

def login_kanban():
    session = requests.Session()
    try:
        r = session.get("https://kanban.interativanet.com.br/?controller=AuthController&action=login")
        soup = BeautifulSoup(r.text, "html.parser")
        csrf_token = soup.find("input", {"name": "csrf_token"})
        
        payload = {
            "username": KANBAN_USER,
            "password": KANBAN_PASS
        }

        if csrf_token:
            payload["csrf_token"] = csrf_token["value"]

        session.post(KANBAN_LOGIN_URL, data=payload)
        return session
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
        return "Configure o Secrets (WHATSFLUX_EMAIL / WHATSFLUX_SENHA)", {}

    try:
        payload = {"email": email_whats, "password": senha_whats}
        res_login = session.post(login_api_url, json=payload, timeout=10)
        
        if res_login.status_code not in [200, 201, 302]:
            return f"Falha Auth (HTTP {res_login.status_code})", {}

        dados_resposta = res_login.json()
        token = dados_resposta.get("token") or dados_resposta.get("access_token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})

        res_users = session.get(users_api_url, timeout=10)
        if res_users.status_code != 200:
            return f"Erro API Users ({res_users.status_code})", {}
            
        resposta_json = res_users.json()
        dados_usuarios = resposta_json.get("users", [])

        def normalizar(texto):
            if not texto: return ""
            return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

        for usuario in dados_usuarios:
            nome_usuario = usuario.get("name", "")
            is_online = usuario.get("online", False)
            nome_usuario_limpo = normalizar(nome_usuario)
            
            for tecnico in tecnicos_alvo:
                tecnico_limpo = normalizar(tecnico)
                if tecnico_limpo in nome_usuario_limpo and is_online:
                    status_tecnicos[tecnico] = "online"

        return "OK", status_tecnicos
    except Exception as e:
        return f"Erro de Conexão ({str(e)[:20]})", {}

def atualizar_kanban(session_kb):
    """
    Sincroniza com o Kanban sem duplicar tarefas e respeita as edições locais.
    """
    if not session_kb:
        return
    
    try:
        r = session_kb.get(KANBAN_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        atividades = soup.find_all("div", class_="activity-content")
        
        tarefas_atuais = st.session_state.tarefas_kanban.copy()
        houve_alteracao = False
        disparar_som = False

        for atividade in reversed(atividades):
            title_p = atividade.find("p", class_="activity-title")
            if not title_p:
                continue
                
            texto_acao = title_p.get_text(" ", strip=True)
            link_task = title_p.find("a")
            date_span = title_p.find("small", class_="activity-date")
            
            if not link_task or not date_span:
                continue
                
            task_id = link_task.get_text(strip=True)
            data_atividade = date_span.get_text(strip=True)
            
            desc_div = atividade.find("div", class_="activity-description")
            titulo_tarefa = desc_div.find("p", class_="activity-task-title").get_text(strip=True) if desc_div else "Sem título"

            if "criou a tarefa" in texto_acao:
                if task_id not in tarefas_atuais:
                    tarefas_atuais[task_id] = {
                        "titulo": titulo_tarefa,
                        "data_criacao": data_atividade,
                        "status": "Pendente"
                    }
                    houve_alteracao = True
                    disparar_som = True

            elif "finalizou a tarefa" in texto_acao:
                if task_id in tarefas_atuais:
                    del tarefas_atuais[task_id]
                    houve_alteracao = True

        if houve_alteracao:
            st.session_state.tarefas_kanban = tarefas_atuais
            salvar_tarefas(tarefas_atuais)
            if disparar_som:
                st.session_state.play_alert = True

    except Exception as e:
        st.sidebar.error(f"Erro ao ler Kanban: {e}")

# ==============================
# LEITURA DA FILA PENDENTE - RM
# ==============================
def atualizar_fila_rm():
    """
    Lê a planilha do RM e retorna somente as linhas
    cuja coluna AA (concluido) esteja vazia.

    A primeira linha é o cabeçalho.
    A leitura dos dados começa na linha 2.
    """

    try:
        resposta = requests.get(
            RM_SHEET_URL,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        resposta.raise_for_status()

        # Lê o CSV retornado pelo Google Sheets
        df_rm = pd.read_csv(
            pd.io.common.StringIO(resposta.text),
            dtype=str,
            keep_default_na=False
        )

        # Verifica se a planilha possui pelo menos 27 colunas
        # AA = 27ª coluna
        if len(df_rm.columns) < 27:
            return [], "A planilha do RM não possui a coluna AA."

        # Coluna AA pelo índice:
        # A=0 ... Z=25, AA=26
        coluna_concluido = df_rm.columns[26]

        pendencias = []

        for indice, linha in df_rm.iterrows():

            valor_concluido = str(
                linha.iloc[26]
            ).strip()

            # Só entra na fila quando "concluido" estiver vazio
            if valor_concluido == "":
                dados_linha = {}

                for numero_coluna, nome_coluna in enumerate(df_rm.columns):
                    dados_linha[nome_coluna] = str(
                        linha.iloc[numero_coluna]
                    ).strip()

                dados_linha["_linha_planilha"] = indice + 2

                pendencias.append(dados_linha)

        return pendencias, None

    except Exception as e:
        return [], f"Erro ao consultar planilha RM: {str(e)[:150]}"


# ==============================
# INICIALIZAÇÃO DE VARIÁVEIS DE ESTADO
# ==============================
if "historico" not in st.session_state:
    st.session_state.historico = []

if "tarefas_kanban" not in st.session_state:
    st.session_state.tarefas_kanban = carregar_tarefas_salvas()

if "play_alert" not in st.session_state:
    st.session_state.play_alert = False

if "fila_rm" not in st.session_state:
    st.session_state.fila_rm = []

 if "erro_rm" not in st.session_state:
    st.session_state.erro_rm = None


if "editando_id" not in st.session_state:
    st.session_state.editando_id = None

if "session" not in st.session_state or not st.session_state.session:
    st.session_state.session = login()

if "session_kanban" not in st.session_state or not st.session_state.session_kanban:
    st.session_state.session_kanban = login_kanban()

# ==============================
# TRATAMENTO DE AÇÕES (EDITAR E EXCLUIR NO TOPO)
# ==============================
params = st.query_params

if "editar_tarefa" in params:
    st.session_state.editando_id = params["editar_tarefa"]
    st.query_params.clear()
    st.rerun()

if "deletar_tarefa" in params:
    task_id_to_del = params["deletar_tarefa"]
    tarefas_atuais = st.session_state.get("tarefas_kanban", {})
    if task_id_to_del in tarefas_atuais:
        del tarefas_atuais[task_id_to_del]
        salvar_tarefas(tarefas_atuais)
        st.session_state.tarefas_kanban = tarefas_atuais
    st.query_params.clear()
    st.rerun()

session = st.session_state.session
session_kb = st.session_state.session_kanban

if not session:
    st.error("Erro no login do PABX")
    st.stop()

# Coleta de dados antes da renderização
agentes = get_agentes(session)
atualizar_kanban(session_kb)

# Atualiza a fila pendente do RM
fila_rm, erro_rm = atualizar_fila_rm()

st.session_state.fila_rm = fila_rm
st.session_state.erro_rm = erro_rm

# ==============================
# RENDERIZAÇÃO DA PÁGINA
# ==============================
st.markdown('<div class="title">📡 Gestor de ServiceDesk - Intercom</div>', unsafe_allow_html=True)

# Métricas
livres = sum(1 for _, s in agentes if s == "livre")
ocupados = sum(1 for _, s in agentes if s == "ocupado")
pausa = sum(1 for _, s in agentes if s == "pausa")
agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))

st.session_state.historico.append({
    "time": agora_br,
    "livres": int(livres),
    "ocupados": int(ocupados),
    "pausa": int(pausa)
})

# 1. CARDS DO TOPO
col1, col2, col3 = st.columns(3)
col1.markdown(f'<div class="small-card green">🟢 {livres}<br>Livres</div>', unsafe_allow_html=True)
col2.markdown(f'<div class="small-card red">🔴 {ocupados}<br>Ocupados</div>', unsafe_allow_html=True)
col3.markdown(f'<div class="small-card yellow">🟡 {pausa}<br>Pausa</div>', unsafe_allow_html=True)

st.write("") 

# 2. GRÁFICO
df_hist = pd.DataFrame(st.session_state.historico)
if not df_hist.empty:
    df_hist["time"] = pd.to_datetime(df_hist["time"], errors="coerce")
    df_hist = df_hist.dropna(subset=["time"]).sort_values("time")
    
    for col in ["livres", "ocupados", "pausa"]:
        if col not in df_hist.columns: df_hist[col] = 0
        
    df_hist[["livres", "ocupados", "pausa"]] = df_hist[["livres", "ocupados", "pausa"]].fillna(0).astype(int)

    series = ["livres", "ocupados"]
    if df_hist["pausa"].sum() > 0:
        series.append("pausa")

    df_plot = df_hist.copy()
    for col in ["livres", "ocupados"]:
        df_plot[col] = df_plot[col].replace(0, None)

    df_melt = df_plot.melt(id_vars=["time"], value_vars=series, var_name="Status", value_name="Quantidade")
    
    # GRÁFICO COM CORES DE STATUS
grafico = df_hist.set_index("time")[["livres", "ocupados", "pausa"]]

grafico_melt = grafico.reset_index().melt(
    id_vars=["time"],
    var_name="Status",
    value_name="Quantidade"
)

cores_status = {
    "livres": "#16a34a",     # Verde
    "ocupados": "#dc2626",   # Vermelho
    "pausa": "#eab308"       # Amarelo
}

chart = {
    "data": grafico_melt,
    "mark": "line",
    "encoding": {
        "x": {
            "field": "time",
            "type": "temporal",
            "title": "Horário"
        },
        "y": {
            "field": "Quantidade",
            "type": "quantitative",
            "title": "Quantidade"
        },
        "color": {
            "field": "Status",
            "type": "nominal",
            "scale": {
                "domain": ["livres", "ocupados", "pausa"],
                "range": [
                    "#16a34a",
                    "#dc2626",
                    "#eab308"
                ]
            },
            "legend": {
                "title": "Status"
            }
        }
    }
}

st.vega_lite_chart(
    grafico_melt,
    chart,
    use_container_width=True
)

# 3. WHATSFLUX
st.write("---")
msg_retorno, status_whats = login_e_get_status_whatsflux()
st.subheader("👥 Status do Suporte Técnico (WhatsFlux)")

if "OK" in msg_retorno:
    colunas_tecnicos = st.columns(len(status_whats))
    for col, (tecnico, status) in zip(colunas_tecnicos, status_whats.items()):
        with col:
            badge = '<span style="color: #4ade80; font-weight: bold;">🟢 ONLINE</span>' if status == "online" else '<span style="color: #f87171; font-weight: bold;">🔴 OFFLINE</span>'
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 12px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
                <div style="font-weight: bold; margin-bottom: 8px; font-size: 15px; color: #f8fafc;">{tecnico}</div>
                <div>{badge}</div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.error(f"Erro WhatsFlux: {msg_retorno}")

# ============================================================
# 4. FILAS DE PENDÊNCIAS
# ============================================================
st.write("---")

# Divide a tela em duas partes iguais
col_kanban, col_rm = st.columns(2, gap="medium")


# ============================================================
# COLUNA 1 - KANBAN
# ============================================================
with col_kanban:

    col_titulo, col_audio = st.columns([3, 1])

    with col_titulo:
        st.subheader("🔔 Fila de tarefa pendente - Kanban")

    with col_audio:
        renderizar_botao_audio()

    if st.session_state.get("play_alert", False):
        st.session_state.play_alert = False

    tarefas_exibidas = st.session_state.get(
        "tarefas_kanban",
        {}
    )

    if tarefas_exibidas:

        for t_id, info in list(tarefas_exibidas.items()):

            if st.session_state.editando_id == t_id:

                # =================================================
                # MODO DE EDIÇÃO DA TAREFA
                # =================================================
                col_input, col_salvar, col_canc = st.columns(
                    [0.76, 0.12, 0.12]
                )

                with col_input:
                    novo_titulo = st.text_input(
                        f"Editar Tarefa #{t_id}",
                        value=info["titulo"],
                        key=f"input_inline_{t_id}",
                        label_visibility="collapsed"
                    )

                with col_salvar:
                    if st.button(
                        "💾 Salvar",
                        key=f"btn_salvar_in_{t_id}",
                        type="primary",
                        use_container_width=True
                    ):
                        st.session_state.tarefas_kanban[t_id]["titulo"] = novo_titulo
                        salvar_tarefas(
                            st.session_state.tarefas_kanban
                        )
                        st.session_state.editando_id = None
                        st.rerun()

                with col_canc:
                    if st.button(
                        "❌ Cancelar",
                        key=f"btn_canc_in_{t_id}",
                        use_container_width=True
                    ):
                        st.session_state.editando_id = None
                        st.rerun()

            else:

                # =================================================
                # MODO DE VISUALIZAÇÃO
                # =================================================
                col_card, col_edit, col_del = st.columns(
                    [0.90, 0.05, 0.05]
                )

                with col_card:
                    st.markdown(
                        f"""
                        <div class="kanban-box">
                            <div style="
                                display:flex;
                                align-items:center;
                                overflow:hidden;
                                white-space:nowrap;
                                text-overflow:ellipsis;
                            ">
                                <span style="
                                    color:#fbbf24;
                                    font-size:18px;
                                    margin-right:8px;
                                ">
                                    ⚠️
                                </span>

                                <span>
                                    <strong>Tarefa #{t_id}</strong>
                                    &nbsp;Criada {info['data_criacao']}
                                    &nbsp;|&nbsp;

                                    <strong>Assunto:</strong>
                                    {info['titulo']}
                                    &nbsp;|&nbsp;

                                    <span style="
                                        color:#f59e0b;
                                        font-weight:bold;
                                    ">
                                        Status: {info['status']}
                                    </span>
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col_edit:

                    if st.button(
                        "✏️",
                        key=f"btn_edt_{t_id}",
                        help="Editar Tarefa",
                        use_container_width=True
                    ):
                        st.session_state.editando_id = t_id
                        st.rerun()

                with col_del:

                    if st.button(
                        "🗑️",
                        key=f"btn_del_{t_id}",
                        help="Excluir Tarefa",
                        use_container_width=True
                    ):
                        del st.session_state.tarefas_kanban[t_id]

                        salvar_tarefas(
                            st.session_state.tarefas_kanban
                        )

                        st.rerun()

                st.markdown(
                    '<div style="margin-bottom:4px;"></div>',
                    unsafe_allow_html=True
                )

    else:
        st.info(
            "Nenhuma tarefa pendente registrada no painel."
        )


# ============================================================
# COLUNA 2 - RM
# ============================================================
with col_rm:

    st.subheader("📋 Fila pendente - RM")

    erro_rm = st.session_state.get("erro_rm")

    if erro_rm:

        st.error(erro_rm)

    else:

        pendencias_rm = st.session_state.get(
            "fila_rm",
            []
        )

        if pendencias_rm:

            st.markdown(
                f"""
                <div style="
                    background:#1e293b;
                    border-radius:8px;
                    padding:10px 15px;
                    margin-bottom:12px;
                    border-left:5px solid #f59e0b;
                ">
                    <strong>
                        ⚠️ {len(pendencias_rm)} pendência(s) aguardando conclusão
                    </strong>
                </div>
                """,
                unsafe_allow_html=True
            )

            for numero, pendencia in enumerate(
                pendencias_rm,
                start=1
            ):

                linha_planilha = pendencia.get(
                    "_linha_planilha",
                    "-"
                )

                # =================================================
                # TENTA ENCONTRAR UM TÍTULO/DESCRIÇÃO ÚTIL
                # =================================================
                titulo_rm = ""

                nomes_prioritarios = [
                    "pendencia",
                    "concluido",
                    
                ]

                for nome_coluna in nomes_prioritarios:

                    for coluna_real in pendencia.keys():

                        if coluna_real.startswith("_"):
                            continue

                        if remover_acentos(
                            str(coluna_real).lower()
                        ) == remover_acentos(
                            nome_coluna.lower()
                        ):

                            valor = str(
                                pendencia.get(
                                    coluna_real,
                                    ""
                                )
                            ).strip()

                            if valor:
                                titulo_rm = valor
                                break

                    if titulo_rm:
                        break

                # Caso não encontre coluna de descrição,
                # usa a primeira informação preenchida.
                if not titulo_rm:

                    for coluna_real, valor in pendencia.items():

                        if coluna_real.startswith("_"):
                            continue

                        valor = str(valor).strip()

                        if valor:
                            titulo_rm = valor
                            break

                if not titulo_rm:
                    titulo_rm = (
                        f"Pendência da linha {linha_planilha}"
                    )

                # =================================================
                # CARD DA PENDÊNCIA RM
                # =================================================
                st.markdown(
                    f"""
                    <div style="
                        background:#1e293b;
                        border-left:5px solid #f59e0b;
                        border-radius:8px;
                        padding:12px 16px;
                        margin-bottom:8px;
                        color:white;
                        min-height:48px;
                        box-sizing:border-box;
                    ">

                        <div style="
                            display:flex;
                            align-items:center;
                            gap:8px;
                        ">

                            <span style="
                                color:#fbbf24;
                                font-size:18px;
                            ">
                                ⚠️
                            </span>

                            <div style="
                                overflow:hidden;
                                width:100%;
                            ">

                                <div style="
                                    font-weight:bold;
                                    color:#f8fafc;
                                    margin-bottom:4px;
                                ">
                                    Pendência RM #{numero}
                                </div>

                                <div style="
                                    color:#cbd5e1;
                                    font-size:14px;
                                    overflow:hidden;
                                    text-overflow:ellipsis;
                                ">
                                    {titulo_rm}
                                </div>

                                <div style="
                                    color:#94a3b8;
                                    font-size:12px;
                                    margin-top:5px;
                                ">
                                    Linha da planilha: {linha_planilha}
                                </div>

                            </div>

                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

        else:

            st.success(
                "✅ Nenhuma pendência RM aguardando conclusão."
            )


# 5. AGENTES DE PLANTÃO
st.write("---")
st.subheader("👨‍💻 Agentes de Plantão")
df_agentes = pd.DataFrame(agentes, columns=["Nome", "Status"])
st.dataframe(df_agentes, use_container_width=True)

# ==============================
# AUTO ATUALIZAR
# ==============================
time.sleep(refresh_rate)
st.rerun()
