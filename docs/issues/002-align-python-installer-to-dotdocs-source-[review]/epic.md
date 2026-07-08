# Epic: Alinhar o instalador Python à fonte já reestruturada em `.docs/`

## Metadata
- work_id: WK-20260701-dotdocs-kit-layout
- date: 2026-07-01
- owner: Esteban D.Dortta
- related_commit: <planned>
- raised_by: AI-Agents (fonte) — commit `6a5e6ba` moveu o kit para `.docs/`

## Context

Divergência detectada ao concluir o lado **fonte** (`EDortta/AI-Agents`,
work_id gêmeo `WK-20260701-dotdocs-kit-layout`). A fonte agora entrega o
kit-owned em `.docs/` (não mais em `docs/`).

O instalador Python (`governancekit/install_agents.py`) foi escrito para ser
resiliente enquanto a fonte **ainda não** tivesse migrado: ele lê o kit da fonte
em `docs/...` e reescreve para o destino `.docs/...` via `_dest_rel`
(`_SRC_DOC_PREFIX = "docs/"` → `_DST_DOC_PREFIX = ".docs/"`). Ver o comentário em
`install_agents.py` ("keeps the installer resilient even if the source repo has
not been restructured to `.docs/` yet").

Com a fonte migrada, esse pressuposto deixou de valer.

## Problem Statement

- `_KIT_DOC_PATHS`, `_KIT_SEED_PATHS`, `_PROJECT_SEED_PATHS` e `_FRESH_PATHS`
  listam caminhos de origem `docs/agents`, `docs/software-overview.md`, etc., que
  **não existem mais** na fonte reestruturada (agora `.docs/agents`, `.docs/...`).
- Resultado: ao instalar a partir da fonte nova, o instalador não encontra os
  arquivos de origem do kit — cópia vazia / erro / instalação incompleta.

## Outcome

- Instalador lê o kit da fonte em `.docs/...` (origem) e continua escrevendo em
  `.docs/...` no destino (mapeamento origem→destino vira identidade para docs).
- `_PROJECT_SEED_PATHS` passa a ler `docs/required-reading.md`,
  `docs/napkin-lessons.md` da fonte (que permanecem em `docs/`).
- Compatível com fontes legadas OU decidir explicitamente exigir fonte `.docs/`.
- Testes (`tests/test_install_agents.py`) atualizados para a fonte `.docs/`.

## Dependencies

- Gêmeo fonte em `AI-Agents`: branch `feature/WK-20260701-dotdocs-kit-layout`,
  commit `6a5e6ba` (kit em `.docs/`, migração legada no bash installer).
- Coordenar o merge para não deixar instalador e fonte em layouts divergentes.

## DoD

- Manifesto de origem lê `.docs/...` para o kit-owned.
- Fresh install a partir da fonte nova produz `.docs/` (kit) + `docs/` (projeto).
- `--upgrade` preserva `docs/` e os seeds `.docs/software-overview.md` / `.docs/limits.md`.
- Migração de layout legado no destino permanece funcional (já implementada).
- Testes verdes.
- (Opcional) suporte a fonte legada OU falha clara se a fonte não tiver `.docs/`.

## Privacy Checklist
- Sem dados pessoais. N/A.

## Session-Close Notes
- Handoff sync status: pending
- Last handoff update date: 2026-07-01
