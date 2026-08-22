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
# CONFIGURAÇÃO DA PÁGINA
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

# Arquivo das tarefas Kanban
TAREFAS_FILE = "tarefas_pendentes.json"

# Arquivo de controle da fila RM
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
}

.queue-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 14px;
    line-height: 1.3;
}

.queue-icon {
    color: #fbbf24;
    font-size: 17px;
    margin-right: 7px;
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
   CARD WHATSFLUX
   ============================================================ */

.whatsflux-card {
    background-color: rgb(30, 41, 59);
    padding: 12px;
    border-radius: 8px;
    border: 1px solid rgb(51, 65, 85);
    text-align: center;
    box-sizing: border-box;
}

.whatsflux-nome {
    font-weight: bold;
    margin-bottom: 8px;
    font-size: 15px;
    color: rgb(248, 250, 252);
}

.whatsflux-online {
    color: rgb(74, 222, 128);
    font-weight: bold;
}

.whatsflux-offline {
    color: rgb(248, 113, 113);
    font-weight: bold;
}

/* ============================================================
   BOTÃO DE ÁUDIO
   ============================================================ */

.audio-container {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    width: 100%;
}

</style>
"""


# ============================================================
# FUNÇÃO PARA RENDERIZAR HTML
# ============================================================

def render_html(conteudo, width="stretch"):
    """
    Usa st.html quando disponível.
    Isso evita que as tags HTML apareçam como texto.
    """

    if hasattr(st, "html"):
        st.html(conteudo, width=width)
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
        if st.session_state.get("play_alert", False)
        else "false"
    )

    sound_html = f"""
    <div class="audio-container">

        <button
            id="btn-ativar-som"
            onclick="testarEAtivarSom()"
            style="
                background:#2563eb;
                color:white;
                border:none;
                border-radius:8px;
                height:40px;
                min-width:190px;
                font-weight:600;
                padding:0 18px;
                cursor:pointer;
                white-space:nowrap;
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

    var audio =
        document.getElementById('notif-sound');

    var deveTocarAutomatico =
        {tocar_agora};

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
                        "❌ Não foi possível ativar o som."
                    );

                }});

        }}

    }}

    if (deveTocarAutomatico && audio) {{

        audio.volume = 1.0;

        audio.play().catch(
            function(e) {{
                console.log(
                    "Autoplay bloqueado pelo navegador."
                );
            }}
        );

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

            if not isinstance(dados, dict):
                return {}

            # ------------------------------------------------
            # CORREÇÃO DE DUPLICIDADE
            #
            # Converte:
            # #5158
            # ##5158
            # 5158
            #
            # todos para:
            # 5158
            #
            # Isso também limpa duplicidades antigas
            # que já tenham sido gravadas no JSON.
            # ------------------------------------------------

            tarefas_normalizadas = {}

            for chave, info in dados.items():

                task_id = normalizar_task_id(
                    chave
                )

                if not task_id:
                    continue

                if not isinstance(
                    info,
                    dict
                ):
                    continue

                # Se a tarefa já existir com o mesmo ID,
                # mantém somente uma.
                tarefas_normalizadas[
                    task_id
                ] = info

            # Se o arquivo antigo tinha duplicidades,
            # salva imediatamente o arquivo corrigido.
            if tarefas_normalizadas != dados:

                salvar_tarefas(
                    tarefas_normalizadas
                )

            return tarefas_normalizadas

    except Exception:

        return {}


def salvar_tarefas(tarefas):

    # --------------------------------------------------------
    # CORREÇÃO DE DUPLICIDADE
    #
    # Antes de salvar, garante novamente que nunca existam
    # chaves como #5158 e 5158 simultaneamente.
    # --------------------------------------------------------

    tarefas_normalizadas = {}

    for chave, info in tarefas.items():

        task_id = normalizar_task_id(
            chave
        )

        if not task_id:
            continue

        if not isinstance(
            info,
            dict
        ):
            continue

        tarefas_normalizadas[
            task_id
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

    if not os.path.exists(RM_STATE_FILE):

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

            dados = json.load(arquivo)

            if not isinstance(dados, dict):

                return {
                    "fingerprint": "",
                    "ocultada": False
                }

            return {
                "fingerprint": dados.get(
                    "fingerprint",
                    ""
                ),
                "ocultada": bool(
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

    """
    Gera uma assinatura dos dados atuais da planilha.

    Se qualquer informação da fila mudar,
    a assinatura muda e a pendência volta a aparecer.
    """

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

    """
    Remove # duplicado.

    Exemplo:
    #5158  -> 5158
    ##5158 -> 5158
    ###5158 -> 5158
    5158   -> 5158
    """

    valor = str(task_id).strip()

    # Remove TODOS os # do início.
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

        tabela = soup.find("table")

        agentes = []

        if not tabela:
            return []

        for linha in tabela.find_all("tr"):

            cols = linha.find_all("td")

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

    """
    Corrige o problema em que valores como:
    "false", "0" ou "offline"
    poderiam ser tratados incorretamente como True.
    """

    status_raw = usuario.get("status")

    # --------------------------------------------------------
    # PRIMEIRO: usa o campo status quando existir
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # SEGUNDO: verifica campos booleanos
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # Aceita vários formatos de resposta
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # IMPORTANTE:
        #
        # Normaliza novamente o dicionário inteiro antes
        # de processar novas atividades.
        #
        # Isso elimina tarefas antigas gravadas como:
        # #5158
        # ##5158
        # 5158
        #
        # e mantém somente:
        # 5158
        # ----------------------------------------------------

        tarefas_atuais = {}

        for chave, info in (
            st.session_state
            .tarefas_kanban
            .items()
        ):

            task_id_normalizado = (
                normalizar_task_id(
                    chave
                )
            )

            if not task_id_normalizado:
                continue

            if not isinstance(
                info,
                dict
            ):
                continue

            # Se já existir, mantém somente uma.
            tarefas_atuais[
                task_id_normalizado
            ] = info

        houve_alteracao = (
            tarefas_atuais
            != st.session_state.tarefas_kanban
        )

        disparar_som = False

        # ----------------------------------------------------
        # CONTROLE DE TAREFAS ENCONTRADAS NO KANBAN
        #
        # Cada ID aparece somente uma vez.
        # ----------------------------------------------------

        ids_criacao_processados = set()

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

            # ------------------------------------------------
            # NORMALIZA ID
            # ------------------------------------------------

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

            # ------------------------------------------------
            # CRIAÇÃO
            #
            # SOMENTE contabiliza quando a atividade do
            # Kanban realmente informa:
            #
            # "criou a tarefa #5158"
            #
            # O mesmo ID nunca é contabilizado duas vezes.
            # ------------------------------------------------

            if "criou a tarefa" in (
                texto_acao.lower()
            ):

                if task_id in ids_criacao_processados:

                    continue

                ids_criacao_processados.add(
                    task_id
                )

                # ------------------------------------------------
                # SE A TAREFA JÁ EXISTE, NÃO CRIA NOVAMENTE.
                #
                # Isso impede:
                #
                # 5158
                # #5158
                # ##5158
                #
                # de virarem tarefas diferentes.
                # ------------------------------------------------

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

            # ------------------------------------------------
            # FINALIZAÇÃO
            # ------------------------------------------------

            elif "finalizou a tarefa" in (
                texto_acao.lower()
            ):

                if task_id in tarefas_atuais:

                    del tarefas_atuais[
                        task_id
                    ]

                    houve_alteracao = True

        # ----------------------------------------------------
        # SALVA SOMENTE O DICIONÁRIO NORMALIZADO
        # ----------------------------------------------------

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

            # Mesmo quando não houve alteração,
            # mantém o session_state normalizado.
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

        # AA = 27ª coluna
        if len(df_rm.columns) < 27:

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

            # ------------------------------------------------
            # SOMENTE QUANDO AA ESTIVER VAZIA
            # ------------------------------------------------

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

    # --------------------------------------------------------
    # SE A PLANILHA MUDOU:
    # REMOVE A EXCLUSÃO ANTERIOR
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # SE USUÁRIO EXCLUIU A FILA:
    # NÃO MOSTRA ATÉ A PLANILHA MUDAR
    # --------------------------------------------------------

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

col1, col2, col3 = st.columns(3)

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
        .dropna(subset=["time"])
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

st.subheader(
    "👥 Status do Suporte Técnico (WhatsFlux)"
)


msg_retorno, status_whats = (
    login_e_get_status_whatsflux()
)


if msg_retorno == "OK":

    colunas_tecnicos = st.columns(
        len(status_whats),
        gap="small"
    )

    for col, (
        tecnico,
        status
    ) in zip(
        colunas_tecnicos,
        status_whats.items()
    ):

        with col:

            if status == "online":

                status_html = """
                <span class="whatsflux-online">
                    🟢 ONLINE
                </span>
                """

            else:

                status_html = """
                <span class="whatsflux-offline">
                    🔴 OFFLINE
                </span>
                """

            render_html(
                f"""
                <div class="whatsflux-card">

                    <div class="whatsflux-nome">
                        {escape(tecnico)}
                    </div>

                    <div>
                        {status_html}
                    </div>

                </div>
                """
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
        [3, 1],
        vertical_alignment="center"
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

        # ----------------------------------------------------
        # SEGURANÇA EXTRA
        #
        # Mesmo que alguma duplicidade chegue até esta etapa,
        # a tela também elimina IDs repetidos.
        # ----------------------------------------------------

        ids_exibidos = set()

        for t_id, info in list(
            tarefas_exibidas.items()
        ):

            t_id_limpo = normalizar_task_id(
                t_id
            )

            if not t_id_limpo:
                continue

            # Nunca exibe o mesmo ID duas vezes.
            if t_id_limpo in ids_exibidos:
                continue

            ids_exibidos.add(
                t_id_limpo
            )

            # =================================================
            # MODO EDIÇÃO
            # =================================================

            if (
                st.session_state.editando_id
                == t_id_limpo
            ):

                col_input, col_salvar, col_canc = (
                    st.columns(
                        [0.76, 0.12, 0.12]
                    )
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
                            t_id_limpo
                        ]["titulo"] = (
                            novo_titulo
                        )

                        salvar_tarefas(
                            st.session_state.tarefas_kanban
                        )

                        st.session_state.editando_id = (
                            None
                        )

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

                        st.session_state.editando_id = (
                            None
                        )

                        st.rerun()

            # =================================================
            # MODO VISUALIZAÇÃO
            # =================================================

            else:

                col_card, col_edit, col_del = (
                    st.columns(
                        [0.90, 0.05, 0.05],
                        vertical_alignment="center"
                    )
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

                                &nbsp; Criada
                                {data_criacao}

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
                        key=(
                            f"btn_edt_"
                            f"{t_id_limpo}"
                        ),
                        help="Editar Tarefa",
                        use_container_width=True
                    ):

                        st.session_state.editando_id = (
                            t_id_limpo
                        )

                        st.rerun()

                with col_del:

                    if st.button(
                        "🗑️",
                        key=(
                            f"btn_del_"
                            f"{t_id_limpo}"
                        ),
                        help="Excluir Tarefa",
                        use_container_width=True
                    ):

                        if t_id_limpo in (
                            st.session_state
                            .tarefas_kanban
                        ):

                            del (
                                st.session_state
                                .tarefas_kanban[
                                    t_id_limpo
                                ]
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


        # =====================================================
        # SOMENTE A QUANTIDADE
        # =====================================================

        if pendencias_rm:

            col_qtd, col_del = st.columns(
                [0.90, 0.10],
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
