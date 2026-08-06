# RESUME — Reconciliar contrato AI-Agents e ferramenta GovernanceKit

- work_id: WK-20260804-governancekit-contract-reassessment
- date: 2026-08-04
- status: `[draft]` — issues escritas, **crítica ainda não feita**

## Origem

Quinze issues (A1–A10 no AI-Agents, G1–G5 no GovernanceKit) escritas por um agente a
partir do projeto governado `AI/CodexBridge`, onde os defeitos apareceram numa
instalação de 2026-08-04 17:20. Preservadas **verbatim**; nada foi editado.

Épica gêmea: `AI/GovernanceKit .../docs/issues/010-contract-vs-tool-reconciliation-[draft]/`.
Cada lado guarda também o conjunto irmão, marcado `[twin]`, para a crítica cruzada.

## Cruzamento com o trabalho de 2026-08-04 (LER ANTES DE CRITICAR)

Parte do parque mudou **no mesmo dia** em que as issues foram escritas, e o agente que
as escreveu observou o CodexBridge instalado às 17:20 — antes destas mudanças chegarem
lá. Verificado agora, no `development` dos dois repos:

| Issue | Situação real hoje |
|---|---|
| **A1** — refs `.docs/` → `docs/` | **já feito** (`WK-20260804-readiness-files-are-project-owned`). Sobra 1 ocorrência em `scripts/install-agents-kit.sh`, e é comentário histórico deliberado, não caminho vivo. Falta confirmar contra o kit **instalado**, que ainda é o antigo. |
| **A2** — alinhar/aposentar o `.sh` | **parcialmente feito**: o `.sh` foi alinhado ao destino `docs/`. A recomendação forte da issue — **aposentar** em vez de alinhar — segue em aberto e é decisão do operador. |
| **A3** — `.gitignore` gerado não cobre `.env*` | **confirmado aberto.** `_gitignore_entries()` devolve 18 entradas e nenhuma cobre `.env`, enquanto o `doctor` reprova por `.env` ausente. Defeito real e reproduzível. |
| **A4** — fronteira de repositório | **aberto no kit.** Foi escrito só no `docs/limits.md` do CodexBridge; o contrato do kit continua sem a regra. |
| **A10** — §8c `[MANDATORY]` sem gatilho | **runtime implementado hoje** (`governancekit concurrency`, `winddown_state`), mas o **gatilho** que a issue cobra continua ausente. Ler junto com o §1c novo. |
| **G2** — compat só numérica | A observação de que `governancekit-integration.json` declara `v1.1.6` vale para a **cópia instalada**; na fonte AI-Agents já está `v1.1.7`. O defeito é a instalação não atualizar o arquivo — mais estreito, e mais fácil de testar, do que o texto sugere. |
| A5, A6, A7, A8, A9, G1, G3, G4, G5 | **abertas, intocadas.** |

Sem esse cruzamento a crítica de amanhã vai discutir defeitos já corrigidos e, pior,
pode desfazê-los.

## Segundo conjunto: B1–B3, origem `jk-structure`

Três issues de outra origem, mesmo dia, mesma raiz: `issues/B1-B3-action-gates-and-enforcement.md`.
Vieram de um incidente de envio de e-mail e trazem uma correção de diagnóstico que
importa — o agente **tinha lido** o contrato inteiro; o arquivo de regras não estava em
índice nenhum. O remédio "leia com mais cuidado" não serve.

A tese delas: **ler no Start Gate não protege regra que só fica relevante três horas
depois**, e a §8c funciona porque ancora o gate na ação, não na abertura.

**Isso critica diretamente o que foi feito hoje.** O §1c que acabei de escrever é uma
regra de *abertura de sessão* — exatamente o padrão que B1 diz que decai. Ao criticar
B1 amanhã, criticar o §1c junto: ou ele ganha gate no momento da ação (antes de
`checkout -b` / `worktree add`), ou herda o mesmo defeito. O hook `SessionStart` que
instalei ajuda no início e não faz nada às 15h.

Prioridade que o autor sugeriu: **B2** (a que teria evitado o incidente, e a mais
barata) → **B3** (fecha a descoberta) → **B1** (mais estrutural, maior risco de virar
ruído).

## Terceiro conjunto: C1–C2, origem `jk-structure` (2026-08-06)

`issues/C1-C2-shared-working-tree-[twin].md` — **duas sessões `claude-code` na mesma pasta e
na mesma branch**. Verbatim + crítica verificada contra o código, no mesmo arquivo.

O ponto: §1c e `survey_concurrency()` modelam concorrência como **topologia de git**, e
topologia não conta processos. `is_current` (`concurrency.py:194`) compara caminho com
`root` — duas sessões no mesmo diretório produzem survey idêntico ao de uma, e o fecho
(`:322`) afirma exclusividade que não existe. Confirmado no código.

Achados da crítica que **não estavam nas issues** e valem mais que parte delas:

- `_unmerged_count` (`concurrency.py:127`) lê só refs locais, e **falha vira `0`** — que
  é o predicado de `removable` (`:67`). Erro de leitura sai como *"merged — this worktree
  can be removed"*. Fail-open na direção perigosa, na linha mais acionável do relatório.
- O lease proposto em `<git-dir>` cai no dir **privado** da worktree; para a coluna de
  sessões aparecer em cada linha da tabela ele tem de morar em `--git-common-dir`,
  chaveado pelo caminho da worktree.
- Heartbeat por idade é o critério mais fraco; `os.kill(pid, 0)` + `hostname` responde
  agora. E **quem toca o heartbeat** decide se a feature funciona: tem de ser efeito
  colateral de todo comando `governancekit`, nunca disciplina do agente — senão herda o
  defeito do B1.
- Caminho do registro: são **quatro** caminhos, três em disco, **duas cópias divergentes**
  (`~/Sync/agent-status.json` viva; `~/.local/state/governancekit/agent-status.json`
  congelada em 03/08 com três sessões mortas de julho). E os dois caminhos XDG discordam
  entre si — `ai-agents/` no contrato, `governancekit/` no `activity_monitor.py`.

**Decidido pelo operador em 2026-08-06** (detalhe em `issues/C1-C2-…`):

- **Registro vai para `${XDG_STATE_HOME:-$HOME/.local/state}/ai-agents/`** — que é o que o
  `AGENTS.md:385` já diz. O argumento que sustentava `~/Sync` caiu na verificação: a pasta
  **não é sincronizada** (o Syncthing sincroniza `~/Sync/Documents` e `~/Sync/Projects`; o
  arquivo está na raiz, fora dos dois). Corrige-se a ferramenta, não o contrato.
- **Dois eixos concomitantes, ortogonais** — git (o que existe no repositório; derivado,
  nada persistido) e sessão (quem opera agora; persistido, com tempo de vida). Nenhum
  substitui o outro: a célula do incidente — N sessões, 1 worktree — é invisível a cada um
  isoladamente. `§1c` fica com as três definições de frente aberta, não com uma trocada.
- Eixo sessão tem duas superfícies: **detecção** em `<git-common-dir>/governancekit/sessions/`
  (não toca `$HOME`, nunca entra no índice) e **relato** cross-project no XDG.

**C1 valida B1 de forma independente.** A §7 que C1 propõe — proibir `git add -A`,
reconferir `HEAD` antes do commit, `fetch` antes de afirmar push — são três gates no
momento da ação, vindos de outro incidente e de outro autor. B1 sobe na ordem.

E reformula o §1c: frente aberta = *trabalho não mesclado* **ou** *agente vivo*, com o
git como uma das duas fontes. Antes de lease, o §1c precisa de gate de ação.

## Ordem que o autor sugeriu

`A1+G1` juntas (A1 corrige, G1 impede recorrência; G1 sozinha reprova todo o parque
instalado) → `A3+G5` → `A5+G3` → `A6` → `A4` → `A7` → `A8, A9, A10, G4`.

## Next Step (DO THIS FIRST)

Criticar A1 e G1 lado a lado, começando por confirmar se A1 ainda tem trabalho depois
do que foi feito hoje — se não tiver, G1 passa a ser a issue crítica isolada e a ordem
sugerida muda. Levar B1 para essa mesma mesa: ela questiona se um gate de abertura
(§1b, §1c) protege alguma coisa, e isso decide como G1 deve verificar.

**Atualizado 2026-08-06 pela crítica de C1/C2:** a mesa de B1 ganhou a §7 de C1 (três
gates de ação, de outro incidente e outro autor). Duas decisões antes de escrever
código: (a) proibir `git add -A` **incondicionalmente** — maior atrito, maior retorno;
(b) corrigir `_unmerged_count`, que hoje transforma falha de leitura em
*"pode ser removida"* num relatório que já mostramos ao operador.

### Placar em 2026-08-06, fim do dia

**21 issues abertas** — A1–A10 (10), G1–G5 (5), B1–B3 (3), C1–C2 (2), D1 (1). Nenhuma
fechada por inteiro:

| | Feito | Falta |
|---|---|---|
| **A1** | refs `.docs/` → `docs/`; **verificado no CodexBridge instalado** | — (fechada na prática) |
| **A2** | o `.sh` foi alinhado ao destino `docs/` | a decisão de **aposentar** o `.sh` |
| **A3** | — | **confirmado em campo**: `.gitignore` do CodexBridge não cobre `.env` |
| **A10** | runtime (`concurrency`, `winddown_state`) | o **gatilho** |
| **G2** | — | **causa isolada**: o upgrade reescreve `AGENTS.md` e **não toca** no `governancekit-integration.json` |
| **C1 §8a / C2 item 6** | **fechado** — registro em `$XDG_STATE_HOME/ai-agents/`, dados migrados (`WK-20260806-activity-registry-xdg`) | — |
| **D1** | **fechada** — gate no commit de entrega (`WK-20260806-council-commit-gate`) | — |

**Primeira rodada de council já registrada**, contra a própria entrega do gate:
3 lentes, 3 achados fechados, 3 perguntas em aberto. Detalhe em
`verification-council-gate-20260806.md`. Fecha o `not validated:` que o
`.docs/agents/council.md` carregava desde 01/07.

**Defeito grave encontrado ao implementar:** o `pre-commit` que o kit instala **nunca
reprovou nada pelo `doctor`** — sem guarda `__main__` em `cli.py`, e o veredito lido por
um heredoc que substituía o pipe. Corrigido, com teste que executa o hook e foi
verificado por mutação. Todo projeto que rodou `install-hooks` estava sem essa metade.

Verificação do parque instalado: `verification-codexbridge-20260806.md` (somente leitura,
depois do upgrade que o operador rodou às 12:36).

**Pendência que não é issue:** `handoff.md` e `docs/napkin-lessons.md` do CodexBridge
carregam memória de sessão do **AI/Agents**, vazada na instalação de 04/08. Os templates
impedem novos vazamentos e não reparam este. Reparo exige decisão humana — pode haver
conteúdo legítimo do CodexBridge por cima.

O resto de C1 e C2 (lease, dois eixos, render, §7) segue aberto e é o corpo principal
das duas.
