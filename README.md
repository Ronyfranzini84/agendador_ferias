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
- Visualizacao do saldo de dias disponiveis para solicitar ferias.
- Selecao de datas diretamente no calendario.
- Registro de ferias pelo proprio usuario.
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

- visualizar todos os usuarios cadastrados;
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

Os dominios `grupocasasbahia.com.br`, `viavarejo.com.br` e `casasbahia.com.br` usam Office 365 como configuracao padrao de SMTP.

### Dashboard do gestor

O dashboard gerencial mostra:

- total de dias futuros de ausencia;
- total de dias futuros de ferias;
- setor com maior impacto no periodo futuro;
- consolidado de ferias agendadas por mes;
- pessoas com saldo insuficiente para novas ferias;
- setores com maior concentracao de ausencias.

Esse painel ajuda a antecipar concentracoes de ausencia e reduzir risco de absenteismo por setor.

## Regras implementadas

- Ferias exigem periodo minimo de 10 dias.
- A data final deve ser igual ou posterior a data inicial.
- O sistema valida saldo disponivel antes de registrar ferias.
- O saldo e calculado com base no tempo de empresa menos os dias de ferias ja utilizados.

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
