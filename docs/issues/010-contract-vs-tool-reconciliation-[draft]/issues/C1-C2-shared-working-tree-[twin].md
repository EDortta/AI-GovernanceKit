# Issues C1–C2 — origem `YouBR/ZeeCred/jk-structure`

Levantadas em 2026-08-06, no dia seguinte ao §1c e ao `governancekit concurrency`, a
partir de um incidente real: **duas sessões `claude-code` na mesma pasta e na mesma
branch**. Preservadas verbatim abaixo; a crítica vem depois, separada.

Elas atacam um ponto cego que o trabalho de ontem tem por construção: §1c e
`survey_concurrency()` modelam concorrência como **topologia de git**. Topologia não
sabe quantos processos ocupam um diretório.

---

## C1 — AI-Agents: §1c, uma terceira forma de frente aberta [verbatim]

**Título:** §1c: uma terceira forma de frente aberta — outra sessão viva no mesmo working tree

### Contexto

§1c define frente aberta como worktree viva ou branch com commits não mesclados. Falta o caso em
que dois agentes ocupam o mesmo working tree. O contrato não o descreve, o runtime não o detecta, e
o relatório de abertura afirma o contrário do que acontece.

### Ocorrência real (2026-08-06, projeto ZeeCred/jk-structure)

Duas sessões claude-code na mesma pasta e na mesma branch `feature/WK-20260805-tatao-triage`. Quatro
efeitos, todos silenciosos:

1. A sessão B commitou por cima; o `git log` da sessão A passou a conter `7c5c9780`, um commit que A
   nunca escreveu.
2. A leu `git branch -r`, não achou a branch, e reportou ao operador "10 commits não pushados". B já
   havia pushado tudo. Ausência de ref remota foi lida como "nunca pushada" — sem fetch, é apenas
   ignorância local.
3. O `git status` de A mostra arquivos sujos que são de B. Um `git add -A` de A varreria trabalho
   alheio para dentro do commit de A.
4. Session-close é por sessão, mas `handoff.md`, `napkin-lessons.md` e `agent-status.json` são por
   repositório: as duas escrevem o mesmo arquivo, último a escrever ganha.

### Mudanças propostas no contrato

- **§1c** — acrescentar o terceiro tipo de frente: outra sessão viva sobre o mesmo working tree.
  Deixar explícito que worktree única não implica sessão única.
- **§1c [MANDATORY]** — na abertura, após o inventário, consultar o registro de sessões. Havendo
  outra entrada viva com o mesmo working tree: reportar ao operador e aguardar autorização antes da
  *primeira escrita* (commit, branch, push, ou edição de documento compartilhado).
- **§7 (branch/commit) [MANDATORY]** — antes de cada commit, confirmar que `HEAD` ainda é o que a
  sessão observou por último; se moveu, parar e reler. Em árvore compartilhada, proibir `git add -A`
  / `git commit -a` — só staging por caminho explícito. Esta regra vale a pena ser incondicional:
  custa nada e elimina a classe inteira.
- **§7 [MANDATORY]** — antes de afirmar estado de push ao operador, `git fetch` ou declarar que a
  leitura é local. "Sem ref remota" ≠ "não pushada".
- **§8 (session-close)** — documentos compartilhados são read-modify-write. Se o arquivo mudou desde
  a leitura, reler e mesclar; nunca sobrescrever.
- **§8a** — dar semântica ao heartbeat: definir idade a partir da qual a entrada é presumida morta (a
  entrada `cursor` de 31/07 continua lá há 6 dias). Presumida morta é *reportada*, não apagada —
  nunca remover entrada alheia.
- **§8a** — reconciliar o caminho do registro com `scripts/agent-worktree.sh:41`. Hoje o contrato
  aponta XDG e a ferramenta aponta `~/Sync`, e só o segundo existe.
- **§1c / `parallel-worktrees.md`** — ao detectar árvore compartilhada, apontar `awt new <work_id>`
  como *a* resolução, não como alternativa avulsa. O documento já existe e resolve o problema; falta
  o contrato dirigir a ele no momento certo.

### Critério de aceitação

Com duas sessões na mesma pasta, a segunda a abrir reporta a primeira pelo nome, agente e idade do
heartbeat, e não escreve nada até autorização. Nenhum agente reporta estado de push sem fetch ou sem
ressalva explícita.

---

## C2 — AI-GovernanceKit: duas sessões contadas como uma [verbatim]

**Título:** `concurrency`: duas sessões no mesmo working tree são contadas como uma

> **Nota de localização:** `governancekit/concurrency.py` está no checkout
> `GovernanceKit-main-merge` (branch `development`); o checkout primário está em
> `feature/uc-008/credential-root-json-profile` e ainda não carrega o módulo. Abrir contra a branch
> que o contém.

### Problema

`survey_concurrency()` enumera topologia de git. `is_current` (`concurrency.py:194`) compara caminho
de worktree com `root` — é propriedade do *diretório*, não do *processo*. Duas sessões no mesmo
diretório produzem survey idêntico ao de uma, ambas renderizadas como `this session`
(`concurrency.py:304`), e o fecho (`:322`) declara que só as outras frentes precisam de autorização —
afirmando exclusividade que não existe.

### Proposta

1. **Lease de sessão.** Na abertura, gravar `<git-dir>/governancekit/sessions/<session-id>.json` com
   `agent`, `pid`, `branch`, `worktree`, `started`, `heartbeat`. Dentro de `.git` o arquivo nunca
   vaza para o índice — não depende de `.gitignore`. Remover no fecho; considerar morto por idade de
   heartbeat. Complementarmente, ler o `agent-status.json` já existente, que hoje é o único registro
   cross-tool.
2. **Modelo.** `OpenItem` ganha `sessions: tuple[SessionLease, ...]`; `ConcurrencySurvey` ganha
   `shared_tree: bool`.
3. **Render.** Quando a frente tem mais de uma sessão viva, trocar `this session` por algo que não
   passe despercebido, e dizer a consequência:

   ```
   * jk-structure  feature/WK-…  this session + 1 outra (claude-code, pid 41207, visto há 3 min)
     ATENÇÃO: working tree compartilhado. HEAD pode mover sob você; `git status`
     mostra arquivos de outra sessão; não use `git add -A`.
   ```
4. **Ordem no hook de `SessionStart`.** O aviso de árvore compartilhada vem *antes* da linha de
   wind-down.
5. **`doctor`.** Advisory, nunca falha — coerente com o docstring do módulo ("nothing here ever fails
   a session").
6. **Caminho do registro.** Uma única fonte, compartilhada com `awt`. Hoje `AGENTS.md:385` (XDG) e
   `agent-worktree.sh:41` (`~/Sync`) discordam, e o XDG não existe na máquina do operador.
7. **Política de lease velho.** Heartbeat vencido → reportar como *presumido morto*, com a idade.
   Nunca apagar lease alheio automaticamente.
8. **Testes.** Dois leases no mesmo worktree; lease velho; diretório sem leases; diretório fora de
   git (tem de continuar silencioso, conforme o contrato do módulo).

### Não-objetivo

Não é lock. A segunda sessão não é bloqueada por código — o relatório informa e o operador decide,
que é o mesmo desenho de §1c.

### Critério de aceitação

Com dois processos no mesmo working tree, `governancekit --root . concurrency`, `resume` e o hook de
`SessionStart` mostram as duas sessões, com agente e idade do heartbeat, e o fecho deixa de afirmar
exclusividade da frente atual.

---
---

# Crítica (2026-08-06, verificada contra o código)

## O que foi confirmado, com evidência

| Alegação | Verificação |
|---|---|
| `is_current` é propriedade do diretório | `concurrency.py:194` — `Path(path).resolve() == root`. Nenhum dado de processo entra no survey. Confirmado. |
| O fecho afirma exclusividade | `concurrency.py:322` — *"N open beyond this session. Working on another one requires the operator's authorization."* Com duas sessões na frente atual, a frase é falsa. Confirmado. |
| Contrato e ferramenta discordam do caminho do registro | `AGENTS.md:385` → `${XDG_STATE_HOME:-$HOME/.local/state}/ai-agents/`; `agent-worktree.sh:41` → `$HOME/Sync/agent-status.json`. **O XDG não existe nesta máquina**; o `~/Sync` existe e está em uso. Confirmado. |
| Entrada `cursor` presa há 6 dias | Lida hoje em `~/Sync/agent-status.json`: `started`/`heartbeat` = `2026-07-31T17:35:50Z`. Continua lá. Confirmado. |
| Localização de `concurrency.py` | Correta: só existe no checkout `GovernanceKit-main-merge`, branch `development`. |

**Terceira fonte que a issue não citou, e que decide o item 6:** o `CLAUDE.md` global do
operador documenta `~/Sync/agent-status.json` como o registro. São três declarações, duas
concordam. **O contrato é o outlier — é ele que se corrige**, não a ferramenta.

## O defeito que a issue descreve e que já está no nosso código

O item 2 da ocorrência — *"ausência de ref remota lida como nunca pushada; sem fetch é apenas
ignorância local"* — é uma instância de um padrão, e o padrão está em `concurrency.py:127`:

```python
out = _git(root, "rev-list", "--count", f"{integration}..{branch}")
if out is None:
    return 0
```

Duas consequências:

1. **Leitura puramente local.** `integration` é a branch local. Se o `development` local está atrás
   do remoto, o `unmerged` está errado — a mesma classe de erro que produziu o "10 commits não
   pushados".
2. **Falha vira zero.** `_git` devolvendo `None` produz `unmerged == 0`, e `unmerged == 0` é
   exatamente o predicado de `removable` (`:67`). Uma falha de leitura vira **"merged — this
   worktree can be removed"**. Fail-open na direção perigosa, na linha mais acionável do relatório.

Isso é trabalho para o C2 e não estava previsto nele. Vale mais que os itens 2–4 da proposta.

## Onde discordo da proposta

**1. `<git-dir>` é o dir privado da worktree, não o comum.** Em uma worktree, `git rev-parse
--git-dir` devolve `.git/worktrees/<nome>`. Leases gravados ali resolvem *"quem mais está nesta
pasta"* — que é o alvo declarado — mas ficam invisíveis para as outras worktrees, e o survey renderiza
**todas** as frentes. Para a coluna de sessões existir em cada linha da tabela, o lease tem de morar
em `--git-common-dir` e ser **chaveado pelo caminho da worktree**. Uma palavra de diferença na issue,
uma feature inteira de diferença no resultado.

**2. Heartbeat por idade é o critério mais fraco disponível, e o único proposto.** Na mesma máquina,
`os.kill(pid, 0)` responde *agora* se o processo existe — sem janela de incerteza, sem falso positivo
de "vivo mas quieto". Custa uma syscall. O lease deve gravar `hostname` também: `pid` só é
interpretável na máquina que o escreveu. Ordem correta: mesmo host → `pid`; host diferente ou pid
reciclado → idade do heartbeat como degradação.

**3. Quem atualiza o heartbeat?** A issue não diz, e essa é a pergunta que decide se a feature
funciona. Se depender de o agente lembrar de tocar o lease, a feature tem exatamente o defeito que
**B1** descreve: uma regra lida na abertura que precisa valer três horas depois. **O heartbeat tem de
ser efeito colateral da ferramenta** — todo comando `governancekit` toca o lease da sessão corrente,
sem ninguém pedir. Aí o §8c (ler o relógio a cada resposta) já dá a cadência de graça.

**4. O `render` sozinho não resolve o efeito 3.** Avisar *"não use `git add -A`"* na abertura é
mitigação por memória. O efeito de varrer arquivo alheio para dentro do commit só desaparece quando o
staging por caminho explícito for regra, e a própria issue já viu isso ao escrever
*"vale a pena ser incondicional"*. **Concordo, e vou além: incondicional de verdade — não
condicionada a detectar árvore compartilhada.** A detecção é a parte frágil (lease pode faltar,
estar velho, ou o outro agente não usar o kit); a disciplina é a parte robusta. Regra que só liga
quando a detecção acerta herda a fragilidade da detecção.

## O que isto muda no §1c — e a ligação com B1

O §1c de ontem modela frente aberta como **topologia**: worktree viva ou branch não mesclada. C1 diz
que a unidade real é a **sessão**, e que a topologia é uma proxy que falha por baixo (duas sessões,
uma linha). Aceito a reformulação: frente aberta = *trabalho não mesclado* **ou** *agente vivo*, com
o git como uma das duas fontes e o registro de sessões como a outra.

E a §7 proposta em C1 é **B1 aplicada**: `git add -A` proibido, HEAD reconferido antes do commit,
fetch antes de afirmar push — três gates no momento da ação, nenhum dependendo de leitura no Start
Gate. É a primeira validação independente da tese do B1, vinda de outro incidente. Isso reforça a
ordem já anotada no `RESUME.md`: **B1 sobe**, e o §1c precisa de gate de ação antes de precisar de
lease.

## Ordem sugerida

1. **§7 de C1** — os três gates. Incondicionais, sem detecção, sem código novo no kit. Eliminam a
   classe inteira dos efeitos 1–3. Fazer junto com **B1**, que é a mesma forma.
2. **§8a de C1, item 6 de C2** — reconciliar o caminho do registro para `~/Sync`. Duas linhas de
   contrato; hoje a documentação aponta para um diretório inexistente.
3. **`_unmerged_count`** — falha deixar de virar `removable`, e a leitura declarar-se local. Defeito
   ativo em código que já mostramos ao operador.
4. **Lease** (C2, itens 1–3, 5, 7, 8) — com `--git-common-dir`, `pid`+`hostname`, e heartbeat como
   efeito colateral da ferramenta.
5. **Item 4 de C2** (ordem no hook) — trivial, entra junto com o lease.

## Aberto, para o operador decidir

- **Proibir `git add -A` incondicionalmente** no §7 muda o hábito em todo projeto governado, inclusive
  onde não há concorrência nenhuma. É o ponto de maior atrito da proposta e o de maior retorno.
- **A entrada `cursor` de 31/07**: a política proposta (reportar, nunca apagar) é a correta e coincide
  com o `CLAUDE.md` global. Mas ninguém vai remover essa entrada — o processo não existe mais. Ou
  existe um comando explícito de limpeza operado por humano, ou o registro acumula lápides para
  sempre.
