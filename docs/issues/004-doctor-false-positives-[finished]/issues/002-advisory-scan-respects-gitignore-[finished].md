# Task: o scan de advisories varre build artifact e submódulo

## Metadata
- work_id: WK-20260717-doctor-false-positives
- date: 2026-07-17
- owner: [OPERATOR_NAME]
- related_commit: <planned>

## Parent Epic
- 004-doctor-false-positives

## Objective

`_check_security_advisories` (`doctor.py:119`) percorre via `_iter_source_files`
(`doctor.py:102`), que **não respeita `.gitignore` e não para em submódulo**.
Resultado observado no AcheiVc (2026-07-17):

```
[HINT] security advisories: review 15 advisory hit(s): ... non-CSPRNG for secrets/ids ×4
  - lct-acheivc-app/.dart_tool/flutter_build/<hash>/main.dart.js:4114  [non-CSPRNG]
  - lct-acheivc-app/.dart_tool/flutter_build/<hash>/main.dart.js:57582 [non-CSPRNG]
```

`main.dart.js` é **saída do compilador Flutter**, dentro de `.dart_tool/`
(gitignored), dentro do submódulo `lct-acheivc-app`. Três razões independentes
para nunca ter sido lido. **4 dos 15 hits eram esse arquivo.**

## Por que isso importa mais do que parece

O `security advisories` é `advisory=True` — não reprova
(`DoctorResult.ok` exclui advisory, `doctor.py:24-26`). O custo não é um FAIL
falso: é **treinar o operador a ignorar a saída**. Quem lê "15 hits" e vê build
artifact para de ler na segunda vez. Aí o `shell injection risk ×3` — que no
AcheiVc é `subprocess.run(cmd, shell=True)` real, em três arquivos — some no meio
do ruído.

Um scan de segurança cuja saída se aprende a ignorar é pior que nenhum: ele
aposenta o risco na cabeça do leitor e o deixa no código
(`design-standards.md` §1, a mesma forma do claim de cobertura falso).

## In Scope
- `governancekit/doctor.py` — `_iter_source_files` (submódulo) + novo
  `_git_ignored_paths` (gitignore) + o filtro em `_check_security_advisories`
- `tests/test_doctor_advisory_scan.py` (novo)

## Out of Scope
- **Unificar os 4 walkers do pacote.** `codemap.py:190` (`_walk_source`, gitignore-aware),
  `doctor.py:102`, `doctor.py:431`, `configure.py:138` — quatro cópias, com
  `SKIP_DIRS`/`_CODEMAP_SKIP` **já divergentes** (o do doctor não tem `.idea`/`.vscode`).
  É o épico `WK-20260717-harness-generation`, que extrai `walk.py` e resolve isto
  de raiz. Ver "Decisão pendente".

## Decisão tomada (operador, 2026-07-19: "ataca task 002")

Feita a **correção pontual (a)** — mas o medo que fazia eu recomendar (b) **não
se materializou.** A opção (a) foi descrita como "adiciona uma quinta variação de
walk ao pacote"; a implementação **não adicionou walker nenhum**:

- `_iter_source_files` foi modificado **no lugar** para pular subdiretório que
  contenha `.git` (submódulo/repo aninhado). Continua sendo um walker, o mesmo.
- Gitignore virou `_git_ignored_paths(root, paths)` — um helper de **consulta ao
  git** (`git check-ignore -z --stdin`, em uma chamada batch), não um walker. Ele
  filtra a lista que o walker já produziu.

Como não há mecanismo geral novo com zero adotantes, o `§7` (a "quinta coisa para
manter em sincronia") não se aplica. O que o épico do arnês fará depois é
**converter** estes dois sítios para o seam `Ignorer` de `walk.py` e **deletá-los**
(`§7`, na direção certa) — trabalho de conversão, não de coexistência.

**Preservado de propósito:** `_check_tracked_secret_files` continua **não**
respeitando gitignore — lá a pergunta é o que o **git rastreia**, não o que existe
no disco. `_git_ignored_paths` é chamado só pelo advisory scan; o check de
segredos usa `git ls-files`, intocado. São perguntas diferentes.

**Fora de escopo, confirmado:** unificar `SKIP_DIRS`/`_CODEMAP_SKIP` (que mudaria
o resultado do doctor em repo com `.vscode/*.sh`) **não** foi feito — fica para o
`walk.py` do épico do arnês, com caracterização antes.

## Test Plan — executado (`design-standards.md` §1: ver falhar antes de corrigir)

`tests/test_doctor_advisory_scan.py` (novo), testando `_check_security_advisories`
direto, no molde de `test_doctor_tracked_secrets.py`:

- `test_scan_skips_gitignored_files` — **falhava sem o fix.** Usa `.dart_tool/`
  (o caso real), **não** `build/` — `build` já está em `_CODEMAP_SKIP`, então o
  primeiro rascunho passava pela razão errada e não exercia o gitignore. Corrigido
  antes de valer (o próprio §1: teste que passa por acaso não testa nada).
- `test_scan_does_not_descend_into_submodule` — **falhava sem o fix.**
- `test_scan_flags_non_ignored_sibling_of_ignored_dir` — **falhava sem o fix**
  (o irmão ignorado sumia, o não-ignorado ficava).
- `test_scan_still_flags_tracked_source` — guard contra pular demais; passa antes
  e depois.
- `test_scan_without_git_still_scans_everything` — fail-open (§6): sem git, o scan
  varre **mais**, nunca menos.

## Security
- `no security impact`. A direção de falha é **fail-open** (`design-standards.md`
  §6): git indisponível / não-repo → `_git_ignored_paths` devolve conjunto vazio →
  o scan inclui tudo. A direção perigosa para um scan de segurança seria pular em
  silêncio; isso nunca acontece. O `test_scan_without_git_still_scans_everything`
  fixa isso.

## Validado
- `python3 -m pytest tests/` → **100 passed** (95 + 5 novos), zero regressão.
- `governancekit --root <AcheiVc> doctor`: **15 hits → 7**. Os 4 `main.dart.js`
  (`.dart_tool/`, gitignored, dentro de submódulo) sumiram; os 3 `shell injection`
  reais do `wa-hub-client` (rastreados) continuam. Um `weak password hash ×3` em
  `converseiro.py`, antes afogado no ruído, agora aparece — era o sinal perdido.
- `bash <AI-Agents>/scripts/run-checks.sh` → all checks passed (gêmeo intocado).

## Privacy
- Personal data impact: no — e **melhorado**. Antes, varrer gitignored fazia o
  doctor ler arquivos que o operador excluiu de propósito do git (`.env` local,
  dumps) e citá-los por `file:line`. O fix para de lê-los: é higiene de
  privacidade entregue, não só redução de ruído.

## DoD
- [x] Decisão (a) vs (b) registrada pelo operador — (a), pontual, sem walker novo
- [x] Hit em arquivo gitignored não aparece
- [x] Scan não desce em submódulo
- [x] Hit em fonte rastreado continua aparecendo
- [x] `_check_tracked_secret_files` **continua** ignorando o gitignore — usa
      `git ls-files`, não `_iter_source_files`; intocado
- [x] Fail-open verificado: sem git, o scan varre tudo (§6)
