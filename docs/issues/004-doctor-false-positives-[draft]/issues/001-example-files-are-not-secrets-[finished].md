# Task: `.example` não é segredo — o doctor reprova o que o próprio kit distribui

## Metadata
- work_id: WK-20260717-doctor-false-positives
- date: 2026-07-17
- owner: [OPERATOR_NAME]
- related_commit: <planned>

## Parent Epic
- 004-doctor-false-positives

## Objective

`_check_tracked_secret_files` (`governancekit/doctor.py:352`) reprova arquivos de
**template**. Dois caminhos independentes, no mesmo check:

```python
forbidden_prefixes = (".credentials/",)                  # linha 370
...
if path.startswith(forbidden_prefixes)                   # linha 377  -> pega .credentials/README.md
   or Path(path).name.startswith(".env")                 # linha 379  -> pega .env.example
```

1. **linha 379** — `.name.startswith(".env")` casa com `.env.example`,
   `.env.sample`, `.env.template`.
2. **linha 377** — `.credentials/` como prefixo reprova **todo** arquivo sob
   `.credentials/`, inclusive os `*.example` e o `README.md` que **o AI-Agents
   distribui de fábrica** (`_FRESH_PATHS` inclui `.credentials`).

## O ponto que dói

**O doctor reprova o próprio kit-fonte.** `handoff.md` do AI-Agents já registrava
`governancekit doctor` como *"FAIL pré-existente ... `.credentials/*.example`
rastreados"*. Isso foi lido como estado conhecido do repo, não como bug da
ferramenta. É a ferramenta que está errada.

E a lógica correta **já existe no repositório gêmeo** —
`AI-Agents/scripts/run-checks.sh` bloco 4:

```bash
offenders="$(git ls-files | grep -E '(^\.env|/\.env|(^|/)\.credentials$)' || true)"
offenders+="$(git ls-files '.credentials/*' | grep -vE '\.example$|(^|/)(README|\.gitignore)' || true)"
```

Note o `grep -vE '\.example$|(^|/)(README|\.gitignore)'`. Os dois gates
respondem à mesma regra (`security-standards.md` §1) e **discordam**. O bash está
certo; o Python está errado.

## In Scope
- `governancekit/doctor.py:352-385`
- `tests/test_doctor_tracked_secrets.py`

## Out of Scope
- Alargar a exclusão para `.env*`. **`.env.local` é segredo de verdade.** A
  exclusão é por sufixo `.example` (+ `README`/`.gitignore` sob `.credentials/`),
  nunca por prefixo `.env`.

## Correção proposta

Exclusão explícita antes das regras de proibição, espelhando o `run-checks.sh`:

```python
def _is_template(path: str) -> bool:
    name = Path(path).name
    return (
        name.endswith(".example")
        or name.endswith(".sample")
        or (path.startswith(".credentials/") and name in ("README.md", ".gitignore"))
    )
```

e `offenders = [p for p in tracked_files if not _is_template(p) and (...)]`.

`design-standards.md` §2: `_is_template` é função pura sobre string — testável
sem FS, sem git, sem mock.

## Test Plan

`tests/test_doctor_tracked_secrets.py` (3 testes hoje). Acrescentar — nomes que
nomeiam a falha, não a função (`design-standards.md` §1):

- `test_env_example_is_not_a_tracked_secret` — **falha sem o fix** (é o bug)
- `test_credentials_example_and_readme_are_not_secrets` — **falha sem o fix**
- `test_env_local_is_still_a_tracked_secret` — o guard contra afrouxar demais;
  passa hoje e **deve continuar passando**
- `test_real_env_is_still_a_tracked_secret` — idem

`design-standards.md` §1: escrever, ver falhar nos dois primeiros, então corrigir.

Rodar: `python -m pytest tests/test_doctor_tracked_secrets.py`
(`not validated:` o repo não documenta o comando de teste em lugar nenhum —
`.pytest_cache/` existe, mas README/AGENTS.md não citam pytest. Lacuna própria.)

## Security
- `mitigated security impact`. O check fica **mais preciso**, não mais permissivo:
  a exclusão é por sufixo comprovado de template. Superfície: um repo que nomeasse
  um segredo real como `x.example` passaria — mas esse já é o contrato do kit
  inteiro (`.credentials/*.example` são distribuídos como template).
- Abuse path: commitar segredo em arquivo terminado em `.example`. Mitigação: o
  scan de advisories continua varrendo o conteúdo.

## Privacy
- Personal data impact: no.

## DoD
- [ ] `.env.example` e `.credentials/*.example` passam
- [ ] `.env` e `.env.local` continuam reprovando
- [ ] 2 testes que falham sem o fix + 2 que guardam contra afrouxar
- [ ] `governancekit --root <AI-Agents> doctor` deixa de reprovar por `.credentials/*.example`
- [ ] A divergência com `run-checks.sh` fechada — os dois gates concordam
