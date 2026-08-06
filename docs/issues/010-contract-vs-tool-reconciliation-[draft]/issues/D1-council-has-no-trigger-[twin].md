# Issue D1 — origem: observação do operador, 2026-08-06

## D1 — `council.md` existe em todo projeto e nunca roda [alta]

### Contexto

O operador observou: *"todos os projetos têm `.docs/agents/council.md`, mas eles não
estão usando de forma obrigatória antes do push."* Verificado, e é pior do que
"não obrigatório" — **não há nenhum momento em que o contrato mande rodar um council**.

Estado real, medido em 2026-08-06:

| Fato | Evidência |
|---|---|
| O arquivo existe em todo projeto governado | 254 linhas em `AI/Agents`, `AI/CodexBridge`, `AI/CodexBridgeMobile` |
| **`AGENTS.md` não o menciona nenhuma vez** | `grep -i council AGENTS.md` → zero |
| Está no índice de leitura | `docs/required-reading.md:26` |
| O gatilho do índice é circular | *"revisão adversarial de trabalho já aprovado"* — só se lê depois de já ter decidido fazer revisão adversarial. Nada decide isso. |
| O contrato **cita** outros arquivos de `.docs/agents/` | `design-standards.md` (§199, §263), `security-standards.md` (§209) |
| O único momento de push no contrato | `AGENTS.md:335` — *"On a push request, the agent asks whether to also merge to `main`"*. É escolha de branch, não revisão. |
| A ferramenta não tem onde pendurar o gate | `governancekit/hooks.py:48` aceita **apenas** `pre-commit`; `install-hooks --hook-type` rejeita qualquer outro. Não existe `pre-push`. |

A épica `005-solid-council-[finished]` construiu o instrumento e o deu por concluído. Não
há nela nenhuma menção a gatilho, momento ou obrigatoriedade — a busca por
`gatilho|trigger|when to run|fora de escopo` no `epic.md` não retorna nada. **Entregou-se
o instrumento sem o acionamento, e o "finished" escondeu isso.**

### Por que isto é B1, e não uma issue solta

`council.md` é a demonstração mais limpa da tese de **B1** que existe no parque: uma regra
que foi lida (está no índice, é alcançável), está bem escrita (254 linhas, com fronteira
explícita contra `governance-precedence.md`), e **nunca acontece**, porque nada a
ancora num momento de ação. É o oposto de §8c, que funciona por mandar ler o relógio a
cada resposta.

Também é **B3** em segundo grau: o índice alcança o arquivo, mas a entrada é um **tópico**
(*"revisão adversarial"*), não um **momento** (*"antes de pedir push"*). Um índice por
tópico só serve a quem já sabe o que procura.

### Objetivo

Que o council aconteça sozinho quando deve acontecer, e que sua ausência seja detectável.

### Escopo

- **`AGENTS.md`, no momento do push** — declarar o gate junto da regra de push que já
  existe (§ da linha 335), no modelo da §8c: o gate **nomeia** `.docs/agents/council.md`,
  não repete o que ele diz.
- **Definir o que dispara.** "Todo push" transforma o council em ruído e ele passa a ser
  ignorado — o risco que a própria B1 nomeia. Candidatos a critério, a decidir:
  mudança classificada como estrutural (`architecture-classification.md`), toque em
  credencial/segurança, ou o próprio `work_id` marcado como tal. **Um council que roda
  sempre é um council que ninguém lê.**
- **`docs/required-reading.md`** — a entrada deixa de ser tópico e passa a nomear o
  momento.
- **`hooks.py`** — suportar `pre-push`, hoje mecanicamente impossível. O hook não decide
  nada (o council produz achados, nunca decisões, por §0 do próprio arquivo): ele
  **lembra** e registra que foi lembrado.
- **`doctor`** — advisory: projeto que tem `council.md` e nenhum gate declarado é
  reportado.
- Fora de escopo: mudar o conteúdo de `council.md`. O instrumento está pronto.

### ARO

- **Assumption**: o council falha por falta de acionamento, não por falta de qualidade.
- **Risk**: gate em todo push vira ruído e leva junto os outros gates. Mitigação: critério
  estreito, e medir quantas vezes disparou antes de alargar.
- **Risk**: `pre-push` que bloqueia trabalho legítimo. O council produz achados, não
  decisões — o hook não pode reprovar, só registrar.
- **Owner**: a definir.

### Plano de teste

- Push de mudança estrutural sem council: o agente para e nomeia o arquivo.
- Push de mudança trivial: passa sem atrito.
- `doctor` num projeto com `council.md` e sem gate: reporta advisory.
- `install-hooks --hook-type pre-push` instala em vez de rejeitar.

### DoD

- `AGENTS.md` tem gate de council ancorado no momento do push, apontando para o arquivo.
- O critério de disparo está escrito e é estreito.
- `hooks.py` aceita `pre-push`.
- `doctor` detecta council sem gate.
- Uma execução real registrada, com os achados que produziu.
