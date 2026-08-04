# Epic: Reconciliar contrato AI-Agents e ferramenta GovernanceKit

## Metadata
- work_id: WK-20260804-governancekit-contract-reassessment
- date: 2026-08-04
- owner: Esteban D.Dortta
- related_commit: <planned>

## Context

O kit de governança se distribui em dois componentes que evoluem separadamente:

- **AI-Agents** — o contrato: `AGENTS.md`, `.docs/agents/*`, `.docs/workflows/*`,
  os artigos de onboarding e o instalador shell `scripts/install-agents-kit.sh`.
  É o texto que o agente lê e obedece.
- **AI-GovernanceKit** — a ferramenta: o CLI `governancekit` (`install-agents`,
  `doctor`, `configure`, `resume`, `map`). É o código que instala, migra e audita.

Vários pontos do contrato dizem explicitamente que a divisão é intencional: o
`AGENTS.md` §8b e o `council.md` §5 fecham com "this contract owns the *what and
why*; the executable collection is the companion runtime work in AI-GovernanceKit
(the *how*)".

A divisão é boa. O que falta é o elo que a mantém honesta: **nada verifica que o
*how* e o *what* concordam.** Quando a ferramenta muda de opinião sobre um caminho e
o texto não acompanha, os dois seguem publicando `[PASS]` um sobre o outro.

## Problem Statement

Em 2026-08-04, no projeto governado `AI/CodexBridge`, uma reinstalação produziu um
repositório em que:

- `governancekit doctor` responde `[PASS] docs/software-overview.md: contains
  project_context_ready: yes` e `[PASS] AI-Agents contract v1.1.6 is compatible with
  GovernanceKit 0.2.3`;
- `AGENTS.md` §1b, sobre o mesmo par de arquivos, manda **parar** — porque nomeia
  `.docs/software-overview.md`, que a mesma execução acabou de mover para `docs/`;
- o `.gitignore` escrito pelo instalador às 17:20 é reprovado pelo `doctor` às 17:26;
- `.governancekit-identity.json`, cuja ausência §8b define como **STOP**, não foi
  criado pela instalação, e o `doctor` a reporta como `[FAIL]` sem que nada pare.

Nenhum desses estados é detectável por quem lê só um dos dois lados. Todos foram
produzidos por uma única execução de instalação, correta segundo cada componente
isoladamente.

A causa raiz não é o caminho errado. É que **um agente que cumpre 100% do contrato e
uma ferramenta que devolve `PASS` podem descrever repositórios diferentes**, e não
existe verificação que compare os dois.

## Outcome

1. Contrato e ferramenta apontam para o mesmo caminho de readiness (`docs/`).
2. O `doctor` reprova a incoerência entre o texto instalado e o que ele próprio
   verifica — o defeito de hoje vira `FAIL` automático amanhã.
3. A checagem de compatibilidade entre versões deixa de ser só numérica.
4. O contrato ganha as regras que hoje não tem (fronteira de repositório) e perde as
   que apontam para arquivos e caminhos inexistentes.

## Dependencies

- A1 (texto) e G1 (verificação) devem entrar no mesmo ciclo: G1 sozinho reprova todas
  as instalações existentes; A1 sozinho não impede a recorrência.
- G2 depende de A1 e A2 estarem publicados, senão a checagem de compatibilidade
  bloqueia combinações hoje em uso.

## DoD

- `grep -rn '\.docs/software-overview\.md\|\.docs/limits\.md'` no kit instalado
  retorna zero ocorrências.
- `governancekit install-agents --upgrade && governancekit doctor` em repositório
  limpo termina com `Result: PASS` (ou apenas com FAILs legítimos de projeto vazio,
  como `docs/issues: missing`).
- O CI do kit executa `install-agents` seguido de `doctor` e falha se o segundo
  reprovar o que o primeiro escreveu.

## Privacy Checklist

Personal data impact: **sim, indireto.** O `AGENTS.md` §1a existe por conformidade
com a LGPD Art. 46: os slots `{{…}}` guardam nome e e-mail do operador e devem ser
preenchidos a partir de arquivo **não rastreado**. A issue A5 toca exatamente essa
mecânica — hoje os slots são preenchidos a partir de `.gk/operator.json`, e não do
`.credentials/identity.json` que §1a nomeia. Verificar, ao fechar A5, que o arquivo
efetivamente usado como fonte está coberto por `.gitignore` em todos os projetos
governados.

## Session-Close Notes
- Handoff sync status: pending
- Last handoff update date: 2026-08-04
