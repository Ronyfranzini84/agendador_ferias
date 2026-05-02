import base64
import json
import re
import smtplib
import subprocess
import unicodedata
from email.message import EmailMessage


PROVEDORES_SMTP = {
    "gmail.com": {"host": "smtp.gmail.com", "port": 587, "use_tls": True},
    "outlook.com": {"host": "smtp-mail.outlook.com", "port": 587, "use_tls": True},
    "hotmail.com": {"host": "smtp-mail.outlook.com", "port": 587, "use_tls": True},
    "live.com": {"host": "smtp-mail.outlook.com", "port": 587, "use_tls": True},
    "office365.com": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "grupocasasbahia.com.br": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "viavarejo.com.br": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "casasbahia.com.br": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
}


class EmailEnvioError(ValueError):
    pass


def _validar_email(endereco):
    endereco_normalizado = (endereco or "").strip()
    if not endereco_normalizado or "@" not in endereco_normalizado:
        raise EmailEnvioError("Informe um e-mail valido.")
    return endereco_normalizado


def _normalizar_texto_email(texto):
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
        conteudo.replace("\\r\\n", "\n")
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

    if conteudo.upper().startswith("MENSAGEM:"):
        conteudo = conteudo.split(":", 1)[1].strip()
    return conteudo


def _codificar_script_powershell(script):
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def _normalizar_saida_powershell(texto):
    conteudo = (texto or "").strip()
    if not conteudo:
        return ""

    if "#< CLIXML" in conteudo:
        linhas = [linha for linha in conteudo.splitlines() if not linha.lstrip().startswith("#< CLIXML")]
        conteudo = "\n".join(linhas).strip()

    return conteudo


def configurar_smtp(endereco_email, smtp_host=None, smtp_port=None, usar_tls=True):
    email_normalizado = _validar_email(endereco_email)
    dominio = email_normalizado.split("@", 1)[1].lower()

    if smtp_host:
        return {
            "host": smtp_host.strip(),
            "port": int(smtp_port or 587),
            "use_tls": usar_tls,
        }

    configuracao = PROVEDORES_SMTP.get(dominio)
    if configuracao is None:
        raise EmailEnvioError(
            "Nao foi possivel identificar o servidor SMTP automaticamente. Informe o host manualmente."
        )

    return configuracao


def _mensagem_erro_autenticacao(exc, endereco_email):
    dominio = endereco_email.split("@", 1)[1].lower()
    detalhe = ""
    resposta = getattr(exc, "smtp_error", b"")
    if resposta:
        try:
            detalhe = resposta.decode("utf-8", errors="ignore").strip()
        except AttributeError:
            detalhe = str(resposta).strip()

    orientacoes = {
        "hotmail.com": "Para contas Hotmail/Outlook, confirme a senha correta da conta Microsoft. Se houver verificacao em duas etapas, use uma app password. Algumas contas tambem exigem SMTP AUTH habilitado.",
        "outlook.com": "Para contas Hotmail/Outlook, confirme a senha correta da conta Microsoft. Se houver verificacao em duas etapas, use uma app password. Algumas contas tambem exigem SMTP AUTH habilitado.",
        "live.com": "Para contas Hotmail/Outlook, confirme a senha correta da conta Microsoft. Se houver verificacao em duas etapas, use uma app password. Algumas contas tambem exigem SMTP AUTH habilitado.",
        "gmail.com": "Para Gmail, normalmente e necessario usar uma app password quando a verificacao em duas etapas estiver ativa.",
        "grupocasasbahia.com.br": "Para contas corporativas Microsoft 365, use a senha correta da conta corporativa ou app password, se a organizacao exigir. Tambem pode ser necessario habilitar SMTP AUTH para a caixa postal.",
        "viavarejo.com.br": "Para contas corporativas Microsoft 365, use a senha correta da conta corporativa ou app password, se a organizacao exigir. Tambem pode ser necessario habilitar SMTP AUTH para a caixa postal.",
        "casasbahia.com.br": "Para contas corporativas Microsoft 365, use a senha correta da conta corporativa ou app password, se a organizacao exigir. Tambem pode ser necessario habilitar SMTP AUTH para a caixa postal.",
    }
    mensagem = orientacoes.get(dominio, "Verifique usuario SMTP, senha e configuracao de autenticacao da conta.")
    if detalhe:
        return f"Falha de autenticacao no SMTP. {mensagem} Resposta do servidor: {detalhe}"
    return f"Falha de autenticacao no SMTP. {mensagem}"


def enviar_email(
    remetente,
    senha,
    destinatario,
    assunto,
    mensagem,
    smtp_host=None,
    smtp_port=None,
    usar_tls=True,
    usuario_smtp=None,
):
    remetente_normalizado = _validar_email(remetente)
    destinatario_normalizado = _validar_email(destinatario)
    usuario_smtp_normalizado = _validar_email(usuario_smtp or remetente_normalizado)

    if not (senha or "").strip():
        raise EmailEnvioError("Informe a senha ou app password do e-mail do gestor.")

    assunto_normalizado = _normalizar_texto_email(assunto)
    mensagem_normalizada = _normalizar_texto_email(mensagem)

    if not assunto_normalizado:
        raise EmailEnvioError("Informe o assunto do e-mail.")

    if not mensagem_normalizada:
        raise EmailEnvioError("Digite a mensagem que sera enviada ao funcionario.")

    configuracao = configurar_smtp(
        remetente_normalizado,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        usar_tls=usar_tls,
    )

    email = EmailMessage()
    email["From"] = remetente_normalizado
    email["To"] = destinatario_normalizado
    email["Subject"] = assunto_normalizado
    email.set_content(mensagem_normalizada)

    try:
        with smtplib.SMTP(configuracao["host"], configuracao["port"], timeout=30) as servidor:
            servidor.ehlo()
            if configuracao["use_tls"]:
                servidor.starttls()
                servidor.ehlo()
            servidor.login(usuario_smtp_normalizado, senha)
            servidor.send_message(email)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailEnvioError(_mensagem_erro_autenticacao(exc, usuario_smtp_normalizado)) from exc
    except OSError as exc:
        raise EmailEnvioError("Nao foi possivel conectar ao servidor SMTP informado.") from exc
    except smtplib.SMTPException as exc:
        raise EmailEnvioError(f"Erro ao enviar e-mail: {exc}") from exc


def _executar_outlook(remetente, destinatario, assunto, mensagem, modo_envio):
    remetente_normalizado = _validar_email(remetente)
    destinatario_normalizado = _validar_email(destinatario)

    assunto_normalizado = _normalizar_texto_email(assunto)
    mensagem_normalizada = _normalizar_texto_email(mensagem)

    if not assunto_normalizado:
        raise EmailEnvioError("Informe o assunto do e-mail.")

    if not mensagem_normalizada:
        raise EmailEnvioError("Digite a mensagem que sera enviada ao funcionario.")

    remetente_escaped = json.dumps(remetente_normalizado.lower())
    destinatario_escaped = json.dumps(destinatario_normalizado)
    assunto_escaped = json.dumps(assunto_normalizado)
    mensagem_escaped = json.dumps(mensagem_normalizada)
    comando_envio = "$mail.Send()" if modo_envio == "send" else "$mail.Save()`n    $mail.Display()"
    retorno_ok = "EMAIL_ENVIADO" if modo_envio == "send" else "RASCUNHO_CRIADO"

    script = f"""
$ErrorActionPreference = 'Stop'
try {{
    $outlook = New-Object -ComObject Outlook.Application
    $namespace = $outlook.GetNamespace('MAPI')
    $mail = $outlook.CreateItem(0)
    $account = $null
    $contas = @()
    foreach ($item in $namespace.Accounts) {{
        if ($item.SmtpAddress) {{
            $contas += $item.SmtpAddress
        }}
        if ($item.SmtpAddress -and $item.SmtpAddress.ToLower() -eq {remetente_escaped}) {{
            $account = $item
            break
        }}
    }}

    if ($null -eq $account) {{
        if ($contas.Count -gt 0) {{
            $listaContas = ($contas | Sort-Object -Unique) -join ', '
            throw "A conta informada nao esta configurada no Outlook Desktop. Contas encontradas: $listaContas"
        }}
        throw 'Nenhuma conta de e-mail foi encontrada no Outlook Desktop.'
    }}

    $mail.SendUsingAccount = $account
    $mail.To = {destinatario_escaped}
    $mail.Subject = {assunto_escaped}
    $mail.Body = {mensagem_escaped}
    {comando_envio}
    Write-Output '{retorno_ok}'
}}
catch {{
    Write-Output ("ERRO_OUTLOOK: " + $_.Exception.Message)
    exit 1
}}
"""

    try:
        resultado = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                _codificar_script_powershell(script),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except OSError as exc:
        raise EmailEnvioError("Nao foi possivel iniciar o Outlook Desktop para envio.") from exc
    except subprocess.TimeoutExpired as exc:
        raise EmailEnvioError("O Outlook demorou demais para responder ao envio do e-mail.") from exc

    if resultado.returncode != 0:
        detalhe = _normalizar_saida_powershell(resultado.stdout or resultado.stderr)
        if detalhe.startswith("ERRO_OUTLOOK: "):
            detalhe = detalhe.removeprefix("ERRO_OUTLOOK: ").strip()
        if not detalhe:
            detalhe = "Falha ao enviar pelo Outlook Desktop."
        raise EmailEnvioError(detalhe)

    if retorno_ok not in (resultado.stdout or ""):
        if modo_envio == "send":
            raise EmailEnvioError("O Outlook nao confirmou o envio do e-mail.")
        raise EmailEnvioError("O Outlook nao confirmou a criacao do rascunho.")


def enviar_email_outlook(remetente, destinatario, assunto, mensagem):
    _executar_outlook(remetente, destinatario, assunto, mensagem, modo_envio="send")


def criar_rascunho_outlook(remetente, destinatario, assunto, mensagem):
    _executar_outlook(remetente, destinatario, assunto, mensagem, modo_envio="draft")