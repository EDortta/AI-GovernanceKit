# Issue AC-3 — origem: concílio de fechamentos, 2026-08-13 (lente: the sweep skeptic)

## AC-3 — a evidência diz "byte for byte" e nada compara bytes [alta]

### Contexto

Metade do fechamento de `6bb1027e#3` prometia: *"remove com revisão dispensada, **e o
arquivo do operador nunca entra**"*.

O que o código faz (`remove_agents.py:306-307`):

```python
items.append(RemovalItem(
    rel, "kit-seeded-unchanged", 1.0, "remove",
    ["matches the file this kit seeds, byte for byte"], False, referenced,
))
```

A única prova exigida para chegar nesse ramo é **"o nome está em
`_CREDENTIALS_SCAFFOLDING` e o instalador registrou ter semeado"**. Nenhum byte é
comparado com nada. A string impressa ao operador afirma uma comparação que não
acontece, no exato campo (`requires_operator_review=False`) que dispensa a revisão
humana — e com `confidence=1.0`.

O comentário logo acima do código descreve corretamente a intenção (*"Byte-identity
against the shipped copy is the evidence the manifest used to carry"*). A intenção não
virou código.

### Reprodução

Alvo com `.credentials/README.md` reescrito pelo operador:

```
'.credentials/README.md'  class='kit-seeded-unchanged' conf=1.0 action='remove' review=False
    evidence=['matches the file this kit seeds, byte for byte']
(conteudo real: '# Credenciais\n\nNOTA DO TIME: rotacionar chaves toda sexta. NAO E TEXTO DO KIT.')
```

Hoje o dano é contido só porque `AC-2` impede o `apply` de agir. No dia em que `AC-2`
fechar, a prosa do operador vai junto, sem revisão.

### Objetivo

Que a evidência impressa seja a evidência usada, e que dispensar revisão humana exija
prova de verdade.

### Escopo

- O ramo `kit-seeded-unchanged` passa a comparar o sha256 do arquivo no alvo contra o
  sha256 da cópia que o kit semeia. É o que o comentário já diz que deveria acontecer.
- Sem correspondência de bytes: `preserve`, `confidence` baixa,
  `requires_operator_review=True`, e a evidência descreve o que de fato se sabe.
- Regra geral, escrita: **nenhuma string de evidência afirma uma verificação que o ramo
  não executou.** Vale para os outros ramos do mesmo arquivo.
- De onde vem a cópia do kit para comparar (tarball pinado? snapshot? hash gravado no
  estado no momento da semeadura?) é decisão de design desta issue. Gravar o hash na
  semeadura é o mais barato e não depende de rede.

### ARO

- **Assumption**: existe um ponto onde o kit sabe o conteúdo que semeou. Se não existir,
  a semeadura é que precisa gravá-lo.
- **Risk**: comparar contra o tarball exige rede num comando que hoje roda offline.
  Mitigação: gravar o sha256 no estado no momento da semeadura.
- **Risk**: alvo semeado por uma versão anterior não tem o hash gravado — mesmo problema
  que `AC-5`. As duas issues precisam de uma resposta comum para a população legada.
- **Owner**: a definir.

### Plano de teste

- `.credentials/README.md` byte-idêntico ao semeado ⇒ `remove`, revisão dispensada.
- Um byte alterado ⇒ `preserve`, `requires_operator_review=True`, evidência sem a frase
  "byte for byte".
- Mutação: voltar a decidir por presença do nome ⇒ o teste do arquivo editado fica
  vermelho. **A asserção fica dentro do `with TemporaryDirectory()`** — ver `AC-4`.
- Varredura: nenhuma outra string de evidência do módulo afirma verificação não feita.

### DoD

- A evidência impressa corresponde ao que o ramo verificou.
- Arquivo do operador com o nome do andaime nunca sai como `remove`/`review=False`.
- Teste verificado por mutação, com o alvo temporário vivo na hora da asserção.
