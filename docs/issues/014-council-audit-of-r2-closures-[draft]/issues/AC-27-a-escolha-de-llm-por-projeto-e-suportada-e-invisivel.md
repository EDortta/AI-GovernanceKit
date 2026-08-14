# Issue AC-27 — origem: pergunta do operador, 2026-08-13 ("cada projeto pode usar um llm diferente e isso foi algo que em algum momento perdemos")

## AC-27 — a escolha de LLM por projeto é suportada e a interface a esconde [alta]

### O que já funciona, medido

Nada no kit amarra um projeto a um provider. A configuração é **por projeto**, em
`.gk/project-config.json`, e é genérica:

```json
{"providers": [{"name": "...", "mode": "env|file-ref",
                "credential_ref": "...", "base_url": "...", "model": "..."}]}
```

- `_collect_providers` (`scope_conversation.py:662-710`) aceita **qualquer** nome. O
  preset só pré-preenche: `base_url = _ask(..., preset[0] if preset else "")`.
- `_configured_llm` (`remove_agents.py:333`) e `configured_adoption_provider`
  (`adoption.py:53`) leem a config do projeto **sem filtrar por preset**.
- Qualquer endpoint compatível com OpenAI serve.

### O que se perdeu

**A descoberta.** O que o operador vê ao escolher:

```
Provider name (Enter ends the list)
  openrouter - 14 free models behind one key; key at https://openrouter.ai/keys
  gemini     - ...
  openai     - ...
  nvidia     - ...
```

Quatro nomes e nenhuma linha dizendo que ele pode digitar outro. O texto de ajuda
(`_print_provider_help`) explica **métodos de credencial** e **papéis de roteamento**, e
não diz uma palavra sobre o universo de providers ser aberto.

O universo **suportado** é "qualquer endpoint compatível com OpenAI". O universo
**visível** são quatro itens — três fixos em `_PAID_ENDPOINTS` (`llm_catalog.py:61`) e um
vindo do catálogo. Um operador que precise de Anthropic, Groq, DeepSeek, um Ollama local
ou o endpoint corporativo da empresa lê aquela tela e conclui que a lista é fechada.

`_PRIMARY_PREFERENCE` (`scope_conversation.py:39`) reforça a leitura: uma ordem fixa
sobre os mesmos quatro nomes.

### Por que isto é a mesma classe que a épica vem medindo

É o **inverso** do `AC-24`. Lá a afirmação existe (onze slots declarados) e a capacidade
não (dez não são usados por nada). Aqui a capacidade existe e **nada a afirma**. As duas
são a mesma pergunta — *o que o produto diz sobre si mesmo corresponde ao que ele faz?* —
e o concílio inteiro só sabia fazê-la numa direção.

### Objetivo

Que um operador saiba, na tela em que escolhe, que pode usar o LLM que quiser, e que a
configuração por projeto seja alcançável sem entrevista interativa.

### Escopo

- O catálogo deixa de se apresentar como lista e passa a se apresentar como **atalhos**:
  uma linha antes dele dizendo que qualquer endpoint compatível com OpenAI serve, e que
  os nomes abaixo só pré-preenchem URL, modelo e nome de variável.
- Um exemplo com provider fora da lista, para que a capacidade tenha rosto.
- **Caminho não interativo.** `configure-project apply` existe, mas nada documenta como
  declarar um provider por ele. Um projeto em CI, ou governado por agente, não deve
  precisar de TTY para escolher o próprio LLM. Interage com `AC-15` — remédio que só
  funciona com terminal é remédio que não funciona.
- Rever `_PRIMARY_PREFERENCE`: preferência fixa sobre quatro nomes é razoável como
  **desempate de detecção**, e não deve parecer política de produto.
- Decidir e escrever o que os presets **são**: atalhos com URL e modelo conhecidos, não
  a lista de providers suportados.

### ARO

- **Assumption**: todos os providers de interesse falam o protocolo OpenAI. É o que o
  código assume hoje em `_llm_extract` e no `agent_scope`.
- **Risk**: convidar provider arbitrário aumenta a superfície de erro de digitação em
  `base_url`. Mitigação: `validate_provider_url` já existe.
- **Risk**: a lista curta pode existir por decisão de produto — providers *recomendados*.
  Se for, precisa estar escrito, e o texto deve dizer "recomendados", não parecer
  exaustivo.
- **Owner**: o operador — é decisão sobre o que o produto declara suportar.

### Plano de teste

- A tela de escolha menciona, em cada locale, que qualquer endpoint compatível serve.
- Entrevista com nome fora dos presets ⇒ provider gravado e usável por
  `configured_adoption_provider` e `_configured_llm`.
- Caminho não interativo declara um provider customizado sem TTY.
- Mutação: remover a frase que abre o universo ⇒ vermelho (o teste afirma sobre a
  **frase traduzida**, não sobre nomes de preset — ver `AC-16`, que é este defeito no
  teste).

### DoD

- A tela diz o que o produto faz.
- Provider fora dos presets funciona ponta a ponta, provado por teste.
- Existe caminho não interativo, documentado.
- O que os presets são está escrito.
