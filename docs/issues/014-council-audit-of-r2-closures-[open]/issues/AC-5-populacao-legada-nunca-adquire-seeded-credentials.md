# Issue AC-5 — origem: concílio de fechamentos, 2026-08-13 (lente: the migrator)

## AC-5 — a correção é forward-only e o parque já adotado nunca se conserta [alta]

### Contexto

O fechamento de `6bb1027e#3` faz o plano confiar em `seeded_credentials`, uma chave nova
no `.gk/manifest.json`. Alvo adotado **antes** de `6116eba` não tem essa chave, e nunca
vai ter:

- `_seed_dir_missing` (`install_agents.py:643-648`) só registra em `seeded` o que ele
  **copiou**. Num alvo que já tem os oito arquivos, tudo cai em `preserved`.
- o ramo de upgrade (`install_agents.py:459-470`) nem passa `seeded` para `_do_upgrade`.

Então `data.get("seeded_credentials", [])` (`remove_agents.py:139`) devolve `[]` para
sempre, e os oito caminhos voltam a `preserve / unknown / conf=0.0` — o sintoma literal
do achado original, para toda a população já adotada.

Não há `KeyError`: o `.get` com default engole. **É silêncio, não crash** — que é pior,
porque a de-adoção parece ter funcionado.

### Reprodução

```
=== manifest written BEFORE 6116eba (no seeded_credentials key) ===
  preserve  .credentials/.gitignore                [unknown] conf=0.0
  preserve  .credentials/README.md                 [unknown] conf=0.0
  (… os oito)
=== manifest written AFTER 6116eba ===
  remove    .credentials/.gitignore                [kit-seeded-unchanged] conf=1.0

# e a re-execução completa não repara:
seeded from the re-run   : []
preserved from the re-run: ['.credentials/.gitignore', … os oito]
seeded_credentials AFTER a full re-run: []
```

### Objetivo

Que um alvo adotado sob a versão anterior alcance o mesmo estado de um alvo novo, sem o
operador precisar saber que existe uma chave nova.

### Escopo

- Um caminho de reparo. Duas formas plausíveis, a decidir:
  1. **derivar**: quando `seeded_credentials` está ausente, comparar os oito nomes
     conhecidos por sha256 contra a cópia do kit e gravar os que baterem. Casa
     naturalmente com `AC-3`, que já vai precisar do hash.
  2. **backfill no upgrade**: `_do_upgrade` passa a receber e gravar o que encontrou.
- Ausência da chave nunca deve significar "nada foi semeado". Deve significar
  "desconhecido" e disparar o reparo — a distinção entre ausente e vazio.
- Alinhar com `AC-13`, que é a mesma classe de defeito do lado do `configure` e **já
  ganhou** um caminho de resgate. Esta issue é o equivalente que faltou.

### ARO

- **Assumption**: os oito nomes semeados por versões anteriores são os mesmos de hoje.
  Se não forem, o reparo por hash falha em silêncio — e vira a pergunta 1 do RESUME
  (`_CREDENTIALS_SCAFFOLDING` fora do gate de deriva).
- **Risk**: reparar por hash marca como semeado um arquivo que o operador escreveu
  identicamente ao template. Aceitável: byte-idêntico ao template é indistinguível por
  construção, e `AC-3` já assume isso.
- **Risk**: `_read_state` descarta `_OPERATOR_PLACEHOLDERS` de manifesto herdado
  (pergunta 6 do RESUME) — pode fechar a porta do reparo para alvos pré-split.
- **Owner**: a definir.

### Plano de teste

- Alvo com manifesto sem a chave ⇒ depois do comando de reparo (ou do próximo upgrade),
  os oito saem como `kit-seeded-unchanged`.
- Alvo legado com um dos oito editado ⇒ esse **não** é marcado como semeado.
- Mutação: remover o reparo ⇒ o teste do alvo legado fica vermelho.
- `remove-agents plan` num alvo legado **antes** do reparo não afirma nada falso.

### DoD

- Alvo legado e alvo novo produzem o mesmo plano.
- Ausente ≠ vazio no leitor de estado.
- Teste verificado por mutação.
