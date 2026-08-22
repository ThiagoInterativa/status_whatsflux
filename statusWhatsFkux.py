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
from html import escape


# ============================================================
# CONFIGURAÇÃO DA PÁGINAf
# ============================================================

st.set_page_config(
    layout="wide",
    page_title="Gestor de ServiceDesk - Intercom"
)


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
    "&action=show&project_id=1"
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

TAREFAS_FILE = "tarefas_pendentes.json"

RM_STATE_FILE = "rm_fila_state.json"


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

CSS = """
<style>

html, body {
    background-color: #0e1117;
}


/* ============================================================
   CARDS DE MÉTRICAS
   ============================================================ */

.small-card {
    padding: 22px;
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


/* ============================================================
   CABEÇALHO DAS FILAS
   ============================================================ */

/*
   IMPORTANTE:
   Kanban e RM agora usam exatamente a mesma altura.
*/

.fila-header {
    width: 100%;
    height: 55px;
    min-height: 55px;
    max-height: 55px;

    display: flex;
    align-items: center;

    box-sizing: border-box;

    overflow: visible;
}


.fila-titulo {
    width: 100%;

    font-size: 24px;
    font-weight: 700;

    color: #f8fafc;

    /*
       Não usa mais ellipsis.
       Isso elimina o "..." aparecendo no título.
    */

    white-space: nowrap;

    overflow: visible;

    text-overflow: clip;

    line-height: 1.2;

    box-sizing: border-box;
}


/* ============================================================
   LINHA SUPERIOR KANBAN
   ============================================================ */

.fila-topo-kanban {
    width: 100%;
    height: 55px;
    min-height: 55px;
    max-height: 55px;

    display: flex;
    align-items: center;

    box-sizing: border-box;
}


/* ============================================================
   ÁREA DO TÍTULO KANBAN
   ============================================================ */

.fila-topo-titulo {
    height: 55px;
    min-height: 55px;

    display: flex;
    align-items: center;

    box-sizing: border-box;
}


/* ============================================================
   ÁREA DO BOTÃO DE SOM
   ============================================================ */

.fila-topo-audio {
    height: 55px;
    min-height: 55px;

    display: flex;
    align-items: center;
    justify-content: center;

    box-sizing: border-box;
}


/* ============================================================
   CARDS DAS FILAS
   ============================================================ */

.queue-card {
    background: #1e293b;

    border-radius: 8px;

    border-left: 5px solid #3b82f6;

    padding: 9px 12px;

    min-height: 42px;

    display: flex;
    align-items: center;

    box-sizing: border-box;

    color: #f8fafc;

    width: 100%;
}


.queue-card-rm {
    background: #1e293b;

    border-radius: 8px;

    border-left: 5px solid #f59e0b;

    padding: 9px 12px;

    min-height: 42px;

    display: flex;
    align-items: center;

    box-sizing: border-box;

    color: #f8fafc;

    width: 100%;
}


.queue-text {
    white-space: nowrap;

    overflow: hidden;

    text-overflow: ellipsis;

    font-size: 14px;

    line-height: 1.3;

    width: 100%;
}


.queue-icon {
    color: #fbbf24;

    font-size: 17px;

    margin-right: 7px;

    flex-shrink: 0;
}


.status-online {
    color: #4ade80;
    font-weight: bold;
}


.status-offline {
    color: #f87171;
    font-weight: bold;
}


/* ============================================================
   BOTÕES EDITAR / EXCLUIR DO KANBAN
   ============================================================ */

div[class*="st-key-btn_edt_"] button,
div[class*="st-key-btn_del_"] button {

    width: 42px !important;
    min-width: 42px !important;
    max-width: 42px !important;

    height: 42px !important;
    min-height: 42px !important;
    max-height: 42px !important;

    padding: 0 !important;
    margin: 0 auto !important;

    display: flex !important;

    align-items: center !important;
    justify-content: center !important;

    line-height: 1 !important;

    text-align: center !important;

    border-radius: 10px !important;

    box-sizing: border-box !important;
}


/* ============================================================
   BOTÕES EDITAR / EXCLUIR NO MODO EDIÇÃO
   ============================================================ */

div[class*="st-key-btn_salvar_"] button,
div[class*="st-key-btn_canc_"] button {

    min-height: 42px !important;

    height: 42px !important;

    display: flex !important;

    align-items: center !important;
    justify-content: center !important;

    padding: 0 !important;

    line-height: 1 !important;
}


/* ============================================================
   CONTAINERS DOS BOTÕES EDITAR / EXCLUIR
   ============================================================ */

div[class*="st-key-btn_edt_"],
div[class*="st-key-btn_del_"] {

    width: 100% !important;

    display: flex !important;

    align-items: center !important;
    justify-content: center !important;

    box-sizing: border-box !important;
}


/* ============================================================
   BOTÃO DE SOM
   ============================================================ */

/*
   O botão está dentro de st.components.v1.html().
   Portanto este CSS é mantido também dentro do componente.
*/

.sound-button {

    width: 150px;

    height: 28px;

    min-width: 150;
    max-width: 150;

    background: #2563eb;

    color: #ffffff;

    border: none;

    border-radius: 7px;

    font-weight: 700;

    font-size: 13px;

    padding: 0;

    cursor: pointer;

    white-space: nowrap;

    display: flex;

    align-items: center;

    justify-content: center;

    text-align: center;

    box-sizing: border-box;
}


.sound-button:hover {
    background: #1d4ed8;
}


/* ============================================================
   AJUSTE DOS CONTAINERS STREAMLIT
   ============================================================ */

div[data-testid="column"] {
    box-sizing: border-box;
}


/* ============================================================
   EVITA ESPAÇAMENTO EXTRA NO HTML
   ============================================================ */

.fila-header p,
.fila-topo-titulo p {
    margin: 0 !important;
    padding: 0 !important;
}


/* ============================================================
   RM E KANBAN
   ============================================================ */

.fila-container {

    width: 100%;

    box-sizing: border-box;
}


/* ============================================================
   RESPONSIVO
   ============================================================ */

@media (max-width: 900px) {

    .fila-titulo {
        font-size: 20px;
    }

}

</style>
"""


# ============================================================
# FUNÇÃO PARA RENDERIZAR HTML
# ============================================================

def render_html(conteudo, width="stretch"):

    if hasattr(st, "html"):

        st.html(
            conteudo,
            width=width
        )

    else:

        st.markdown(
            conteudo,
            unsafe_allow_html=True
        )


render_html(CSS)


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
        if st.session_state.get(
            "play_alert",
            False
        )
        else "false"
    )

    sound_html = f"""
    <!DOCTYPE html>

    <html>

    <head>

        <style>

            html,
            body {{

                margin: 0;
                padding: 0;

                width: 100%;
                height: 55px;

                background: transparent;

                overflow: hidden;

            }}


            .sound-wrapper {{

                width: 130%;
                height: 55px;

                display: flex;

                align-items: center;

                justify-content: center;

                box-sizing: border-box;

            }}


            .sound-button {{

                width: 120px;
                height: 28px;

                min-width: 120px;
                max-width: 120px;

                background: #2563eb;

                color: #ffffff;

                border: none;

                border-radius: 7px;

                font-weight: 700;

                font-size: 13px;

                padding: 0;

                cursor: pointer;

                white-space: nowrap;

                display: flex;

                align-items: center;

                justify-content: center;

                text-align: center;

                box-sizing: border-box;

            }}


            .sound-button:hover {{

                background: #1d4ed8;

            }}

        </style>

    </head>


    <body>

        <div class="sound-wrapper">

            <button
                id="btn-ativar-som"
                class="sound-button"
                onclick="testarEAtivarSom()"
            >
                🔊 Testar Som
            </button>

        </div>


        <audio
            id="notif-sound"
            src="{audio_url}"
            preload="auto"
        ></audio>


        <script>

            var audio =
                document.getElementById(
                    'notif-sound'
                );


            var deveTocarAutomatico =
                {tocar_agora};


            function testarEAtivarSom() {{

                if (!audio) {{

                    alert(
                        "❌ Áudio não encontrado."
                    );

                    return;

                }}


                audio.volume = 1.0;

                audio.currentTime = 0;


                audio.play()

                    .then(function(){{

                        alert(
                            "✅ Excelente! Som do painel ativado."
                        );

                    }})

                    .catch(function(err){{

                        alert(
                            "❌ Não foi possível ativar o som."
                        );

                        console.log(
                            "Erro ao reproduzir áudio:",
                            err
                        );

                    }});

            }}


            if (
                deveTocarAutomatico
                && audio
            ) {{

                audio.volume = 1.0;

                audio.currentTime = 0;

                audio.play().catch(
                    function(e){{

                        console.log(
                            "Autoplay bloqueado pelo navegador."
                        );

                    }}
                );

            }}

        </script>

    </body>

    </html>
    """


    st.components.v1.html(
        sound_html,
        height=55
    )


# ============================================================
# PERSISTÊNCIA KANBAN
# ============================================================

def carregar_tarefas_salvas():

    if not os.path.exists(
        TAREFAS_FILE
    ):

        return {}

    try:

        with open(
            TAREFAS_FILE,
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(
                arquivo
            )

            if not isinstance(
                dados,
                dict
            ):

                return {}


            tarefas_normalizadas = {}


            for task_id, info in dados.items():

                task_id_limpo = normalizar_task_id(
                    task_id
                )

                if not task_id_limpo:

                    continue


                if not isinstance(
                    info,
                    dict
                ):

                    info = {}


                tarefas_normalizadas[
                    task_id_limpo
                ] = info


            if tarefas_normalizadas != dados:

                try:

                    salvar_tarefas(
                        tarefas_normalizadas
                    )

                except Exception:

                    pass


            return tarefas_normalizadas

    except Exception:

        return {}


def salvar_tarefas(tarefas):

    tarefas_normalizadas = {}


    if isinstance(
        tarefas,
        dict
    ):

        for task_id, info in tarefas.items():

            task_id_limpo = normalizar_task_id(
                task_id
            )

            if not task_id_limpo:

                continue


            if not isinstance(
                info,
                dict
            ):

                info = {}


            tarefas_normalizadas[
                task_id_limpo
            ] = info


    with open(
        TAREFAS_FILE,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            tarefas_normalizadas,
            arquivo,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# PERSISTÊNCIA RM
# ============================================================

def carregar_estado_rm():

    if not os.path.exists(
        RM_STATE_FILE
    ):

        return {
            "fingerprint": "",
            "ocultada": False
        }


    try:

        with open(
            RM_STATE_FILE,
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(
                arquivo
            )


            if not isinstance(
                dados,
                dict
            ):

                return {
                    "fingerprint": "",
                    "ocultada": False
                }


            return {

                "fingerprint":
                    dados.get(
                        "fingerprint",
                        ""
                    ),

                "ocultada":
                    bool(
                        dados.get(
                            "ocultada",
                            False
                        )
                    )

            }

    except Exception:

        return {
            "fingerprint": "",
            "ocultada": False
        }


def salvar_estado_rm(estado):

    with open(
        RM_STATE_FILE,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            estado,
            arquivo,
            indent=4,
            ensure_ascii=False
        )


def gerar_fingerprint_rm(pendencias):

    dados = json.dumps(
        pendencias,
        ensure_ascii=False,
        sort_keys=True
    )

    return hashlib.sha256(
        dados.encode("utf-8")
    ).hexdigest()


# ============================================================
# UTILITÁRIOS
# ============================================================

def remover_acentos(txt):

    if txt is None:

        return ""

    return "".join(
        c
        for c in unicodedata.normalize(
            "NFD",
            str(txt)
        )
        if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(txt):

    return remover_acentos(
        str(txt)
    ).lower().strip()


def normalizar_task_id(task_id):

    valor = str(
        task_id
    ).strip()


    while valor.startswith("#"):

        valor = valor[1:]


    return valor.strip()


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

        token_element = soup.find(
            "input",
            {"name": "_token"}
        )

        if not token_element:

            return None

        token = token_element.get(
            "value"
        )

        payload = {

            "login":
                EMAIL,

            "senha":
                SENHA,

            "_token":
                token

        }

        res = session.post(
            LOGIN_URL,
            data=payload,
            timeout=20
        )

        if res.url != LOGIN_URL:

            return session

        return None

    except Exception:

        return None


# ============================================================
# LOGIN KANBAN
# ============================================================

def login_kanban():

    session = requests.Session()

    try:

        login_page = (
            "https://kanban.interativanet.com.br/"
            "?controller=AuthController&action=login"
        )

        r = session.get(
            login_page,
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

            "username":
                KANBAN_USER,

            "password":
                KANBAN_PASS

        }

        if csrf_token:

            payload[
                "csrf_token"
            ] = csrf_token.get(
                "value"
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
# AGENTES PABX
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

        tabela = soup.find(
            "table"
        )

        agentes = []


        if not tabela:

            return []


        for linha in tabela.find_all(
            "tr"
        ):

            cols = linha.find_all(
                "td"
            )


            if len(cols) < 3:

                continue


            nome = (
                cols[0]
                .get_text(
                    " ",
                    strip=True
                )
                .split(
                    "Última chamada"
                )[0]
                .strip()
            )


            status_txt = remover_acentos(
                cols[2]
                .get_text(
                    strip=True
                )
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
                    (
                        nome,
                        status
                    )
                )


        return agentes

    except Exception:

        return []


# ============================================================
# WHATSFLUX
# ============================================================

def interpretar_status_whatsflux(usuario):

    status_raw = usuario.get(
        "status"
    )


    if status_raw is not None:

        status = normalizar_texto(
            status_raw
        )


        if status in (
            "online",
            "ativo",
            "available",
            "disponivel",
            "connected",
            "conectado"
        ):

            return "online"


        return "offline"


    online_raw = usuario.get(
        "online",
        usuario.get(
            "is_online",
            usuario.get(
                "isOnline",
                False
            )
        )
    )


    if isinstance(
        online_raw,
        bool
    ):

        return (
            "online"
            if online_raw
            else "offline"
        )


    if isinstance(
        online_raw,
        (int, float)
    ):

        return (
            "online"
            if online_raw == 1
            else "offline"
        )


    online_txt = normalizar_texto(
        online_raw
    )


    if online_txt in (
        "true",
        "1",
        "online",
        "ativo",
        "active",
        "available",
        "disponivel"
    ):

        return "online"


    return "offline"


def login_e_get_status_whatsflux():

    login_api_url = (
        "https://api.whatsflux.com.br/auth/login"
    )

    users_api_url = (
        "https://api.whatsflux.com.br/users"
    )

    session = requests.Session()


    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36",

        "Accept":
            "application/json, text/plain, */*",

        "Content-Type":
            "application/json;charset=UTF-8",

        "Referer":
            "https://app.whatsflux.com.br/login",

        "Origin":
            "https://app.whatsflux.com.br"

    }


    session.headers.update(
        headers
    )


    tecnicos_alvo = [

        "Leonardo",
        "Matheus",
        "Gabriel",
        "Ramon",
        "Thiago",
        "Vinicius"

    ]


    status_tecnicos = {

        nome:
            "offline"

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

            "email":
                email_whats,

            "password":
                senha_whats

        }


        res_login = session.post(
            login_api_url,
            json=payload,
            timeout=15
        )


        if res_login.status_code not in (
            200,
            201,
            302
        ):

            return (
                f"Falha Auth "
                f"(HTTP {res_login.status_code})",
                {}
            )


        dados_resposta = res_login.json()


        token = (
            dados_resposta.get("token")
            or dados_resposta.get("access_token")
            or dados_resposta.get("accessToken")
        )


        if token:

            session.headers.update({

                "Authorization":
                    f"Bearer {token}"

            })


        res_users = session.get(
            users_api_url,
            timeout=15
        )


        if res_users.status_code != 200:

            return (
                f"Erro API Users "
                f"({res_users.status_code})",
                {}
            )


        resposta_json = res_users.json()


        if isinstance(
            resposta_json,
            list
        ):

            dados_usuarios = resposta_json

        elif isinstance(
            resposta_json,
            dict
        ):

            dados_usuarios = (
                resposta_json.get("users")
                or resposta_json.get("data")
                or resposta_json.get("results")
                or []
            )

        else:

            dados_usuarios = []


        if not isinstance(
            dados_usuarios,
            list
        ):

            dados_usuarios = []


        for usuario in dados_usuarios:

            if not isinstance(
                usuario,
                dict
            ):

                continue


            nome_usuario = str(
                usuario.get(
                    "name",
                    ""
                )
            ).strip()


            nome_usuario_limpo = normalizar_texto(
                nome_usuario
            )


            status_atual = (
                interpretar_status_whatsflux(
                    usuario
                )
            )


            for tecnico in tecnicos_alvo:

                tecnico_limpo = normalizar_texto(
                    tecnico
                )


                if (
                    tecnico_limpo
                    == nome_usuario_limpo
                    or tecnico_limpo
                    in nome_usuario_limpo
                ):

                    status_tecnicos[
                        tecnico
                    ] = status_atual


        return (
            "OK",
            status_tecnicos
        )


    except Exception as e:

        return (
            f"Erro de Conexão "
            f"({str(e)[:80]})",
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


        tarefas_atuais_brutas = (
            st.session_state
            .get(
                "tarefas_kanban",
                {}
            )
            .copy()
        )


        tarefas_atuais = {}


        for task_id_antigo, info in (
            tarefas_atuais_brutas.items()
        ):

            task_id_limpo = normalizar_task_id(
                task_id_antigo
            )


            if not task_id_limpo:

                continue


            if not isinstance(
                info,
                dict
            ):

                info = {}


            tarefas_atuais[
                task_id_limpo
            ] = info


        if (
            tarefas_atuais
            != tarefas_atuais_brutas
        ):

            salvar_tarefas(
                tarefas_atuais
            )

            houve_alteracao_inicial = True

        else:

            houve_alteracao_inicial = False


        houve_alteracao = (
            houve_alteracao_inicial
        )

        disparar_som = False


        tarefas_criadas_kanban = set()


        for atividade in reversed(
            atividades
        ):

            title_p = atividade.find(
                "p",
                class_="activity-title"
            )


            if not title_p:

                continue


            texto_acao = (
                title_p
                .get_text(
                    " ",
                    strip=True
                )
            )


            link_task = title_p.find(
                "a"
            )


            date_span = title_p.find(
                "small",
                class_="activity-date"
            )


            if (
                not link_task
                or not date_span
            ):

                continue


            task_id = normalizar_task_id(
                link_task.get_text(
                    strip=True
                )
            )


            if not task_id:

                continue


            data_atividade = (
                date_span
                .get_text(
                    strip=True
                )
            )


            desc_div = atividade.find(
                "div",
                class_="activity-description"
            )


            titulo_element = None


            if desc_div:

                titulo_element = (
                    desc_div.find(
                        "p",
                        class_="activity-task-title"
                    )
                )


            if titulo_element:

                titulo_tarefa = (
                    titulo_element
                    .get_text(
                        " ",
                        strip=True
                    )
                )

            else:

                titulo_tarefa = "Sem título"


            if "criou a tarefa" in (
                texto_acao.lower()
            ):

                if task_id in (
                    tarefas_criadas_kanban
                ):

                    continue


                tarefas_criadas_kanban.add(
                    task_id
                )


                if task_id not in tarefas_atuais:

                    tarefas_atuais[
                        task_id
                    ] = {

                        "titulo":
                            titulo_tarefa,

                        "data_criacao":
                            data_atividade,

                        "status":
                            "Pendente"

                    }


                    houve_alteracao = True

                    disparar_som = True


                else:

                    info_atual = (
                        tarefas_atuais[
                            task_id
                        ]
                    )


                    if not isinstance(
                        info_atual,
                        dict
                    ):

                        info_atual = {}


                    if not info_atual.get(
                        "titulo"
                    ):

                        info_atual[
                            "titulo"
                        ] = titulo_tarefa

                        houve_alteracao = True


                    if not info_atual.get(
                        "data_criacao"
                    ):

                        info_atual[
                            "data_criacao"
                        ] = data_atividade

                        houve_alteracao = True


                    if not info_atual.get(
                        "status"
                    ):

                        info_atual[
                            "status"
                        ] = "Pendente"

                        houve_alteracao = True


                    tarefas_atuais[
                        task_id
                    ] = info_atual


            elif "finalizou a tarefa" in (
                texto_acao.lower()
            ):

                if task_id in tarefas_atuais:

                    del tarefas_atuais[
                        task_id
                    ]

                    houve_alteracao = True


        tarefas_unicas = {}


        for task_id, info in tarefas_atuais.items():

            task_id_limpo = normalizar_task_id(
                task_id
            )


            if not task_id_limpo:

                continue


            tarefas_unicas[
                task_id_limpo
            ] = info


        if (
            tarefas_unicas
            != tarefas_atuais
        ):

            tarefas_atuais = tarefas_unicas

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


        else:

            st.session_state.tarefas_kanban = (
                tarefas_atuais
            )


    except Exception as e:

        st.sidebar.error(
            f"Erro ao ler Kanban: {e}"
        )


# ============================================================
# LEITURA RM
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


        if len(
            df_rm.columns
        ) < 27:

            return (
                [],
                "A planilha do RM não possui "
                "a coluna AA.",
                ""
            )


        pendencias = []


        for indice, linha in df_rm.iterrows():

            valor_concluido = str(
                linha.iloc[26]
            ).strip()


            if valor_concluido == "":

                dados_linha = {}


                for numero_coluna, nome_coluna in enumerate(
                    df_rm.columns
                ):

                    dados_linha[
                        nome_coluna
                    ] = str(
                        linha.iloc[
                            numero_coluna
                        ]
                    ).strip()


                dados_linha[
                    "_linha_planilha"
                ] = indice + 2


                pendencias.append(
                    dados_linha
                )


        fingerprint = (
            gerar_fingerprint_rm(
                pendencias
            )
        )


        return (
            pendencias,
            None,
            fingerprint
        )


    except Exception as e:

        return (
            [],
            (
                "Erro ao consultar "
                f"planilha RM: "
                f"{str(e)[:150]}"
            ),
            ""
        )


# ============================================================
# ESTADO INICIAL
# ============================================================

if "historico" not in st.session_state:

    st.session_state.historico = []


if "tarefas_kanban" not in st.session_state:

    st.session_state.tarefas_kanban = (
        carregar_tarefas_salvas()
    )

else:

    tarefas_sessao = {}


    for task_id, info in (
        st.session_state
        .tarefas_kanban
        .items()
    ):

        task_id_limpo = normalizar_task_id(
            task_id
        )


        if not task_id_limpo:

            continue


        tarefas_sessao[
            task_id_limpo
        ] = info


    st.session_state.tarefas_kanban = (
        tarefas_sessao
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

    st.session_state.session = None


if "session_kanban" not in st.session_state:

    st.session_state.session_kanban = None


# ============================================================
# LOGINS
# ============================================================

if not st.session_state.session:

    st.session_state.session = login()


if not st.session_state.session_kanban:

    st.session_state.session_kanban = (
        login_kanban()
    )


# ============================================================
# SESSÕES
# ============================================================

session = st.session_state.session

session_kb = (
    st.session_state.session_kanban
)


if not session:

    st.error(
        "❌ Erro no login do PABX."
    )

    st.stop()


# ============================================================
# COLETA DOS DADOS
# ============================================================

agentes = get_agentes(
    session
)


atualizar_kanban(
    session_kb
)


# ============================================================
# RM
# ============================================================

fila_rm_bruta, erro_rm, rm_fingerprint = (
    atualizar_fila_rm()
)


st.session_state.erro_rm = erro_rm


if erro_rm:

    st.session_state.fila_rm = []

else:

    estado_rm = carregar_estado_rm()


    if (
        estado_rm.get(
            "fingerprint",
            ""
        )
        != rm_fingerprint
    ):

        estado_rm = {

            "fingerprint":
                rm_fingerprint,

            "ocultada":
                False

        }


        salvar_estado_rm(
            estado_rm
        )


    if estado_rm.get(
        "ocultada",
        False
    ):

        st.session_state.fila_rm = []

    else:

        st.session_state.fila_rm = (
            fila_rm_bruta
        )


# ============================================================
# TÍTULO
# ============================================================

render_html(
    """
    <div class="title">
        📡 Gestor de ServiceDesk - Intercom
    </div>
    """
)


# ============================================================
# MÉTRICAS
# ============================================================

livres = sum(
    1
    for _, status in agentes
    if status == "livre"
)


ocupados = sum(
    1
    for _, status in agentes
    if status == "ocupado"
)


pausa = sum(
    1
    for _, status in agentes
    if status == "pausa"
)


agora_br = datetime.now(
    ZoneInfo("America/Sao_Paulo")
)


st.session_state.historico.append(
    {

        "time":
            agora_br,

        "livres":
            int(livres),

        "ocupados":
            int(ocupados),

        "pausa":
            int(pausa)

    }
)


# ============================================================
# CARDS
# ============================================================

col1, col2, col3 = st.columns(
    3
)


col1.markdown(
    f"""
    <div class="small-card green">
        🟢 {livres}<br>
        Livres
    </div>
    """,
    unsafe_allow_html=True
)


col2.markdown(
    f"""
    <div class="small-card red">
        🔴 {ocupados}<br>
        Ocupados
    </div>
    """,
    unsafe_allow_html=True
)


col3.markdown(
    f"""
    <div class="small-card yellow">
        🟡 {pausa}<br>
        Pausa
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
        .dropna(
            subset=["time"]
        )
        .sort_values("time")
    )


    for coluna in [
        "livres",
        "ocupados",
        "pausa"
    ]:

        if coluna not in df_hist.columns:

            df_hist[coluna] = 0


    df_hist[
        [
            "livres",
            "ocupados",
            "pausa"
        ]
    ] = (
        df_hist[
            [
                "livres",
                "ocupados",
                "pausa"
            ]
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

    "data":
        grafico_melt,

    "mark":
        "line",

    "encoding": {

        "x": {

            "field":
                "time",

            "type":
                "temporal",

            "title":
                "Horário"

        },

        "y": {

            "field":
                "Quantidade",

            "type":
                "quantitative",

            "title":
                "Quantidade"

        },

        "color": {

            "field":
                "Status",

            "type":
                "nominal",

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

                "title":
                    "Status"

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

    # --------------------------------------------------------
    # CABEÇALHO KANBAN
    #
    # Título e botão possuem exatamente 55px de altura.
    # --------------------------------------------------------

    col_titulo, col_audio = st.columns(
        [3.1, 1.9],
        vertical_alignment="center"
    )


    with col_titulo:

        render_html(
            """
            <div class="fila-topo-titulo">

                <div class="fila-titulo">
                    🔔 Fila de tarefa pendente - Kanban
                </div>

            </div>
            """
        )


    with col_audio:

        renderizar_botao_audio()


    # --------------------------------------------------------
    # LIMPA O ALERTA DEPOIS DE RENDERIZAR O BOTÃO
    # --------------------------------------------------------

    if st.session_state.get(
        "play_alert",
        False
    ):

        st.session_state.play_alert = False


    # --------------------------------------------------------
    # TAREFAS
    # --------------------------------------------------------

    tarefas_exibidas_brutas = (
        st.session_state
        .get(
            "tarefas_kanban",
            {}
        )
    )


    tarefas_exibidas = {}


    for t_id, info in (
        tarefas_exibidas_brutas.items()
    ):

        t_id_limpo = normalizar_task_id(
            t_id
        )


        if not t_id_limpo:

            continue


        if not isinstance(
            info,
            dict
        ):

            info = {}


        tarefas_exibidas[
            t_id_limpo
        ] = info


    if (
        tarefas_exibidas
        != tarefas_exibidas_brutas
    ):

        st.session_state.tarefas_kanban = (
            tarefas_exibidas
        )


        salvar_tarefas(
            tarefas_exibidas
        )


    # --------------------------------------------------------
    # EXISTEM TAREFAS
    # --------------------------------------------------------

    if tarefas_exibidas:

        for t_id, info in list(
            tarefas_exibidas.items()
        ):

            t_id_limpo = normalizar_task_id(
                t_id
            )


            # =================================================
            # MODO EDIÇÃO
            # =================================================

            if (
                st.session_state.editando_id
                == t_id
            ):

                (
                    col_input,
                    col_salvar,
                    col_canc
                ) = st.columns(
                    [0.76, 0.12, 0.12],
                    vertical_alignment="center"
                )


                with col_input:

                    novo_titulo = st.text_input(
                        f"Editar Tarefa #{t_id_limpo}",

                        value=info.get(
                            "titulo",
                            ""
                        ),

                        key=(
                            f"input_inline_"
                            f"{t_id_limpo}"
                        ),

                        label_visibility="collapsed"
                    )


                with col_salvar:

                    if st.button(
                        "💾",

                        key=(
                            f"btn_salvar_"
                            f"{t_id_limpo}"
                        ),

                        help="Salvar",

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
                        "❌",

                        key=(
                            f"btn_canc_"
                            f"{t_id_limpo}"
                        ),

                        help="Cancelar",

                        use_container_width=True
                    ):

                        st.session_state.editando_id = None

                        st.rerun()


            # =================================================
            # MODO NORMAL
            # =================================================

            else:

                (
                    col_card,
                    col_edit,
                    col_del
                ) = st.columns(
                    [0.85, 0.08, 0.08],
                    vertical_alignment="center"
                )


                with col_card:

                    titulo = escape(
                        str(
                            info.get(
                                "titulo",
                                "Sem título"
                            )
                        )
                    )


                    data_criacao = escape(
                        str(
                            info.get(
                                "data_criacao",
                                ""
                            )
                        )
                    )


                    status_tarefa = escape(
                        str(
                            info.get(
                                "status",
                                "Pendente"
                            )
                        )
                    )


                    render_html(
                        f"""
                        <div class="queue-card">

                            <span class="queue-icon">
                                ⚠️
                            </span>

                            <div class="queue-text">

                                <strong>
                                    Tarefa #{escape(t_id_limpo)}
                                </strong>

                                &nbsp; Criada {data_criacao}

                                &nbsp; | &nbsp;

                                <strong>
                                    Assunto:
                                </strong>

                                {titulo}

                                &nbsp; | &nbsp;

                                <span style="
                                    color:#f59e0b;
                                    font-weight:bold;
                                ">
                                    Status: {status_tarefa}
                                </span>

                            </div>

                        </div>
                        """
                    )


                with col_edit:

                    if st.button(
                        "✏️",

                        key=f"btn_edt_{t_id_limpo}",

                        help="Editar Tarefa",

                        use_container_width=True
                    ):

                        st.session_state.editando_id = t_id

                        st.rerun()


                with col_del:

                    if st.button(
                        "🗑️",

                        key=f"btn_del_{t_id_limpo}",

                        help="Excluir Tarefa",

                        use_container_width=True
                    ):

                        if t_id in (
                            st.session_state
                            .tarefas_kanban
                        ):

                            del (
                                st.session_state
                                .tarefas_kanban[t_id]
                            )


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

    # ========================================================
    # CABEÇALHO RM
    #
    # TEM EXATAMENTE A MESMA ALTURA DO CABEÇALHO KANBAN.
    # ========================================================

    render_html(
        """
        <div class="fila-header">

            <div class="fila-titulo">
                📋 Fila pendente - RM
            </div>

        </div>
        """
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


        # =====================================================
        # EXISTEM PENDÊNCIAS RM
        # =====================================================

        if pendencias_rm:

            col_qtd, col_del = st.columns(
                [0.99, 0.10],
                vertical_alignment="center"
            )


            with col_qtd:

                quantidade = len(
                    pendencias_rm
                )


                render_html(
                    f"""
                    <div class="queue-card-rm">

                        <span class="queue-icon">
                            ⚠️
                        </span>

                        <strong>
                            {quantidade}
                            pendência(s)
                            aguardando conclusão
                        </strong>

                    </div>
                    """
                )


            with col_del:

                if st.button(
                    "🗑️",

                    key="btn_deletar_fila_rm",

                    help=(
                        "Ocultar as pendências atuais. "
                        "Elas voltarão quando a planilha "
                        "for alterada."
                    ),

                    use_container_width=True
                ):

                    estado_rm = (
                        carregar_estado_rm()
                    )


                    estado_rm[
                        "ocultada"
                    ] = True


                    salvar_estado_rm(
                        estado_rm
                    )


                    st.session_state.fila_rm = []


                    st.rerun()


        else:

            st.success(
                "✅ Nenhuma pendência RM aguardando conclusão."
            )


# ============================================================
# AGENTES DE PLANTÃO
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
