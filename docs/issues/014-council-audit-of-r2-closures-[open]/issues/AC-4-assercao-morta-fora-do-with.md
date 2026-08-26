# Issue AC-4 — origem: concílio de fechamentos, 2026-08-13 (lente: the claim auditor)

## AC-4 — o teste que protege o arquivo do operador é código morto [alta]

### Contexto

`tests/test_remove_agents_poisoned_manifest.py::test_the_operators_own_credential_files_are_never_candidates`
existe, tem nome exato, roda e passa. Ele não testa nada.

O `with TemporaryDirectory()` fecha na linha 171. `build_removal_plan(root)` é chamado na
linha 178, **depois**, quando `root` já foi apagado. O plano volta vazio, `readme is
None`, e o `if` da linha 180 — onde mora a única asserção que protege o arquivo do
operador — nunca executa.

Sobrevivem só duas asserções, sobre `identity.json` e `llm/openrouter.key`, e essas
passam por outro motivo: os nomes não estão em `_CREDENTIALS_SCAFFOLDING`, então nunca
chegariam ao ramo perigoso de qualquer forma.

### Reprodução

Mutação que reintroduz o defeito que o teste deveria pegar — trocar a evidência de
semeadura por mera presença no diretório:

```
mutate: 'if expected is None and rel in _kit_seeded_credentials(root):'
     -> "if expected is None and rel.startswith(_CREDENTIALS_DIR + '/'):"

pytest ...::test_the_operators_own_credential_files_are_never_candidates -v
=> 1 passed
```

Reproduzindo o corpo do teste com os mesmos helpers, mas com o tmpdir **ainda vivo**:

```
'.credentials/README.md' remove 1.0 False ['matches the file this kit seeds, byte for byte']
```

O teste passa porque não observa nada.

### Objetivo

Que a asserção execute, e que a classe inteira de "asserção depois do `with`" fique
detectável neste repositório.

### Escopo

- Corrigir a indentação: a asserção volta para dentro do `with`.
- **Varrer a suíte inteira** pela mesma forma — asserção sobre estado de um
  `TemporaryDirectory`/`tmp_path` fora do bloco, `if` cuja condição só é verdadeira
  quando o alvo existe, teste cujo corpo inteiro é opcional. É a lente do sweep skeptic
  aplicada aos testes.
- Considerar um guarda barato e permanente: teste que falha se `build_removal_plan`
  recebe um `root` inexistente, em vez de devolver plano vazio em silêncio. Um plano
  vazio para um diretório que não existe é a condição que tornou a asserção invisível.
- Fora de escopo: o conteúdo da asserção — isso é `AC-3`.

### ARO

- **Assumption**: este é um erro de forma (indentação), não de intenção. O teste sabe o
  que quer afirmar.
- **Risk**: corrigido, o teste fica vermelho — porque o defeito de `AC-3` é real.
  **Isso é o resultado desejado**, e é a prova de que `AC-3` precisa fechar.
- **Risk**: a varredura pode achar outros testes mortos e alargar o escopo. Mitigação:
  cada um vira issue própria; esta fecha com a lista.
- **Owner**: a definir.

### Plano de teste

- O teste corrigido fica **vermelho** contra o `HEAD` atual e verde depois de `AC-3`.
- A mutação "presença em vez de semeadura" deixa o teste vermelho.
- A varredura devolve uma lista escrita — mesmo que vazia, escrita.

### DoD

- A asserção executa (provado por ela ficar vermelha antes de `AC-3`).
- A varredura por testes da mesma forma está feita e registrada.
- Nenhum teste do repositório afirma sobre estado de diretório já apagado.

---

## A varredura que o DoD pede — registrada, 2026-08-13

O DoD diz *"a varredura devolve uma lista escrita — mesmo que vazia, escrita"*. Eu não a
fiz, e **dois céticos a fizeram por mim** e apontaram a omissão. Fica aqui porque uma
varredura que existe só na saída de um subagente não é registro.

**Método (second caller, o mais estreito):** AST sobre `tests/*.py`, procurando statement
depois de um `with TemporaryDirectory()` fechado, no mesmo nível ou menor, dentro da mesma
função, que **toque o filesystem** (`exists`/`read_text`/`is_file`/`is_dir`/`rglob`), use
`root`/`tmp`/`tmp_path`/`target`/`project`, ou re-chame `build_removal_plan`/`run_*`.

**Resultado: 0.**

**Método (fix auditor / LGPD, mais largo):** qualquer asserção posicionada depois do bloco.
**27 ocorrências** (o LGPD contou 14 com um filtro intermediário). Todas conferidas, todas
benignas: operam sobre valor **capturado dentro** do bloco — `message`, `offer`, `text`,
`completed.stdout`, `result.message`, `item` — e nenhuma volta a tocar o diretório apagado,
que era o que fazia a asserção do `AC-4` observar nada.

### A observação que sobra, e é a que importa

Quatro das 27 estão neste mesmo arquivo. **A forma que escondeu o defeito continua sendo o
estilo da casa**: capturar dentro, afirmar fora. É seguro hoje e um refactor que mova uma
chamada que toca `root` para baixo do bloco o reintroduz de forma invisível.

O guarda que entrou no teste — `assertIsNotNone(readme, "the assertion below must actually
run")` — protege **um** caso. A classe continua aberta, e nenhum gate a fecha.
Candidato a issue própria, se o operador quiser: um teste que falhe quando uma asserção
depender de diretório temporário já fechado.
