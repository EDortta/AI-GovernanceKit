# Issue AC-13 — origem: concílio de fechamentos, 2026-08-13 (lente: the sweep skeptic)

## AC-13 — `configure --set` grava chave arbitrária no manifesto versionado [média]

### Contexto

O fechamento de `ade371f5#5` acrescentou um ramo de retorno antecipado ao
`run_configure`, para que um `--set` explícito fosse gravado mesmo quando nenhum token
sobrou no alvo. O resgate funciona — verificado, e é o que salva a população legada.

Mas o caminho normal filtra o preset aos tokens realmente encontrados
(`configure.py:230`):

```python
values = {t: v for t, v in preset.items() if t in found}
```

O ramo novo (`configure.py:224`) persiste o preset **inteiro**, sem esse filtro e sem
validação em `parse_set_pairs`.

E `_write_state` só desvia para o arquivo local as chaves de `_OPERATOR_PLACEHOLDERS` e
`_SENSITIVE_PLACEHOLDERS`. Qualquer outra cai na metade **rastreada** —
`.gk/manifest.json`, que é deliberadamente versionado (`install_agents.py:1865`).

O comando imprime `No kit placeholders found — nothing to configure`, sai `rc=0`, e
grava o valor num arquivo que vai para o git.

### Reprodução

```
$ governancekit --root T configure --set DB_PASSWORD=hunter2 </dev/null
AI GovernanceKit configure
No kit placeholders found — nothing to configure.
rc=0
$ cat T/.gk/manifest.json
{ "files": {}, "metadata": { "DB_PASSWORD": "hunter2" }, "ref": "v1.2.1", … }
```

A saída diz que nada foi configurado. O disco discorda.

### Objetivo

Que `--set` aceite apenas o que o kit declara, e que nada que o operador digita como
segredo caia na metade versionada por omissão de uma lista.

### Escopo

- `parse_set_pairs` (ou o ramo de retorno antecipado) valida a chave contra os
  placeholders declarados. Chave desconhecida: erro nomeado, `rc != 0`, nada gravado.
- A mensagem final descreve o que aconteceu. `nothing to configure` seguido de escrita é
  a mesma classe que `6bb1027e#7` e `#8` fecharam do lado da adoção.
- **Revisar a política de destino por omissão.** Hoje "não está em nenhuma das duas
  listas" ⇒ vai para o arquivo versionado. O default seguro é o contrário: desconhecido
  vai para o local, ou é recusado. Esta é a metade da issue que a crítica de **LGPD**
  precisa olhar — o nome que o operador digita é dado pessoal, e o destino por omissão
  decide se ele vai para o repositório.
- Ver pergunta 2 do RESUME: `_read_state` filtra só `_OPERATOR_PLACEHOLDERS` da metade
  rastreada, não `_SENSITIVE_PLACEHOLDERS` — a assimetria é da mesma família.

### ARO

- **Assumption**: `--set` existe para preencher placeholders do kit, não para gravar
  metadata arbitrária. Se existir um uso legítimo do segundo, precisa de flag própria.
- **Risk**: validar quebra scripts do parque que gravam chaves próprias hoje. Mitigação:
  medir antes; se houver uso, a flag separada resolve.
- **Risk**: mudar o destino por omissão move dado entre arquivos em alvos existentes.
  Precisa de migração — ver `AC-12`.
- **Owner**: a definir.

### Plano de teste

- `--set` com chave desconhecida ⇒ `rc != 0`, `.gk/manifest.json` inalterado.
- `--set` com chave declarada e sensível ⇒ vai para o arquivo local, não para o
  versionado.
- `--set` num alvo já renderizado ⇒ continua gravando (o resgate de `ade371f5#5` não pode
  regredir; seu teste continua verde).
- Mutação: remover a validação ⇒ teste vermelho.

### DoD

- Nenhuma chave não declarada entra em `.gk/manifest.json`.
- A saída do comando corresponde ao que ele escreveu.
- O destino por omissão está escrito e justificado, com a lente de LGPD aplicada.
