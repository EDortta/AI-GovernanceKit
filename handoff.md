# Handoff

## [2026-08-04] WK-20260804-concurrency-awareness - ready-for-review

- branch: `development`; `main` intocada; sem push

### Estado

- `governancekit/concurrency.py`: `survey_concurrency()` enumera as frentes abertas
  DESTE repositório — worktrees vivas e branches com commits fora da integração,
  deduplicadas — e marca as worktrees sem nada por mesclar como removíveis.
- `winddown_state()` **implementa o §8c**, que definia `session_winddown_hour` e
  `session_close_budget` desde maio dizendo que o kit "can surface" e nada surfaceava.
- Superfícies: comando `concurrency` (`--json`, `--closing`), bloco no `resume`,
  check advisory no `doctor`.
- Contrato no AI/Agents: §1c nova, §7 e §8c com referência cruzada, `session-restore`
  com passo 0 e `session-close` com o passo do que fica aberto.
- Hook `SessionStart` em `~/.claude/settings.json`, fail-open.

### Validação e pendências

- 310 testes; `run-checks` do AI/Agents verde. Pacote reinstalado; hook exercido nos
  dois casos (com kit e sem git).
- O gate de contexto do próprio kit pegou uma regressão minha: a primeira versão do
  §1c levou `base_contracts` a 8021/8000. Compactado.

### Frentes que ficam abertas para o dia seguinte

- `GovernanceKit` @ `feature/uc-008/credential-root-json-profile` — **+1 commit não
  mesclado**, perfil de credencial em JSON na raiz. É a única com trabalho real parado.
- `GovernanceKit-remove-agents` @ `feature/uc-010/remove-agents-safe-plan` — **mesclada;
  a worktree pode ser removida hoje sem perder nada.**
- `GovernanceKit/GovernanceKit-adoption-flow` @ `feature/uc-011/simplified-adoption-flow`
  — **mesclada; a worktree pode ser removida hoje sem perder nada.**

Remover as duas mescladas resolve, de passagem, o bloqueio da reescrita de histórico:
sobrariam dois checkouts em vez de quatro.

### Próximo passo

Operador testa `install-agents --upgrade` no CodexBridge; depois `merge-to-main.sh` e
decisão sobre push e sobre a reescrita de histórico.

## [2026-08-04] WK-20260804-review-findings - ready-for-review

- branch: `development`; `main` intocada; sem push

### Estado

- Cinco achados da revisão fechados: URL do provedor exige https (http só em
  loopback), redirect cross-host com credencial recusado, tarball sem checksum
  conhecido agora **recusa** em vez de avisar (`--allow-unverified` aceita de
  propósito), arquivo com vários diretórios de topo vira erro, `try/except` morto
  do `remove_agents` removido, e o `main()` de 583 linhas virou tabela de despacho
  (26 linhas) com dois testes segurando a forma.
- Este repo saiu do layout antigo: readiness files de `.docs/` para `docs/`,
  referências atualizadas, codemap regenerado.

### Validação e pendências

- 296 testes. Dois FAIL pré-existentes e não tocados no `doctor` deste checkout:
  `docs/architecture.md` citado em required-reading mas inexistente, e identidade
  de host não configurada.
- **Reescrita de histórico não executada.** Backup verificado em
  `scratchpad/governancekit-pre-rewrite-20260804.bundle` ("records a complete
  history"). Motivo da parada: este checkout é um *worktree* de
  `AI/GovernanceKit/.git`, que tem outros três worktrees vivos com trabalho não
  mesclado (`uc-008`, `uc-010`, `uc-011`). Reescrever o object store invalidaria os
  quatro, além de exigir force-push num repo publicado — e não há segredo em jogo,
  só placeholders.

### Próximo passo

Decidir a reescrita de histórico (4 worktrees + force-push) ou arquivá-la.

## [2026-08-04] WK-20260804-wa-hub-and-context-authoring - ready-for-review

- branch: `development`; `main` intocada; sem push

### Estado

- wa-hub desacoplado: `scripts/notify-nexo.sh` e `scripts/governancekit.env.example`
  removidos (ninguém os chamava). Nenhuma credencial real esteve no histórico — só
  placeholders `[WA_HUB_KEY]`/`[WA_HUB_DEST]`, então não há rotação a fazer.
- `doctor` lia o flag de prontidão por substring e casava a prosa do próprio template
  (`set \`limits_ready: yes\` only after…`), reportando PASS sobre arquivo com `no`.
  Agora ancorado na LINHA de metadata, como o instalador shell sempre fez.
- Novo `governancekit author-context`: classifica cada documento
  (absent/template/authored/ready), RASCUNHA os não escritos com o LLM do projeto,
  REVISA os escritos pelo operador sem reescrevê-los, e só move o flag para `yes`
  na confirmação do operador. Sem README/DESCRIPTION, explica por que vale escrever
  um antes e para.
- `agent_scope`: extraídos `request_completion()` e `read_confined_sources()` — um
  único caminho endurecido para o provedor.

### Validação e pendências

- 285 testes. Pacote reinstalado. Fluxo exercido em alvos temporários nos três
  estados (template→draft, authored→review, sem provider→erro acionável).
- Pendente de decisão do operador: reescrita de histórico para apagar as referências
  wa-hub das 8 tags publicadas — quebra os sha256 fixados em `KNOWN_TARBALL_SHA256`.
- Este repo ainda está no layout antigo (`.docs/limits.md`); a migração reversa só
  roda no `--upgrade`.

### Próximo passo

Decidir a reescrita de histórico; testar `install-agents --upgrade` no CodexBridge.

## [2026-08-04] WK-20260804-home-shadow-and-ownership - ready-for-review

- work_id: WK-20260804-refuse-home-root, WK-20260804-readiness-files-are-project-owned,
  WK-20260804-session-memory-stays-in-development
- branch: `development` (three feature branches merged; `main` untouched)

### Estado

- `assert_governable_root()` recusa `$HOME`, qualquer ancestral dele e a raiz do
  filesystem, chamada em `cli.main()` antes do dispatch. Antecedente: um kit
  instalado em `$HOME` sombreava todo projeto abaixo, para seis ferramentas.
- `docs/software-overview.md` e `docs/limits.md` voltaram a ser project-owned:
  `_KIT_SEED_PATHS` vazio, ambos em `_PROJECT_SEED_PATHS`, `_LEGACY_KIT_DOC_NAMES`
  não os varre mais, e `_migrate_readiness_files_to_docs()` traz de volta os alvos
  já em `.docs/` (move, remove symlink, ou preserva em `.gk/readiness-migration/`).
- `_SESSION_MEMORY_TEMPLATES` faz `handoff.md` e `docs/napkin-lessons.md` serem
  semeados de template vazio — o instalador copiava a memória do próprio kit.
- `scripts/merge-to-main.sh` + `docs/project-rules.md`: trabalho parte e retorna a
  `development`; `docs/issues/`, `docs/napkin-lessons.md` e `handoff.md` nunca vão
  para `main`.

### Validação e pendências

- Suíte: 266 passed. Pacote reinstalado (`pip install --user`), trava e layout novo
  ativos no binário.
- `merge-to-main.sh` validado em clone descartável: primeiro merge e segundo merge
  (com conflito modify/delete) resolvem por remoção; produto chega, `development`
  intacto. **A `main` real não foi tocada** — aguarda o teste do operador.
- Sem push em nenhum repo.

### Próximo passo

Operador testa `governancekit install-agents --upgrade` no CodexBridge; depois,
`scripts/merge-to-main.sh` nos dois repos e decisão sobre push.

## Current Status

- work_id: GH-6-simplified-adoption
- branch: `main`
- status: published and installed locally; session closed.
- delivered: interactive `install-agents` now builds a deterministic proposal
  first, names the configured `provider / model`, and asks before any API scope
  analysis. Declining keeps LLM enrichment off; quick and non-interactive paths
  remain deterministic. The command prints the GovernanceKit version before
  installation prompts. Provider errors name the configured provider/model,
  avoiding the misleading “selected agent” attribution.
- security: no credential value, endpoint response body, or project content is
  logged; existing protected-reference handling remains unchanged.
- delivered next: before upgrade drift or adoption discovery begins, the CLI
  announces that a large project may take several minutes; accepted LLM
  enrichment announces the configured provider/model and the 90-second bound.
- delivered next: discovery emits each scanned first-level directory and prunes
  nested Git repositories and linked worktrees before reading their source.
- delivered next: an LLM response rejected for invalid evidence is a highlighted
  operator warning, not an item hidden in an unresolved comma-list. It identifies
  provider/model, expected `path: reason` evidence, and the safe `n` action.
- published: merge commits `3f96377`, `c9e277f`, and `e3f771c` integrated the
  consent/version, visible bounded discovery, and actionable LLM-warning changes;
  `origin/main` is synchronized and the local package was reinstalled.
- validation: `PYTHONPATH=. pytest -q` → 247 passed; `git diff --check` passed.
- next: run one real interactive upgrade on a large consumer checkout and review
  the visible scan, the optional LLM prompt, and any operator warning before
  starting the remaining adoption-epic work.

- work_id: GH-6-simplified-adoption
- branch: `feature/uc-011/simplified-adoption-flow`
- status: first implementation stage complete; proposal/apply core pending commit.
- delivered: normal `install-agents` now produces a consolidated, evidence-based
  adoption proposal. `--quick` applies generated docs, `--review` is interactive,
  `--advanced` retains config-session, and CI requires `--non-interactive
  --accept-generated`. Existing ready project documents are never overwritten.
- validation: `PYTHONPATH=. pytest -q` → 238 passed, 1 skipped.
- delivered next: help raiz reorganizado em "Start here" e "Advanced commands";
  comandos avançados continuam disponíveis e apontam para sua ajuda específica.
- delivered next: upgrades com configuração aceita agora detectam frameworks,
  linguagens e gerenciadores novos como drift consultivo, sem reescrever política.
- validation: `PYTHONPATH=. pytest -q` → 239 passed, 1 skipped.
- delivered next: a proposta unificada usa o provider primário configurado, quando
  disponível, por meio do adaptador read-only já validado. Resumo, domínios e
  evidências viram proposta; falha de provider é pendência e não bloqueia adoção.
- validation: `PYTHONPATH=. pytest -q` → 240 passed, 1 skipped.
- next: add provider-backed proposal enrichment and upgrade/drift coverage before
  closing GitHub #6.

- work_id: GH-5-remove-agents
- branch: `feature/uc-010/remove-agents-safe-plan`
- status: LLM-assisted extraction complete; pending commit, push, and GitHub close.
- delivered: `remove-agents plan` inventories only safe regular files below the
  selected root and writes `.gk/remove-agents-plan.json`; `apply` deletes only
  manifest-hash-identical, unreferenced files after a per-file backup and restore
  manifest. Modified, unknown, referenced, and symlink paths are preserved.
- validation: `PYTHONPATH=. pytest -q` → 236 passed.
- delivered next: `remove-agents plan --with-llm` sends only a modified, unreferenced
  candidate to the configured primary provider and records a structured split. Apply
  requires `--accept-project-extractions`, writes operator-owned content under
  `docs/project-rules/ai-agents-extracted/`, updates required reading, replaces the
  kit file with its proposed reusable remainder, and backs up the original first.
- validation: `PYTHONPATH=. pytest -q` → 237 passed.
- next: commit and push this branch, then close GitHub #5; start #6 separately.

- work_id: WK-20260729-secure-project-adoption
- work_id: WK-20260729-secure-project-adoption
- branch: `feature/project-scope-conversation`
- status: core interview implementation committed for review; epic remains in progress.
- scope: secure, localized conversational project adoption after `install-agents`,
  `install-agents --upgrade`, and interactive configuration sessions.
- evidence: a real CodexBridgeMobile upgrade produced a useful domain proposal in
  English under a PT-BR operational environment, then ended with an ambiguous
  `Domains (comma-separated...)` prompt. The epic makes locale precedence and
  explicit accept/edit/merge/discard decisions contractual.
- follow-up evidence: after completing domains and capabilities, the provider
  prompt accepted `openai:::general` without explaining that `general` is not a
  valid routing role. It failed only at the end and offered no local retry.
  Task 007 now requires guided provider collection, explanation/example/spacing,
  immediate validation, and resumable progress without secrets.
- delivered: operational locale, guided PT-BR/EN/ES prompts with visual spacing,
  in-place provider validation, saved/pending defaults, provider purpose/role,
  root-confined source selection, isolated temporary agent workspace, strict
  proposal validation, and Unicode-safe issue slugs.
- validation: GovernanceKit `pytest -q` -> 184 passed; AI-Agents
  `scripts/run-checks.sh` passed. Critical-review revision isolated the agent
  workspace from the full project root.
- remaining: durable mid-interview draft recovery, provider validation before
  scope-agent invocation, and dependency/sensitivity metadata remain open tasks;
  do not close the epic from this commit.
- next: test the interactive upgrade against CodexBridgeMobile before closing
  the remaining tasks.

## Prior Status

- work_id: WK-20260727-restore-landing
- status: finished
- Public landing uses EDortta links and restored Pix, ETH, and Ko-fi values.
- Reusable README/templates keep placeholders. Package version is 0.2.2.

## Prior Status


- work_id: WK-20260727-context-hardening
- branch: `feature/uc-007/context-hardening`
- status: finished
- delivered: honest tokenizer estimate metadata; semantic task/risk categories;
  enforced reserve; declared-order emission; required retrieval failure; weighted
  lexical ranking; containment; inspect diagnostics; timestamp/prune telemetry;
  `governancekit --version` with nearest-project version and upgrade indication.
- validation: 136 pytest PASS; real AI-Agents context 19,221 / 21,000 usable;
  AI-Agents gate PASS.
- not validated: three-project benchmark because only AI-Agents currently carries
  the compatible v1.1.3 context manifest.
- compatibility: Amazon Q Developer adapter added to installer; both landing pages
  now describe the shared, upgrade-protected mandatory context.

## Prior Status


- work_id: WK-20260727-context-optimization
- date: 2026-07-27
- branch: `feature/uc-006/context-optimization`
- status: finished
- summary: Added schema validation, deterministic task/risk selection,
  `full`/`sections`/lexical `retrieve`, token-counter injection, hard budgets,
  provenance, duplicate reporting, stable JSON, and metadata-only JSONL.
- validation: `python3 -m pytest -q` -> 125 passed; real AI-Agents manifest inspected
  at 19,692 / 22,000 exact tokens for implementation + runtime; JSON build parsed.
- not validated: third-party agent integrations.
- next: no implementation action remains; merge/push authorized. Release and deploy
  remain separate gated actions.
- release follow-up: AI-Agents `v1.1.2` published; GovernanceKit default installer
  ref and verified tarball SHA-256 updated to that immutable tag.
- published-ref install validated in a temporary target; manifest, schemas,
  context documentation, and telemetry ignore rule were present.

## Prior Status

- work_id: WK-20260717-doctor-false-positives
- date: 2026-07-20
- branch: `main` (mergeada e pushada — `origin/main` = `06ee872`)
- status: Épico `004-doctor-false-positives-[finished]` fechado. Duas tasks, ambas
  `[finished]`, na `main` e no GitHub.

### O que foi feito

Descoberto em uso real (`governancekit doctor` sobre `Lucedata/AcheiVc`, 2026-07-17):
o doctor produzia FAILs/HINTs falsos que treinam o operador a ignorar a saída, e aí
o sinal real se perde no ruído.

- **Task 001** — `.example` não é segredo. `_check_tracked_secret_files` reprovava
  `.env.example` e os `.credentials/*.example`/`README*` que o próprio AI-Agents
  distribui — o doctor reprovava o kit-fonte. Fix: `_is_secret_template()`, exclusão
  por sufixo de template, espelhando `run-checks.sh` §4 do gêmeo. `.env.local`/
  `.env.production` (SEC-0221) continuam reprovando.
- **Task 002** — advisory scan varria gitignored e descia em submódulo (4 dos 15
  hits do AcheiVc eram `main.dart.js` do Flutter). Fix pontual, **sem walker novo**:
  `_iter_source_files` pula subdir com `.git`; `_git_ignored_paths` filtra via
  `git check-ignore -z --stdin` (fail-open, §6). No AcheiVc: **15 → 7 hits**, os
  `shell injection` reais e um `weak password hash` antes afogado passaram a aparecer.

### Validação

`python3 -m pytest tests/` → **100 passed** (87 originais + 13 novos). Gêmeo
AI-Agents intocado (`run-checks.sh` verde).

### Aberto / próximo

- **`walk.py` do épico do arnês** (`WK-20260717-harness-generation`, ainda não
  aberto) deve **converter e deletar** `_iter_source_files` + `_git_ignored_paths`
  para o seam `Ignorer` compartilhado — os 4 walkers do pacote (`codemap.py:190`,
  `doctor.py` ×2, `configure.py:138`) continuam duplicados, com `SKIP_DIRS`/
  `_CODEMAP_SKIP` **já divergentes**. Este fix é conversão futura (§7), não
  coexistência.
- **AcheiVc** não recebeu o kit ainda — o operador vai testar `install-agents
  --upgrade` lá por conta própria (repo em layout legado `docs/`, 27 arquivos
  pendentes → limpar antes; a migração move `docs/` → `.docs/` com backup).

---

## Current Status (histórico)

- work_id: WK-20260702-per-host-identity-runtime
- date: 2026-07-02
- branch: (working tree — not committed)
- status: Per-host identity runtime implemented and validated (65 tests green),
  pending review/commit. Issue moved to `[review]`. Companion AI-Agents contract
  issue still `[draft]` (separate epic).

## Summary (2026-07-02, per-host identity)

Added runtime collection + enforcement of per-host/instance identity. New module
`governancekit/identity.py` persists `operator_name`, `host_id`, `instance_path`,
`sibling_path`, `assigned_ports`, `branch_ownership` to a gitignored per-instance
file `.governancekit-identity.json` (no secrets). `configure` collects the fields
(interactive prompts + `--operator-name/--host-id/--instance-path/--sibling-path/
--assigned-ports/--branch-ownership` flags), refuses to save while a required field
(operator_name/host_id/instance_path) is missing, and auto-adds the file to
`.gitignore`. `doctor` gained a MANDATORY `host identity` gate (`[FAIL]` /
`ok:false` when missing or incomplete) and an advisory `sibling branch` same-branch
guard. `resume` shows active `operator@host` + git branch and warns on sibling
collision. Field names align with the AI-Agents companion contract issue. Tests:
`test_configure.py` (identity collection), `test_doctor.py` (pass/fail on
presence/absence/incomplete), `test_resume.py` (display + missing warning).

### Next Steps (per-host identity)

- Review the working-tree diff; commit if accepted (do NOT deploy — gated step).
- Implement companion AI-Agents contract issue (`mandate-per-host-programmer-identity`).

## Prior Status (WK-20260701-dotdocs-kit-layout)

- branch: feature/WK-20260701-dotdocs-kit-layout
- status: AI-GovernanceKit side implemented and validated, pending
  review/commit. AI-Agents side scaffolded as epic (not yet implemented).

## Summary

Moved the kit out of `docs/` into `.docs/`, freeing `docs/` to be 100% the host
project's. Resolves three operator concerns: (1) legacy projects that already used
`docs/` are no longer invaded; (2) ownership is unambiguous (kit = `.docs/`, project
= `docs/`); (3) tracking kit docs in git is now a prompted, persisted choice.

Key mechanics in `governancekit/install_agents.py`:
- `_dest_rel()` maps source `docs/…` → dest `.docs/…` for kit docs, keeping
  project-owned seeds (`required-reading.md`, `napkin-lessons.md`) in `docs/`.
  Resilient even if the AI-Agents source repo still uses `docs/`.
- `_FRESH_PATHS` replaces the wholesale `docs` copy with explicit kit paths, so a
  new project never inherits the source repo's active issues/project docs.
- `_migrate_legacy_layout()` (run before `--upgrade`/`--docs-only`) moves kit docs
  `docs/*` → `.docs/`, promotes `docs/project/*` → `docs/`, backs up to
  `.docs-migration-bak/`, reports collisions, idempotent (no-op once `.docs/` exists).
- `_resolve_track_kit_docs()` + `.governancekit` config: CLI flag → config → prompt
  → default (untracked). `.gitignore` emits a single `.docs/` entry (or omits it when
  tracking); secrets (`.credentials`, `handoff.md`) stay ignored regardless.

This repo migrated in place (`git mv` docs → .docs; `docs/project/README.md` →
`docs/README.md`). Doctor readiness checks now read `.docs/`.

## Next Steps

- Review the diff; commit if accepted (do NOT deploy — separate gated step).
- Implement the twin AI-Agents epic `docs/issues/002-dotdocs-kit-layout-[draft]/`
  (restructure source to `.docs/`, update `install-agents-kit.sh` + migration,
  update AGENTS.md/CLAUDE.md/READMEs). Coordinate merges so installer and source
  don't diverge.

## Blockers / Risks

- Cross-repo: AI-Agents source still uses `docs/`. `_dest_rel` mapping makes this
  non-blocking, but the source should be restructured for consistency.
- Legacy migration validated by unit test, not a full network end-to-end install.
- `install-agents-kit.sh` (AI-Agents shell mirror) NOT yet updated — tracked as
  task 002 in the AI-Agents epic.

## Files Changed

AI-GovernanceKit:
- `governancekit/install_agents.py` — `.docs/` layout, `_dest_rel`, legacy migration,
  track-kit-docs prompt/config, `_FRESH_PATHS`/`_UPGRADE_PATHS` rework
- `governancekit/cli.py` — `--track`/`--no-track` group, migration/gitignore output
- `governancekit/doctor.py` — readiness checks read `.docs/`
- `AGENTS.md`, `README.md`, `docs/required-reading.md`, `docs/README.md`,
  `docs/napkin-lessons.md`, `.docs/software-overview.md`, `.docs/agents/README.md`
- moved: `docs/{agents,workflows,software-overview.md,limits.md,issues/templates}`
  → `.docs/…`; `docs/project/README.md` → `docs/README.md`
- `tests/test_install_agents.py`, `tests/test_doctor.py`

Issue 002 (installer ↔ source alignment) — IMPLEMENTED (pending review):
- `governancekit/install_agents.py` — new `_resolve_src()` reads kit docs from the
  source's `.docs/` (restructured source, AI-Agents commit 6a5e6ba) with fallback to
  `docs/` (legacy source); project seeds always from `docs/`. Wired into
  `_do_fresh`/`_do_upgrade`. Folder renamed `002-…-[draft]` → `[review]`.
- `tests/test_install_agents.py` — +2 tests (57 total, green).

WhatsApp notification (wa-hub / Nexo):
- `scripts/notify-nexo.sh` (new) — sends an operator DM as "*GovernanceKit* —"
  (identity via text signature; ensureSenderTag idempotent, no alias hijack).
  Config in `~/.config/wa-hub/governancekit.env` (0600, local-only) — currently an
  INTERIM shared key; proper provisioning requested in wa-hub issue 014.
- Completion DM sent (id 3EB06519843829755B7736).

Landing / docs pages:
- `docs/index.html` — new trilingual (PT/ES/EN) "Novidades / What's new" band for a
  semi-technical audience (benefit-first), nav link `#whatsnew`, button → melhorias.html
- `docs/melhorias.html` (new) — beautiful technical backlog page: what/why/how/impact/
  migration/roadmap, with a docs/ → .docs/ directory-diff signature. Reuses the brand
  tokens (Uruguay palette, Fraunces/Inter/JetBrains Mono). The roadmap has a "outras
  coisas" placeholder to extend. NOTE: mirror/link from the AI-Agents index later.

AI-Agents (source kit) — scaffolded, not implemented:
- `docs/issues/002-dotdocs-kit-layout-[draft]/` (epic + 3 tasks)

## Checks / Tests Executed

- `python3 -m pytest -q` -> PASS, 55 tests.
- Local integration (no network): `_do_fresh` + `_ensure_project_docs` on a fake
  source -> kit in `.docs/`, project files in `docs/`, readiness flag reset,
  `.gitignore` emits single `.docs/`.
- Legacy migration covered by `test_migrate_legacy_layout_moves_kit_and_promotes_project`.

## Security Impact

- mitigated security impact
- Secrets (`.credentials`, `handoff.md`) remain in the managed `.gitignore` section
  regardless of the track-kit-docs choice — verified by regression test.
- `.governancekit` stores only the boolean track preference; no secrets.

## Model / Migration Changes

- No DB/model migrations. Repo-layout migration only (docs → .docs), reversible via
  `.docs-migration-bak/` when the installer performs it on legacy projects.
