# RESUME — WK-20260701-dotdocs-kit-layout (installer side)

## Next Step (DO THIS FIRST)
Revisar e coordenar o merge com o lado fonte (AI-Agents, commit `6a5e6ba`). O
instalador já lê a fonte em `.docs/` com fallback para `docs/` — nada bloqueia.

## Status
- IMPLEMENTADO (pending review). `_resolve_src()` detecta o layout da fonte:
  prefere `.docs/…` (fonte reestruturada) e cai para `docs/…` (fonte legada);
  seeds do projeto (`docs/required-reading.md`, `docs/napkin-lessons.md`) sempre de `docs/`.
- 57 testes verdes (2 novos: `_resolve_src` e fresh install a partir de fonte `.docs/`).

## Context
- Fonte: `AI-Agents` branch `feature/WK-20260701-dotdocs-kit-layout`, commit `6a5e6ba`.
- Destino já usa `.docs/`; migração legada no destino já implementada.

## Files in play
- `governancekit/install_agents.py` (`_resolve_src`, chamado em `_do_fresh`/`_do_upgrade`)
- `tests/test_install_agents.py` (`test_resolve_src_prefers_dotdocs_source`,
  `test_fresh_install_reads_dotdocs_source`)
