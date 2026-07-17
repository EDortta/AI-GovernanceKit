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
- `governancekit/doctor.py:102-116` (`_iter_source_files`)
- `tests/test_doctor.py`

## Out of Scope
- **Unificar os 4 walkers do pacote.** `codemap.py:190` (`_walk_source`, gitignore-aware),
  `doctor.py:102`, `doctor.py:431`, `configure.py:138` — quatro cópias, com
  `SKIP_DIRS`/`_CODEMAP_SKIP` **já divergentes** (o do doctor não tem `.idea`/`.vscode`).
  É o épico `WK-20260717-harness-generation`, que extrai `walk.py` e resolve isto
  de raiz. Ver "Decisão pendente".

## Decisão pendente (operador)

Duas saídas, e **elas não devem coexistir** (`design-standards.md` §7: não deixe o
caminho velho e o novo "por via das dúvidas"):

**(a) Correção pontual aqui** — `_iter_source_files` passa a usar
`git check-ignore --stdin` (precedente no próprio arquivo: `doctor.py:401` já
shella `git check-ignore -q`) e a pular diretório que contenha `.git`
(= submódulo). Rápido; adiciona uma quinta variação de walk ao pacote.

**(b) Esperar o épico do arnês**, que extrai `walk.py` com um seam `Ignorer`
(`NullIgnorer`/`GlobIgnorer`/`GitIgnorer`) e converte os quatro sítios. Correto;
mais longe.

Recomendação: **(b)**, com esta task ficando `[blocked]` e citada no épico — a não
ser que o ruído incomode antes. Adicionar um quinto walker para depois deletá-lo é
exatamente o que §7 chama de quinta coisa para manter em sincronia.

**Atenção, se for (b):** unificar `SKIP_DIRS` **muda o resultado do doctor** —
`_CODEMAP_SKIP` não tem `.idea`/`.vscode`, então um repo com `.vscode/*.sh` deixa
de ser varrido. É mudança de comportamento; pinar com teste de caracterização
antes (`design-standards.md` §1).

**Atenção, em qualquer saída:** o doctor deve continuar **não** respeitando
gitignore no `_check_tracked_secret_files` — lá a pergunta é o que o **git**
rastreia, não o que existe no disco. São perguntas diferentes; um walker
compartilhado precisa de um `Ignorer` explícito por chamador, não de um default
global.

## Test Plan

- `test_advisory_scan_skips_gitignored_files` — cria repo temp com `.gitignore`
  contendo `build/`, planta `build/x.py` com padrão de advisory; sem o fix o hit
  aparece. **Falha sem o fix.**
- `test_advisory_scan_does_not_descend_into_submodule` — dir com `.git` dentro
  e arquivo com padrão. **Falha sem o fix.**
- `test_advisory_scan_still_finds_tracked_source` — guard contra pular demais.

`run_doctor` hoje é lista literal (`doctor.py:46`) sem seam de checks, então testar
um check isolado exige `write_valid_repo()` inteiro (`tests/test_doctor.py:162`).
O épico do arnês introduz `run_doctor(root, *, checks=None)` — se (b) for a saída,
estes testes ficam triviais.

## Security
- `no security impact` no comportamento defendido: o scan é advisory e continua
  varrendo todo arquivo **rastreado**. O risco é o oposto — pular demais e perder
  hit real. Daí o terceiro teste.

## Privacy
- Personal data impact: no. **Nota:** varrer gitignored significa que o doctor
  hoje lê arquivos que o operador excluiu deliberadamente do git — `.env` local,
  dumps. A saída cita `file:line`. Não houve vazamento observado (a saída é local),
  mas parar de ler o que é gitignored **também é higiene de privacidade**, não só
  redução de ruído.

## DoD
- [ ] Decisão (a) vs (b) registrada pelo operador
- [ ] Hit em arquivo gitignored não aparece
- [ ] Scan não desce em submódulo
- [ ] Hit em fonte rastreado continua aparecendo
- [ ] Se (b): `_check_tracked_secret_files` **continua** ignorando o gitignore — a
      pergunta dele é sobre o índice do git, não sobre o disco
