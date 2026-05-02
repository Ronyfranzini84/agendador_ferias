import json
import os
import re
import socket
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app_paths import caminho_recurso
from bd_crud import (
    EmailJaCadastradoError,
    TIPO_FERIAS,
    atualizar_ferias,
    criar_usuario,
    deletar_ferias,
    deletar_usuario,
    ler_todos_usuarios,
    modificar_usuario,
)
from calendar_component import calendar
from envio_email import EmailEnvioError, enviar_email, enviar_email_outlook
from groq_ai import GroqAIError, gerar_rascunho_email_ia, gerar_resumo_dashboard_ia


PASTA_ATUAL = Path(__file__).parent
CAMINHO_CALENDARIO = caminho_recurso("calendar_options.json")
FORMATO_DATA = "%Y-%m-%d"
FORMATO_DATA_BR = "%d/%m/%Y"
SEM_EQUIPE_ID = "sem-equipe"
TIPOS_OCORRENCIA = {
    "ferias": "Férias",
    "folga": "Folga",
    "atestado": "Atestado",
}
CHAVE_LOGADO = "logado"
CHAVE_USUARIO = "usuario"
CHAVE_PAGINA_GESTAO = "page_gestao_usuarios"
CHAVE_TELA_GESTOR = "tela_gestor"
CHAVE_ULTIMO_CLICK = "ultimo_click"
CHAVE_DATA_INICIO = "data_inicio"
CHAVE_DATA_FINAL = "data_final"
CHAVE_FRACIONAR_FERIAS = "fracionar_ferias"
CHAVE_PLANO_FRACIONAMENTO = "plano_fracionamento"
CHAVE_FERIAS_GESTOR = "gestor_ferias_id"
CHAVE_EDITOR_DATA_INICIO = "gestor_editor_data_inicio"
CHAVE_EDITOR_DATA_FIM = "gestor_editor_data_fim"
CHAVE_EDITOR_TIPO = "gestor_editor_tipo"
CHAVE_LISTA_RECURSO = "gestor_lista_recurso"
CHAVE_LISTA_SETOR_FORM = "gestor_setor_form"
CHAVE_LISTA_DATA_INICIO = "gestor_lista_data_inicio"
CHAVE_LISTA_DATA_FIM = "gestor_lista_data_fim"
CHAVE_LISTA_USUARIO = "gestor_lista_usuario"
CHAVE_LISTA_TIPO = "gestor_lista_tipo"
CHAVE_USUARIO_MOD_EM_EDICAO = "mod_usuario_id_atual"
CHAVE_MENSAGEM_RODAPE = "mensagem_rodape"
CHAVE_EMAIL_DESTINATARIO = "email_destinatario_usuario"
PORTA_APP = 8501

st.image(str(caminho_recurso("wave.png")), use_container_width=True)

def recarregar():
    st.rerun()


def sair():
    limpar_datas()
    limpar_gestao_ferias()
    limpar_formulario_modificacao()
    st.session_state[CHAVE_LOGADO] = False
    st.session_state.pop(CHAVE_USUARIO, None)
    st.session_state[CHAVE_PAGINA_GESTAO] = False
    st.session_state[CHAVE_TELA_GESTOR] = "calendario"
    st.session_state[CHAVE_ULTIMO_CLICK] = ""
    st.session_state.pop(CHAVE_MENSAGEM_RODAPE, None)


def inicializar_estado():
    st.session_state.setdefault(CHAVE_LOGADO, False)
    st.session_state.setdefault(CHAVE_PAGINA_GESTAO, False)
    st.session_state.setdefault(
        CHAVE_TELA_GESTOR,
        "gestao" if st.session_state.get(CHAVE_PAGINA_GESTAO) else "calendario",
    )
    st.session_state.setdefault(CHAVE_ULTIMO_CLICK, "")
    st.session_state.setdefault(CHAVE_FERIAS_GESTOR, None)


def definir_mensagem_rodape(tipo, texto):
    st.session_state[CHAVE_MENSAGEM_RODAPE] = {"tipo": tipo, "texto": texto}


def obter_chave_api_groq_streamlit():
    chave_env = os.getenv("GROQ_API_KEY", "").strip()
    if chave_env:
        return chave_env

    try:
        chave_secret = str(st.secrets.get("GROQ_API_KEY", "")).strip()
    except Exception:
        chave_secret = ""
    return chave_secret


def normalizar_texto_ia(texto):
    conteudo = (texto or "").strip()
    if not conteudo:
        return ""

    for _ in range(3):
        if "\\" not in conteudo:
            break
        if not any(token in conteudo for token in ("\\n", "\\u", "\\t", "\\r")):
            break

        anterior = conteudo
        try:
            conteudo = conteudo.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            break

        if conteudo == anterior:
            break

    conteudo = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), conteudo)

    conteudo = (
        conteudo.replace("\\\\r\\\\n", "\n")
        .replace("\\\\n", "\n")
        .replace("\\\\t", "\t")
        .replace("\\\\r", "\n")
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .strip()
    )

    conteudo = "".join(
        ch for ch in unicodedata.normalize("NFD", conteudo) if unicodedata.category(ch) != "Mn"
    )
    conteudo = conteudo.replace("ç", "c").replace("Ç", "C")
    return conteudo


def extrair_assunto_mensagem_ia(resposta_ia):
    resposta_normalizada = normalizar_texto_ia(resposta_ia)
    assunto = ""
    mensagem = ""
    linhas = [linha.rstrip() for linha in resposta_normalizada.splitlines()]

    for indice, linha in enumerate(linhas):
        if linha.upper().startswith("ASSUNTO:"):
            assunto = linha.split(":", 1)[1].strip()
            restante = linhas[indice + 1 :]
            if restante and restante[0].strip().upper() == "MENSAGEM:":
                restante = restante[1:]
            mensagem = "\n".join(restante).strip()
            break

    if not assunto:
        assunto = "Comunicado do gestor"
    if not mensagem:
        mensagem = resposta_normalizada

    if mensagem.upper().startswith("MENSAGEM:"):
        mensagem = mensagem.split(":", 1)[1].strip()

    return assunto, mensagem


def obter_ip_local():
    conexao = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        conexao.connect(("8.8.8.8", 80))
        return conexao.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        conexao.close()


def renderizar_info_compartilhamento():
    ip_local = obter_ip_local()
    st.info(
        "Acesso da equipe na rede local: "
        f"http://{ip_local}:{PORTA_APP}"
    )


def renderizar_assinatura():
    st.markdown(
        """
        <style>
        .assinatura-app {
            margin-top: 6px;
            font-size: 12px;
            line-height: 1;
            color: rgba(255, 255, 255, 0.82);
            font-family: "Brush Script MT", "Segoe Script", cursive;
            text-align: left;
            pointer-events: none;
        }
        </style>
        <div class="assinatura-app">Rony Franzini 2026</div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_mensagem_rodape():
    mensagem = st.session_state.pop(CHAVE_MENSAGEM_RODAPE, None)
    if not mensagem:
        return

    tipo = mensagem.get("tipo", "info")
    texto = mensagem.get("texto", "")
    if hasattr(st, tipo):
        getattr(st, tipo)(texto)
    else:
        st.info(texto)


def carregar_opcoes_calendario():
    with CAMINHO_CALENDARIO.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def normalizar_setor_id(valor):
    return str(valor).strip().lower().replace(" ", "-")


def mapa_setores(calendar_options=None):
    opcoes = calendar_options or carregar_opcoes_calendario()
    mapa = {SEM_EQUIPE_ID: SEM_EQUIPE_ID}
    for recurso in opcoes.get("resources", []):
        setor_nome = recurso.get("building") or recurso.get("title") or recurso.get("id")
        setor_id = normalizar_setor_id(setor_nome)
        for chave in {recurso.get("id"), recurso.get("title"), recurso.get("building"), setor_id}:
            if chave:
                mapa[str(chave)] = setor_id
    return mapa


def normalizar_recurso_id(recurso_id, calendar_options=None):
    if not recurso_id:
        return SEM_EQUIPE_ID
    return mapa_setores(calendar_options).get(str(recurso_id), str(recurso_id))


def recursos_calendario(calendar_options=None):
    opcoes = calendar_options or carregar_opcoes_calendario()
    recursos = []
    setores_adicionados = set()
    for recurso in opcoes.get("resources", []):
        setor_nome = recurso.get("building") or recurso.get("title") or recurso.get("id")
        setor_id = normalizar_setor_id(setor_nome)
        if setor_id in setores_adicionados:
            continue

        setores_adicionados.add(setor_id)
        recursos.append({
            "id": setor_id,
            "title": setor_nome,
            "building": recurso.get("building") or setor_nome,
        })

    if not any(recurso.get("id") == SEM_EQUIPE_ID for recurso in recursos):
        recursos.append({"id": SEM_EQUIPE_ID, "building": "Sem equipe", "title": "Sem equipe"})
    return recursos


def formatar_recurso(recurso):
    return recurso.get("title") or recurso.get("building") or str(recurso.get("id", "Sem equipe"))


def nome_recurso_por_id(recurso_id, recursos_por_id, calendar_options=None):
    recurso_normalizado = normalizar_recurso_id(recurso_id, calendar_options)
    recurso = recursos_por_id.get(recurso_normalizado or SEM_EQUIPE_ID)
    if recurso is None:
        return "Sem equipe"
    return formatar_recurso(recurso)


def recurso_usuario_timeline_id(usuario_id):
    return f"usuario-{usuario_id}"


def usuario_id_por_recurso_timeline(recurso_id):
    prefixo = "usuario-"
    if not recurso_id or not str(recurso_id).startswith(prefixo):
        return None
    try:
        return int(str(recurso_id).removeprefix(prefixo))
    except ValueError:
        return None


def recursos_timeline_por_usuario(usuarios, recursos_por_id, calendar_options):
    recursos = []
    for usuario in usuarios:
        setor_id = normalizar_recurso_id(usuario.recurso_id, calendar_options)
        recursos.append(
            {
                "id": recurso_usuario_timeline_id(usuario.id),
                "title": usuario.nome,
                "building": nome_recurso_por_id(setor_id, recursos_por_id, calendar_options),
            }
        )
    return recursos


def usuarios_por_nome():
    usuarios = ler_todos_usuarios()
    return {usuario.nome: usuario for usuario in usuarios}


def converter_data(valor):
    if hasattr(valor, "strftime"):
        return valor
    return datetime.strptime(valor, FORMATO_DATA).date()


def converter_data_iso(valor):
    if hasattr(valor, "strftime"):
        return valor.strftime(FORMATO_DATA)
    return valor


def formatar_data_br(valor):
    if not valor:
        return ""

    if hasattr(valor, "strftime"):
        return valor.strftime(FORMATO_DATA_BR)

    return datetime.strptime(valor, FORMATO_DATA).strftime(FORMATO_DATA_BR)


def definir_tela_gestor(tela):
    st.session_state[CHAVE_TELA_GESTOR] = tela
    st.session_state[CHAVE_PAGINA_GESTAO] = tela == "gestao"


def iterar_datas_periodo(data_inicio, data_fim):
    inicio = converter_data(data_inicio)
    fim = converter_data(data_fim)
    total_dias = (fim - inicio).days
    for deslocamento in range(total_dias + 1):
        yield inicio + pd.Timedelta(days=deslocamento)


def construir_registros_dashboard(usuarios, recursos_por_id, calendar_options):
    hoje = datetime.now().date()
    registros = []

    for usuario in usuarios:
        setor_id = normalizar_recurso_id(usuario.recurso_id, calendar_options)
        setor_nome = nome_recurso_por_id(setor_id, recursos_por_id, calendar_options)
        saldo = usuario.dias_para_solicitar()

        for evento in usuario.eventos_ferias:
            inicio_evento = converter_data(evento.inicio_ferias)
            fim_evento = converter_data(evento.fim_ferias)
            if fim_evento < hoje:
                continue

            inicio_evento = max(inicio_evento, hoje)
            for data_evento in iterar_datas_periodo(inicio_evento, fim_evento):
                registros.append(
                    {
                        "data": pd.Timestamp(data_evento),
                        "mes": pd.Timestamp(data_evento).strftime("%m/%Y"),
                        "setor": setor_nome,
                        "usuario": usuario.nome,
                        "tipo": evento.tipo,
                        "saldo_disponivel": saldo,
                    }
                )

    return pd.DataFrame(registros)


def pagina_dashboard_gestor():
    st.subheader("Dashboard do gestor")
    st.caption("Resumo de férias e ausências futuras para apoiar a prevenção de absenteísmo.")

    usuarios = ler_todos_usuarios()
    calendar_options = carregar_opcoes_calendario()
    recursos = recursos_calendario(calendar_options)
    recursos_por_id = {recurso["id"]: recurso for recurso in recursos}
    dashboard_df = construir_registros_dashboard(usuarios, recursos_por_id, calendar_options)

    usuarios_sem_saldo = []
    for usuario in usuarios:
        saldo = usuario.dias_para_solicitar()
        if saldo < 10:
            usuarios_sem_saldo.append(
                {
                    "Funcionário": usuario.nome,
                    "Setor": nome_recurso_por_id(
                        normalizar_recurso_id(usuario.recurso_id, calendar_options),
                        recursos_por_id,
                        calendar_options,
                    ),
                    "Saldo disponível": saldo,
                }
            )

    total_ausencias = int(len(dashboard_df)) if not dashboard_df.empty else 0
    total_ferias = int((dashboard_df["tipo"] == TIPO_FERIAS).sum()) if not dashboard_df.empty else 0

    if dashboard_df.empty:
        setor_critico = "Sem ausências futuras"
    else:
        setor_critico = (
            dashboard_df.groupby("setor").size().sort_values(ascending=False).index[0]
        )

    col1, col2, col3 = st.columns(3)
    col1.metric("Dias futuros de ausência", total_ausencias)
    col2.metric("Dias futuros de férias", total_ferias)
    col3.metric("Setor mais impactado", setor_critico)

    st.divider()

    col_grafico, col_alertas = st.columns([0.6, 0.4])

    with col_grafico:
        st.markdown("#### Férias agendadas por mês")
        if dashboard_df.empty:
            st.info("Nenhuma ausência futura encontrada para compor o gráfico.")
        else:
            ferias_por_mes = (
                dashboard_df[dashboard_df["tipo"] == TIPO_FERIAS]
                .groupby("mes")
                .agg(dias_agendados=("data", "count"), colaboradores=("usuario", "nunique"))
                .reset_index()
            )
            if ferias_por_mes.empty:
                st.info("Nenhuma férias futura cadastrada no momento.")
            else:
                ferias_por_mes["ordem"] = pd.to_datetime(ferias_por_mes["mes"], format="%m/%Y")
                ferias_por_mes = ferias_por_mes.sort_values("ordem").drop(columns="ordem")
                st.bar_chart(ferias_por_mes.set_index("mes")["dias_agendados"], use_container_width=True)
                st.dataframe(ferias_por_mes, use_container_width=True, hide_index=True)

    with col_alertas:
        st.markdown("#### Pessoas sem saldo suficiente")
        st.caption("Considera saldo menor que 10 dias, abaixo do mínimo exigido para novas férias.")
        if usuarios_sem_saldo:
            st.dataframe(pd.DataFrame(usuarios_sem_saldo), use_container_width=True, hide_index=True)
        else:
            st.success("Nenhum funcionário com saldo insuficiente no momento.")

    st.divider()
    st.markdown("#### Setores com maior concentração de ausências")
    if dashboard_df.empty:
        st.info("Sem dados futuros para consolidar setores.")
    else:
        setores_df = (
            dashboard_df.groupby("setor")
            .agg(
                dias_ausentes=("data", "count"),
                colaboradores_afetados=("usuario", "nunique"),
            )
            .reset_index()
            .sort_values(["dias_ausentes", "colaboradores_afetados"], ascending=[False, False])
        )
        st.bar_chart(setores_df.set_index("setor")["dias_ausentes"], use_container_width=True)
        st.dataframe(setores_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Insight executivo com IA (Groq)")
    st.caption("A IA analisa os indicadores acima e sugere prioridades de acao para o gestor.")

    if st.button("Gerar insight com IA", use_container_width=True):
        contexto = {
            "data_referencia": datetime.now().strftime("%Y-%m-%d"),
            "total_dias_ausencia": total_ausencias,
            "total_dias_ferias": total_ferias,
            "setor_mais_impactado": setor_critico,
            "setores": [] if dashboard_df.empty else dashboard_df.groupby("setor").size().sort_values(ascending=False).to_dict(),
            "usuarios_com_saldo_insuficiente": [item["Funcionário"] for item in usuarios_sem_saldo],
        }
        try:
            st.session_state["dashboard_insight_ia"] = gerar_resumo_dashboard_ia(
                contexto_dashboard=contexto,
                chave_api=obter_chave_api_groq_streamlit(),
            )
        except GroqAIError as exc:
            st.error(str(exc))

    insight_ia = st.session_state.get("dashboard_insight_ia", "").strip()
    if insight_ia:
        st.markdown(insight_ia)


def limpar_datas():
    for chave in (CHAVE_DATA_INICIO, CHAVE_DATA_FINAL, CHAVE_FRACIONAR_FERIAS, CHAVE_PLANO_FRACIONAMENTO):
        st.session_state.pop(chave, None)


def limpar_gestao_ferias():
    for chave in (
        CHAVE_FERIAS_GESTOR,
        CHAVE_ULTIMO_CLICK,
        CHAVE_EDITOR_DATA_INICIO,
        CHAVE_EDITOR_DATA_FIM,
        CHAVE_EDITOR_TIPO,
        CHAVE_LISTA_RECURSO,
        CHAVE_LISTA_SETOR_FORM,
        CHAVE_LISTA_DATA_INICIO,
        CHAVE_LISTA_DATA_FIM,
        CHAVE_LISTA_USUARIO,
        CHAVE_LISTA_TIPO,
        "form_lista_data_inicio",
        "form_lista_data_fim",
    ):
        st.session_state.pop(chave, None)


def limpar_formulario_usuario(tipo_formulario):
    campos_por_formulario = {
        "criar": (
            "criar_nome",
            "criar_email",
            "criar_acesso_gestor",
            "criar_recurso_id",
            "criar_inicio_empresa",
            "criar_senha",
        ),
        "modificar": (
            "mod_usuario",
            "mod_nome",
            "mod_email",
            "mod_acesso_gestor",
            "mod_recurso_id",
            "mod_inicio_empresa",
            "mod_senha",
        ),
    }

    for chave in campos_por_formulario.get(tipo_formulario, ()):
        st.session_state.pop(chave, None)


def limpar_formulario_modificacao():
    limpar_formulario_usuario("modificar")
    st.session_state["mod_usuario"] = None
    st.session_state.pop(CHAVE_USUARIO_MOD_EM_EDICAO, None)


def limpar_formulario_email():
    for chave in (
        "email_modo_envio",
        "email_remetente",
        "email_destinatario",
        "email_assunto",
        "email_mensagem",
        "email_senha",
        "email_smtp_host",
        "email_smtp_port",
        "email_usuario_smtp",
        "email_tom_ia",
        "email_objetivo_ia",
        "email_assunto_pendente",
        "email_mensagem_pendente",
        "email_feedback_ia",
    ):
        st.session_state.pop(chave, None)


def renderizar_tab_envio_email(usuarios):
    gestor = st.session_state[CHAVE_USUARIO]
    usuarios_disponiveis = [usuario for usuario in usuarios if usuario.id != gestor.id]
    usuario_por_id = {usuario.id: usuario for usuario in usuarios_disponiveis}
    ids_usuarios = [usuario.id for usuario in usuarios_disponiveis]

    if ids_usuarios and st.session_state.get(CHAVE_EMAIL_DESTINATARIO) not in ids_usuarios:
        st.session_state[CHAVE_EMAIL_DESTINATARIO] = ids_usuarios[0]

    st.session_state.setdefault("email_remetente", gestor.email)
    st.session_state.setdefault("email_destinatario", "")
    st.session_state.setdefault("email_assunto", "")
    st.session_state.setdefault("email_mensagem", "")
    st.session_state.setdefault("email_usuario_smtp", gestor.email)
    st.session_state.setdefault("email_tom_ia", "Profissional e cordial")
    st.session_state.setdefault("email_objetivo_ia", "")

    assunto_pendente = st.session_state.pop("email_assunto_pendente", None)
    mensagem_pendente = st.session_state.pop("email_mensagem_pendente", None)
    if assunto_pendente is not None:
        st.session_state["email_assunto"] = assunto_pendente
    if mensagem_pendente is not None:
        st.session_state["email_mensagem"] = mensagem_pendente

    feedback_ia = st.session_state.pop("email_feedback_ia", "")
    if feedback_ia:
        st.success(feedback_ia)

    if st.session_state.get("email_modo_envio") not in {"Outlook Desktop", "SMTP"}:
        st.session_state["email_modo_envio"] = "SMTP"

    if ids_usuarios and not st.session_state.get("email_destinatario"):
        primeiro_usuario = usuario_por_id[st.session_state[CHAVE_EMAIL_DESTINATARIO]]
        st.session_state["email_destinatario"] = primeiro_usuario.email

    st.caption("Envio de e-mail com remetente e destinatario livres.")
    st.caption("Os dominios grupocasasbahia.com.br, viavarejo.com.br e casasbahia.com.br usam Office 365 por padrao.")

    with st.form("form_enviar_email_gestor"):
        modo_envio = st.radio(
            "Modo de envio",
            ["Outlook Desktop", "SMTP"],
            horizontal=True,
            key="email_modo_envio",
        )
        remetente = st.text_input("E-mail remetente", key="email_remetente")
        if ids_usuarios:
            usuario_id = st.selectbox(
                "Preencher com funcionario cadastrado",
                ids_usuarios,
                format_func=lambda valor: usuario_por_id[valor].nome,
                key=CHAVE_EMAIL_DESTINATARIO,
            )
            funcionario = usuario_por_id[usuario_id]
            usar_email_funcionario = st.form_submit_button(
                "Usar e-mail do funcionario selecionado",
                use_container_width=True,
            )
            if usar_email_funcionario:
                st.session_state["email_destinatario"] = funcionario.email
                st.rerun()
        destinatario = st.text_input("E-mail destinatario", key="email_destinatario")
        assunto = st.text_input("Assunto", key="email_assunto")
        mensagem = st.text_area("Mensagem", key="email_mensagem", height=180)
        tom_ia = st.selectbox(
            "Tom sugerido pela IA",
            ["Profissional e cordial", "Direto e objetivo", "Empatico e acolhedor"],
            key="email_tom_ia",
        )
        objetivo_ia = st.text_input(
            "Objetivo opcional para IA (ex: confirmar periodo de ferias)",
            key="email_objetivo_ia",
        )
        senha = ""
        smtp_host = None
        smtp_porto = None
        usar_tls = True

        if modo_envio == "SMTP":
            senha = st.text_input(
                "Senha/App password do e-mail remetente",
                type="password",
                key="email_senha",
            )
            with st.expander("Configuracao SMTP avancada"):
                st.text_input(
                    "Usuario de login SMTP",
                    key="email_usuario_smtp",
                    help="Use este campo se o login SMTP for diferente do e-mail remetente informado acima.",
                )
                smtp_host = st.text_input(
                    "Servidor SMTP",
                    key="email_smtp_host",
                    placeholder="Deixe em branco para detectar automaticamente",
                )
                smtp_porto = st.text_input(
                    "Porta SMTP",
                    key="email_smtp_port",
                    placeholder="587",
                )
                usar_tls = st.checkbox("Usar TLS", value=True, key="email_smtp_tls")
        else:
            st.info(
                "O Outlook Desktop precisa estar configurado na maquina com essa conta. "
                "Para conta corporativa, o modo rascunho costuma ser o caminho mais confiavel."
            )

        enviar = st.form_submit_button("Enviar e-mail", use_container_width=True)
        gerar_ia = st.form_submit_button("Gerar assunto e mensagem com IA", use_container_width=True)

    if gerar_ia:
        try:
            contexto_email = {
                "gestor": gestor.nome,
                "remetente": remetente,
                "destinatario": destinatario,
                "assunto_atual": assunto,
                "mensagem_atual": mensagem,
                "tom": tom_ia,
                "objetivo": objetivo_ia,
            }
            resposta_ia = gerar_rascunho_email_ia(
                contexto_email=contexto_email,
                chave_api=obter_chave_api_groq_streamlit(),
            )
            assunto_ia, mensagem_ia = extrair_assunto_mensagem_ia(resposta_ia)
            st.session_state["email_assunto_pendente"] = assunto_ia
            st.session_state["email_mensagem_pendente"] = mensagem_ia
            st.session_state["email_feedback_ia"] = "Rascunho gerado com IA. Revise antes de enviar."
            st.rerun()
        except GroqAIError as exc:
            st.error(str(exc))

    if enviar:
        try:
            if modo_envio == "Outlook Desktop":
                enviar_email_outlook(
                    remetente=remetente,
                    destinatario=destinatario,
                    assunto=assunto,
                    mensagem=mensagem,
                )
            else:
                enviar_email(
                    remetente=remetente,
                    senha=senha,
                    destinatario=destinatario,
                    assunto=assunto,
                    mensagem=mensagem,
                    smtp_host=(smtp_host or "").strip() or None,
                    smtp_port=(smtp_porto or "").strip() or None,
                    usar_tls=usar_tls,
                    usuario_smtp=st.session_state.get("email_usuario_smtp"),
                )
        except EmailEnvioError as exc:
            st.error(str(exc))
            if modo_envio == "SMTP":
                st.info(
                    "Se a conta for Microsoft 365 corporativa, teste com a senha real da conta corporativa ou app password. "
                    "Se o login SMTP for diferente do remetente, preencha o campo de login SMTP na configuracao avancada."
                )
            else:
                st.info(
                    "Confirme que o Outlook Desktop esta instalado, aberto e com a conta remetente configurada no perfil atual do Windows."
                )
        else:
            st.success(f"E-mail enviado com sucesso para {destinatario}.")
            limpar_formulario_email()


def sincronizar_formulario_modificacao(usuario, recurso_id_padrao):
    usuario_id_atual = st.session_state.get(CHAVE_USUARIO_MOD_EM_EDICAO)
    if usuario_id_atual == usuario.id:
        return

    st.session_state[CHAVE_USUARIO_MOD_EM_EDICAO] = usuario.id
    st.session_state["mod_nome"] = usuario.nome
    st.session_state["mod_email"] = usuario.email
    st.session_state["mod_acesso_gestor"] = usuario.acesso_gestor
    st.session_state["mod_recurso_id"] = recurso_id_padrao
    st.session_state["mod_inicio_empresa"] = converter_data(usuario.inicio_na_empresa)
    st.session_state["mod_senha"] = ""


def campos_usuario_validos(nome, email, senha=None, exigir_senha=False):
    if not nome.strip():
        st.error("Informe o nome do usuário.")
        return False

    if not email.strip():
        st.error("Informe o e-mail do usuário.")
        return False

    if exigir_senha and not senha:
        st.error("Informe uma senha para o usuário.")
        return False

    return True


def calcular_dias_consumidos_ferias(total_dias, fracionar_ferias):
    if fracionar_ferias:
        return total_dias

    if total_dias in (15, 20):
        # Sem fracionamento, 15 ou 20 dias implicam venda do restante para fechar 30.
        return 30

    return total_dias


def dias_validos_por_plano_fracionamento(plano):
    opcoes = {
        "10 + 10 + 10": {10},
        "10 + 20": {10, 20},
        "15 + 15": {15},
    }
    return opcoes.get(plano, set())


def validar_periodo_ferias(usuario, data_inicio, data_fim, dias_ja_reservados=0, dias_consumidos=None):
    data_inicio_iso = converter_data_iso(data_inicio)
    data_fim_iso = converter_data_iso(data_fim)
    total_dias = (
        datetime.strptime(data_fim_iso, FORMATO_DATA)
        - datetime.strptime(data_inicio_iso, FORMATO_DATA)
    ).days + 1

    if total_dias <= 0:
        definir_mensagem_rodape("error", "A data final deve ser igual ou posterior à data inicial.")
        return None

    if total_dias < 10:
        definir_mensagem_rodape("error", "O período mínimo para solicitar férias é de 10 dias.")
        return None

    dias_para_validacao = total_dias if dias_consumidos is None else int(dias_consumidos)
    dias_disponiveis = usuario.dias_para_solicitar() + dias_ja_reservados
    if dias_disponiveis < dias_para_validacao:
        mensagem_consumo = ""
        if dias_para_validacao != total_dias:
            mensagem_consumo = f" (esta solicitacao consome {dias_para_validacao} dias)"
        definir_mensagem_rodape(
            "error",
            f"Você solicitou {total_dias} dias{mensagem_consumo}, mas o usuário possui apenas {dias_disponiveis} dias disponíveis no ano.",
        )
        return None

    return data_inicio_iso, data_fim_iso, total_dias


def validar_periodo_ocorrencia(usuario, data_inicio, data_fim, tipo, dias_ja_reservados=0, dias_consumidos=None):
    if tipo == TIPO_FERIAS:
        return validar_periodo_ferias(
            usuario,
            data_inicio,
            data_fim,
            dias_ja_reservados=dias_ja_reservados,
            dias_consumidos=dias_consumidos,
        )

    data_inicio_iso = converter_data_iso(data_inicio)
    data_fim_iso = converter_data_iso(data_fim)
    total_dias = (
        datetime.strptime(data_fim_iso, FORMATO_DATA)
        - datetime.strptime(data_inicio_iso, FORMATO_DATA)
    ).days + 1

    if total_dias <= 0:
        definir_mensagem_rodape("error", "A data final deve ser igual ou posterior à data inicial.")
        return None

    return data_inicio_iso, data_fim_iso, total_dias


def renderizar_gestao_ferias_gestor(calendar_events, usuarios, recursos_por_id, calendar_options):
    with st.expander("Gerenciar lista do setor"):
        usuarios_por_id = {usuario.id: usuario for usuario in usuarios}
        eventos_por_id = {evento["id"]: evento for evento in calendar_events}
        evento_id = st.session_state.get(CHAVE_FERIAS_GESTOR)

        if not calendar_events:
            definir_mensagem_rodape("info", "Nenhuma ocorrência cadastrada para editar no momento.")

        if evento_id is not None and evento_id in eventos_por_id:
            evento = eventos_por_id[evento_id]
            dados_evento = evento["extendedProps"]
            usuario_alvo = usuarios_por_id[dados_evento["usuario_id"]]
            st.subheader("Editar ocorrência")
            st.caption(
                f"Período selecionado: {formatar_data_br(evento['start'])} até {formatar_data_br(evento['end'])}"
            )
            st.caption(
                f"Funcionário: {usuario_alvo.nome} | Setor: {nome_recurso_por_id(dados_evento['recurso_id'], recursos_por_id, calendar_options)}"
            )

            tipos_ocorrencia = list(TIPOS_OCORRENCIA.keys())
            with st.form("form_gerenciar_ferias"):
                tipo_ocorrencia = st.selectbox(
                    "Tipo de ocorrência",
                    tipos_ocorrencia,
                    index=tipos_ocorrencia.index(dados_evento["tipo"]),
                    format_func=lambda valor: TIPOS_OCORRENCIA[valor],
                    key=CHAVE_EDITOR_TIPO,
                )
                nova_data_inicio = st.date_input(
                    "Nova data de início",
                    value=converter_data(evento["start"]),
                    key=CHAVE_EDITOR_DATA_INICIO,
                    format="DD/MM/YYYY",
                )
                nova_data_fim = st.date_input(
                    "Nova data final",
                    value=converter_data(evento["end"]),
                    key=CHAVE_EDITOR_DATA_FIM,
                    format="DD/MM/YYYY",
                )
                col_alterar, col_limpar = st.columns(2)
                with col_alterar:
                    alterar = st.form_submit_button("Alterar ocorrência", use_container_width=True)
                with col_limpar:
                    limpar = st.form_submit_button("Limpar ocorrência", use_container_width=True)

            if alterar:
                periodo_validado = validar_periodo_ocorrencia(
                    usuario_alvo,
                    nova_data_inicio,
                    nova_data_fim,
                    tipo_ocorrencia,
                    dias_ja_reservados=dados_evento.get("dias_consumidos", dados_evento["total_dias"])
                    if dados_evento["tipo"] == TIPO_FERIAS
                    else 0,
                )
                if periodo_validado is not None:
                    data_inicio_iso, data_fim_iso, _ = periodo_validado
                    atualizar_ferias(
                        int(evento_id),
                        data_inicio_iso,
                        data_fim_iso,
                        tipo=tipo_ocorrencia,
                    )
                    definir_mensagem_rodape("success", "Ocorrência alterada com sucesso.")
                    limpar_gestao_ferias()
                    recarregar()

            if limpar:
                deletar_ferias(int(evento_id))
                definir_mensagem_rodape("success", "Ocorrência removida com sucesso.")
                limpar_gestao_ferias()
                recarregar()
        elif evento_id is not None:
            limpar_gestao_ferias()
            definir_mensagem_rodape("info", "Seleção limpa porque a ocorrência não está mais disponível.")

        st.divider()
        st.subheader("Adicionar ocorrência")
        recurso_id = st.session_state.get(CHAVE_LISTA_RECURSO)
        data_inicio = st.session_state.get(CHAVE_LISTA_DATA_INICIO)
        data_fim = st.session_state.get(CHAVE_LISTA_DATA_FIM)
        usuario_preselecionado = usuarios_por_id.get(st.session_state.get(CHAVE_LISTA_USUARIO))

        setores_disponiveis = list(recursos_por_id.keys())
        if recurso_id is None and usuario_preselecionado is not None:
            recurso_id = normalizar_recurso_id(usuario_preselecionado.recurso_id, calendar_options)
        setor_padrao = recurso_id if recurso_id in recursos_por_id else setores_disponiveis[0]
        setor_form_atual = st.session_state.get(CHAVE_LISTA_RECURSO)
        if setor_form_atual is not None:
            setor_form_atual = normalizar_recurso_id(setor_form_atual, calendar_options)

        if setor_form_atual not in setores_disponiveis:
            st.session_state[CHAVE_LISTA_RECURSO] = setor_padrao
        else:
            st.session_state[CHAVE_LISTA_RECURSO] = setor_form_atual

        st.session_state.pop(CHAVE_LISTA_SETOR_FORM, None)

        if recurso_id is not None and data_inicio is not None:
            st.caption(
                f"Seleção rápida da lista: {nome_recurso_por_id(recurso_id, recursos_por_id, calendar_options)} | "
                f"{formatar_data_br(data_inicio)}"
                + (f" até {formatar_data_br(data_fim)}" if data_fim else "")
            )
        else:
            definir_mensagem_rodape(
                "info",
                "Você pode usar o clique na lista como atalho, ou preencher o formulário abaixo diretamente.",
            )

        setor_form = st.selectbox(
            "Setor",
            setores_disponiveis,
            format_func=lambda valor: nome_recurso_por_id(valor, recursos_por_id, calendar_options),
            key=CHAVE_LISTA_RECURSO,
        )

        usuarios_disponiveis = [
            usuario
            for usuario in usuarios
            if normalizar_recurso_id(usuario.recurso_id, calendar_options) == setor_form
        ]
        if (
            usuario_preselecionado is not None
            and normalizar_recurso_id(usuario_preselecionado.recurso_id, calendar_options) == setor_form
            and all(usuario.id != usuario_preselecionado.id for usuario in usuarios_disponiveis)
        ):
            usuarios_disponiveis.insert(0, usuario_preselecionado)

        usuario_ids_disponiveis = [usuario.id for usuario in usuarios_disponiveis]

        if st.session_state.get(CHAVE_LISTA_USUARIO) not in usuario_ids_disponiveis:
            if (
                usuario_preselecionado is not None
                and usuario_preselecionado.id in usuario_ids_disponiveis
            ):
                st.session_state[CHAVE_LISTA_USUARIO] = usuario_preselecionado.id
            else:
                st.session_state.pop(CHAVE_LISTA_USUARIO, None)

        if not usuarios_disponiveis:
            definir_mensagem_rodape(
                "info",
                "Nenhum usuário vinculado a esse setor. Defina o setor no cadastro do usuário.",
            )
            if st.button("Limpar seleção da lista", use_container_width=True):
                limpar_gestao_ferias()
                st.rerun()
            return

        data_inicial_padrao = converter_data(data_inicio) if data_inicio else datetime.now().date()
        data_final_padrao = converter_data(data_fim or data_inicio) if (data_fim or data_inicio) else datetime.now().date()

        with st.form("form_criar_ocorrencia_lista"):
            usuario_id = st.selectbox(
                "Funcionário",
                usuario_ids_disponiveis,
                format_func=lambda valor: usuarios_por_id[valor].nome,
                key=CHAVE_LISTA_USUARIO,
            )
            tipo_ocorrencia = st.selectbox(
                "Tipo de ocorrência",
                list(TIPOS_OCORRENCIA.keys()),
                format_func=lambda valor: TIPOS_OCORRENCIA[valor],
                key=CHAVE_LISTA_TIPO,
            )
            data_inicio_form = st.date_input(
                "Data inicial",
                value=data_inicial_padrao,
                key="form_lista_data_inicio",
                format="DD/MM/YYYY",
            )
            data_fim_form = st.date_input(
                "Data final",
                value=data_final_padrao,
                key="form_lista_data_fim",
                format="DD/MM/YYYY",
            )

            fracionar_lista = False
            plano_fracionamento_lista = None
            if tipo_ocorrencia == TIPO_FERIAS:
                fracionar_lista = st.radio(
                    "Fracionar férias?",
                    options=("Sim", "Não"),
                    horizontal=True,
                    key="form_lista_fracionar",
                ) == "Sim"
                if fracionar_lista:
                    plano_fracionamento_lista = st.selectbox(
                        "Plano de fracionamento",
                        options=["10 + 10 + 10", "10 + 20", "15 + 15"],
                        key="form_lista_plano",
                    )

            registrar = st.form_submit_button("Registrar ocorrência", use_container_width=True)

        if registrar:
            usuario_alvo = usuarios_por_id[usuario_id]
            dias_consumidos_lista = None
            if tipo_ocorrencia == TIPO_FERIAS:
                total_dias_lista = (
                    datetime.strptime(converter_data_iso(data_fim_form), FORMATO_DATA)
                    - datetime.strptime(converter_data_iso(data_inicio_form), FORMATO_DATA)
                ).days + 1

                if fracionar_lista and plano_fracionamento_lista:
                    dias_validos = dias_validos_por_plano_fracionamento(plano_fracionamento_lista)
                    if dias_validos and total_dias_lista not in dias_validos:
                        definir_mensagem_rodape(
                            "error",
                            f"Com o plano {plano_fracionamento_lista}, o período atual deve ter {', '.join(str(dia) for dia in sorted(dias_validos))} dias.",
                        )
                        renderizar_mensagem_rodape()
                        return

                dias_consumidos_lista = calcular_dias_consumidos_ferias(total_dias_lista, fracionar_lista)

            periodo_validado = validar_periodo_ocorrencia(
                usuario_alvo,
                data_inicio_form,
                data_fim_form,
                tipo_ocorrencia,
                dias_consumidos=dias_consumidos_lista,
            )
            if periodo_validado is not None:
                data_inicio_iso, data_fim_iso, _ = periodo_validado
                usuario_alvo.adiciona_ferias(
                    data_inicio_iso,
                    data_fim_iso,
                    tipo=tipo_ocorrencia,
                    dias_consumidos=dias_consumidos_lista,
                )
                definir_mensagem_rodape("success", "Ocorrência registrada com sucesso.")
                limpar_gestao_ferias()
                recarregar()

        if st.button("Limpar seleção da lista", use_container_width=True):
            limpar_gestao_ferias()
            st.rerun()

        renderizar_mensagem_rodape()


def login():
    usuarios = usuarios_por_nome()
    if not usuarios:
        st.warning("Nenhum usuário cadastrado. Crie um usuário no banco para acessar o sistema.")
        return

    with st.container(border=True):
        st.markdown("Agendamento de Férias!")
        nome_usuario = st.selectbox("Selecione seu nome", list(usuarios.keys()))
        senha = st.text_input("Digite sua senha", type="password")

        if st.button("Acessar", use_container_width=True):
            usuario = usuarios[nome_usuario]
            if usuario.verifica_senha(senha):
                st.success("Login bem-sucedido.")
                st.session_state[CHAVE_LOGADO] = True
                st.session_state[CHAVE_USUARIO] = usuario
                recarregar()
            else:
                st.error("Senha incorreta.")

        renderizar_assinatura()

    renderizar_info_compartilhamento()


def pagina_gestao():
    ano_atual = datetime.now().year
    ano_anterior = ano_atual - 1

    with st.sidebar:
        tab_gestao_usuarios()

    for usuario in ler_todos_usuarios():
        _, tirados_ant, _ = usuario.dias_por_ano(ano_anterior)
        direito_atual, tirados_atual, disponivel_atual = usuario.dias_por_ano(ano_atual)

        with st.container(border=True):
            col_nome, col_ant, col_atual, col_disp = st.columns([2, 1, 1, 1])

            with col_nome:
                if disponivel_atual < 10:
                    st.error(f"##### {usuario.nome}")
                else:
                    st.markdown(f"##### {usuario.nome}")

            with col_ant:
                st.metric(
                    label=f"Usado em {ano_anterior}",
                    value=f"{tirados_ant} dias",
                )

            with col_atual:
                st.metric(
                    label=f"Usado em {ano_atual}",
                    value=f"{tirados_atual} dias",
                    delta=f"{tirados_atual - tirados_ant:+d} vs {ano_anterior}",
                    delta_color="inverse",
                )

            with col_disp:
                label_disp = f"Disponível {ano_atual} (de {direito_atual})"
                if disponivel_atual < 10:
                    st.error(f"**{label_disp}:** {disponivel_atual} dias")
                elif disponivel_atual > direito_atual * 0.8:
                    st.warning(f"**{label_disp}:** {disponivel_atual} dias")
                else:
                    st.success(f"**{label_disp}:** {disponivel_atual} dias")


def tab_gestao_usuarios():
    tab_vis, tab_cria, tab_mod, tab_del, tab_email = st.tabs(["Visualizar", "Criar", "Modificar", "Deletar", "E-mail"])

    usuarios = ler_todos_usuarios()
    recursos = recursos_calendario()
    recursos_por_id = {recurso["id"]: recurso for recurso in recursos}
    opcoes_recurso = [recurso["id"] for recurso in recursos]
    calendar_options = carregar_opcoes_calendario()

    with tab_vis:
        dados_usuarios = [
            {
                "id": usuario.id,
                "nome": usuario.nome,
                "email": usuario.email,
                "acesso_gestor": usuario.acesso_gestor,
                "inicio_na_empresa": formatar_data_br(usuario.inicio_na_empresa),
                "setor": nome_recurso_por_id(usuario.recurso_id, recursos_por_id, calendar_options),
            }
            for usuario in usuarios
        ]
        if dados_usuarios:
            st.dataframe(pd.DataFrame(dados_usuarios).set_index("id"), use_container_width=True)
        else:
            st.info("Nenhum usuário cadastrado.")

    with tab_cria:
        with st.form("form_criar_usuario", clear_on_submit=True):
            nome = st.text_input("Nome", key="criar_nome")
            email = st.text_input("Email", key="criar_email")
            acesso_gestor = st.checkbox("Acesso Gestor", value=False, key="criar_acesso_gestor")
            recurso_id = st.selectbox(
                "Setor",
                opcoes_recurso,
                format_func=lambda valor: nome_recurso_por_id(valor, recursos_por_id, calendar_options),
                key="criar_recurso_id",
            )
            inicio_na_empresa = st.date_input("Início na empresa", key="criar_inicio_empresa", format="DD/MM/YYYY")
            senha = st.text_input("Senha", type="password", key="criar_senha")
            criar = st.form_submit_button("Criar Usuário", use_container_width=True)

        if criar:
            if campos_usuario_validos(nome, email, senha=senha, exigir_senha=True):
                try:
                    criar_usuario(
                        nome=nome.strip(),
                        senha=senha,
                        email=email.strip(),
                        acesso_gestor=acesso_gestor,
                        recurso_id=normalizar_recurso_id(recurso_id, calendar_options),
                        inicio_na_empresa=inicio_na_empresa,
                    )
                except EmailJaCadastradoError as exc:
                    st.error(str(exc))
                else:
                    st.success("Usuário criado com sucesso.")
                    limpar_formulario_usuario("criar")
                    recarregar()

    with tab_mod:
        usuario_dict = {usuario.nome: usuario for usuario in usuarios}
        if not usuario_dict:
            st.info("Nenhum usuário disponível para modificação.")
        else:
            nomes_usuarios = list(usuario_dict.keys())
            nome_usuario = st.selectbox(
                "Selecione o usuário para modificar",
                nomes_usuarios,
                index=None,
                placeholder="Escolha um usuário",
                key="mod_usuario",
            )

            if nome_usuario is not None:
                usuario = usuario_dict[nome_usuario]
                recurso_id_padrao = normalizar_recurso_id(usuario.recurso_id, calendar_options)
                sincronizar_formulario_modificacao(usuario, recurso_id_padrao)
                with st.form("form_modificar_usuario"):
                    nome = st.text_input("Nome", key="mod_nome")
                    email = st.text_input("Email", key="mod_email")
                    acesso_gestor = st.checkbox(
                        "Modificar Acesso Gestor",
                        key="mod_acesso_gestor",
                    )
                    recurso_id = st.selectbox(
                        "Setor",
                        opcoes_recurso,
                        format_func=lambda valor: nome_recurso_por_id(valor, recursos_por_id, calendar_options),
                        key="mod_recurso_id",
                    )
                    inicio_na_empresa = st.date_input(
                        "Início na empresa",
                        key="mod_inicio_empresa",
                        format="DD/MM/YYYY",
                    )
                    senha = st.text_input(
                        "Nova senha",
                        type="password",
                        key="mod_senha",
                        help="Deixe em branco para manter a senha atual.",
                    )
                    modificar = st.form_submit_button("Modificar Usuário", use_container_width=True)

                if modificar and campos_usuario_validos(nome, email):
                    dados_usuario = {
                        "nome": nome.strip(),
                        "email": email.strip(),
                        "acesso_gestor": acesso_gestor,
                        "recurso_id": normalizar_recurso_id(recurso_id, calendar_options),
                        "inicio_na_empresa": inicio_na_empresa,
                    }
                    if senha:
                        dados_usuario["senha"] = senha

                    try:
                        modificar_usuario(id=usuario.id, **dados_usuario)
                    except EmailJaCadastradoError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Usuário modificado com sucesso.")
                        limpar_formulario_modificacao()
                        recarregar()

    with tab_del:
        usuario_dict = {usuario.nome: usuario for usuario in usuarios}
        if not usuario_dict:
            st.info("Nenhum usuário disponível para exclusão.")
        else:
            nome_usuario = st.selectbox("Selecione o usuário para deletar", usuario_dict.keys(), key="del_usuario")
            usuario = usuario_dict[nome_usuario]

            if st.button("Deletar Usuário", use_container_width=True):
                deletar_usuario(id=usuario.id)
                st.success("Usuário deletado com sucesso.")
                recarregar()

    with tab_email:
        renderizar_tab_envio_email(usuarios)

def verifica_adiciona_ferias(data_inicio, data_fim, fracionar_ferias, plano_fracionamento=None):
    usuario = st.session_state[CHAVE_USUARIO]
    total_dias = (
        datetime.strptime(converter_data_iso(data_fim), FORMATO_DATA)
        - datetime.strptime(converter_data_iso(data_inicio), FORMATO_DATA)
    ).days + 1

    if fracionar_ferias and plano_fracionamento:
        dias_validos = dias_validos_por_plano_fracionamento(plano_fracionamento)
        if dias_validos and total_dias not in dias_validos:
            definir_mensagem_rodape(
                "error",
                f"Com o plano {plano_fracionamento}, o período atual deve ter {', '.join(str(dia) for dia in sorted(dias_validos))} dias.",
            )
            return

    dias_consumidos = calcular_dias_consumidos_ferias(total_dias, fracionar_ferias)
    periodo_validado = validar_periodo_ferias(
        usuario,
        data_inicio,
        data_fim,
        dias_consumidos=dias_consumidos,
    )
    if periodo_validado is not None:
        data_inicio_iso, data_fim_iso, _ = periodo_validado
        usuario.adiciona_ferias(data_inicio_iso, data_fim_iso, dias_consumidos=dias_consumidos)
        definir_mensagem_rodape("success", "Férias adicionadas com sucesso.")
        limpar_datas()


def pagina_calendario():
    calendar_options = carregar_opcoes_calendario()
    usuarios = ler_todos_usuarios()
    recursos_setor = recursos_calendario(calendar_options)
    recursos_por_id = {recurso["id"]: recurso for recurso in recursos_setor}
    calendar_options["resources"] = recursos_timeline_por_usuario(usuarios, recursos_por_id, calendar_options)
    usuarios_por_id = {usuario.id: usuario for usuario in usuarios}
    calendar_events = []
    for usuario in usuarios:
        eventos_usuario = usuario.lista_ferias()
        for evento in eventos_usuario:
            setor_id = normalizar_recurso_id(evento.get("resourceId"), calendar_options)
            evento["resourceId"] = recurso_usuario_timeline_id(usuario.id)
            evento.setdefault("extendedProps", {})["recurso_id"] = setor_id
            evento["title"] = f"{usuario.nome} | {TIPOS_OCORRENCIA.get(evento['extendedProps'].get('tipo'), 'Ocorrência')}"
        calendar_events.extend(eventos_usuario)

    usuario = st.session_state[CHAVE_USUARIO]

    with st.expander("Dias para solicitar"):
        dias_para_tirar = usuario.dias_para_solicitar()
        st.markdown(f"O funcionário {usuario.nome} possui {dias_para_tirar} dias disponíveis para solicitar.")

    calendar_widget = calendar(events=calendar_events, options=calendar_options, key="ferias_calendar")
    callback = calendar_widget.get("callback") if calendar_widget else None

    if callback == "dateClick":
        raw_date = calendar_widget["dateClick"]["date"]
        recurso = calendar_widget["dateClick"].get("resource") or {}
        recurso_id = recurso.get("id")
        usuario_lista_id = usuario_id_por_recurso_timeline(recurso_id)
        chave_clique = f"{raw_date}|{recurso_id or ''}"
        if chave_clique != st.session_state[CHAVE_ULTIMO_CLICK]:
            st.session_state[CHAVE_ULTIMO_CLICK] = chave_clique

            data_selecionada = raw_date.split("T")[0]
            if usuario.acesso_gestor and usuario_lista_id in usuarios_por_id:
                usuario_lista = usuarios_por_id[usuario_lista_id]
                setor_id = normalizar_recurso_id(usuario_lista.recurso_id, calendar_options)
                st.session_state[CHAVE_FERIAS_GESTOR] = None
                for chave in (CHAVE_EDITOR_DATA_INICIO, CHAVE_EDITOR_DATA_FIM, CHAVE_EDITOR_TIPO):
                    st.session_state.pop(chave, None)
                if (
                    st.session_state.get(CHAVE_LISTA_RECURSO) != setor_id
                    or CHAVE_LISTA_DATA_INICIO not in st.session_state
                    or st.session_state.get(CHAVE_LISTA_USUARIO) != usuario_lista_id
                ):
                    for chave in (CHAVE_LISTA_USUARIO, CHAVE_LISTA_TIPO, "form_lista_data_inicio", "form_lista_data_fim"):
                        st.session_state.pop(chave, None)
                    st.session_state[CHAVE_LISTA_RECURSO] = setor_id
                    st.session_state[CHAVE_LISTA_USUARIO] = usuario_lista_id
                    st.session_state[CHAVE_LISTA_DATA_INICIO] = data_selecionada
                    st.session_state.pop(CHAVE_LISTA_DATA_FIM, None)
                    definir_mensagem_rodape(
                        "info",
                        f"Membro selecionado: {usuario_lista.nome} | "
                        f"Setor: {nome_recurso_por_id(setor_id, recursos_por_id, calendar_options)} | "
                        f"Data inicial: {formatar_data_br(data_selecionada)}",
                    )
                else:
                    st.session_state[CHAVE_LISTA_DATA_FIM] = data_selecionada
                    definir_mensagem_rodape(
                        "info",
                        f"Período para {usuario_lista.nome}: {formatar_data_br(st.session_state[CHAVE_LISTA_DATA_INICIO])} até "
                        f"{formatar_data_br(data_selecionada)}",
                    )
            else:
                if CHAVE_DATA_INICIO not in st.session_state:
                    st.session_state[CHAVE_DATA_INICIO] = data_selecionada
                    definir_mensagem_rodape("warning", f"Data de início selecionada: {formatar_data_br(data_selecionada)}")
                else:
                    st.session_state[CHAVE_DATA_FINAL] = data_selecionada
                    data_inicio = st.session_state[CHAVE_DATA_INICIO]
                    data_final = data_selecionada
                    total_dias_selecionado = (
                        datetime.strptime(converter_data_iso(data_final), FORMATO_DATA)
                        - datetime.strptime(converter_data_iso(data_inicio), FORMATO_DATA)
                    ).days + 1
                    cols = st.columns([0.7, 0.3])
                    with cols[0]:
                        st.warning(f"Data início selecionada: {formatar_data_br(data_inicio)}")
                    with cols[1]:
                        st.button("Limpar", use_container_width=True, on_click=limpar_datas)

                    cols = st.columns([0.7, 0.3])
                    with cols[0]:
                        st.warning(f"Data final selecionada: {formatar_data_br(data_selecionada)}")
                    with cols[1]:
                        fracionar_ferias = st.radio(
                            "Fracionar férias?",
                            options=("Sim", "Não"),
                            horizontal=True,
                            key=CHAVE_FRACIONAR_FERIAS,
                        ) == "Sim"

                        plano_fracionamento = None
                        if fracionar_ferias and total_dias_selecionado in (10, 15, 20, 30):
                            plano_fracionamento = st.selectbox(
                                "Plano de fracionamento",
                                options=["10 + 10 + 10", "10 + 20", "15 + 15"],
                                key=CHAVE_PLANO_FRACIONAMENTO,
                            )

                        st.button(
                            "Adicionar férias",
                            use_container_width=True,
                            on_click=verifica_adiciona_ferias,
                            args=(data_inicio, data_selecionada, fracionar_ferias, plano_fracionamento),
                        )
                
                definir_mensagem_rodape("info", f"Data clicada: {formatar_data_br(data_selecionada)}")

    if usuario.acesso_gestor and callback == "eventClick":
        evento_clicado = calendar_widget["eventClick"]["event"]
        st.session_state[CHAVE_FERIAS_GESTOR] = evento_clicado.get("id")
        for chave in (CHAVE_EDITOR_DATA_INICIO, CHAVE_EDITOR_DATA_FIM, CHAVE_EDITOR_TIPO):
            st.session_state.pop(chave, None)
        st.session_state.pop(CHAVE_LISTA_RECURSO, None)
        st.session_state.pop(CHAVE_LISTA_DATA_INICIO, None)
        st.session_state.pop(CHAVE_LISTA_DATA_FIM, None)
        st.session_state.pop(CHAVE_LISTA_USUARIO, None)
        st.session_state.pop(CHAVE_LISTA_TIPO, None)
        st.session_state.pop("form_lista_data_inicio", None)
        st.session_state.pop("form_lista_data_fim", None)

    if usuario.acesso_gestor:
        renderizar_gestao_ferias_gestor(calendar_events, usuarios, recursos_por_id, calendar_options)
    else:
        renderizar_mensagem_rodape()

def pagina_principal():
    col_titulo, col_sair = st.columns([0.8, 0.2])
    with col_titulo:
        st.title("Gerenciador de Férias")
    with col_sair:
        st.write("")
        st.button("Sair", use_container_width=True, on_click=sair)
    st.divider()
    usuario = st.session_state[CHAVE_USUARIO]

    if usuario.acesso_gestor:
        cols = st.columns(3)
        
        with cols[0]:
            if st.button("Gerenciar Usuários", use_container_width=True):
                definir_tela_gestor("gestao")
                st.rerun()
        with cols[1]:
            if st.button("Acessar Calendário", use_container_width=True):
                definir_tela_gestor("calendario")
                st.rerun()
        with cols[2]:
            if st.button("Dashboard", use_container_width=True):
                definir_tela_gestor("dashboard")
                st.rerun()

    tela_gestor = st.session_state.get(CHAVE_TELA_GESTOR, "calendario")

    if usuario.acesso_gestor and tela_gestor == "dashboard":
        pagina_dashboard_gestor()
    elif st.session_state[CHAVE_PAGINA_GESTAO]:
        pagina_gestao()
    else:
        pagina_calendario()


def main():
    inicializar_estado()

    if not st.session_state[CHAVE_LOGADO]:
        login()
    else:
        pagina_principal()


main()




