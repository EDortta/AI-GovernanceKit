# Issues B1–B3 — origem `YouBR/ZeeCred/jk-structure`

Levantadas por um agente em 2026-08-04, a partir de um incidente real de envio de
e-mail. Preservadas verbatim. Correção do próprio autor ao diagnóstico inicial, que
muda o remédio e por isso abre o conjunto:

> Não foi leitura rápida. Eu li o `AGENTS.md` inteiro, 538 linhas, no começo da sessão.
> O `contacts.md` não estava lá, nem no `docs/required-reading.md`, nem no `CLAUDE.md`
> global — que cita `~/.config/email/ZeeCred/send.py` mas não o arquivo ao lado dele.
> Não havia como chegar nele lendo o que manda ler.
>
> Foi falha de cobertura do índice, não de atenção. Se o remédio for "leia com mais
> cuidado", esse caso específico se repete.
>
> Dito isso, o problema apontado é real e tem uma raiz mais funda: **ler no início da
> sessão não protege uma regra que só fica relevante três horas depois.** O kit já
> acertou isso uma vez — a §8c manda ler o relógio no início de cada resposta, e é por
> isso que ela funciona. O padrão a generalizar é esse.

Prioridade sugerida pelo autor: **B2** teria evitado o incidente e é a mais barata;
**B3** fecha o buraco de descoberta; **B1** é a mais estrutural e a que mais rende no
longo prazo, mas também a que mais arrisca virar ruído se aplicada a ações demais.

---

## B1 — Regras críticas devem ter gate no momento da ação, não apenas leitura no Start Gate [alta]

### Contexto

O Start Gate (§1) faz o agente ler o contrato no início da sessão. Isso funciona para
regras que valem o tempo todo (escopo, branch, deploy), mas falha para regras que só se
tornam relevantes muito depois — quando o contexto inicial já competiu com centenas de
mensagens.

A §8c é a exceção que prova a regra: ela não confia na leitura inicial, ela manda ler o
relógio **no início de cada resposta**. É um gate ancorado na ação, e por isso é
respeitado.

Em 2026-08-04, num projeto governado pelo kit, um agente que havia lido o contrato
inteiro no início da sessão enviou um e-mail omitindo um destinatário exigido por uma
regra de cópia recorrente, e sem o template obrigatório. As duas regras existiam, em
arquivo próprio, e não foram consultadas no instante do envio.

### Objetivo

Que ações de efeito externo ou irreversível disparem a releitura da regra que as
governa, no momento em que acontecem.

### Escopo

- Introduzir em `AGENTS.md` uma seção de **gates por ação**, no modelo da §8c: para cada
  classe de ação (enviar e-mail/mensagem, abrir issue/PR, criar branch, deploy, mexer em
  credencial), declarar o que deve ser lido ou verificado imediatamente antes.
- O gate deve **nomear o arquivo a consultar, não descrever a regra** — assim ele não
  desatualiza quando a regra muda.
- Fora de escopo: reescrever as regras em si.

### ARO

- **Assumption**: gates curtos e ancorados em ação são cumpridos; parágrafos lidos uma
  vez no início, não.
- **Risk**: excesso de gates vira ruído e todos passam a ser ignorados. Limitar às ações
  de efeito externo ou irreversível.
- **Owner**: a definir.

### Plano de teste

- Sessão longa (100+ mensagens) que termina num envio de e-mail; verificar se o agente
  consultou a fonte antes de enviar.
- Revisão de transcrições: a ação foi precedida da leitura?

### DoD

- Seção de gates por ação no `AGENTS.md`, cobrindo no mínimo e-mail, issue/PR e deploy.
- Cada gate aponta para um arquivo, não repete a regra.

---

## B2 — Regra determinística pertence à ferramenta, não à documentação [alta]

### Contexto

"Sempre inclua fulano em cópia" é prosa: depende de o agente lembrar, no instante certo,
de um texto lido antes. Um script que **recusa** o envio sem aquela cópia não depende de
memória nenhuma.

Caso concreto de 2026-08-04: o helper de envio de e-mail e o arquivo de contatos com as
regras de cópia estavam **no mesmo diretório**. O helper não lia o arquivo. O agente
também não, e o e-mail saiu incompleto. A informação estava a um `open()` de distância do
código que precisava dela.

Este é o padrão que a própria §3 do contrato já defende para código: *"uma guarda pertence
dentro da operação perigosa, não no chamador. Se todo call site precisa lembrar da
checagem, um não vai lembrar."* A observação vale para o contrato tanto quanto para o
código que ele governa.

### Objetivo

Toda regra do kit que possa ser verificada por máquina deve virar verificação executável;
a documentação passa a explicar o **porquê**, não a ser o mecanismo de garantia.

### Escopo

- Levantar as regras do `AGENTS.md` e dos contratos de projeto que são deterministicamente
  verificáveis. Candidatas evidentes: destinatários e cópias obrigatórias de e-mail; nome
  de branch conforme o regex da §7; corpo de issue/PR não vazio (§6); ausência de segredo
  no diff.
- Para cada uma, implementar a verificação **onde a ação acontece** — no helper, no hook
  de pre-commit, no `doctor`.
- Manter a prosa apenas como justificativa, com ponteiro para a verificação.
- Primeiro alvo sugerido, por ser barato e ter causado incidente: fazer o `send.py` ler o
  arquivo de contatos, aplicar as regras de cópia recorrentes e falhar com mensagem clara
  quando o envio as violar.

### ARO

- **Assumption**: as regras recorrentes já estão declaradas em formato legível por
  máquina, ou podem ser convertidas.
- **Risk**: verificação rígida demais bloqueia caso legítimo. Prever escape explícito e
  **registrado**, nunca silencioso.
- **Owner**: a definir.

### Plano de teste

- Envio que viola uma regra de cópia declarada deve falhar, citando a regra e o arquivo.
- Envio conforme deve passar sem atrito.
- Nome de branch inválido deve ser recusado **antes** do `checkout -b`, não depois.

### DoD

- Pelo menos as regras de e-mail com enforcement no `send.py`.
- Inventário das demais regras verificáveis, com decisão de implementar ou justificar por
  que fica em prosa.

---

## B3 — `required-reading.md` não alcança arquivos locais fora do checkout [alta]

### Contexto

O contrato declara `docs/required-reading.md` como "o índice único" de leitura. Na prática
ele só lista arquivos do repositório. Regras operacionais reais moram fora dele — dados
pessoais e credenciais não entram em arquivo rastreado, e é correto que não entrem.

Em 2026-08-04, um agente não encontrou a agenda de destinatários de e-mail de um projeto
porque ela vive em `~/.config/`. Ele havia lido o contrato inteiro. O arquivo não estava
em nenhum índice, e o `CLAUDE.md` global citava o script **ao lado dele** sem mencioná-lo.
Não era possível descobri-lo lendo o que o contrato manda ler.

### Objetivo

Que o índice de leitura cubra também as fontes locais, e que a incompletude seja
**detectável** em vez de descoberta por incidente.

### Escopo

- Permitir entradas fora do checkout no `docs/required-reading.md`, com caminho e uma
  linha de propósito — **nunca o conteúdo**, que pode ser pessoal ou sensível.
- Verificação no `doctor`: toda entrada do índice existe; e todo caminho citado como fonte
  de regra nos contratos está no índice.
- Documentar a convenção: dado pessoal e segredo ficam fora do repositório, mas a
  **existência e a localização** do arquivo são indexadas.

### ARO

- **Assumption**: indexar caminho e propósito não expõe dado sensível.
- **Risk**: índice apontando para arquivo ausente numa máquina nova gera falso alarme.
  Marcar entradas opcionais como tal.
- **Owner**: a definir.

### Plano de teste

- `doctor` falha quando o índice aponta para caminho inexistente.
- `doctor` falha quando um contrato cita um arquivo de regra ausente do índice.
- Clone novo sem os arquivos locais: aviso claro, não erro fatal.

### DoD

- Índice suporta e documenta entradas locais.
- `doctor` cobre existência e completude.
- Convenção registrada de onde mora dado sensível e como ele é indexado.
