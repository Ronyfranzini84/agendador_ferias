import os


MODELO_PADRAO = "llama-3.3-70b-versatile"


class GroqAIError(ValueError):
    pass


def obter_chave_api_groq(chave_informada=None):
    chave = (chave_informada or "").strip() or os.getenv("GROQ_API_KEY", "").strip()
    if not chave:
        raise GroqAIError(
            "Configure a chave da Groq em GROQ_API_KEY para usar os recursos de IA."
        )
    return chave


def _chamar_groq(prompt_sistema, prompt_usuario, chave_api=None, modelo=MODELO_PADRAO):
    try:
        from groq import Groq
    except ImportError as exc:
        raise GroqAIError(
            "A biblioteca groq nao esta instalada no ambiente. Instale com: pip install groq"
        ) from exc

    try:
        cliente = Groq(api_key=obter_chave_api_groq(chave_api))
        resposta = cliente.chat.completions.create(
            model=modelo,
            temperature=0.3,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario},
            ],
        )
    except GroqAIError:
        raise
    except Exception as exc:
        raise GroqAIError(f"Falha ao consultar a IA da Groq: {exc}") from exc

    conteudo = ""
    try:
        conteudo = (resposta.choices[0].message.content or "").strip()
    except Exception as exc:
        raise GroqAIError("A Groq retornou uma resposta vazia ou invalida.") from exc

    if not conteudo:
        raise GroqAIError("A Groq retornou uma resposta vazia.")
    return conteudo


def gerar_resumo_dashboard_ia(contexto_dashboard, chave_api=None):
    sistema = (
        "Voce e um assistente de RH para planejamento de ferias. "
        "Responda em portugues brasileiro, de forma objetiva, com foco em risco operacional. "
        "Escreva sem acentos e sem cedilha em toda a resposta."
    )
    usuario = (
        "Analise os dados a seguir e responda com tres blocos: "
        "(1) Diagnostico rapido, (2) Riscos por setor e periodo, (3) Acoes recomendadas para o gestor.\n\n"
        f"Dados: {contexto_dashboard}"
    )
    return _chamar_groq(sistema, usuario, chave_api=chave_api)


def gerar_rascunho_email_ia(contexto_email, chave_api=None):
    sistema = (
        "Voce escreve comunicacoes corporativas para gestores de equipes. "
        "Responda em portugues brasileiro, com tom profissional e claro. "
        "Escreva sem acentos e sem cedilha em toda a resposta."
    )
    usuario = (
        "Gere um assunto e um corpo de e-mail para o colaborador com base no contexto. "
        "Formato obrigatorio: primeira linha com 'ASSUNTO: ...', depois uma linha em branco e 'MENSAGEM:' seguido do texto. "
        "Nao use acentos ou cedilha (exemplos corretos: criancas, ferias, acao).\n\n"
        f"Contexto: {contexto_email}"
    )
    return _chamar_groq(sistema, usuario, chave_api=chave_api)
