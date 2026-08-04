# Issues — repositório `EDortta/AI-Agents`

Dez issues. Metadados comuns a todas:

- work_id: `WK-20260804-governancekit-contract-reassessment`
- date: 2026-08-04
- owner: Esteban D.Dortta
- parent epic: `epic.md` — Reconciliar contrato AI-Agents e ferramenta GovernanceKit
- versão observada: AI-Agents `v1.1.7`, instalada em `AI/CodexBridge` em 2026-08-04 17:20

---

## A1 — Mover todas as referências de readiness de `.docs/` para `docs/` [crítica]

### Objective

O `AGENTS.md` §1b manda o agente parar quando `.docs/software-overview.md` ou
`.docs/limits.md` faltam. O GovernanceKit 0.2.3 move esses dois arquivos para `docs/`
na instalação, deliberadamente e com justificativa escrita no código. O contrato
precisa nomear o caminho onde os arquivos efetivamente estão, senão o gate obrigatório
manda parar em toda instalação correta.

### Evidência

```
$ grep -rn '\.docs/software-overview\.md\|\.docs/limits\.md' AGENTS.md .docs/ docs/required-reading.md | wc -l
35
$ grep -rn '[^.]docs/software-overview\.md\|[^.]docs/limits\.md' AGENTS.md .docs/ docs/required-reading.md | wc -l
0
```

Decisão do lado da ferramenta, em
`governancekit/install_agents.py::_migrate_readiness_files_to_docs`:

> *"They were classified as kit-owned between 2026-07-01 and 2026-08-04 and installed
> under `.docs/`. They are project-owned — the project writes them and owns their
> readiness flags — so the Start Gate must read them from `docs/`, which the kit never
> overwrites."*

### In Scope

Trocar `.docs/software-overview.md` → `docs/software-overview.md` e
`.docs/limits.md` → `docs/limits.md` em:

| arquivo | linhas | criticidade |
|---|---|---|
| `AGENTS.md` | 40, 99, 100, 113, 114, 116, 146 | §1b é o gate obrigatório |
| `.docs/context-manifest.yaml` | 9, 11 | carregador determinístico de contexto |
| bloco gerado de `docs/required-reading.md` | 15, 16 | índice único de leitura |
| `.docs/agents/_shared.md` | 13 | preâmbulo comum a todos os papéis |
| `.docs/agents/council.md` | 159, 171 | ver A8 |
| `.docs/workflows/php-audit.md` | 9 | pré-condição da auditoria |
| `.docs/workflows/delphi-audit.md` | 9 | idem |
| `.docs/workflows/typescript-audit.md` | 9 | idem |
| `.docs/articles/*` (pt-BR, en, es) | `01-first-day-setup.md:7,8,36,38`; `09-senior-workflow-and-automation.md:50`; `ai-agents-in-vscodium-chat*.md:50,51,59,91` | é o material que ensina o programador onde escrever |

Ajustar também §2 do `AGENTS.md` (linha 146): a exceção "`.docs/software-overview.md`
e `.docs/limits.md` são semeados pelo kit mas preenchidos e preservados por projeto"
deixa de ser exceção — os dois passam a ser simplesmente território do projeto, como
`docs/project-rules.md`. A tabela da linha 40 muda junto.

### Out of Scope

- Alterar o comportamento do instalador shell — é A2.
- Criar a verificação automática de coerência — é G1.
- Migrar arquivos em projetos já instalados — o `governancekit` já faz isso.

### ARO

- **Acceptance:** `grep -rn '\.docs/software-overview\.md\|\.docs/limits\.md'` no
  repositório do kit retorna zero. Um projeto recém-instalado passa em
  `governancekit doctor` sem que o `AGENTS.md` mande parar.
- **Risk:** baixo em si; alto se sair sem A2 — o instalador shell continuaria
  semeando em `.docs/` e recriando a divergência a cada execução.
- **Operations:** projetos já instalados recebem a correção no próximo `--upgrade`;
  os arquivos de conteúdo já foram migrados pelo `governancekit`, então não há passo
  manual para o operador.

### Test Plan

- Instalação limpa em repositório vazio → `doctor` não reporta arquivo de readiness
  ausente, e `AGENTS.md` §1b nomeia os arquivos que existem.
- Instalação sobre projeto que tem `.docs/limits.md` preenchido → após `--upgrade`,
  o conteúdo está em `docs/limits.md`, e nenhum documento do kit aponta para o
  caminho antigo.

### Security
Nenhum impacto direto. Indireto: enquanto o gate aponta para caminho inexistente, o
`AGENTS.md` §1b — que também é o gate que impede trabalho em projeto sem limites
declarados — está inoperante como controle.

### Privacy
Personal data impact: não.

### DoD
- Zero ocorrências do caminho antigo no repositório do kit.
- `AGENTS.md` §2 não trata mais os dois arquivos como exceção de propriedade.
- Nota no CHANGELOG explicando a migração e apontando o release do GovernanceKit
  correspondente.

---

## A2 — Alinhar `install-agents-kit.sh` ao destino `docs/` (ou aposentá-lo) [crítica]

### Objective

Existem hoje **dois instaladores operando em direções opostas** no mesmo repositório.
Quem rodar por último ganha.

| componente | destino de readiness | evidência |
|---|---|---|
| `governancekit` 0.2.3 (Python) | `docs/` | `install_agents.py:77-78,577,582`; `discover.py:35-36`; `codemap.py:409-410`; `scope_conversation.py:18-19`; `adoption.py:126` |
| `scripts/install-agents-kit.sh` v1.1.7 | `.docs/` | linhas 76-77, 997, 1754, 1807-1809, 1867-1869, 1980-1981 |

O agravante é que o `.sh` é o caminho que os artigos de onboarding ensinam, e o
`AGENTS.md` §1a instrui o operador a rodar `install-agents-kit.sh --target . --upgrade`
quando faltam slots. Um operador seguindo a documentação reverte a migração da
ferramenta.

A linha 1795 do próprio `.sh` documenta o sintoma: projetos contornaram o problema
com symlink (`.docs/limits.md -> ../docs/limits.md`, "a real arrangement, seen in
wa-hub"). Três arranjos coexistem hoje no parque instalado — arquivo em `.docs/`,
arquivo em `docs/`, e symlink entre os dois.

### In Scope

Escolher uma das duas saídas e executá-la inteira:

- **(a) Alinhar:** `.sh` passa a semear, preservar e validar em `docs/`; as linhas
  1807-1809 (`sed_in_place` das flags de readiness), 1867-1869 (preserved
  project-local) e 1980-1981 (verificação final) mudam de alvo; o array de
  `kit_files` (1754) deixa de incluir `software-overview.md` e `limits.md`.
- **(b) Aposentar:** o `.sh` vira um wrapper fino que delega para `governancekit
  install-agents`, e todas as referências nos artigos e no §1a passam a citar o CLI.

Recomendação: **(b)**. Duas implementações da mesma instalação é a causa raiz; alinhar
só adia a próxima divergência.

### Out of Scope
- O texto do contrato — é A1.

### ARO
- **Acceptance:** rodar `.sh --upgrade` e `governancekit install-agents --upgrade` em
  qualquer ordem, no mesmo repositório, produz o mesmo estado de disco.
- **Risk:** aposentar o `.sh` quebra automações que o chamam direto. Levantar antes
  quem o invoca (o próprio kit instala uma cópia em `scripts/` de cada projeto).
- **Operations:** se for (b), manter o `.sh` respondendo com mensagem de
  redirecionamento por pelo menos um ciclo, em vez de removê-lo.

### Test Plan
- Teste de idempotência cruzada: `.sh` → `governancekit` → `.sh`, verificando que o
  terceiro passo não move nem recria nada.
- Instalação a partir de um projeto no arranjo symlink (`.docs/limits.md ->
  ../docs/limits.md`), confirmando que o resultado é um arquivo real em `docs/`.

### Security
Nenhum impacto direto.

### Privacy
Personal data impact: não.

### DoD
- Um único caminho de instalação documentado nos artigos e no §1a.
- Teste de idempotência cruzada no CI.

---

## A3 — O bloco `.gitignore` gerado não cobre `.env*` [alta]

### Objective

O instalador escreve um bloco gerenciado no `.gitignore` do projeto alvo. O bloco não
cobre `.env*`, que o próprio `AGENTS.md` §7 proíbe commitar — e o `doctor` do release
corrente reprova exatamente essa ausência.

### Evidência

Bloco escrito em `AI/CodexBridge` às 17:20:

```
# AI-Agents kit — managed by governancekit install-agents
AGENTS.md
.cursorrules
CLAUDE.md
...
.credentials
handoff.md
...
# end AI-Agents kit
```

`doctor` no mesmo repositório, às 17:26:

```
[FAIL] gitignore secrets: .gitignore does not cover secret paths: .env
```

Mesma ferramenta, mesma versão, mesmo repositório, seis minutos de intervalo.

### In Scope
- Acrescentar `.env` e `.env.*` ao bloco gerenciado (preservando `.env.example`, que
  é rastreado de propósito em vários projetos — usar `!.env.example`).
- Verificar se o bloco é escrito pelo `.sh`, pelo CLI, ou por ambos, e corrigir onde
  estiver (ver A2).

### Out of Scope
- O teste de CI que teria pegado isso — é G5.

### ARO
- **Acceptance:** `install-agents` seguido de `doctor`, em repositório limpo, não
  produz `[FAIL] gitignore secrets`.
- **Risk:** um `!.env.example` mal posicionado pode desrastrear um arquivo hoje
  versionado. Verificar a ordem das regras.
- **Operations:** projetos existentes recebem no próximo `--upgrade`; o bloco é
  gerenciado, então não há merge manual.

### Test Plan
- Repositório limpo → `install-agents` → `doctor` → sem FAIL de gitignore.
- Repositório com `.env.example` rastreado → após upgrade, `git status` não mostra o
  arquivo como removido nem ignorado.

### Security
Impacto direto: o bloco gerenciado é o controle que impede commit de segredo, e hoje
ele tem um buraco no formato de arquivo de segredo mais comum do ecossistema.

### Privacy
Personal data impact: sim, potencial — `.env` costuma carregar credenciais e dados de
conexão.

### DoD
- Bloco cobre `.env`, `.env.*`, preserva `.env.example`.
- `doctor` limpo logo após instalação.

---

## A4 — O contrato não define fronteira de repositório [alta]

### Objective

O `AGENTS.md` define escopo como propriedade **da tarefa** ("Keep scope tight to the
issue/request", §3) e nunca como propriedade **do lugar**. Não existe regra que diga
que o agente trabalha em um repositório e apenas nele. §3b cobre efeito externo
(mensagem, e-mail, webhook, API de terceiro, deploy) e não cobre **ler outro
repositório**.

### Evidência

```
$ grep -rniE 'outro (projeto|repositório)|other (repo|project)|outside (the|this) repos|repository boundary|cross-repo' AGENTS.md .docs/agents/
.docs/agents/credentials-operations.md:12:  operator-local reference outside the repository.
.docs/agents/council.md:139:  to other repositories — blast radius greater than one repo.
```

Duas ocorrências, ambas incidentais. Nenhuma é regra de escopo.

### Incidente que originou

2026-08-04, no `AI/CodexBridge`. Pedido do operador: *"temos épicas e issues para
implementar"* — sem nomear projeto. O CodexBridge não tinha `docs/issues/` (o `doctor`
confirma: `[FAIL] docs/issues: missing`). A sessão do agente vinha com seis
*additional working directories* concedidos pelo harness, entre eles a pasta de um
épico de outro produto. O agente localizou esse épico e o inspecionou: `epic.md`,
`RESUME.md`, sete arquivos de issue, o estado de dois checkouts e o histórico git de
um produto sem relação com o projeto ativo.

Nenhuma escrita ocorreu. **E nenhuma regra foi violada, porque não existia regra.**
Um agente que cumpra 100% do contrato pode inspecionar outro produto e continuar
formalmente conforme.

Agravante: o gate §1b, que deveria ter impedido o trabalho (o projeto não tinha
`docs/issues/` nem readiness configurado), **autorizou** — o agente carregou o
`AGENTS.md` do kit-fonte em `~/`, encontrou lá os arquivos **do kit**, e concluiu que
o gate havia passado. Ver A6.

### In Scope

Nova subseção em §3 (ou §3c, ao lado de "Untrusted Content and External Actions"),
com pelo menos:

- O escopo do agente é **um repositório**: aquele em que a sessão foi aberta.
- **A proibição inclui leitura.** `ls`, `find`, `grep`, `git log` em outro projeto já
  está fora de escopo — não é preciso escrever nada para violar.
- **Diretórios adicionais concedidos pelo harness não são autorização.** Um caminho
  estar acessível diz respeito ao ambiente, não ao contrato.
- **Menção não é autorização.** O operador citar outro projeto não abre o outro
  projeto; abre a possibilidade de pedir.
- Se a tarefa parecer exigir outro repositório: **parar e perguntar — não sair
  procurando.**
- Exceções nominais, se o projeto tiver alguma, vão em `docs/limits.md`, e a lista de
  exceções é fechada: necessidade não prevista é pedido ao operador, não interpretação
  extensiva.

### Out of Scope
- Enforcement executável (o harness é quem concede os diretórios; o kit não os
  controla). Esta issue é contrato, não sandbox.

### ARO
- **Acceptance:** o incidente acima, reencenado, viola uma regra nominal e citável.
- **Risk:** regra escrita apertada demais bloqueia diagnóstico legítimo — ler
  `/etc/<produto>/`, criar fixture git descartável no scratchpad. Por isso a válvula
  é `docs/limits.md` com exceções nominais, e não uma proibição absoluta no contrato.
- **Operations:** produtos que orquestram outros repositórios em runtime (é o caso do
  CodexBridge) precisam da distinção explícita: *o que o produto alcança em execução
  não estende o escopo de quem o desenvolve*.

### Test Plan
- Revisão adversarial: dado o texto novo, um agente consegue justificar a leitura do
  épico de outro produto? Se sim, o texto ainda não fecha.

### Security
Impacto direto: é uma regra de confinamento. A ausência dela é a diferença entre
"o agente não fez" e "o agente não podia fazer".

### Privacy
Personal data impact: sim, potencial — outro repositório pode conter dados pessoais
que o agente não deveria alcançar, e hoje nada o impede de lê-los.

### DoD
- Regra escrita em `AGENTS.md`, com a leitura explicitamente incluída na proibição.
- Implementação de referência disponível em
  `AI/CodexBridge/docs/limits.md`, seção "Fronteira de repositório" (inclui a seção
  "Antecedente" registrando este incidente).

---

## A5 — Quatro arquivos de identidade, e o contrato nomeia dois que não existem [alta]

### Objective

O `AGENTS.md` cita dois arquivos de identidade diferentes, o instalador produz um
terceiro, e o `doctor` sugere um quarto. Nenhum dos dois que o contrato nomeia existe
após uma instalação bem-sucedida.

### Evidência — estado em `AI/CodexBridge` após instalação de 17:20

| arquivo | quem cita | existe | schema |
|---|---|---|---|
| `.credentials/identity.json` | `AGENTS.md` §1a (linhas 5, 54, 74) | **não** — o diretório existe, com symlinks de credencial | valores dos slots `{{…}}` |
| `.governancekit-identity.json` | `AGENTS.md` §8b + `doctor` | **não** | `operator_name`, `host_id`, `instance_path`, `sibling_path`, `assigned_ports`, `branch_ownership` |
| `.gk/operator.json` | nenhuma seção do contrato | **sim** (17:20, modo 600) | `metadata.OPERATOR_NAME`, `metadata.SMTP_ACCOUNT`, `state_version` |
| `.gk/project-config.json` | só o `[HINT]` do `doctor` | não | não documentado |

Os slots `{{…}}` foram preenchidos corretamente — a partir de `.gk/operator.json`, não
de `.credentials/identity.json`, que §1a nomeia como a fonte. O passo funciona; a
documentação descreve outro arquivo.

§8b é `[MANDATORY]`: *"Before any action, read/establish this instance's identity file.
If it is absent → **STOP**. Do not inspect, branch, edit, or commit until identity is
established."* O instalador rodou e deixou o arquivo ausente.

### In Scope
- Um nome, um schema, um propósito. Decidir se identidade de operador (nome, SMTP) e
  identidade de instância (host, portas, branch ownership) são um arquivo ou dois — e,
  se forem dois, nomear os dois no contrato com propósitos distintos.
- §1a e §8b passam a citar o mesmo arquivo que a ferramenta efetivamente escreve e lê.
- Documentar `.gk/project-config.json` ou removê-lo do `doctor`.

### Out of Scope
- Fazer o `install-agents` coletar a identidade — é G3.

### ARO
- **Acceptance:** após instalação limpa, todo arquivo de identidade citado pelo
  contrato existe, e todo arquivo criado pela ferramenta é citado pelo contrato.
- **Risk:** renomear arquivo já em uso em projetos instalados exige caminho de
  migração; reaproveitar `_migrate_readiness_files_to_docs` como modelo (idempotente,
  não destrutivo).

### Test Plan
- Instalação limpa → `doctor` sem `[FAIL] host identity`.
- Projeto com `.gk/operator.json` legado → após upgrade, identidade legível pelo nome
  novo, sem perda de valor.

### Security
Impacto direto no §1a, que existe por conformidade LGPD Art. 46: os valores pessoais
do operador devem sair de arquivo **não rastreado**. Confirmar que o arquivo-fonte
final está coberto por `.gitignore` em todos os projetos (hoje `.gk/operator.json` e
`.credentials` estão; validar o nome novo).

### Privacy
Personal data impact: **sim** — nome e e-mail do operador.

### DoD
- Um nome canônico por propósito, citado em §1a e §8b.
- Migração idempotente a partir dos nomes legados.
- Arquivo-fonte coberto por `.gitignore` no bloco gerenciado.

---

## A6 — §1b descreve o gate em prosa e nunca aponta para o gate executável [média]

### Objective

O gate executável que faltava **existe**: `governancekit doctor` verifica os quatro
arquivos obrigatórios, as duas flags de readiness, o índice de leitura, segredos
rastreados e identidade, e devolve `Result: FAIL`. O `AGENTS.md` §1b nunca o menciona
— descreve o procedimento em prosa e deixa a verificação a cargo da leitura do agente.

O modo de falha é conhecido e já ocorreu: em projeto ainda não governado, o agente
carrega o `AGENTS.md` do kit-fonte em `~/`, encontra os arquivos **do kit**, e conclui
que o gate passou. Valida o kit, não o projeto. **Foi o gate que autorizou o incidente
de A4.**

### In Scope
- §1b passa a instruir: rodar `governancekit doctor`; saída diferente de zero é o gate
  falhando; relatar as linhas `[FAIL]` ao operador e parar.
- A prosa atual vira explicação do *porquê*, não procedimento.
- Corrigir o defeito de contagem: *"If **either** file is missing"* para uma lista de
  **quatro** itens (linha 108) → "if **any** of them".
- Definir o comportamento quando o CLI não está instalado: fallback documentado para a
  verificação manual, sem fingir que o gate passou.

### Out of Scope
- Adicionar verificações novas ao `doctor`.

### ARO
- **Acceptance:** agente em projeto sem readiness configurado para, cita a linha
  `[FAIL]` que o levou a parar, e não confunde arquivos do kit-fonte com arquivos do
  projeto.
- **Risk:** tornar o `governancekit` dependência dura do contrato. Mitigar com o
  fallback documentado.

### Test Plan
- Repositório sem readiness → agente para e cita o `doctor`.
- Repositório sem o CLI instalado → agente usa o fallback e diz explicitamente que a
  verificação foi manual.

### Security
Indireto: §1b é o gate que impede trabalho em projeto sem limites declarados.

### Privacy
Personal data impact: não.

### DoD
- §1b cita o comando; "either" corrigido; fallback documentado.

---

## A7 — §8a aponta o monitor para um caminho que não existe [alta]

### Objective

§8a manda escrever o status da sessão em
`${XDG_STATE_HOME:-$HOME/.local/state}/ai-agents/agent-status.json`, é opt-in pela
presença do arquivo, e fecha com *"Never invent a different location: an agent writing
its status where the monitor does not look is worse than not writing it at all."*

Esse caminho não existe nesta máquina. O que existe e está vivo é
`~/Sync/agent-status.json` — e `~/Sync/agent-log.md`, escrito às 17:22 de 2026-08-04
por outra sessão de agente. É também o que o `~/CLAUDE.md` global do operador manda
usar.

Resultado: quem obedece §8a some do painel; quem obedece o `CLAUDE.md` viola §8a. E o
opt-in-por-presença garante que o conflito seja silencioso — o agente que segue §8a
simplesmente pula a seção e não reporta nada.

### Evidência
```
$ ls ${XDG_STATE_HOME:-$HOME/.local/state}/ai-agents/
ls: cannot access '/home/esteban/.local/state/ai-agents/': No such file or directory
$ ls -la ~/Sync/agent-status.json ~/Sync/agent-log.md
-rw------- 1 esteban esteban   1298 08-04 12:52 /home/esteban/Sync/agent-status.json
-rw-rw-r-- 1 esteban esteban 271057 08-04 17:22 /home/esteban/Sync/agent-log.md
```

### In Scope
- Decidir o caminho canônico. Duas alternativas legítimas: adotar `~/Sync/` (a
  instalação real, sincronizada entre máquinas — que é justamente o que um monitor
  *cross-project e cross-host* quer) ou manter XDG e migrar o existente.
- Se XDG for mantido: `governancekit doctor` deve reportar quando existe monitor em
  local não canônico, em vez de deixar os dois coexistirem em silêncio.
- Reconciliar com o `~/CLAUDE.md` global — hoje as duas instruções são contraditórias
  e o `CLAUDE.md` tem precedência prática, porque carrega em toda sessão.

### Out of Scope
- Formato do JSON e do log (`agent-log.md`) — estão bons e em uso.

### ARO
- **Acceptance:** um caminho, citado igual no `AGENTS.md`, no `CLAUDE.md` global e no
  que a ferramenta verifica.
- **Risk:** migrar o `agent-status.json` vivo com sessões ativas registradas dentro.
  Migração deve ser merge, não overwrite.

### Test Plan
- Duas sessões simultâneas de agentes diferentes escrevem e removem suas entradas sem
  perder a do outro.

### Security
`agent-status.json` está em modo 600 e `agent-log.md` em 664. Se o caminho mudar,
preservar a permissão restritiva do status.

### Privacy
Personal data impact: baixo — nomes de projeto e descrição de tarefa.

### DoD
- Um caminho canônico; `CLAUDE.md` global e `AGENTS.md` concordam; sem cópia órfã.

---

## A8 — `council.md` depende de estrutura do overview que o seed não declara [média]

### Objective

`council.md` §5 (linhas 159 e 171) monta o conselho lendo *"the six lines of the
Target Project Checklist"* de `.docs/software-overview.md`, e a dependência é
`[MANDATORY]`: se o overview não estiver pronto, *"the council cannot be selected —
every question above reads from it. Say so and stop; do not guess the answers."*

O seed de `software-overview.md` traz essa seção como um checklist de orientação, no
fim do arquivo, sem em momento algum declarar que **é contrato consumido por outro
documento**. Quem preencher o arquivo com estrutura própria — que é exatamente o que
o seed pede: *"the programmer must replace this content with that project's actual
context"* — quebra o council em silêncio.

Verificado: aconteceu. O `docs/software-overview.md` do `AI/CodexBridge`, preenchido
com produto, stack, usuários, módulos e comportamento chave, **não tem o checklist**.
O council está inselecionável naquele projeto e nada avisa.

### In Scope
- Marcar as seis linhas no seed como estrutura obrigatória, com o motivo e o
  consumidor nomeado (`.docs/agents/council.md` §5).
- Ou desacoplar: `council.md` deriva as questões do conteúdo do overview em vez de
  exigir um cabeçalho literal.
- Se ficar acoplado, o `doctor` deve verificar a presença das seis linhas junto com
  `project_context_ready: yes` — hoje a flag pode estar `yes` com o contrato quebrado.
- O caminho citado nas linhas 159 e 171 muda em A1.

### Out of Scope
- O conteúdo das seis perguntas — está bom.

### ARO
- **Acceptance:** um overview preenchido do zero, seguindo o seed, mantém o council
  selecionável — ou o `doctor` avisa que não mantém.
- **Risk:** exigir estrutura literal engessa o overview, que é documento do projeto.
  Preferir o desacoplamento.

### Test Plan
- Overview preenchido sem o checklist → `doctor` avisa, ou o council funciona mesmo
  assim. Hoje: nem um nem outro.

### Security
Não aplicável.

### Privacy
Personal data impact: não.

### DoD
- O acoplamento é explícito no seed, ou não existe mais.

---

## A9 — §2 manda o agente rodar o instalador, contra §1a e §1b [média]

### Objective

§1a é categórico: *"Antes de qualquer outra ação... Pare imediatamente. Não execute
nenhuma ação — nem leitura de código, nem inspeção, nem branch, nem commit."* §2, umas
linhas abaixo, manda o agente rodar `governancekit install-agents --upgrade` antes da
primeira issue ou mudança de código.

As duas instruções não podem valer ao mesmo tempo, e a segunda é a mais invasiva das
duas: a execução de hoje neste projeto **alterou `.gitignore`, que é arquivo
rastreado**, e escreveu um bloco que o `doctor` do mesmo release reprova (A3).

### In Scope
- Decidir de quem é a ação de instalar. Recomendação: **do operador**, não do agente.
  O agente detecta que a instalação está desatualizada ou incompleta, **reporta**, e
  para — coerente com §1a, com §1b e com a regra geral de não fazer mudança estrutural
  sem aprovação.
- Se o agente puder rodar o instalador, então §1a precisa dizer explicitamente que
  essa é a única ação permitida antes do gate passar, e o instalador não pode tocar em
  arquivo rastreado sem avisar o que vai mudar.

### Out of Scope
- O conteúdo do bloco `.gitignore` — é A3.

### ARO
- **Acceptance:** não há mais duas instruções contraditórias sobre a mesma ação.
- **Risk:** se a instalação passar a ser só do operador, projetos ficam desatualizados
  por mais tempo. Mitigar com `doctor` reportando a defasagem de versão de forma
  visível.

### Test Plan
- Leitura adversarial de §1a + §2: um agente consegue derivar duas condutas opostas?

### Security
Indireto: modificação de arquivo rastreado sem aviso é mudança fora do escopo
declarado da sessão.

### Privacy
Personal data impact: não.

### DoD
- §1a e §2 concordam sobre quem instala e quando.

---

## A10 — §8c é `[MANDATORY]` mas não tem gatilho [média]

### Objective

§8c é declarado *strong limiter*: garantir uma hora de pista para fechar todas as
sessões paralelas antes do fim do dia. A mecânica depende inteiramente de o agente
lembrar de ler o relógio: *"Agents have no continuous clock, so the check is
action-triggered: read the local wall-clock time (e.g. `date +%H:%M`) at the start of
each response."*

Nada força essa leitura. É a única regra `[MANDATORY]` do contrato cuja verificação é
um hábito.

Registro honesto desta sessão: o aviso de wind-down só foi emitido às 17:26 porque o
relógio foi consultado deliberadamente, no meio de outro assunto. Se o assunto não
tivesse surgido, não teria sido.

### In Scope
- Ancorar em algo que o agente já faz sempre. Opções: `governancekit resume` (que §
  programmer.md já manda rodar no início da sessão) imprimir a hora e a pista restante;
  ou o `doctor` reportá-las; ou o próprio `AGENTS.md` amarrar a leitura do relógio a
  um gatilho concreto do fluxo (abertura de sessão, e cada `git commit`).
- A companion runtime já está prevista no texto: *"AI-GovernanceKit `resume`/`doctor`
  can surface the active `session_winddown_hour` and the current runway."* Falta
  implementar e o contrato passar a depender disso em vez do hábito.

### Out of Scope
- Os valores padrão (17:00 / 60min) — estão bons.

### ARO
- **Acceptance:** a pista restante chega ao agente sem que ele precise lembrar de
  pedi-la.
- **Risk:** ruído — avisar cedo demais, ou a cada resposta, treina o agente a ignorar.

### Test Plan
- Sessão iniciada às 16:50 → o aviso aparece por si na primeira resposta após as 17:00.

### Security
Não aplicável.

### Privacy
Personal data impact: não.

### DoD
- O gatilho existe fora da memória do agente.
