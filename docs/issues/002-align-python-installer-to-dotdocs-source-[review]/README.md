# 002 — Alinhar o instalador Python à fonte `.docs/`

## Metadata
- work_id: WK-20260701-dotdocs-kit-layout
- date: 2026-07-01
- owner: Esteban D.Dortta
- related_commit: <planned>

## Objective
- Atualizar `governancekit/install_agents.py` para ler o kit-owned da fonte em
  `.docs/...` (a fonte AI-Agents já foi reestruturada), mantendo o destino `.docs/`.

## Scope
- In scope: manifesto de origem (`_KIT_DOC_PATHS`, `_KIT_SEED_PATHS`,
  `_FRESH_PATHS`, `_UPGRADE_PATHS`, `_DOCS_PATHS`), lógica `_dest_rel`/`_SRC_DOC_PREFIX`,
  seeds de projeto (`docs/required-reading.md`, `docs/napkin-lessons.md`), testes.
- Out of scope: o instalador bash (feito na fonte AI-Agents, work_id gêmeo).

## ARO
- Acceptance: instalar a partir da fonte `.docs/` gera kit em `.docs/` e `docs/`
  livre; upgrade preserva `docs/` + seeds; testes verdes.
- Risk: instalador e fonte em layouts divergentes se os merges não forem coordenados.
- Operations: sem deploy.

## Privacy
- N/A.

## Task Index
- issues/001-read-kit-from-dotdocs-source-[draft].md
