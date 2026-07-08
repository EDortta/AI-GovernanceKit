# Task: Ler o kit-owned da fonte em `.docs/` no instalador Python

## Metadata
- work_id: WK-20260701-dotdocs-kit-layout
- date: 2026-07-01
- owner: [OPERATOR_NAME]
- related_commit: <planned>

## Parent Epic
- 002-align-python-installer-to-dotdocs-source

## Objective
Fazer `install_agents.py` ler os caminhos de origem do kit em `.docs/...`, casando
com a fonte AI-Agents já reestruturada, sem quebrar a escrita no destino `.docs/`.

## In Scope
- Atualizar constantes de origem para `.docs/`:
  - `_KIT_DOC_PATHS`: `.docs/agents`, `.docs/workflows`, `.docs/articles`,
    `.docs/icons`, `.docs/issues/templates`, `.docs/issues/README.md`.
  - Incluir também `.docs/index.html` e `.docs/concepts.html` (o bash installer
    já os trata como kit-owned).
  - `_KIT_SEED_PATHS`: `.docs/software-overview.md`, `.docs/limits.md`.
  - `_PROJECT_SEED_PATHS`: mantém `docs/required-reading.md`, `docs/napkin-lessons.md`.
- Ajustar `_SRC_DOC_PREFIX`/`_dest_rel`: com origem já em `.docs/`, o remapeamento
  origem→destino para o kit vira identidade. Decidir entre:
  (a) tornar `_dest_rel` idempotente (não prefixar `.docs/` duas vezes), ou
  (b) zerar o remap e usar caminhos de destino diretos.
- (Opcional) Compatibilidade retroativa: detectar se a fonte tem `.docs/` ou `docs/`
  e escolher o prefixo de origem; senão, falhar com mensagem clara.

## Out of Scope
- Instalador bash (fonte AI-Agents).

## Test Plan
- `tests/test_install_agents.py`: usar uma fixture de fonte com layout `.docs/`.
- Fresh install → kit em `.docs/`, `docs/` semeada (README + required-reading + napkin).
- `--upgrade` → preserva `docs/` e seeds `.docs/software-overview.md`/`.docs/limits.md`.
- Migração de layout legado no destino continua funcional e idempotente.

## Security
- Preservar `.credentials` e `handoff.md` como hoje. Sem segredos em logs.

## DoD
- Origem lida de `.docs/`; sem prefixo duplicado.
- Testes verdes.
- Comportamento paritário com o bash installer (fonte AI-Agents, commit `6a5e6ba`).
