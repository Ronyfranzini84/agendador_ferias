# Agendador de Ferias

Aplicacao em Streamlit para controle de ferias, folgas e atestados, com operacao por usuario comum e por gestor.

## Visao geral

O app permite:

- login de usuarios cadastrados;
- consulta de saldo de ferias disponivel;
- agendamento de ferias diretamente pelo calendario;
- gestao de ocorrencias por gestores;
- cadastro e manutencao de usuarios;
- envio de e-mails a partir da area do gestor;
- dashboard gerencial com indicadores para prevenir concentracao de ausencias.

## Funcionalidades

### Usuario comum

- Acesso por login com nome e senha.
- Visualizacao do saldo de dias disponiveis para solicitar ferias (saldo do ano atual).
- Selecao de datas diretamente no calendario.
- Registro de ferias pelo proprio usuario.
- Opcao de fracionamento no momento da solicitacao:
  - Fracionar: `Sim` ou `Nao`.
  - Planos disponiveis quando fracionar: `10 + 10 + 10`, `10 + 20`, `15 + 15`.
  - Se escolher `Nao` e solicitar `15` ou `20` dias, o sistema considera consumo de `30` dias (regra de venda do restante).
- Visualizacao, na tela inicial, do link da rede local para acesso ao sistema hospedado na empresa.

### Gestor

- Acesso ao calendario completo da equipe.
- Cadastro de ocorrencias dos tipos:
	- Ferias
	- Folga
	- Atestado
- Edicao e remocao de ocorrencias ja cadastradas.
- Preenchimento rapido de ocorrencias clicando diretamente na lista/calendario.
- Limpeza de selecao para reiniciar rapidamente um novo lancamento.

### Gestao de usuarios

Na area `Gerenciar Usuarios`, o gestor pode:

- visualizar todos os usuarios cadastrados com comparativo de uso de ferias por ano;
- criar novos usuarios;
- modificar nome, e-mail, senha, setor, data de inicio e acesso de gestor;
- deletar usuarios.

### Envio de e-mail

Na aba `E-mail`, o gestor pode:

- informar remetente e destinatario livremente;
- usar o e-mail de um funcionario cadastrado como preenchimento rapido;
- enviar por `SMTP`;
- tentar envio por `Outlook Desktop` quando configurado na maquina;
- configurar login SMTP, host, porta e TLS.
- gerar sugestao de assunto e mensagem com IA (Groq), mantendo revisao humana antes do envio.

Os dominios `grupocasasbahia.com.br`, `viavarejo.com.br` e `casasbahia.com.br` usam Office 365 como configuracao padrao de SMTP.

### Dashboard do gestor

O dashboard gerencial mostra:

- total de dias futuros de ausencia;
- total de dias futuros de ferias;
- setor com maior impacto no periodo futuro;
- consolidado de ferias agendadas por mes;
- pessoas com saldo insuficiente para novas ferias;
- setores com maior concentracao de ausencias.
- insight executivo com IA (Groq), com diagnostico e recomendacoes de acao.

Esse painel ajuda a antecipar concentracoes de ausencia e reduzir risco de absenteismo por setor.

## Regras implementadas

- Ferias exigem periodo minimo de 10 dias.
- A data final deve ser igual ou posterior a data inicial.
- O sistema valida saldo disponivel antes de registrar ferias.
- O saldo para solicitacao considera o ano atual (nao acumula todo o historico da empresa).
- O saldo e calculado por ano calendario com proporcionalidade:
  - Ano de entrada: proporcional aos dias trabalhados no ano.
  - Primeiro ano completo: proporcional ao periodo a partir do aniversario de empresa.
  - Segundo ano completo em diante: 30 dias fixos.
- Em ferias, o sistema diferencia dias de periodo e dias consumidos:
  - Com fracionamento: consumo igual ao periodo solicitado.
  - Sem fracionamento, em pedidos de 15 ou 20 dias: consumo de 30 dias.

### Comparativo anual de ferias

A tela `Gerenciar Usuarios` exibe, para cada funcionario:

- dias usados no ano anterior;
- dias usados no ano atual (com delta em relacao ao ano anterior);
- dias disponiveis no ano atual com indicador visual:
  - verde: uso dentro do esperado;
  - amarelo: muitos dias ainda disponiveis (risco de acumulo);
  - vermelho: saldo critico (menos de 10 dias disponiveis).

## Dados e persistencia

- O banco utilizado e SQLite.
- Em ambiente de desenvolvimento, o banco fica no proprio projeto.
- No executavel, o banco passa a ser salvo em `%LOCALAPPDATA%\AgendadorFerias\bd_usuarios.sqlite`.
- Se o banco nao existir, ele e criado automaticamente na primeira execucao.
- As tabelas tambem sao criadas automaticamente quando necessario.

## Navegacao principal

Para usuarios com acesso de gestor, a tela principal oferece:

- `Gerenciar Usuarios`
- `Acessar Calendario`
- `Dashboard`

## Executavel para outro laptop

1. No projeto, execute `build_exe.bat`.
2. O build gera `dist\AgendadorFerias.exe`.
3. Copie esse executavel para o laptop que vai hospedar o sistema.
4. Ao abrir o executavel, o app sobe em `http://127.0.0.1:8501` e tambem mostra o link da rede local, por exemplo `http://192.168.0.25:8501`.
5. Para outros usuarios acessarem, compartilhe esse link da rede local e permita o acesso quando o Firewall do Windows solicitar.

### Resultado esperado ao abrir o executavel

- O navegador local abre automaticamente no sistema.
- O console do executavel mostra:
	- `Local URL`, para uso no proprio computador servidor.
	- `Network URL`, que e o link a ser compartilhado com os demais funcionarios.
- A porta padrao da aplicacao e `8501`.

## Como compartilhar com outros usuarios

- O laptop que executar o `.exe` funciona como servidor do sistema.
- O executavel precisa permanecer aberto para os outros acessarem.
- Os demais usuarios acessam pelo navegador usando o link exibido pelo app na rede local.
- Todos usam a mesma porta `8501`; o que muda entre gestor e funcionario e apenas o login.
- Se necessario, libere a porta no Firewall do Windows para redes privadas.

## Observacoes

- O banco de dados do executavel fica em `%LOCALAPPDATA%\AgendadorFerias\bd_usuarios.sqlite` no computador que estiver hospedando o sistema.
- `calendar_options.json` e `wave.png` vao empacotados junto no build.
- O executavel precisa ficar aberto no laptop servidor para os outros usuarios acessarem o link.
- O build atual usa PyInstaller com metadados do `streamlit` incluidos para permitir a inicializacao correta do executavel.

## IA com Groq (opcional)

Para habilitar os recursos de IA no formulario de e-mail e no dashboard, configure a chave da Groq na variavel de ambiente abaixo:

- `GROQ_API_KEY`

Exemplo no PowerShell (sessao atual):

```powershell
$env:GROQ_API_KEY = "sua_chave_aqui"
```

Se a chave nao estiver configurada, o sistema continua funcionando normalmente sem os recursos de IA.
