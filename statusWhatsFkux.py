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
import hashlib
import html

st.set_page_config(layout="wide")


# ============================================================
# CONFIG
# ============================================================

LOGIN_URL = "https://pabx.evence.com.br/login"

MONITOR_URL = (
    "https://pabx.evence.com.br/"
    "callcenter/monitoramentoAgentes/"
    "detalhes?agentes=46,47,49,50,52,53"
)

KANBAN_LOGIN_URL = (
    "https://kanban.interativanet.com.br/"
    "?controller=AuthController&action=check"
)

KANBAN_URL = (
    "https://kanban.interativanet.com.br/"
    "?controller=ProjectOverviewController"
    "&action=show"
    "&project_id=1"
    "&search=status%3Aopen"
)

EMAIL = st.secrets["EMAIL"]
SENHA = st.secrets["SENHA"]

KANBAN_USER = st.secrets["KANBAN_USER"]
KANBAN_PASS = st.secrets["KANBAN_PASS"]

RM_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1Gy-rZali0-GwjEMgcCY9TB4K0i-MXUnPN0LH6quj36Y/"
    "export?format=csv&gid=1341521358"
)

# Arquivo antigo do Kanban
TAREFAS_FILE = "tarefas_pendentes.json"

# NOVO arquivo para controlar exclusões da fila RM
RM_EXCLUIDAS_FILE = "rm_pendencias_excluidas.json"


# ============================================================
# CONTROLE DE ATUALIZAÇÃO
# ============================================================

st.sidebar.header("⚙️ Configurações")

refresh_rate = st.sidebar.slider(
    "Tempo de atualização (segundos)",
    min_value=10,
    max_value=300,
    value=30,
    step=5
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    body {
        background-color: #0e1117;
        color: white;
    }

    .small-card {
        padding: 26px;
        border-radius: 8px;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
        line-height: 1.2;
    }

    .green {
        background-color: #16a34a;
    }

    .red {
        background-color: #dc2626;
    }

    .yellow {
        background-color: #eab308;
    }

    .title {
        text-align: center;
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 20px;
    }

    .kanban-box {
        background: #1e293b;
        border-left: 5px solid #3b82f6;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
        color: white;
        font-size: 15px;
        min-height: 48px;
        box-sizing: border-box;
    }

    .rm-box {
        background: #1e293b;
        border-left: 5px solid #f59e0b;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
        color: white;
        font-size: 15px;
        min-height: 48px;
        box-sizing: border-box;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# ÁUDIO
# ============================================================

def renderizar_botao_audio():

    audio_url = (
        "https://notificationsounds.com/storage/"
        "sounds/file-sounds-1150-pristine.mp3"
    )

    tocar_agora = (
        "true"
        if st.session_state.get("play_alert", False)
        else "false"
    )

    sound_html = f"""
    <div style="
        display:flex;
        justify-content:flex-end;
        align-items:center;
        height:40px;
    ">

        <button
            id="btn-ativar-som"
            onclick="testarEAtivarSom()"
            style="
                background:#2563eb;
                color:white;
                border:none;
                border-radius:8px;
                height:40px;
                font-weight:600;
                padding:0 18px;
                cursor:pointer;
            "
        >
            🔊 Ativar & Testar Som
        </button>

    </div>

    <audio
        id="notif-sound"
        src="{audio_url}"
        preload="auto"
    ></audio>

    <script>

        var audio = document.getElementById("notif-sound");

        var deveTocarAutomatico = {tocar_agora};

        function testarEAtivarSom() {{

            if (audio) {{

                audio.volume = 1.0;

                audio.play()
                    .then(function() {{

                        alert(
                            "✅ Excelente! Som do painel ativado."
                        );

                    }})
                    .catch(function(err) {{

                        alert(
                            "❌ Erro ao ativar o som. "
                            + "Verifique o volume do computador."
                        );

                    }});
            }}
        }}

        if (deveTocarAutomatico && audio) {{

            audio.volume = 1.0;

            audio.play().catch(function(e) {{

                console.log(
                    "Autoplay bloqueado pelo navegador."
                );

            }});
        }}

    </script>
    """

    st.components.v1.html(
        sound_html,
        height=50
    )


# ============================================================
# PERSISTÊNCIA KANBAN
# ============================================================

def carregar_tarefas_salvas():

    if not os.path.exists(TAREFAS_FILE):
        return {}

    try:

        with open(
            TAREFAS_FILE,
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(arquivo)

            if isinstance(dados, dict):
                return dados

    except Exception:
        pass

    return {}


def salvar_tarefas(tarefas):

    with open(
        TAREFAS_FILE,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            tarefas,
            arquivo,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# PERSISTÊNCIA DAS EXCLUSÕES RM
# ============================================================

def carregar_rm_excluidas():

    if not os.path.exists(RM_EXCLUIDAS_FILE):
        return {}

    try:

        with open(
            RM_EXCLUIDAS_FILE,
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(arquivo)

            if isinstance(dados, dict):
                return dados

    except Exception:
        pass

    return {}


def salvar_rm_excluidas(dados):

    with open(
        RM_EXCLUIDAS_FILE,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            dados,
            arquivo,
            indent=4,
            ensure_ascii=False
        )


def gerar_fingerprint_rm(dados_linha):

    """
    Cria uma identificação única para a pendência.

    Se o conteúdo da linha da planilha mudar,
    o fingerprint muda e a pendência volta a aparecer.
    """

    dados = {}

    for chave, valor in dados_linha.items():

        if str(chave).startswith("_"):
            continue

        dados[str(chave)] = str(valor).strip()

    texto = json.dumps(
        dados,
        sort_keys=True,
        ensure_ascii=False
    )

    return hashlib.md5(
        texto.encode("utf-8")
    ).hexdigest()


# ============================================================
# UTILS
# ============================================================

def remover_acentos(txt):

    return "".join(
        c
        for c in unicodedata.normalize("NFD", str(txt))
        if unicodedata.category(c) != "Mn"
    )


# ============================================================
# LOGIN PABX
# ============================================================

def login():

    session = requests.Session()

    try:

        r = session.get(
            LOGIN_URL,
            timeout=20
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        token_input = soup.find(
            "input",
            {"name": "_token"}
        )

        if not token_input:
            return None

        token = token_input.get("value")

        payload = {
            "login": EMAIL,
            "senha": SENHA,
            "_token": token
        }

        res = session.post(
            LOGIN_URL,
            data=payload,
            timeout=20
        )

        if res.url != LOGIN_URL:
            return session

    except Exception:
        pass

    return None


# ============================================================
# LOGIN KANBAN
# ============================================================

def login_kanban():

    session = requests.Session()

    try:

        r = session.get(
            "https://kanban.interativanet.com.br/"
            "?controller=AuthController&action=login",
            timeout=20
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        csrf_token = soup.find(
            "input",
            {"name": "csrf_token"}
        )

        payload = {
            "username": KANBAN_USER,
            "password": KANBAN_PASS
        }

        if csrf_token:

            payload["csrf_token"] = (
                csrf_token.get("value")
            )

        session.post(
            KANBAN_LOGIN_URL,
            data=payload,
            timeout=20
        )

        return session

    except Exception:
        return None


# ============================================================
# AGENTES
# ============================================================

def get_agentes(session):

    try:

        r = session.get(
            MONITOR_URL,
            timeout=20
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        tabela = soup.find("table")

        if not tabela:
            return []

        agentes = []

        for linha in tabela.find_all("tr"):

            cols = linha.find_all("td")

            if len(cols) < 3:
                continue

            nome = (
                cols[0]
                .get_text(" ", strip=True)
                .split("Última chamada")[0]
                .strip()
            )

            status_txt = remover_acentos(
                cols[2]
                .get_text(strip=True)
                .lower()
            )

            if "pausa" in status_txt:

                status = "pausa"

            elif (
                "ocupado" in status_txt
                or "falando" in status_txt
            ):

                status = "ocupado"

            elif "livre" in status_txt:

                status = "livre"

            elif "indisponivel" in status_txt:

                status = "offline"

            else:

                status = "offline"

            if nome:
                agentes.append(
                    (nome, status)
                )

        return agentes

    except Exception:
        return []


# ============================================================
# WHATSFLUX
# ============================================================

def login_e_get_status_whatsflux():

    login_api_url = (
        "https://api.whatsflux.com.br/auth/login"
    )

    users_api_url = (
        "https://api.whatsflux.com.br/users"
    )

    session = requests.Session()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/json, text/plain, */*"
        ),
        "Content-Type": (
            "application/json;charset=UTF-8"
        ),
        "Referer": (
            "https://app.whatsflux.com.br/login"
        ),
        "Origin": (
            "https://app.whatsflux.com.br"
        )
    }

    session.headers.update(headers)

    tecnicos_alvo = [
        "Leonardo",
        "Matheus",
        "Gabriel",
        "Ramon",
        "Thiago",
        "Vinicius"
    ]

    status_tecnicos = {
        nome: "offline"
        for nome in tecnicos_alvo
    }

    try:

        email_whats = st.secrets[
            "WHATSFLUX_EMAIL"
        ]

        senha_whats = st.secrets[
            "WHATSFLUX_SENHA"
        ]

    except KeyError:

        return (
            "Configure o Secrets "
            "(WHATSFLUX_EMAIL / WHATSFLUX_SENHA)",
            {}
        )

    try:

        payload = {
            "email": email_whats,
            "password": senha_whats
        }

        res_login = session.post(
            login_api_url,
            json=payload,
            timeout=10
        )

        if res_login.status_code not in [
            200,
            201,
            302
        ]:

            return (
                f"Falha Auth "
                f"(HTTP {res_login.status_code})",
                {}
            )

        dados_resposta = res_login.json()

        token = (
            dados_resposta.get("token")
            or dados_resposta.get("access_token")
        )

        if token:

            session.headers.update(
                {
                    "Authorization":
                    f"Bearer {token}"
                }
            )

        res_users = session.get(
            users_api_url,
            timeout=10
        )

        if res_users.status_code != 200:

            return (
                f"Erro API Users "
                f"({res_users.status_code})",
                {}
            )

        resposta_json = res_users.json()

        dados_usuarios = resposta_json.get(
            "users",
            []
        )

        def normalizar(texto):

            if not texto:
                return ""

            return (
                unicodedata
                .normalize("NFKD", texto)
                .encode("ASCII", "ignore")
                .decode("ASCII")
                .lower()
                .strip()
            )

        for usuario in dados_usuarios:

            nome_usuario = usuario.get(
                "name",
                ""
            )

            is_online = usuario.get(
                "online",
                False
            )

            nome_usuario_limpo = normalizar(
                nome_usuario
            )

            for tecnico in tecnicos_alvo:

                tecnico_limpo = normalizar(
                    tecnico
                )

                if (
                    tecnico_limpo
                    in nome_usuario_limpo
                    and is_online
                ):

                    status_tecnicos[
                        tecnico
                    ] = "online"

        return "OK", status_tecnicos

    except Exception as e:

        return (
            f"Erro de Conexão "
            f"({str(e)[:20]})",
            {}
        )


# ============================================================
# ATUALIZA KANBAN
# ============================================================

def atualizar_kanban(session_kb):

    if not session_kb:
        return

    try:

        r = session_kb.get(
            KANBAN_URL,
            timeout=20
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        atividades = soup.find_all(
            "div",
            class_="activity-content"
        )

        tarefas_atuais = (
            st.session_state
            .tarefas_kanban
            .copy()
        )

        houve_alteracao = False
        disparar_som = False

        for atividade in reversed(atividades):

            title_p = atividade.find(
                "p",
                class_="activity-title"
            )

            if not title_p:
                continue

            texto_acao = title_p.get_text(
                " ",
                strip=True
            )

            link_task = title_p.find("a")

            date_span = title_p.find(
                "small",
                class_="activity-date"
            )

            if not link_task or not date_span:
                continue

            task_id = link_task.get_text(
                strip=True
            )

            data_atividade = date_span.get_text(
                strip=True
            )

            desc_div = atividade.find(
                "div",
                class_="activity-description"
            )

            titulo_tarefa = (
                desc_div
                .find(
                    "p",
                    class_="activity-task-title"
                )
                .get_text(strip=True)
                if desc_div
                and desc_div.find(
                    "p",
                    class_="activity-task-title"
                )
                else "Sem título"
            )

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

            st.session_state.tarefas_kanban = (
                tarefas_atuais
            )

            salvar_tarefas(
                tarefas_atuais
            )

            if disparar_som:

                st.session_state.play_alert = True

    except Exception as e:

        st.sidebar.error(
            f"Erro ao ler Kanban: {e}"
        )


# ============================================================
# LEITURA DA FILA RM
# ============================================================

def atualizar_fila_rm():

    try:

        resposta = requests.get(
            RM_SHEET_URL,
            timeout=20,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )

        resposta.raise_for_status()

        df_rm = pd.read_csv(
            pd.io.common.StringIO(
                resposta.text
            ),
            dtype=str,
            keep_default_na=False
        )

        if len(df_rm.columns) < 27:

            return (
                [],
                "A planilha do RM não possui "
                "a coluna AA."
            )

        pendencias = []

        for indice, linha in df_rm.iterrows():

            valor_concluido = str(
                linha.iloc[26]
            ).strip()

            # Só entra se AA estiver vazia
            if valor_concluido != "":
                continue

            dados_linha = {}

            for numero_coluna, nome_coluna in enumerate(
                df_rm.columns
            ):

                dados_linha[
                    nome_coluna
                ] = str(
                    linha.iloc[numero_coluna]
                ).strip()

            dados_linha[
                "_linha_planilha"
            ] = indice + 2

            # Identificação do conteúdo atual da linha
            fingerprint = gerar_fingerprint_rm(
                dados_linha
            )

            dados_linha[
                "_fingerprint"
            ] = fingerprint

            pendencias.append(
                dados_linha
            )

        return pendencias, None

    except Exception as e:

        return (
            [],
            "Erro ao consultar planilha RM: "
            + str(e)[:150]
        )


# ============================================================
# REMOVE RM DA VISUALIZAÇÃO
# ============================================================

def excluir_pendencia_rm(pendencia):

    excluidas = carregar_rm_excluidas()

    linha = str(
        pendencia.get(
            "_linha_planilha",
            ""
        )
    )

    fingerprint = pendencia.get(
        "_fingerprint",
        ""
    )

    if not linha or not fingerprint:
        return

    # Guardamos o fingerprint da versão da linha
    excluidas[linha] = fingerprint

    salvar_rm_excluidas(
        excluidas
    )


# ============================================================
# FILTRA RM EXCLUÍDO PELO USUÁRIO
# ============================================================

def filtrar_pendencias_rm(
    pendencias
):

    excluidas = carregar_rm_excluidas()

    resultado = []

    linhas_atuais = set()

    for pendencia in pendencias:

        linha = str(
            pendencia.get(
                "_linha_planilha",
                ""
            )
        )

        fingerprint = pendencia.get(
            "_fingerprint",
            ""
        )

        linhas_atuais.add(linha)

        fingerprint_salvo = excluidas.get(
            linha
        )

        # Se não foi excluída
        if fingerprint_salvo is None:

            resultado.append(
                pendencia
            )

        # Se a planilha mudou
        elif fingerprint_salvo != fingerprint:

            # A linha mudou.
            # Remove a exclusão antiga.
            excluidas.pop(
                linha,
                None
            )

            resultado.append(
                pendencia
            )

        # Caso contrário:
        # permanece excluída.

    # Limpa registros de linhas
    # que não existem mais na planilha.
    for linha in list(excluidas.keys()):

        if linha not in linhas_atuais:

            excluidas.pop(
                linha,
                None
            )

    salvar_rm_excluidas(
        excluidas
    )

    return resultado


# ============================================================
# INICIALIZAÇÃO SESSION STATE
# ============================================================

if "historico" not in st.session_state:

    st.session_state.historico = []


if "tarefas_kanban" not in st.session_state:

    st.session_state.tarefas_kanban = (
        carregar_tarefas_salvas()
    )


if "play_alert" not in st.session_state:

    st.session_state.play_alert = False


if "fila_rm" not in st.session_state:

    st.session_state.fila_rm = []


if "erro_rm" not in st.session_state:

    st.session_state.erro_rm = None


if "editando_id" not in st.session_state:

    st.session_state.editando_id = None


if "session" not in st.session_state:

    st.session_state.session = login()

elif not st.session_state.session:

    st.session_state.session = login()


if "session_kanban" not in st.session_state:

    st.session_state.session_kanban = login_kanban()

elif not st.session_state.session_kanban:

    st.session_state.session_kanban = login_kanban()


# ============================================================
# SESSÕES
# ============================================================

session = st.session_state.session

session_kb = (
    st.session_state.session_kanban
)


if not session:

    st.error(
        "Erro no login do PABX"
    )

    st.stop()


# ============================================================
# COLETA DE DADOS
# ============================================================

agentes = get_agentes(
    session
)

atualizar_kanban(
    session_kb
)

fila_rm_bruta, erro_rm = (
    atualizar_fila_rm()
)

if not erro_rm:

    fila_rm = filtrar_pendencias_rm(
        fila_rm_bruta
    )

else:

    fila_rm = []


st.session_state.fila_rm = fila_rm

st.session_state.erro_rm = erro_rm


# ============================================================
# TÍTULO
# ============================================================

st.markdown(
    '<div class="title">'
    '📡 Gestor de ServiceDesk - Intercom'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# MÉTRICAS
# ============================================================

livres = sum(
    1
    for _, s in agentes
    if s == "livre"
)

ocupados = sum(
    1
    for _, s in agentes
    if s == "ocupado"
)

pausa = sum(
    1
    for _, s in agentes
    if s == "pausa"
)

agora_br = datetime.now(
    ZoneInfo("America/Sao_Paulo")
)

st.session_state.historico.append(
    {
        "time": agora_br,
        "livres": int(livres),
        "ocupados": int(ocupados),
        "pausa": int(pausa)
    }
)


# ============================================================
# CARDS
# ============================================================

col1, col2, col3 = st.columns(3)

col1.markdown(
    f"""
    <div class="small-card green">
        🟢 {livres}<br>Livres
    </div>
    """,
    unsafe_allow_html=True
)

col2.markdown(
    f"""
    <div class="small-card red">
        🔴 {ocupados}<br>Ocupados
    </div>
    """,
    unsafe_allow_html=True
)

col3.markdown(
    f"""
    <div class="small-card yellow">
        🟡 {pausa}<br>Pausa
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")


# ============================================================
# GRÁFICO
# ============================================================

df_hist = pd.DataFrame(
    st.session_state.historico
)

if not df_hist.empty:

    df_hist["time"] = pd.to_datetime(
        df_hist["time"],
        errors="coerce"
    )

    df_hist = (
        df_hist
        .dropna(subset=["time"])
        .sort_values("time")
    )

    for col in [
        "livres",
        "ocupados",
        "pausa"
    ]:

        if col not in df_hist.columns:
            df_hist[col] = 0

    df_hist[
        ["livres", "ocupados", "pausa"]
    ] = (
        df_hist[
            ["livres", "ocupados", "pausa"]
        ]
        .fillna(0)
        .astype(int)
    )

    grafico = (
        df_hist
        .set_index("time")
        [
            [
                "livres",
                "ocupados",
                "pausa"
            ]
        ]
    )

    grafico_melt = (
        grafico
        .reset_index()
        .melt(
            id_vars=["time"],
            var_name="Status",
            value_name="Quantidade"
        )
    )

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

                    "domain": [
                        "livres",
                        "ocupados",
                        "pausa"
                    ],

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


# ============================================================
# WHATSFLUX
# ============================================================

st.write("---")

msg_retorno, status_whats = (
    login_e_get_status_whatsflux()
)

st.subheader(
    "👥 Status do Suporte Técnico (WhatsFlux)"
)

if "OK" in msg_retorno:

    colunas_tecnicos = st.columns(
        len(status_whats)
    )

    for col, (
        tecnico,
        status
    ) in zip(
        colunas_tecnicos,
        status_whats.items()
    ):

        with col:

            badge = (
                '<span style="'
                'color:#4ade80;'
                'font-weight:bold;'
                '">🟢 ONLINE</span>'
                if status == "online"
                else
                '<span style="'
                'color:#f87171;'
                'font-weight:bold;'
                '">🔴 OFFLINE</span>'
            )

            st.markdown(
                f"""
                <div style="
                    background-color:#1e293b;
                    padding:12px;
                    border-radius:8px;
                    border:1px solid #334155;
                    text-align:center;
                ">

                    <div style="
                        font-weight:bold;
                        margin-bottom:8px;
                        font-size:15px;
                        color:#f8fafc;
                    ">
                        {html.escape(tecnico)}
                    </div>

                    <div>
                        {badge}
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

else:

    st.error(
        f"Erro WhatsFlux: {msg_retorno}"
    )


# ============================================================
# FILAS
# ============================================================

st.write("---")

col_kanban, col_rm = st.columns(
    2,
    gap="medium"
)


# ============================================================
# KANBAN
# ============================================================

with col_kanban:

    col_titulo, col_audio = st.columns(
        [3, 1]
    )

    with col_titulo:

        st.subheader(
            "🔔 Fila de tarefa pendente - Kanban"
        )

    with col_audio:

        renderizar_botao_audio()

    if st.session_state.get(
        "play_alert",
        False
    ):

        st.session_state.play_alert = False

    tarefas_exibidas = (
        st.session_state
        .get(
            "tarefas_kanban",
            {}
        )
    )

    if tarefas_exibidas:

        for t_id, info in list(
            tarefas_exibidas.items()
        ):

            # ----------------------------------------------------
            # EDIÇÃO
            # ----------------------------------------------------

            if (
                st.session_state.editando_id
                == t_id
            ):

                col_input, col_salvar, col_canc = (
                    st.columns(
                        [0.76, 0.12, 0.12]
                    )
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

                        st.session_state.tarefas_kanban[
                            t_id
                        ]["titulo"] = novo_titulo

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

            # ----------------------------------------------------
            # VISUALIZAÇÃO
            # ----------------------------------------------------

            else:

                col_card, col_edit, col_del = (
                    st.columns(
                        [0.90, 0.05, 0.05]
                    )
                )

                # Corrige o problema do ##
                task_id_visual = str(
                    t_id
                ).strip()

                # Se o site já retorna #5158,
                # mostramos exatamente #5158.
                if not task_id_visual.startswith("#"):

                    task_id_visual = (
                        "#" + task_id_visual
                    )

                titulo_seguro = html.escape(
                    str(
                        info.get(
                            "titulo",
                            "Sem título"
                        )
                    )
                )

                data_segura = html.escape(
                    str(
                        info.get(
                            "data_criacao",
                            ""
                        )
                    )
                )

                status_seguro = html.escape(
                    str(
                        info.get(
                            "status",
                            "Pendente"
                        )
                    )
                )

                # ------------------------------------------------
                # CORREÇÃO PRINCIPAL:
                # usamos st.html em vez de st.markdown
                # para o card.
                # ------------------------------------------------

                with col_card:

                    st.html(
                        f"""
                        <div class="kanban-box">

                            <div style="
                                display:flex;
                                align-items:center;
                                gap:8px;
                                overflow:hidden;
                            ">

                                <span style="
                                    color:#fbbf24;
                                    font-size:18px;
                                    flex-shrink:0;
                                ">
                                    ⚠️
                                </span>

                                <div style="
                                    overflow:hidden;
                                    white-space:nowrap;
                                    text-overflow:ellipsis;
                                ">

                                    <strong>
                                        Tarefa {html.escape(task_id_visual)}
                                    </strong>

                                    &nbsp;&nbsp;

                                    Criada {data_segura}

                                    &nbsp; | &nbsp;

                                    <strong>
                                        Assunto:
                                    </strong>

                                    {titulo_seguro}

                                    &nbsp; | &nbsp;

                                    <span style="
                                        color:#f59e0b;
                                        font-weight:bold;
                                    ">
                                        Status: {status_seguro}
                                    </span>

                                </div>

                            </div>

                        </div>
                        """
                    )

                # ------------------------------------------------
                # EDITAR
                # ------------------------------------------------

                with col_edit:

                    if st.button(
                        "✏️",
                        key=f"btn_edt_{t_id}",
                        help="Editar Tarefa",
                        use_container_width=True
                    ):

                        st.session_state.editando_id = t_id

                        st.rerun()

                # ------------------------------------------------
                # EXCLUIR
                # ------------------------------------------------

                with col_del:

                    if st.button(
                        "🗑️",
                        key=f"btn_del_{t_id}",
                        help="Excluir Tarefa",
                        use_container_width=True
                    ):

                        del st.session_state.tarefas_kanban[
                            t_id
                        ]

                        salvar_tarefas(
                            st.session_state.tarefas_kanban
                        )

                        st.rerun()

    else:

        st.info(
            "Nenhuma tarefa pendente registrada no painel."
        )


# ============================================================
# RM
# ============================================================

with col_rm:

    st.subheader(
        "📋 Fila pendente - RM"
    )

    erro_rm = st.session_state.get(
        "erro_rm"
    )

    if erro_rm:

        st.error(
            erro_rm
        )

    else:

        pendencias_rm = (
            st.session_state
            .get(
                "fila_rm",
                []
            )
        )

        # --------------------------------------------------------
        # CONTADOR
        # --------------------------------------------------------

        if pendencias_rm:

            st.html(
                f"""
                <div style="
                    background:#1e293b;
                    border-radius:8px;
                    padding:10px 15px;
                    margin-bottom:12px;
                    border-left:5px solid #f59e0b;
                ">

                    <strong>
                        ⚠️ {len(pendencias_rm)}
                        pendência(s)
                        aguardando conclusão
                    </strong>

                </div>
                """
            )

            # ----------------------------------------------------
            # CADA PENDÊNCIA
            #
            # Não mostramos mais:
            # - data
            # - título
            # - linha da planilha
            #
            # Apenas a pendência e o botão de excluir.
            # ----------------------------------------------------

            for numero, pendencia in enumerate(
                pendencias_rm,
                start=1
            ):

                col_rm_card, col_rm_del = (
                    st.columns(
                        [0.90, 0.10]
                    )
                )

                with col_rm_card:

                    st.html(
                        f"""
                        <div class="rm-box">

                            <span style="
                                color:#fbbf24;
                                font-size:18px;
                                margin-right:8px;
                            ">
                                ⚠️
                            </span>

                            <strong>
                                Pendência RM #{numero}
                            </strong>

                        </div>
                        """
                    )

                with col_rm_del:

                    if st.button(
                        "🗑️",
                        key=(
                            "btn_del_rm_"
                            + str(
                                pendencia.get(
                                    "_linha_planilha",
                                    numero
                                )
                            )
                        ),
                        help=(
                            "Ocultar esta pendência "
                            "até a planilha ser alterada"
                        ),
                        use_container_width=True
                    ):

                        excluir_pendencia_rm(
                            pendencia
                        )

                        st.rerun()

        else:

            st.success(
                "✅ Nenhuma pendência RM "
                "aguardando conclusão."
            )


# ============================================================
# AGENTES
# ============================================================

st.write("---")

st.subheader(
    "👨‍💻 Agentes de Plantão"
)

df_agentes = pd.DataFrame(
    agentes,
    columns=[
        "Nome",
        "Status"
    ]
)

st.dataframe(
    df_agentes,
    use_container_width=True
)


# ============================================================
# AUTO ATUALIZAÇÃO
# ============================================================

time.sleep(
    refresh_rate
)

st.rerun()
