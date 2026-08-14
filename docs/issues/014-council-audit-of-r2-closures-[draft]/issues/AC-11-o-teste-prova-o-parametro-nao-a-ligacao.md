# Issue AC-11 — origem: concílio de fechamentos, 2026-08-13 (lente: the claim auditor)

## AC-11 — o teste prova o parâmetro e nunca a ligação com `--docs-only` [média]

### Contexto

O achado `ade371f5#2` era: *"o `rmtree` no topo do `_do_upgrade` serve os dois modos,
então o refresh de documentação apaga os backups dos contratos de raiz que ele nunca
toca"*. O gatilho é **dois comandos reais em sequência**: `--upgrade`, depois
`--docs-only`.

O fechamento é `test_docs_only_does_not_destroy_the_backups_of_a_full_upgrade`. O teste
chama `ia._do_upgrade(..., clear_backups=False)` **à mão**. Ele prova que o parâmetro
funciona. Nunca prova que `--docs-only` o passa.

### Reprodução

Reinstalar o defeito no único lugar onde ele podia existir — o call site:

```
mutate install_agents.py: 'clear_backups=not docs_only,' -> 'clear_backups=True,'
pytest tests/  =>  506 passed, 2 skipped, 6 subtests passed in 41.45s
```

Controle, mutando dentro da função:

```
mutate: 'if clear_backups:' -> 'if True:'
pytest tests/  =>  1 failed, 505 passed
                   FAILED …test_docs_only_does_not_destroy_the_backups_of_a_full_upgrade
```

O teste enxerga a função e não enxerga a ligação. O gatilho do achado — `install_agents.py:463`
— não tem cobertura nenhuma.

### Objetivo

Que o teste exercite o gatilho que o achado descreve: dois comandos, na ordem, pela
porta de entrada real.

### Escopo

- Um teste que chama `run_install_agents(upgrade=True)` e depois
  `run_install_agents(docs_only=True)`, e afirma sobre `.gk/pre-upgrade/`. Nível de
  entrada, não da função interna.
- Manter o teste atual — ele cobre a função e é barato. O problema é ele ser o **único**.
- Esta é a forma geral que `AC-16`, `AC-17` e `AC-18` também têm. Vale extrair a lição
  para `docs/napkin-lessons.md` uma vez, não quatro: **teste que chama a função interna
  com o argumento certo prova o argumento, não a decisão de passá-lo.**

### ARO

- **Assumption**: `run_install_agents` é testável sem rede. Os repros do concílio
  mostraram que sim, com `_download` mockado.
- **Risk**: teste de ponta a ponta é mais lento e mais frágil. Mitigação: um por gatilho,
  não um por asserção.
- **Owner**: a definir.

### Plano de teste

- `--upgrade` (gera backup) → `--docs-only` ⇒ `.gk/pre-upgrade/` intacto.
- Mutação `clear_backups=not docs_only` → `clear_backups=True` ⇒ **vermelho**. É esta a
  mutação que hoje passa; ela é o critério de aceite desta issue.
- O teste antigo continua verde.

### DoD

- A mutação no call site fica vermelha.
- A lição sobre "provar o parâmetro em vez da ligação" está escrita uma vez, em
  `napkin-lessons.md`.
