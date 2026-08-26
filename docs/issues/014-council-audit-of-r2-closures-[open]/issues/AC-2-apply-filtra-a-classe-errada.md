# Issue AC-2 — origem: concílio de fechamentos, 2026-08-13 (lente: the sweep skeptic)

## AC-2 — o `remove-agents apply` nunca remove o que o plano manda remover [alta]

### Contexto

O achado `6bb1027e#3` era: *"os oito caminhos entram como unknown/preserve, então a
de-adoção continua deixando o andaime do kit no disco — o sintoma do achado, intacto"*.

O fechamento mudou o **plano**: os oito caminhos de `.credentials/` agora saem como
`kit-seeded-unchanged`, `action="remove"`, `confidence=1.0`.

O `apply` não foi tocado:

```python
removable = [item for item in plan.items
             if item.classification == "kit-owned-unchanged" and item.action == "remove"]
```

`remove_agents.py:380`. A classe que o plano emite é `kit-seeded-unchanged`
(`remove_agents.py:306`). **Ela não está no filtro.** O sintoma que o achado descreve
segue exatamente onde estava — a de-adoção deixa o andaime no disco — e agora com o
agravante de o kit ter dito por escrito que ia removê-lo.

### Reprodução

```
$ governancekit --root T remove-agents plan
  remove: .credentials/.gitignore [kit-seeded-unchanged]
  remove: .credentials/README.md [kit-seeded-unchanged]
  remove: AGENTS.md [kit-owned-unchanged]
$ governancekit --root T remove-agents apply
  removed: AGENTS.md
depois do apply, .credentials ainda tem: ['.gitignore', 'README.md']
```

A pergunta em aberto da própria rodada 2 — *"apply do remove-agents não exercitado de
ponta a ponta"* — **era** o defeito. Ela foi escrita e não foi seguida.

### Objetivo

Que o `apply` remova o que o `plan` diz que vai remover, e que a divergência entre os
dois seja impossível de reintroduzir em silêncio.

### Escopo

- `apply_removal_plan` passa a decidir por `action`, não por `classification` — o
  `action` já é a decisão; classificar de novo no `apply` é a segunda fonte de verdade
  que produziu este defeito.
- Se alguma classe precisa mesmo ser excluída do `apply`, a exclusão é explícita e
  nomeada, não implícita por omissão de uma string.
- Um teste de **ponta a ponta** `plan` → `apply`: o que o plano imprime como `remove`
  some do disco. É o teste que a pergunta em aberto pedia.
- Fora de escopo: a evidência mentirosa do plano (`AC-3`) e a revisão dispensada
  (`AC-3`). Esta issue é só sobre plano e apply concordarem.

### ARO

- **Assumption**: `action` é a decisão e `classification` é a explicação. Filtrar por
  explicação é o erro de categoria que causou isto.
- **Risk**: corrigir o filtro faz o `apply` passar a remover de verdade os oito — e hoje
  a evidência que autoriza isso é falsa (`AC-3`). **`AC-3` tem de fechar antes ou junto
  com esta**, ou a correção transforma um no-op em perda de arquivo do operador.
- **Owner**: a definir.

### Plano de teste

- `plan` + `apply` num alvo com os oito semeados ⇒ os oito somem, backup gravado.
- `plan` + `apply` num alvo onde um deles foi editado ⇒ o editado **fica** (depende de
  `AC-3`).
- Mutação: reintroduzir o filtro por `classification` ⇒ o teste de ponta a ponta fica
  vermelho.
- Qualquer item com `action == "preserve"` nunca é tocado pelo `apply`.

### DoD

- `plan` e `apply` concordam, provado por teste de ponta a ponta.
- A mutação que reintroduz o defeito deixa esse teste vermelho.
- `AC-3` fechada antes ou no mesmo commit.
