# Issue AC-22 — origem: crítica de quatro céticos sobre AC-1, 2026-08-13 (lente: LGPD)

## AC-22 — o manifesto versionado grava o hash de arquivos renderizados com dado pessoal [média]

### Contexto

O código já aceitou este argumento uma vez, por escrito, e não o aplicou aos arquivos
que ele mesmo renderiza.

`install_agents.py:1145-1150`, sobre `.credentials/`:

> *a SHA-256 of a low-entropy token is a confirmation oracle*

`install_agents.py:1160-1173` grava o SHA-256 de **todo arquivo instalado** no
`.gk/manifest.json` — o arquivo explicitamente **não** ignorado, commitado pelo time por
decisão de projeto.

Para `AGENTS.md` o template é público: o kit o distribui, no ref que o próprio manifesto
registra. A única incógnita no arquivo renderizado é `{{OPERATOR_NAME}}`, e o conjunto de
candidatos é a lista de pessoas do time. O hash confirma qual.

O mesmo vale para qualquer arquivo do kit que carregue slot pessoal ou financeiro.

### Reprodução

```
=== committed manifest.json (FULL) ===
{
  "files": {
    "AGENTS.md":    "f14923871e0de3c1761f1bfb1a15984441ce5b519ec5bced05c3fac3de05e9d0",
    "donations.md": "99887c711d32177298430d02b94cfa9246832b761fe9f43add2a795830ca153d"
  }, ... }
=== .gk/.gitignore ===
# manifest.json is intentionally NOT ignored — the team must share it.
hash of PII-rendered donations.md recorded in COMMITTED manifest: True
```

(`AGENTS.md` continha `Toda mensagem ao operador (Esteban Calegari)`; `donations.md`
continha payload PIX e nome do titular.)

### Objetivo

Que o argumento que o kit já aceitou para `.credentials/` valha para todo arquivo cujo
conteúdo renderizado contém dado pessoal.

### Escopo

- Identificar quais arquivos instalados podem conter slot de `_OPERATOR_PLACEHOLDERS` ou
  `_SENSITIVE_PLACEHOLDERS` depois de renderizados.
- Para esses, gravar o hash do **template** (pré-render), não do resultado. O manifesto
  passa a responder *"este arquivo veio deste template"* em vez de
  *"este arquivo tem exatamente este conteúdo"* — e a deriva continua detectável, porque
  a comparação passa a ser feita contra a fonte pré-renderizada, que `_prerender_source`
  já produz.
- Alternativa mais simples, se a de cima quebrar a detecção de deriva: mover o hash
  desses arquivos para a metade **local** do estado. Custa a verificação entre clones e
  preserva a de-adoção.
- Escrever a regra: **nada derivado de dado pessoal entra na metade versionada**, hash
  incluído. Hoje a regra existe só para `.credentials/`, e por acidente de escopo.

### ARO

- **Assumption**: o time é o conjunto de candidatos, então a entropia é baixa. Verdadeiro
  para `OPERATOR_NAME`; menos para `PIX_PAYLOAD`, que é longo — mas confirmação de *"é
  este payload?"* continua sendo confirmação.
- **Risk**: mudar o que o hash significa quebra `remove-agents` e o julgamento de deriva,
  que são os dois consumidores. Precisa de migração — ver `AC-12` sobre mudar o
  significado de artefato persistido sem mudar o formato.
- **Risk**: hash do template não detecta edição do arquivo renderizado. Mitigação: é
  exatamente o que `_prerender_source` existe para permitir, comparando contra a fonte
  já renderizada com os mesmos valores.
- **Owner**: a definir.

### Plano de teste

- Arquivo renderizado com `OPERATOR_NAME` ⇒ o hash no manifesto rastreado não muda
  quando só o valor do operador muda.
- Deriva real (edição à mão) ⇒ continua detectada.
- `remove-agents` continua classificando corretamente.
- Mutação: voltar a gravar o hash do renderizado ⇒ vermelho.

### DoD

- Nenhum hash derivado de dado pessoal na metade versionada.
- A regra está escrita, e não vale só para `.credentials/`.
- Deriva e de-adoção continuam funcionando, provado por teste.
