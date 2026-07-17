# doctor: falsos positivos que treinam o operador a ignorar o FAIL

## Metadata
- work_id: WK-20260717-doctor-false-positives
- date: 2026-07-17
- owner: [OPERATOR_NAME]
- related_commit: <planned>

## Objective
- Parar de reprovar `.env.example` e `.credentials/*.example` como segredo rastreado (`_check_tracked_secret_files`).
- Parar de varrer arquivos gitignored e conteúdo de submódulo no scan de security advisories (`_iter_source_files`).

## Scope
- In scope: `governancekit/doctor.py` (`_check_tracked_secret_files`, `_iter_source_files`), `tests/test_doctor_tracked_secrets.py`, `tests/test_doctor.py`.
- Out of scope: unificar os 4 walkers do pacote (é o épico `WK-20260717-harness-generation`, que resolve a task 002 de raiz). Esta issue pode ser fechada com a correção pontual **ou** absorvida por aquele épico — decisão do operador.

## ARO
- Acceptance: um repo com `.env.example` e `.credentials/x.example` rastreados passa no `tracked secrets`; um `.env` de verdade continua reprovando. O scan de advisories não reporta hit em arquivo gitignored nem dentro de submódulo.
- Risk: **afrouxar demais.** O check existe por `security-standards.md` §1. A correção deve excluir apenas o que é comprovadamente template (`*.example`, `README`, `.gitignore`), nunca alargar para `.env*`.
- Operations: nenhuma. Ferramenta de linha de comando local.

## Descoberto em

Uso real, 2026-07-17: `governancekit --root ~/Sync/Projects/Lucedata/AcheiVc doctor`.

De 15 findings, **5 eram ruído** — 1 FAIL falso e 4 HINTs de build artifact. O
operador que roda isso duas vezes e vê ruído para de ler a saída; aí o FAIL real
(`gitignore secrets: .gitignore does not cover .env`, que era verdade e foi
corrigido) some junto no meio.

## Task Index
- 001-example-files-are-not-secrets-[draft].md
- 002-advisory-scan-respects-gitignore-[draft].md
