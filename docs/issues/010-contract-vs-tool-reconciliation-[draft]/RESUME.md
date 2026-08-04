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

## Ordem que o autor sugeriu

`A1+G1` juntas (A1 corrige, G1 impede recorrência; G1 sozinha reprova todo o parque
instalado) → `A3+G5` → `A5+G3` → `A6` → `A4` → `A7` → `A8, A9, A10, G4`.

## Next Step (DO THIS FIRST)

Criticar A1 e G1 lado a lado, começando por confirmar se A1 ainda tem trabalho depois
do que foi feito hoje — se não tiver, G1 passa a ser a issue crítica isolada e a ordem
sugerida muda. Levar B1 para essa mesma mesa: ela questiona se um gate de abertura
(§1b, §1c) protege alguma coisa, e isso decide como G1 deve verificar.
