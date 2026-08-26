# Issue AC-25 — origem: crítica do grupo remove-agents, 2026-08-13 (lente: LGPD)

## AC-25 — uma entrada de manifesto envenenada faz o kit enviar a chave do operador ao provider [crítica]

### Contexto

`_candidate_paths` começa em `candidates = set(manifest)` — o `.gk/manifest.json`, que é a
metade **compartilhada e commitada** do estado. Uma entrada plantada por um colega, por um
PR mesclado ou por uma versão antiga do kit torna candidato **qualquer** caminho, inclusive
o diretório onde moram os tokens reais do operador.

O hash não bate (o atacante não conhece o conteúdo), a execução cai no ramo
`elif expected:` e, com `--with-llm` e provider configurado, o planner **lê o arquivo
inteiro e entrega o conteúdo ao extractor**, que o envia ao provider terceiro.

O destino é o próprio provider cuja chave está sendo exfiltrada.

`_configured_llm` tem docstring dizendo *"never its secret"*. O código evita com cuidado
vazar o segredo como **credencial** — e o envia como **conteúdo**.

### Reprodução

Extractor-espião, sem chamada de rede, alvo sintético em /tmp:

```
provider accepted by the planner? {'name': 'openrouter', 'mode': 'file-ref',
                                   'credential_ref': '.credentials/llm/openrouter.key', ...}
  extract-project-content    .credentials/identity.json         [mixed-content] review=True
  extract-project-content    .credentials/llm/openrouter.key    [mixed-content] review=True

files whose CONTENT went to the extractor:
   .credentials/identity.json         CPF in payload? True
     payload: '{"operator":"Esteban Calegari","cpf":"123.456.789-00"}'
   .credentials/llm/openrouter.key    real token in payload? True
     payload: 'sk-or-v1-REAL-OPERATOR-TOKEN-DO-NOT-SEND-ANYWHERE'
```

### O que isto NÃO é

Não é causado pelo grupo `AC-2`/`AC-3`/`AC-4`/`AC-5`, e o grupo não o agrava:
`_candidate_paths` e o ramo do extractor não foram tocados, e `mixed-content` produz
`action="extract-project-content"`, que o `AC-2` não move para o `apply` — continua atrás
de `--accept-project-extractions`.

Também não depende de `--with-llm` para ser ruim: sem provider, o arquivo ainda vira
candidato e aparece no plano. Com provider, ele sai da máquina.

### Objetivo

Que `.credentials/` nunca vire candidato por reivindicação do estado compartilhado, e que
nenhum caminho leia conteúdo de lá para enviar a terceiro.

### Escopo

- **`.credentials/` sai do universo de candidatos por manifesto.** O único caminho para
  aquele diretório passa a ser a tabela do snapshot (`AC-3`), que nomeia exatamente os
  oito arquivos do andaime e nada mais. É o mesmo raciocínio que `_write_state` já aplica
  ao **escrever** (`.credentials/` nunca entra em `files`); falta aplicá-lo ao **ler**.
- **`_is_kit_installable('.credentials/llm/openrouter.key')` devolve `True`** — medido.
  Esse guarda existe para perguntar *"esta reivindicação é sequer plausível?"* e responde
  "sim" para o diretório de chaves privadas. Deve responder não.
- O extractor nunca deve receber conteúdo de caminho sob `.credentials/`, mesmo que
  alguma rota futura o torne candidato. Guarda no ponto de leitura, não só na seleção —
  duas camadas, porque a primeira já falhou uma vez.
- Escrever a regra: **o estado compartilhado é entrada não confiável**, e é a terceira vez
  que ela é violada por um caminho diferente (`ade371f5#0` pela substituição, `AC-20` pelo
  filtro assimétrico de `_read_state`, e agora pela seleção de candidatos).

### ARO

- **Assumption**: nenhum uso legítimo precisa que uma entrada de manifesto aponte para
  `.credentials/`. O `_write_state` nunca escreve uma, então qualquer uma que exista é
  herdada, forjada, ou bug de versão antiga.
- **Risk**: um alvo legado pode ter entrada legítima antiga apontando para lá. Mitigação:
  ignorar em vez de falhar, e dizer.
- **Risk**: bloquear a leitura no extractor pode esconder um caso legítimo de extração de
  conteúdo de projeto. Nenhum arquivo de `.credentials/` é conteúdo de projeto.
- **Owner**: o operador — envolve o que sai da máquina.

### Plano de teste

- Manifesto com entrada para `.credentials/llm/openrouter.key` ⇒ **não** vira candidato.
- O mesmo, com `--with-llm` e extractor-espião ⇒ o extractor **não** recebe conteúdo algum
  de `.credentials/`.
- `_is_kit_installable` recusa qualquer caminho sob `.credentials/`.
- Os oito do andaime continuam sendo candidatos pela tabela do snapshot.
- Mutação: devolver `candidates = set(manifest)` sem filtro ⇒ vermelho.

### DoD

- Nenhum caminho sob `.credentials/` é alcançável por reivindicação do estado
  compartilhado.
- Nenhum conteúdo de `.credentials/` chega ao extractor.
- A regra sobre o estado compartilhado como entrada não confiável está escrita, com as
  três violações citadas.
