# Issue AC-6 — origem: concílio de fechamentos, 2026-08-13 (lente: the migrator)

## AC-6 — o instalador shell apaga `seeded_credentials` do manifesto [alta]

> **Atenção de escopo:** esta issue muda `scripts/install-agents-kit.sh`, que vive em
> **`AI/Agents`**, outro repositório, no release **pinado v1.2.1**. Mexer ali é mudança
> de contrato compartilhado com raio de explosão maior que um repo — gatilho
> `[MANDATORY]` de concílio por si só (`council.md` §4) — e arrasta a cadeia de versões
> da épica `012`. **Não é uma correção local deste kit.**

### Contexto

O commit `c7b2838` reconhece por escrito que existe *"uma frota onde os dois
instaladores rodam"*. Num alvo dessa frota:

1. o kit Python em `6116eba` grava `seeded_credentials` no `.gk/manifest.json`
2. qualquer execução do `install-agents-kit.sh` v1.2.1 depois disso apaga a chave

`write_manifest` (`install-agents-kit.sh:877-901`) lê o manifesto anterior, carrega
adiante **apenas** `files` e `metadata`, e regrava um dict novo. Tudo o mais some, sem
uma linha de aviso.

O alvo que já estava consertado volta ao estado do achado `6bb1027e#3`. **A ordem de
subida não é livre**, e nada no parque diz isso.

### Reprodução

Extraindo `write_manifest` verbatim das linhas 877-901 e rodando:

```
BEFORE (written by the Python kit at 6116eba):
['files', 'metadata', 'ref', 'repo', 'seeded_credentials', 'state_version']
AFTER  (one run of the shell installer v1.2.1):
['files', 'metadata', 'ref', 'repo', 'state_version']
```

`ref`, `repo` e `state_version` são reescritos pelo shell com valores próprios, então o
dano visível é `seeded_credentials`. O mecanismo, porém, é geral: **qualquer chave nova
que o kit Python gravar será apagada pelo shell.** Esta issue trata a classe, não a
chave.

### Objetivo

Que os dois instaladores possam rodar em qualquer ordem sem um destruir o estado do
outro, e que a incompatibilidade seja detectável antes de causar dano.

### Escopo

Três decisões, e a escolha é do operador porque duas delas mexem em outro repositório:

1. **`write_manifest` preserva chaves desconhecidas** (o certo a longo prazo): lê o
   manifesto, atualiza o que sabe, mantém o resto. Exige release do AI-Agents e bump da
   cadeia de versões (épica `012`).
2. **O kit Python detecta e repara**: `doctor` reporta manifesto cujo `state_version` é
   dele mas que perdeu chaves esperadas; o próximo upgrade reconstrói. Fica todo dentro
   deste repositório, e casa com `AC-5`, que já vai precisar de um caminho de reparo.
3. **Gate de deriva**: o `_kit_snapshot.json` (épica `013`) já existe para exatamente
   este tipo de afirmação entre os dois kits. O conjunto de chaves do manifesto entra no
   snapshot, e a divergência fica vermelha.

Recomendação: **2 + 3 agora**, e 1 quando a cadeia de versões abrir. 2 protege o parque
sem release; 3 impede que a próxima chave nova repita isto.

### ARO

- **Assumption**: o shell installer continua em uso no parque. Se não continuar, esta
  issue vira documentação de uma incompatibilidade histórica.
- **Risk**: mudar o shell exige release do AI-Agents, novo pin, novo snapshot, e a épica
  `012` está em `[review]`. Fazer isso dentro desta épica mistura duas cadeias.
- **Risk**: reparar só do lado Python deixa a janela aberta enquanto o shell roda por
  último. É uma aceitação de risco, e precisa estar escrita.
- **Owner**: o operador — decisão de escopo cruzando repositório.

### Plano de teste

- Manifesto com chave extra + `write_manifest` do shell ⇒ a chave sobrevive (opção 1).
- Manifesto que perdeu a chave ⇒ `doctor` reporta e o upgrade repara (opção 2).
- Gate de deriva vermelho quando os dois lados discordam do conjunto de chaves (opção 3).
- Ordem livre: Python→shell→Python e shell→Python→shell terminam no mesmo estado.

### DoD

- A ordem de subida é livre, ou a restrição está escrita onde o operador do parque a lê.
- A classe do defeito (chave nova apagada em silêncio) tem gate, não só a chave de hoje.
- Se a escolha for aceitar o risco, a aceitação está escrita nos termos de
  `delivery-loop.md` §9.
