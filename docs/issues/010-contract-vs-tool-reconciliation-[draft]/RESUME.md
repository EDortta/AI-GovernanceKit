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

## Crítica de A1, G1 e B1 — feita em 2026-08-06 (fim do dia)

Nada foi implementado. Três conclusões, todas verificadas contra o parque instalado.

### A1 — **REABERTA**. O placar anterior estava errado

O `AGENTS.md` do CodexBridge, reescrito em 2026-08-06 17:15 com `ref: v1.1.7` no
`.gk/manifest.json`, **ainda nomeia `.docs/software-overview.md`** nas linhas 40, 99,
100, 113, 114. O §1b segue inoperante lá, dois dias depois da issue e depois de um
upgrade rodado hoje.

O que eu havia verificado em 06/08 foi que **os arquivos** estão em `docs/` — não que o
**texto do gate** aponta para `docs/`. A linha "fechada na prática" do placar abaixo saiu
dessa verificação incompleta.

A cadeia de publicação tem **quatro elos**, e a A1 só cobre o primeiro:

| elo | estado |
|---|---|
| 1. fonte AI-Agents corrigida | ✅ 04/08 |
| 2. tag publicada | ❌ **não existe `v1.1.8`** — nem local nem no remoto. `fb9f253` (17:23 de hoje) declara a versão sem cortar a tag |
| 3. GovernanceKit aponta para ela | ❌ `install_agents.py:21` `DEFAULT_REF = "v1.1.7"` + `KNOWN_TARBALL_SHA256` só até v1.1.7 |
| 4. projeto roda upgrade | ✅ rodou — e recebeu o texto velho |

Consequências para a issue: o critério de aceitação (`grep` na fonte) **não prova nada**
e passa a ser *"num projeto governado, §1b nomeia os caminhos que o `doctor` verifica"*.
E o **elo 3 é do GovernanceKit** — A1 não fecha dentro do repo onde foi escrita.
O pin de checksum faz o elo 2/3 falhar **fechado**, que é o comportamento certo.

### G1 — sobe de prioridade; escopo cresce de caminhos para caminhos **e versões**

`doctor` read-only no CodexBridge, hoje, com o código de `development`:

```
[PASS] docs/software-overview.md: contains `project_context_ready: yes`
[PASS] AI-Agents integration contract: contract v1.1.6 is compatible with GovernanceKit 0.2.3
```

Duas incoerências num relatório verde: a que G1 descreve, e uma que ela **não** cobre —
`v1.1.6` sai do `.docs/governancekit-integration.json` enquanto o `.gk/manifest.json` ao
lado registra `ref: v1.1.7`. Não é contrato-contra-ferramenta: é a **ferramenta
discordando dela mesma**, e carimbando `PASS` na linha que compara as duas. Isso absorve
o G2.

Três pontos de desenho:

- **Comparar hashes do manifest não substitui G1.** O `AGENTS.md` do CodexBridge **bate
  com o hash dele**: foi instalado fielmente e está errado. Drift pega arquivo
  adulterado; coerência pega contrato fiel e obsoleto — que é o defeito deste épico.
  (Achado lateral: `_check_manifest_drift`, `doctor.py:566`, só confere **presença** e
  nunca compara os sha256 que guarda.)
- **Gerar o texto a partir da constante não serve** porque as duas fontes vivem em
  repositórios com ciclos de release diferentes. A verificação cruzada é a reconciliação
  honesta — G1 está certa como está.
- **O `Operations` da G1 subestima.** Com a cadeia da A1 quebrada, G1 como `FAIL` acende
  vermelho em todo projeto **sem remédio disponível**. Entra como `HINT` que **nomeia o
  remédio** (`upgrade to >= vX`) e vira `FAIL` no release em que os quatro elos fecharem.

### B1 — refutada pelo próprio incidente que a originou

A §3b do `AGENTS.md` diz, `[MANDATORY]`, desde `bbf2871` (**27/07, oito dias antes do
incidente**) e presente nas v1.1.6 e v1.1.7:

> *"No external effect without explicit confirmation. Sending a message (WhatsApp,
> e-mail, push, webhook) … is never fired on the agent's own initiative."*

Está no `AGENTS.md` do `jk-structure` (kit v1.1.7), o projeto onde o e-mail saiu. O
agente leu as 538 linhas — ele mesmo diz — e enviou. **A regra que a B1 propõe criar já
existia, era `[MANDATORY]`, cobria e-mail por nome, foi lida e não disparou.**

A leitura que a B1 faz da §8c está errada no ponto que importa: a §8c não funciona por
ser ancorada na **ação**, e sim na **resposta** — *"leia o relógio no início de cada
resposta"*, incondicional, sem reconhecer classe nenhuma. Um gate que começa com *"quando
você for enviar um e-mail"* tem como pré-condição o agente **perceber a classe da ação**,
e perceber a classe falha junto com lembrar da regra.

Experimento controlado, entregue hoje: o `council.md` tinha **cinco gatilhos
`[MANDATORY]` em prosa** — cinco semanas, zero rodadas. O que o fez rodar foi mover a
detecção para dentro da ferramenta (`detect_triggers`) e o bloqueio para o `pre-commit`.
Prosa: 0. Máquina: bloqueou na primeira tentativa. É a tese da **B2**, verificada em
campo, contra a da B1. E o modo de falha do excesso de gates não é ruído — é **silêncio**:
os cinco gatilhos nunca incomodaram ninguém.

**B1 reduzida a um item:** um gate **incondicional** de entrega, que nomeia arquivos em
vez de repetir regras — e que já existe desde hoje (bullet do council na §7). As três
gates da §7 do C1 (`git add -A`, reconferir `HEAD`, `fetch` antes de afirmar push) são
todas detectáveis por máquina e migram para a **B2**. O e-mail idem (`send.py` lendo o
`contacts.md`). **B3 confirmado vivo:** `contacts` não aparece no `required-reading.md`
nem no `AGENTS.md` do `jk-structure` — a falha que causou o incidente foi de
**descoberta**, não de disciplina.

## Next Step (DO THIS FIRST) — ordem revista em 2026-08-06

1. **A1 elos 2–3** — cortar a tag e apontar `DEFAULT_REF` + checksum para ela. É o único
   trabalho que conserta o parque. **Bloqueado: exige push, decisão do operador.**
2. **B3** — sobe de terceiro para segundo: é a falha que causou o incidente e é a mais
   barata (`grep` + entrada no índice).
3. **G1 como `HINT`**, já vendo incoerência de versão (absorve G2).
4. **B2** — inventário de regras determinísticas, `send.py` primeiro.
5. **G1 vira `FAIL`** quando os quatro elos fecharem.
6. **B1** — fechada como subsumida, ou reduzida ao item único acima.

**Duas decisões do operador, pendentes desde a crítica de C1/C2:** (a) proibir
`git add -A` — pela crítica da B1, **no hook**, não na prosa; (b) corrigir
`_unmerged_count` (`concurrency.py:127`), que transforma falha de leitura em
*"pode ser removida"* — o mesmo relatório que mostramos ao operador hoje diz que duas
worktrees são removíveis.

**Alerta de concorrência:** `fb9f253` ("cut v1.1.8") foi commitado às 17:23:46 de
2026-08-06, durante esta sessão e por outro escritor, e `origin/development` já aponta
para ele — **o repositório foi empurrado**. É o cenário do C1 acontecendo ao vivo.

### Placar em 2026-08-06, fim do dia

**21 issues abertas** — A1–A10 (10), G1–G5 (5), B1–B3 (3), C1–C2 (2), D1 (1). Nenhuma
fechada por inteiro:

| | Feito | Falta |
|---|---|---|
| **A1** | refs `.docs/` → `docs/` **na fonte** | **REABERTA** — elos 2–3 (tag + `DEFAULT_REF`/checksum). O `AGENTS.md` do CodexBridge ainda nomeia `.docs/`. Ver a crítica acima |
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
