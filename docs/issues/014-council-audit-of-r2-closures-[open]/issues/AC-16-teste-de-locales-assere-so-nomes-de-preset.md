# Issue AC-16 — origem: concílio de fechamentos, 2026-08-13 (lente: the claim auditor)

## AC-16 — "teste em três locales" assere só o que é invariante por idioma [média]

### Contexto

O achado `6bb1027e#1` tinha duas metades: o catálogo de providers ficou em inglês, e o
texto localizado virou código morto atrás de um `or True`. O fechamento: *"linhas
derivadas e localizadas; teste em três locales"*.

A metade **derivada** está testada. A metade **localizada** não.

`test_the_provider_catalog_is_offered_in_every_locale` afirma que os nomes dos presets —
`gemini`, `openai`, `openrouter` — aparecem em cada locale. Nome de preset é
identificador: **invariante por idioma**. O teste passaria com a saída inteira em inglês.

### Reprodução

Reverter a metade localizada (`scope_conversation.py:358` volta a pedir
`_provider_catalog_lines('en')` para qualquer locale):

```
mutante, pt-BR:
  openrouter - 14 free models behind one key; key at https://openrouter.ai/keys
  nvidia     - suggests its URL, model and credential name; key at https://build.nvidia.com/

pytest …::test_the_provider_catalog_is_offered_in_every_locale -v  => 1 passed
pytest tests/                                                       => 506 passed, 2 skipped
```

HEAD corrigido imprime `14 modelos gratuitos com uma única chave; chave em …`. O teste
não distingue os dois.

### Objetivo

Que um teste de localização afirme sobre o que muda com o idioma.

### Escopo

- O teste passa a afirmar sobre texto **traduzido** — uma frase de cada locale que não
  exista nos outros. Nome de preset e URL ficam de fora por serem invariantes.
- Varrer os demais testes de locale do repositório pela mesma pergunta: *este teste
  passaria com a saída inteira em inglês?*
- Absorve a pergunta 8 do RESUME: `_collect_providers`
  (`scope_conversation.py:637-712`) só tem ramos pt-BR e inglês — `Saved LLM
  configuration`, `Use this detected LLM configuration`, `Choose env, file, create, or
  help`, `Enter a base URL…` caem em inglês para `es`. É anterior a esta entrega, mas
  está dentro do que "teste em três locales" faz crer que está coberto. **Ou o `es` é
  traduzido, ou o alcance real da localização é escrito onde alguém leia.**
- Interage com o item (d) do concílio geral desta épica (*"está tudo em inglês
  simplificado"*): o que é traduzido e o que não é precisa de uma regra, não de caso a
  caso.

### ARO

- **Assumption**: os três locales são compromisso do produto. Se `es` não for, o teste
  deve testar dois e dizer por quê.
- **Risk**: afirmar sobre frase traduzida quebra o teste a cada ajuste de redação.
  Mitigação: afirmar sobre uma frase-âncora curta por locale, escolhida para ser estável.
- **Owner**: a definir.

### Plano de teste

- Mutação "todo locale usa `en`" ⇒ **vermelho**. É o critério de aceite.
- Cada locale tem ao menos uma âncora que só existe nele.
- O alcance real da localização em `_collect_providers` está testado ou escrito.

### DoD

- A mutação que desliga a localização fica vermelha.
- O que é traduzido e o que não é está escrito.
- A varredura dos testes de locale está registrada.
