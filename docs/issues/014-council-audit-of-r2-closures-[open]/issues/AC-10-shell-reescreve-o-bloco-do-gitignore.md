# Issue AC-10 — origem: concílio de fechamentos, 2026-08-13 (lente: the migrator)

## AC-10 — o instalador shell reescreve o bloco do `.gitignore` e derruba dois fechamentos [alta]

> **Atenção de escopo:** como `AC-6`, esta issue toca `scripts/install-agents-kit.sh` em
> **`AI/Agents`**, release pinado v1.2.1. Contrato compartilhado, raio maior que um repo.

### Contexto

Dois fechamentos da rodada 2 puseram sufixos no bloco gerenciado do `.gitignore` de raiz:

- `ade371f5#1` — `*.kit-new` (guarda o **nome do operador**)
- `6bb1027e#12` — `*.pre-draft` (guarda a **prosa do operador**)

Os dois foram verificados com `git check-ignore` real e se sustentam — enquanto só o kit
Python roda.

Os dois instaladores usam **marcadores idênticos** para delimitar o bloco:

```
# AI-Agents kit — managed by governancekit install-agents
```

`write_root_gitignore_secrets` (`install-agents-kit.sh:786-839`) remove o bloco inteiro e
escreve o seu, que não contém nenhum dos dois sufixos. Os dois artefatos que guardam
dado do operador voltam a aparecer em `git status`, a um `git add -A` do commit —
exatamente o dano que os dois fechamentos existem para impedir.

O bloco do shell também não tem `.docs/`, `.docs-migration-bak/` nem os arquivos de
regra por ferramenta.

O próprio kit Python já nomeia esse perigo na direção oposta
(`install_agents.py:1224-1231`, sobre `pre-migrate/`). A direção que estes dois
fechamentos criaram ficou desprotegida.

### Reprodução

```
=== after the PYTHON installer (6116eba/c7b2838):
.gitignore:23:*.kit-new     AGENTS.md.kit-new
.gitignore:24:*.pre-draft   docs/software-overview.md.pre-draft
=== after the SHELL installer v1.2.1 rewrote the block:
  *** NOT IGNORED ***
--- git status --porcelain:
?? .gitignore
?? AGENTS.md.kit-new
?? docs/
```

### Objetivo

Que o conteúdo do bloco gerenciado seja uma coisa só, com uma fonte, e que dois
instaladores não possam discordar dele em silêncio.

### Escopo

Mesma estrutura de decisão de `AC-6`, e as duas devem ser decididas juntas:

1. **Sincronizar o shell** — exige release do AI-Agents e bump da cadeia (épica `012`).
2. **Marcadores distintos por instalador**, para que um não coma o bloco do outro. Mais
   barato, mas deixa dois blocos e a pergunta de quem vence.
3. **Gate de deriva** (épica `013`): o conteúdo do bloco entra no `_kit_snapshot.json` e
   a divergência entre os dois kits fica vermelha. É o mecanismo que este repositório já
   construiu para exatamente esta classe.

Recomendação: **3 agora** (fecha a classe, sem release), **1 quando a cadeia abrir**.

Escopo adicional, independente de qual opção: as entradas que o bloco do Python tem e o
do shell não — `.docs/`, `.docs-migration-bak/`, regras por ferramenta — entram na mesma
comparação.

### ARO

- **Assumption**: o dano é real só em alvos onde os dois instaladores rodam. Quantos são
  é a pergunta 14 do RESUME, e é para o operador.
- **Risk**: dois blocos (opção 2) confundem quem lê o `.gitignore` à mão.
- **Risk**: sem nenhuma das três, o dano é silencioso e o operador só descobre depois do
  `git add -A`. **Isto é exposição de dado pessoal do operador em repositório** — a
  crítica de LGPD desta issue precisa olhar exatamente isso.
- **Owner**: o operador — cruza repositório.

### Plano de teste

- Python → shell → `git check-ignore` ⇒ os dois sufixos continuam ignorados.
- shell → Python → idem.
- Gate de deriva vermelho quando os blocos divergem.
- Alvo que já tem `AGENTS.md.kit-new` **rastreado** desde antes: o ignore não desrastreia
  — o comportamento esperado precisa estar escrito.

### DoD

- O bloco gerenciado tem uma fonte de verdade, ou a divergência é vermelha.
- O caso "já rastreado desde antes" tem resposta escrita.
- Se a escolha for aceitar o risco até a próxima release, a aceitação está escrita.
