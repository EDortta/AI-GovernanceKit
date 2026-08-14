# Handoff

## [2026-08-14] Fase 0 do WK-20260813-council-audit-of-r2-closures — commitada; execução noturna achada quebrada

- branch: `development`, commits `74bfefa` (conteúdo) e `3effe89` (0.3.1→0.3.2). Não
  empurrado. `main` intocada.
- RESUME: `docs/issues/014-council-audit-of-r2-closures-[draft]/RESUME.md`
- work_id: `WK-20260813-council-audit-of-r2-closures`

### Entregue

Fase 0 do `PLANO-UNIFICADO.md`, três grupos, cada um com concílio de quatro lentes
passado na sessão interativa de 2026-08-13 (não pela execução noturna — ver abaixo):

- **AC-1** (render gate) — a fonte é renderizada com as respostas guardadas do projeto
  antes de ser comparada contra o alvo. 5 rodadas, 63 testes novos, suíte 508 → 571.
- **AC-2/AC-3/AC-4/AC-5** (remove-agents) — evidência "byte a byte" passa a comparar
  bytes de verdade, contra `_kit_snapshot.json` derivado do tarball checksum-verificado
  do release pinado. 3 rodadas, 19 mutações, suíte 576 → 595.
- **AC-25 + AC-28** — fecha exfiltração da chave do operador por manifesto envenenado
  (achado mais grave da lente LGPD) e a emenda do SMTP guiado (`mailbox.py` novo).

Versão: `0.3.1 → 0.3.2` (um sub-versão por fase concluída, regra do próprio
`PLANO-UNIFICADO.md`, confirmada pelo operador nesta sessão). `pytest`: 636 passed.
Reinstalado localmente via `pip install --user --force-reinstall --no-deps .`.

### Achado — execução noturna sem PASS nenhum

`scripts/run_plan.py` rodou de 2026-08-13T21:17 a 2026-08-14T11:37+ tentando a Fase 1
(`CONFIRM-TREE`, `AC-13`, `AC-20`, `AC-21`, `AC-22`, `AC-28-emenda`, `AC-29`) e voltou
**0 PASS em 200 veredictos de concílio**, sem erro/traceback registrado, e sem
modificar um único arquivo em 13+ horas (mtimes confirmam: tudo no working tree é de
antes de 21:17). Mais consistente com `claude -p` falhando silenciosamente no
ambiente de cron (`@reboot`, sem TTY/auth) do que com 200 rejeições reais. Crontab já
desarmado pelo operador. Detalhe e próximo passo: seção "Sessão encerrada 2026-08-14"
no RESUME da épica.

### Aberto, com dono

- **Fase 1** (`manifest.override.json`, `AC-13/20/21/22/28-emenda/29`) — sem código
  implementado. Bloqueada em diagnosticar o `claude -p` de cron antes de reimplementar
  ou rearmar a execução noturna.

## [2026-08-12] R2-16' e item 4 da #7 — concílio de duas rodadas, nada empurrado

- branch: `development`, **não empurrada**. `main` intocada. Nenhuma tag, nenhum deploy.
- RESUME: `docs/issues/011-sending-email-canonico-[review]/RESUME.md`

### Entregue

**R2-16'** — o `_do_upgrade` substituía todo arquivo de topo com um `shutil.copy2` nu.
Agora aplica a tabela de decisão do instalador shell **e a ordem dela**: a fonte baixada
é renderizada com as respostas guardadas antes de qualquer comparação. A paridade entre
as duas listas de arquivos protegidos virou asserção lida do release pinado.

**Item 4 da issue #7** — o `doctor` audita a §Sending Email por **digest** contra o
release pinado, nos dois portadores, com remédio diferente por portador e severidade
espelhada na do shell.

### Concílio — duas rodadas, quatro lentes na primeira

**r1: 16 achados + 12 perguntas, 16 sobreviveram ao §2, 15 viraram teste, 1 aceitação de
risco escrita. r2: 9 achados + 7 perguntas, 9 viraram teste.** Todos reproduzidos; os
registros legíveis por máquina estão em `.gk/council/`.

Três dos nove achados da rodada 2 eram **regressões das correções da rodada 1**, uma
delas de segurança (substituição encadeada expondo segredo local a partir da metade
compartilhada do estado). Nenhum deles existiria sem a primeira rodada — que é o
argumento para a segunda existir.

**Os fechamentos da rodada 2 não foram auditados**: o §4 proíbe a terceira rodada. Cada
um tem teste vermelho sem a correção, e a verificação de ponta a ponta foi refeita em
alvo real (`scripts/verify-elo4.sh`), mas ninguém além de mim olhou para eles.

### Aberto, com dono

- **AI-Agents** — o `write_manifest` do `install-agents-kit.sh` pula os `DRIFTED` e não
  pula os `PRESERVED`: a perda de dados do SWEEP-1 existe igual do lado shell, em release,
  e este repositório não pode fechá-la.
- `_do_fresh --force` continua apagando `AGENTS.md` editado — aceitação de risco escrita,
  porque os dois instaladores concordam e mudar um lado só recria a divergência.

### Checks

`pytest tests -q` → 457 passed, 6 subtests. `doctor` deste repositório: os mesmos três
`[FAIL]` de sempre (identidade de host, placeholder e índice), verificados presentes em
`HEAD` sem estas mudanças.

**Next:** decisão do operador — empurrar `development`, e se os fechamentos da rodada 2
merecem uma leitura humana antes disso.

---

## [2026-08-11] release v0.3.0, parque migrado, gate de deriva, 4 achados fechados

- branch: `development`, empurrada. `main` **consolidada e tagueada `v0.3.0`** (48
  commits — o backlog de 45 que a sessão anterior deixou, mais os desta).
- **Nenhum deploy.** Tags publicadas: AI-Agents `v1.2.1`, GovernanceKit `v0.3.0`.
- RESUMEs: `docs/issues/012-version-chain-coordination-[review]/`,
  `docs/issues/013-kit-drift-gate-[finished]/`,
  `docs/issues/011-sending-email-canonico-[review]/` (5 → 1 achado aberto)

### Regra nova do operador

**Quando a tag de um dos dois kits avança, a versão do outro acompanha** — não
necessariamente com o mesmo número. E o `governancekit` é **global da máquina**, por
design: um binário, um parque. Projeto consumidor não gateia release do kit; o
acoplamento é de máquina.

### Entregue

`0.2.3 → 0.3.0`, pinado em AI-Agents `v1.2.1`. 45 commits estavam parados sob
`[Unreleased]` com a versão intocada, e a cópia instalada estava congelada em 06/08 —
sem `council.py`, 6 módulos divergentes. Agora é byte a byte igual ao `main` tagueado.

**Parque: 28 dos 29 projetos governados em `v1.2.1`**, exceto
`YouBR/ZeeCred/jk-dashboard-backup`, excluído pelo operador. Inclui quatro migrações de
layout `docs/` → `.docs/` e um `--migrate-content` (`Contraponto`, 78 arquivos de
migração interrompida, 5 contratos legados extraídos). Backups em
`scratchpad/backup-20260811/`.

**Gate de deriva (R2-18)** — `governancekit/kit_drift.py` + `_kit_snapshot.json` +
`scripts/refresh-kit-snapshot.py`. Snapshot **derivado** do tarball verificado por
checksum, nunca digitado; quatro asserções offline. Cada direção verificada por mutação.

**Quatro dos cinco achados restantes da r2.** R2-16 era maior que o texto: sem TTY o
`configure` não preenchia nada enquanto o `doctor` reprovava não-advisory nomeando o
`configure` como remédio. R2-2 ganhou guarda no ponto da destruição. R2-15 já caíra com
o bump do pin, e ganhou guard. R2-17 **não é reproduzível** — o único caller já
normaliza.

### Defeitos encontrados fora do escopo, e corrigidos

- `doctor` morria em traceback, sem veredicto, em qualquer projeto com diretório sem
  permissão de busca. Anterior à release; achado no `GestaoContasFernanda`.
- `test_the_hook_does_not_block_when_the_toolchain_is_missing` nunca produziu a condição
  que nomeia: o *user site* segue no `sys.path`. Passava porque a cópia instalada era
  velha demais para chegar ao gate.

### Onde eu errei

Disse ao operador que o range permissivo protegeria o parque antigo — não protege, cada
projeto carrega a própria cópia do contrato. E enquadrei o `jk-structure` como
bloqueador da release, quando o acoplamento é só do binário global. O operador pegou os
dois. Também troquei a branch da worktree errada e usei `git stash` esquecendo que ele é
compartilhado entre worktrees do mesmo repo; nada se perdeu, nada foi commitado sujo.

### Next

**Épica 010/006 — reconciliação contrato × ferramenta.** As issues A1–A10, B1–B3,
C1–C2, G1–G5 estão escritas e **nunca foram criticadas**; a tabela de estado do RESUME é
de 04/08 e já envelheceu (A3, B3 e D1 têm commits de fechamento que ela não registra).
O operador aprovou seguir, e adiou para amanhã.

Aberto além disso: **R2-16'** (`_do_upgrade` sobrescreve arquivo de topo sem hash-check
nem stash) é o único dos cinco que não foi tocado. E a pergunta que o concílio deixou:
nada verifica que a contagem do §4 foi escrita no napkin — mesma forma que o R2-18 tinha
antes do gate.

## [2026-08-10] gh-7 — §Sending Email canônica - released, 6 achados abertos

- branch: `development`, empurrada (`origin/development` **criada** nesta sessão; não
  existia). `main` intocada, 45 commits atrás — consolidação não foi feita.
- **Nenhum deploy.** O AI-Agents é que ganhou tag: `v1.2.0`.
- RESUME: `docs/issues/011-sending-email-canonico-[review]/RESUME.md`

> A entrada abaixo, `blocked-on-round-2`, é histórico: a rodada 2 rodou no mesmo dia.

### Entregue

Itens 1, 2 e 3 da issue #7 fechados; item 4 (o `doctor` auditar a seção) parcial —
nenhum check a audita pelo nome; o que existe audita o índice para onde ela aponta e
detecta contrato obsoleto que ainda a prescreve.

`DEFAULT_REF = "v1.2.0"` com checksum verificado pela URL exata que o `_download` usa.
Cadeia conferida no **elo 4**: install real num projeto novo entrega tudo, e não
reivindica o `templates/` do projeto.

### Council

Duas rodadas. **19 achados na r1** (8 sobreviveram ao §2, 6 viraram teste),
**16 distintos na r2**, dos quais **10 fechados** por decisão do operador.

A r2 pegou duas coisas minhas que importam: eu revertera a entrada `templates` deste
instalador por perda de dados e não olhara o instalador shell, que tinha o mesmo
defeito em release; e eu inventara três dos quatro números do registro da r1 num
documento cuja função, pelo §4, é justamente substituir palpite por medida.

### Aberto — 6 achados

Ordem sugerida, os dois primeiros porque ainda podem apagar arquivo:

1. **R2-2** — manifesto envenenado não tem reparo. `prune_missing` só descarta entrada
   cujo arquivo sumiu, então a entrada sobrevive; o `remove-agents` remove a confiança
   1.0 sem revisão. Precisa de um `--repair-manifest` explícito, não de efeito colateral.
2. **R2-16'** — `_do_upgrade` sobrescreve arquivos de topo sem hash-check e sem stash,
   e o comentário do `doctor` afirma o contrário ("protected files are never
   overwritten"). O `.kit-new` nunca é escrito por este instalador.
3. **R2-15** — `configure` não persiste em `.gk/`, então o `--upgrade` seguinte desfaz.
4. **R2-11** — entradas de napkin sem as quatro contagens que o §4 exige.
5. **R2-17** — `_is_kit_owned` usa `startswith("docs/")` sem `as_posix()`.
6. **R2-18** — sem gate de deriva entre os dois kits; "uma origem só" é prosa.

**Next:** decidir se `development` vai para `main` (hoje 45 atrás), e abrir issue para
R2-2 e R2-16'.

---

## [2026-08-10] gh-7 — §Sending Email canônica - blocked-on-round-2

- branch: `development`, 37 commits a frente de `origin/main`. `main` intocada.
- **Nada empurrado.** Nenhum deploy, nenhuma tag.
- RESUME: `docs/issues/011-sending-email-canonico-[review]/RESUME.md`

### Entregue

Dois commits. Itens 1, 2 e 3 da issue #7 fechados; o item 4 (doctor) parcial — nenhum
check audita a seção pelo nome, o que existe audita o índice para onde ela aponta e
detecta contrato obsoleto que ainda a prescreve.

### Council — rodada 1

Três lentes. **19 achados, 19 sobreviveram ao §2, 8 fechados (6 com teste), 11
abertos.** O decisivo foi contra a própria correção: acrescentar `templates` às listas
de caminhos gerenciados apagava a pasta `templates/` do projeto no segundo upgrade, em
silêncio, com o `remove-agents` depois planejando removê-la a confiança 1.0.

**A rodada 2 não rodou.** Pelo §4 a entrega não está gateada.

**Next:** rodar a rodada 2 contra `HEAD`, focada na reversão do `templates` e nas três
correções do `_WITHDRAWN_CITATIONS`.

---

## [2026-08-07] Epico 010 — A3, B3 e o gatilho de council - ready-for-review

- branch: `development`, 34 commits a frente de `main`. **Nada empurrado.**

### Entregue

Lado ferramenta dos quatro trabalhos de hoje. Gemeos em `AI/Agents`: `8660853`,
`9a34b57`, `889eabe`, `b8dec46`.

- **`fff5907` — gatilho `not-validated`.** Produziu tres falsos positivos em dois dias
  e bloqueou o proprio session-close do kit. Os dois defeitos eram de escopo, e o
  `council.md` §4 ja dizia o escopo certo: lia o ARQUIVO `handoff.md` inteiro em vez das
  linhas ADICIONADAS pelo diff, e nao distinguia mencao de declaracao. Agora le o diff, e
  o escopo e o heading que encerra a linha: secao de testes ou heading de entrada =
  reivindicacao; qualquer outra subsecao = prosa. Verificado 4/4 contra as ocorrencias
  reais dos dois `handoff.md`.
- **`79e16aa` — A3.** `_gitignore_entries` devolvia 18 entradas e nenhuma cobria `.env`,
  enquanto `_check_gitignore_secrets` reprovava o repositorio por exatamente isso. Duas
  listas sobre um contrato. Agora `SECRET_IGNORE_PATTERNS` mora em `install_agents.py`, o
  `doctor` importa dela os nomes de template, e o teste afirma que o bloco gerado
  satisfaz cada sonda do verificador. As sondas OBRIGATORIAS continuam duas de proposito
  — alarga-las acenderia de vermelho todo projeto ja instalado.
- **`56ff8f0` — B3.** Dois checks novos sobre a secao `Fontes locais` do indice:
  `local reading sources` (obrigatorio ausente reprova, opcional avisa) e
  `local sources indexed` (ADVISORY — caminho local citado por contrato e ausente do
  indice). Advisory de proposito: e um detector, e os quatro ultimos defeitos deste kit
  foram de deteccao.

### O que isto muda para ESTE repo

- O `governancekit` instalado em site-packages e o **0.2.3 de 04/08** e nao tem o
  subcomando `council`. Todo council de hoje rodou com `PYTHONPATH` apontado para a
  fonte. E a cadeia de publicacao da A1, agora demonstrada contra o proprio gate.
- `adoption.py:129` ainda casa marcador de readiness por substring — mesmo defeito de
  mencao-versus-uso ja corrigido em `doctor` e `context_authoring`. Fora do escopo de
  hoje, registrado como pergunta aberta no round.
- `_update_gitignore` sempre reescreve o bloco no FIM do arquivo, entao uma linha que o
  operador pos depois do bloco antigo perde prioridade na proxima instalacao. Pre-existente.

### Blockers/Risks

- **A1 elo 3 e nosso**: `install_agents.py:21` `DEFAULT_REF` + `KNOWN_TARBALL_SHA256`
  seguem em v1.1.7. Depende de a tag ser cortada e empurrada — decisao do operador.
- **Nada avalia o orcamento de contexto num projeto instalado**: nem `hooks.py`, nem
  `doctor.py`, nem `install_agents.py` chamam `build_context`. Zero telemetria em
  qualquer projeto. O manifesto e instalado e fica inerte.

### Files changed

`governancekit/{council,doctor,install_agents}.py`,
`tests/{test_council,test_doctor_gitignore,test_doctor_local_sources}.py` (o ultimo novo),
`docs/napkin-lessons.md`, `docs/issues/010-.../RESUME.md`.

### Checks/Tests executed

- `python3 -m pytest tests/ -q` — **382 verdes**, 6 subtests.
- Mutacao em cada fix: desliguei o mecanismo e confirmei o teste ficar vermelho.
- Campo: `doctor` contra o AI-Agents real, checks de gitignore e de fontes locais `[PASS]`.
- Tabela de 23 sondas com `git check-ignore` num repo de verdade, nos dois sentidos.

### Suggested restart prompt

> Retoma o epico 010. `RESUME.md` tem a ordem revista de 2026-08-07. Proximo item nao
> bloqueado: **G1 como `HINT`** no `doctor`, absorvendo a G2 — reproduzir primeiro o
> `[PASS] contract v1.1.6 is compatible` ao lado de um `.gk/manifest.json` que diz
> `ref: v1.1.7`, que e a ferramenta discordando dela mesma.

## [2026-08-06] WK-20260806-council-commit-gate + crítica A1/G1/B1 - ready-for-review

- branch: `development` (`feature/uc-012/council-commit-gate` mesclada); `main` intocada;
  sem push

### Entregue

- **`governancekit/council.py`** (novo) — gate de council no commit de entrega. Registro
  amarrado ao **sha256 do diff staged** (council de ontem não libera o commit de hoje;
  emenda invalida a rodada), gatilhos detectáveis (`.docs/`, `AGENTS.md`, `templates/`,
  `not validated:` ancorado, sweep por contagem, pedido do operador), teto de 2 rodadas
  com escalação, waiver explícito e registrado. Estados em `.gk/council/<fingerprint>.json`.
- **`doctor.py::_check_council_gate`** — não-advisory só quando bloqueia; **silencioso
  quando nada está staged**; `CouncilError` nunca trava um commit.
- **`cli.py`** — subcomando `council` (`--json`, `--record`, `--waive`, `--requested`).
- **Dois defeitos graves no `pre-commit` que o kit instala** — ele **nunca reprovou nada
  pelo `doctor`**: (1) `cli.py` não tinha guarda `__main__`, então `python3 -m
  governancekit.cli` importava, não imprimia e saía 0; (2) o veredito era lido por
  `python3 - <<'PY'`, onde o heredoc **substitui o pipe** como stdin. A guarda foi para o
  `cli.py` (não só no `__main__.py`) para reparar hooks já escritos em repositórios, sem
  reinstalar. Teste que **executa** o hook, verificado por mutação.
- 342 testes verdes.

### Crítica de A1, G1 e B1 (feita hoje, não implementada)

Detalhe em `docs/issues/010-contract-vs-tool-reconciliation-[draft]/RESUME.md`. O que
recai **sobre este repositório**:

- **A1 depende de um elo que é nosso.** `install_agents.py:21` — `DEFAULT_REF = "v1.1.7"`
  mais a tabela `KNOWN_TARBALL_SHA256`, que só conhece até v1.1.7. Enquanto isso não
  subir, a correção de caminhos do AI-Agents **não chega a projeto nenhum**: o CodexBridge
  rodou upgrade hoje às 17:15 e recebeu o texto velho, com o §1b apontando para `.docs/`.
  Não existe tag `v1.1.8` (nem local, nem no remoto), embora o AI-Agents já declare
  `ref: v1.1.8`. O pin de checksum faz isso falhar **fechado** — comportamento certo.
- **G1 (contract coherence) cresce de caminhos para caminhos + versões.** `doctor` no
  CodexBridge diz `[PASS] contract v1.1.6 is compatible` (lido do
  `.docs/governancekit-integration.json`) enquanto o `.gk/manifest.json` ao lado registra
  `ref: v1.1.7` — a ferramenta discordando dela mesma. Isso absorve o G2. Entra como
  `HINT` que nomeia o remédio; vira `FAIL` quando a cadeia da A1 fechar, senão acende
  vermelho sem saída.
- **Comparar hashes do manifest NÃO substitui G1**: o `AGENTS.md` do CodexBridge bate com
  o hash dele — instalado fielmente e errado. Achado lateral: `_check_manifest_drift`
  (`doctor.py:566`) só confere **presença** e nunca compara os sha256 que guarda.
- **B1 refutada** ⇒ o que muda aqui: as três gates da §7 do C1 (`git add -A`, reconferir
  `HEAD`, `fetch` antes de afirmar push) são detectáveis por máquina e viram trabalho de
  **hook**, não de prosa.

### Blockers/Risks

- `_unmerged_count` (`concurrency.py:127`) lê só refs locais e **falha vira `0`**, que é o
  predicado de `removable`. O relatório de hoje diz que `uc-010` e `uc-011` são removíveis;
  uma falha de leitura diria o mesmo. Decisão pendente do operador.
- Worktrees `uc-010` e `uc-011` mescladas e não removidas; `uc-008` com +1 commit.
- Reescrita de histórico ainda pendente de decisão (bundle em
  `scratchpad/governancekit-pre-rewrite-20260804.bundle`).

### Files changed

- `governancekit/{council.py,cli.py,doctor.py,hooks.py,activity_monitor.py}`
- `tests/{test_council.py,test_doctor.py,test_hooks.py}`, `docs/advanced-usage.html`
- `docs/issues/010-contract-vs-tool-reconciliation-[draft]/{RESUME.md,verification-*.md,issues/D1-*.md}`

### Checks/Tests executed

- `pytest` -> 342 passed
- `git commit` real em repo de rascunho -> matriz completa do gate (bloqueia, libera,
  emenda re-bloqueia, waiver sem motivo recusado, rodada 3 recusada na gravação)
- `doctor` read-only contra `AI/CodexBridge` -> reproduz G1, G2 e A3 em campo

### Related commits

- `51be26b`, merge `484b508` (sem push)

### Suggested restart prompt

- "Continue work_id WK-20260804-governancekit-contract-reassessment. Read AGENTS.md,
  docs/software-overview.md, docs/limits.md e
  `docs/issues/010-contract-vs-tool-reconciliation-[draft]/RESUME.md`. A crítica de
  A1/G1/B1 está feita; o elo que trava tudo é `DEFAULT_REF` em `install_agents.py:21`,
  e ele depende de uma tag que o operador precisa autorizar."

## [2026-08-04] WK-20260804-concurrency-awareness - ready-for-review

- branch: `development`; `main` intocada; sem push

### Estado

- `governancekit/concurrency.py`: `survey_concurrency()` enumera as frentes abertas
  DESTE repositório — worktrees vivas e branches com commits fora da integração,
  deduplicadas — e marca as worktrees sem nada por mesclar como removíveis.
- `winddown_state()` **implementa o §8c**, que definia `session_winddown_hour` e
  `session_close_budget` desde maio dizendo que o kit "can surface" e nada surfaceava.
- Superfícies: comando `concurrency` (`--json`, `--closing`), bloco no `resume`,
  check advisory no `doctor`.
- Contrato no AI/Agents: §1c nova, §7 e §8c com referência cruzada, `session-restore`
  com passo 0 e `session-close` com o passo do que fica aberto.
- Hook `SessionStart` em `~/.claude/settings.json`, fail-open.

### Validação e pendências

- 310 testes; `run-checks` do AI/Agents verde. Pacote reinstalado; hook exercido nos
  dois casos (com kit e sem git).
- O gate de contexto do próprio kit pegou uma regressão minha: a primeira versão do
  §1c levou `base_contracts` a 8021/8000. Compactado.

### Frentes que ficam abertas para o dia seguinte

- `GovernanceKit` @ `feature/uc-008/credential-root-json-profile` — **+1 commit não
  mesclado**, perfil de credencial em JSON na raiz. É a única com trabalho real parado.
- `GovernanceKit-remove-agents` @ `feature/uc-010/remove-agents-safe-plan` — **mesclada;
  a worktree pode ser removida hoje sem perder nada.**
- `GovernanceKit/GovernanceKit-adoption-flow` @ `feature/uc-011/simplified-adoption-flow`
  — **mesclada; a worktree pode ser removida hoje sem perder nada.**

Remover as duas mescladas resolve, de passagem, o bloqueio da reescrita de histórico:
sobrariam dois checkouts em vez de quatro.

### Adendo 18:00 — 18 issues gravadas para amanhã

Preservadas de dois scratchpads de sessão (que não sobrevivem) para épica gêmea
`docs/issues/010-contract-vs-tool-reconciliation-[draft]/` e a irmã `006-` no AI/Agents:

- **A1–A10** (contrato) e **G1–G5** (ferramenta), origem `AI/CodexBridge`.
- **B1–B3**, origem `jk-structure`: gates no momento da ação, regra determinística na
  ferramenta, e o índice de leitura que não alcança `~/.config/`.

O `RESUME.md` da épica traz o cruzamento com o trabalho de hoje — A1 já feito, A2 pela
metade, A3 confirmada aberta, A10 com runtime pronto e gatilho ausente — e registra que
**B1 acusa o §1c escrito hoje**: regra de abertura de sessão é o padrão que ela chama de
decaído. Sem esse cruzamento a crítica de amanhã rediscute defeito fechado.

### Próximo passo

Operador testa `install-agents --upgrade` no CodexBridge; depois `merge-to-main.sh` e
decisão sobre push e sobre a reescrita de histórico.

## [2026-08-04] WK-20260804-review-findings - ready-for-review

- branch: `development`; `main` intocada; sem push

### Estado

- Cinco achados da revisão fechados: URL do provedor exige https (http só em
  loopback), redirect cross-host com credencial recusado, tarball sem checksum
  conhecido agora **recusa** em vez de avisar (`--allow-unverified` aceita de
  propósito), arquivo com vários diretórios de topo vira erro, `try/except` morto
  do `remove_agents` removido, e o `main()` de 583 linhas virou tabela de despacho
  (26 linhas) com dois testes segurando a forma.
- Este repo saiu do layout antigo: readiness files de `.docs/` para `docs/`,
  referências atualizadas, codemap regenerado.

### Validação e pendências

- 296 testes. Dois FAIL pré-existentes e não tocados no `doctor` deste checkout:
  `docs/architecture.md` citado em required-reading mas inexistente, e identidade
  de host não configurada.
- **Reescrita de histórico não executada.** Backup verificado em
  `scratchpad/governancekit-pre-rewrite-20260804.bundle` ("records a complete
  history"). Motivo da parada: este checkout é um *worktree* de
  `AI/GovernanceKit/.git`, que tem outros três worktrees vivos com trabalho não
  mesclado (`uc-008`, `uc-010`, `uc-011`). Reescrever o object store invalidaria os
  quatro, além de exigir force-push num repo publicado — e não há segredo em jogo,
  só placeholders.

### Próximo passo

Decidir a reescrita de histórico (4 worktrees + force-push) ou arquivá-la.

## [2026-08-04] WK-20260804-wa-hub-and-context-authoring - ready-for-review

- branch: `development`; `main` intocada; sem push

### Estado

- wa-hub desacoplado: `scripts/notify-nexo.sh` e `scripts/governancekit.env.example`
  removidos (ninguém os chamava). Nenhuma credencial real esteve no histórico — só
  placeholders `[WA_HUB_KEY]`/`[WA_HUB_DEST]`, então não há rotação a fazer.
- `doctor` lia o flag de prontidão por substring e casava a prosa do próprio template
  (`set \`limits_ready: yes\` only after…`), reportando PASS sobre arquivo com `no`.
  Agora ancorado na LINHA de metadata, como o instalador shell sempre fez.
- Novo `governancekit author-context`: classifica cada documento
  (absent/template/authored/ready), RASCUNHA os não escritos com o LLM do projeto,
  REVISA os escritos pelo operador sem reescrevê-los, e só move o flag para `yes`
  na confirmação do operador. Sem README/DESCRIPTION, explica por que vale escrever
  um antes e para.
- `agent_scope`: extraídos `request_completion()` e `read_confined_sources()` — um
  único caminho endurecido para o provedor.

### Validação e pendências

- 285 testes. Pacote reinstalado. Fluxo exercido em alvos temporários nos três
  estados (template→draft, authored→review, sem provider→erro acionável).
- Pendente de decisão do operador: reescrita de histórico para apagar as referências
  wa-hub das 8 tags publicadas — quebra os sha256 fixados em `KNOWN_TARBALL_SHA256`.
- Este repo ainda está no layout antigo (`.docs/limits.md`); a migração reversa só
  roda no `--upgrade`.

### Próximo passo

Decidir a reescrita de histórico; testar `install-agents --upgrade` no CodexBridge.

## [2026-08-04] WK-20260804-home-shadow-and-ownership - ready-for-review

- work_id: WK-20260804-refuse-home-root, WK-20260804-readiness-files-are-project-owned,
  WK-20260804-session-memory-stays-in-development
- branch: `development` (three feature branches merged; `main` untouched)

### Estado

- `assert_governable_root()` recusa `$HOME`, qualquer ancestral dele e a raiz do
  filesystem, chamada em `cli.main()` antes do dispatch. Antecedente: um kit
  instalado em `$HOME` sombreava todo projeto abaixo, para seis ferramentas.
- `docs/software-overview.md` e `docs/limits.md` voltaram a ser project-owned:
  `_KIT_SEED_PATHS` vazio, ambos em `_PROJECT_SEED_PATHS`, `_LEGACY_KIT_DOC_NAMES`
  não os varre mais, e `_migrate_readiness_files_to_docs()` traz de volta os alvos
  já em `.docs/` (move, remove symlink, ou preserva em `.gk/readiness-migration/`).
- `_SESSION_MEMORY_TEMPLATES` faz `handoff.md` e `docs/napkin-lessons.md` serem
  semeados de template vazio — o instalador copiava a memória do próprio kit.
- `scripts/merge-to-main.sh` + `docs/project-rules.md`: trabalho parte e retorna a
  `development`; `docs/issues/`, `docs/napkin-lessons.md` e `handoff.md` nunca vão
  para `main`.

### Validação e pendências

- Suíte: 266 passed. Pacote reinstalado (`pip install --user`), trava e layout novo
  ativos no binário.
- `merge-to-main.sh` validado em clone descartável: primeiro merge e segundo merge
  (com conflito modify/delete) resolvem por remoção; produto chega, `development`
  intacto. **A `main` real não foi tocada** — aguarda o teste do operador.
- Sem push em nenhum repo.

### Próximo passo

Operador testa `governancekit install-agents --upgrade` no CodexBridge; depois,
`scripts/merge-to-main.sh` nos dois repos e decisão sobre push.

## Current Status

- work_id: GH-6-simplified-adoption
- branch: `main`
- status: published and installed locally; session closed.
- delivered: interactive `install-agents` now builds a deterministic proposal
  first, names the configured `provider / model`, and asks before any API scope
  analysis. Declining keeps LLM enrichment off; quick and non-interactive paths
  remain deterministic. The command prints the GovernanceKit version before
  installation prompts. Provider errors name the configured provider/model,
  avoiding the misleading “selected agent” attribution.
- security: no credential value, endpoint response body, or project content is
  logged; existing protected-reference handling remains unchanged.
- delivered next: before upgrade drift or adoption discovery begins, the CLI
  announces that a large project may take several minutes; accepted LLM
  enrichment announces the configured provider/model and the 90-second bound.
- delivered next: discovery emits each scanned first-level directory and prunes
  nested Git repositories and linked worktrees before reading their source.
- delivered next: an LLM response rejected for invalid evidence is a highlighted
  operator warning, not an item hidden in an unresolved comma-list. It identifies
  provider/model, expected `path: reason` evidence, and the safe `n` action.
- published: merge commits `3f96377`, `c9e277f`, and `e3f771c` integrated the
  consent/version, visible bounded discovery, and actionable LLM-warning changes;
  `origin/main` is synchronized and the local package was reinstalled.
- validation: `PYTHONPATH=. pytest -q` → 247 passed; `git diff --check` passed.
- next: run one real interactive upgrade on a large consumer checkout and review
  the visible scan, the optional LLM prompt, and any operator warning before
  starting the remaining adoption-epic work.

- work_id: GH-6-simplified-adoption
- branch: `feature/uc-011/simplified-adoption-flow`
- status: first implementation stage complete; proposal/apply core pending commit.
- delivered: normal `install-agents` now produces a consolidated, evidence-based
  adoption proposal. `--quick` applies generated docs, `--review` is interactive,
  `--advanced` retains config-session, and CI requires `--non-interactive
  --accept-generated`. Existing ready project documents are never overwritten.
- validation: `PYTHONPATH=. pytest -q` → 238 passed, 1 skipped.
- delivered next: help raiz reorganizado em "Start here" e "Advanced commands";
  comandos avançados continuam disponíveis e apontam para sua ajuda específica.
- delivered next: upgrades com configuração aceita agora detectam frameworks,
  linguagens e gerenciadores novos como drift consultivo, sem reescrever política.
- validation: `PYTHONPATH=. pytest -q` → 239 passed, 1 skipped.
- delivered next: a proposta unificada usa o provider primário configurado, quando
  disponível, por meio do adaptador read-only já validado. Resumo, domínios e
  evidências viram proposta; falha de provider é pendência e não bloqueia adoção.
- validation: `PYTHONPATH=. pytest -q` → 240 passed, 1 skipped.
- next: add provider-backed proposal enrichment and upgrade/drift coverage before
  closing GitHub #6.

- work_id: GH-5-remove-agents
- branch: `feature/uc-010/remove-agents-safe-plan`
- status: LLM-assisted extraction complete; pending commit, push, and GitHub close.
- delivered: `remove-agents plan` inventories only safe regular files below the
  selected root and writes `.gk/remove-agents-plan.json`; `apply` deletes only
  manifest-hash-identical, unreferenced files after a per-file backup and restore
  manifest. Modified, unknown, referenced, and symlink paths are preserved.
- validation: `PYTHONPATH=. pytest -q` → 236 passed.
- delivered next: `remove-agents plan --with-llm` sends only a modified, unreferenced
  candidate to the configured primary provider and records a structured split. Apply
  requires `--accept-project-extractions`, writes operator-owned content under
  `docs/project-rules/ai-agents-extracted/`, updates required reading, replaces the
  kit file with its proposed reusable remainder, and backs up the original first.
- validation: `PYTHONPATH=. pytest -q` → 237 passed.
- next: commit and push this branch, then close GitHub #5; start #6 separately.

- work_id: WK-20260729-secure-project-adoption
- work_id: WK-20260729-secure-project-adoption
- branch: `feature/project-scope-conversation`
- status: core interview implementation committed for review; epic remains in progress.
- scope: secure, localized conversational project adoption after `install-agents`,
  `install-agents --upgrade`, and interactive configuration sessions.
- evidence: a real CodexBridgeMobile upgrade produced a useful domain proposal in
  English under a PT-BR operational environment, then ended with an ambiguous
  `Domains (comma-separated...)` prompt. The epic makes locale precedence and
  explicit accept/edit/merge/discard decisions contractual.
- follow-up evidence: after completing domains and capabilities, the provider
  prompt accepted `openai:::general` without explaining that `general` is not a
  valid routing role. It failed only at the end and offered no local retry.
  Task 007 now requires guided provider collection, explanation/example/spacing,
  immediate validation, and resumable progress without secrets.
- delivered: operational locale, guided PT-BR/EN/ES prompts with visual spacing,
  in-place provider validation, saved/pending defaults, provider purpose/role,
  root-confined source selection, isolated temporary agent workspace, strict
  proposal validation, and Unicode-safe issue slugs.
- validation: GovernanceKit `pytest -q` -> 184 passed; AI-Agents
  `scripts/run-checks.sh` passed. Critical-review revision isolated the agent
  workspace from the full project root.
- remaining: durable mid-interview draft recovery, provider validation before
  scope-agent invocation, and dependency/sensitivity metadata remain open tasks;
  do not close the epic from this commit.
- next: test the interactive upgrade against CodexBridgeMobile before closing
  the remaining tasks.

## Prior Status

- work_id: WK-20260727-restore-landing
- status: finished
- Public landing uses EDortta links and restored Pix, ETH, and Ko-fi values.
- Reusable README/templates keep placeholders. Package version is 0.2.2.

## Prior Status


- work_id: WK-20260727-context-hardening
- branch: `feature/uc-007/context-hardening`
- status: finished
- delivered: honest tokenizer estimate metadata; semantic task/risk categories;
  enforced reserve; declared-order emission; required retrieval failure; weighted
  lexical ranking; containment; inspect diagnostics; timestamp/prune telemetry;
  `governancekit --version` with nearest-project version and upgrade indication.
- validation: 136 pytest PASS; real AI-Agents context 19,221 / 21,000 usable;
  AI-Agents gate PASS.
- not validated: three-project benchmark because only AI-Agents currently carries
  the compatible v1.1.3 context manifest.
- compatibility: Amazon Q Developer adapter added to installer; both landing pages
  now describe the shared, upgrade-protected mandatory context.

## Prior Status


- work_id: WK-20260727-context-optimization
- date: 2026-07-27
- branch: `feature/uc-006/context-optimization`
- status: finished
- summary: Added schema validation, deterministic task/risk selection,
  `full`/`sections`/lexical `retrieve`, token-counter injection, hard budgets,
  provenance, duplicate reporting, stable JSON, and metadata-only JSONL.
- validation: `python3 -m pytest -q` -> 125 passed; real AI-Agents manifest inspected
  at 19,692 / 22,000 exact tokens for implementation + runtime; JSON build parsed.
- not validated: third-party agent integrations.
- next: no implementation action remains; merge/push authorized. Release and deploy
  remain separate gated actions.
- release follow-up: AI-Agents `v1.1.2` published; GovernanceKit default installer
  ref and verified tarball SHA-256 updated to that immutable tag.
- published-ref install validated in a temporary target; manifest, schemas,
  context documentation, and telemetry ignore rule were present.

## Prior Status

- work_id: WK-20260717-doctor-false-positives
- date: 2026-07-20
- branch: `main` (mergeada e pushada — `origin/main` = `06ee872`)
- status: Épico `004-doctor-false-positives-[finished]` fechado. Duas tasks, ambas
  `[finished]`, na `main` e no GitHub.

### O que foi feito

Descoberto em uso real (`governancekit doctor` sobre `Lucedata/AcheiVc`, 2026-07-17):
o doctor produzia FAILs/HINTs falsos que treinam o operador a ignorar a saída, e aí
o sinal real se perde no ruído.

- **Task 001** — `.example` não é segredo. `_check_tracked_secret_files` reprovava
  `.env.example` e os `.credentials/*.example`/`README*` que o próprio AI-Agents
  distribui — o doctor reprovava o kit-fonte. Fix: `_is_secret_template()`, exclusão
  por sufixo de template, espelhando `run-checks.sh` §4 do gêmeo. `.env.local`/
  `.env.production` (SEC-0221) continuam reprovando.
- **Task 002** — advisory scan varria gitignored e descia em submódulo (4 dos 15
  hits do AcheiVc eram `main.dart.js` do Flutter). Fix pontual, **sem walker novo**:
  `_iter_source_files` pula subdir com `.git`; `_git_ignored_paths` filtra via
  `git check-ignore -z --stdin` (fail-open, §6). No AcheiVc: **15 → 7 hits**, os
  `shell injection` reais e um `weak password hash` antes afogado passaram a aparecer.

### Validação

`python3 -m pytest tests/` → **100 passed** (87 originais + 13 novos). Gêmeo
AI-Agents intocado (`run-checks.sh` verde).

### Aberto / próximo

- **`walk.py` do épico do arnês** (`WK-20260717-harness-generation`, ainda não
  aberto) deve **converter e deletar** `_iter_source_files` + `_git_ignored_paths`
  para o seam `Ignorer` compartilhado — os 4 walkers do pacote (`codemap.py:190`,
  `doctor.py` ×2, `configure.py:138`) continuam duplicados, com `SKIP_DIRS`/
  `_CODEMAP_SKIP` **já divergentes**. Este fix é conversão futura (§7), não
  coexistência.
- **AcheiVc** não recebeu o kit ainda — o operador vai testar `install-agents
  --upgrade` lá por conta própria (repo em layout legado `docs/`, 27 arquivos
  pendentes → limpar antes; a migração move `docs/` → `.docs/` com backup).

---

## Current Status (histórico)

- work_id: WK-20260702-per-host-identity-runtime
- date: 2026-07-02
- branch: (working tree — not committed)
- status: Per-host identity runtime implemented and validated (65 tests green),
  pending review/commit. Issue moved to `[review]`. Companion AI-Agents contract
  issue still `[draft]` (separate epic).

## Summary (2026-07-02, per-host identity)

Added runtime collection + enforcement of per-host/instance identity. New module
`governancekit/identity.py` persists `operator_name`, `host_id`, `instance_path`,
`sibling_path`, `assigned_ports`, `branch_ownership` to a gitignored per-instance
file `.governancekit-identity.json` (no secrets). `configure` collects the fields
(interactive prompts + `--operator-name/--host-id/--instance-path/--sibling-path/
--assigned-ports/--branch-ownership` flags), refuses to save while a required field
(operator_name/host_id/instance_path) is missing, and auto-adds the file to
`.gitignore`. `doctor` gained a MANDATORY `host identity` gate (`[FAIL]` /
`ok:false` when missing or incomplete) and an advisory `sibling branch` same-branch
guard. `resume` shows active `operator@host` + git branch and warns on sibling
collision. Field names align with the AI-Agents companion contract issue. Tests:
`test_configure.py` (identity collection), `test_doctor.py` (pass/fail on
presence/absence/incomplete), `test_resume.py` (display + missing warning).

### Next Steps (per-host identity)

- Review the working-tree diff; commit if accepted (do NOT deploy — gated step).
- Implement companion AI-Agents contract issue (`mandate-per-host-programmer-identity`).

## Prior Status (WK-20260701-dotdocs-kit-layout)

- branch: feature/WK-20260701-dotdocs-kit-layout
- status: AI-GovernanceKit side implemented and validated, pending
  review/commit. AI-Agents side scaffolded as epic (not yet implemented).

## Summary

Moved the kit out of `docs/` into `.docs/`, freeing `docs/` to be 100% the host
project's. Resolves three operator concerns: (1) legacy projects that already used
`docs/` are no longer invaded; (2) ownership is unambiguous (kit = `.docs/`, project
= `docs/`); (3) tracking kit docs in git is now a prompted, persisted choice.

Key mechanics in `governancekit/install_agents.py`:
- `_dest_rel()` maps source `docs/…` → dest `.docs/…` for kit docs, keeping
  project-owned seeds (`required-reading.md`, `napkin-lessons.md`) in `docs/`.
  Resilient even if the AI-Agents source repo still uses `docs/`.
- `_FRESH_PATHS` replaces the wholesale `docs` copy with explicit kit paths, so a
  new project never inherits the source repo's active issues/project docs.
- `_migrate_legacy_layout()` (run before `--upgrade`/`--docs-only`) moves kit docs
  `docs/*` → `.docs/`, promotes `docs/project/*` → `docs/`, backs up to
  `.docs-migration-bak/`, reports collisions, idempotent (no-op once `.docs/` exists).
- `_resolve_track_kit_docs()` + `.governancekit` config: CLI flag → config → prompt
  → default (untracked). `.gitignore` emits a single `.docs/` entry (or omits it when
  tracking); secrets (`.credentials`, `handoff.md`) stay ignored regardless.

This repo migrated in place (`git mv` docs → .docs; `docs/project/README.md` →
`docs/README.md`). Doctor readiness checks now read `.docs/`.

## Next Steps

- Review the diff; commit if accepted (do NOT deploy — separate gated step).
- Implement the twin AI-Agents epic `docs/issues/002-dotdocs-kit-layout-[draft]/`
  (restructure source to `.docs/`, update `install-agents-kit.sh` + migration,
  update AGENTS.md/CLAUDE.md/READMEs). Coordinate merges so installer and source
  don't diverge.

## Blockers / Risks

- Cross-repo: AI-Agents source still uses `docs/`. `_dest_rel` mapping makes this
  non-blocking, but the source should be restructured for consistency.
- Legacy migration validated by unit test, not a full network end-to-end install.
- `install-agents-kit.sh` (AI-Agents shell mirror) NOT yet updated — tracked as
  task 002 in the AI-Agents epic.

## Files Changed

AI-GovernanceKit:
- `governancekit/install_agents.py` — `.docs/` layout, `_dest_rel`, legacy migration,
  track-kit-docs prompt/config, `_FRESH_PATHS`/`_UPGRADE_PATHS` rework
- `governancekit/cli.py` — `--track`/`--no-track` group, migration/gitignore output
- `governancekit/doctor.py` — readiness checks read `.docs/`
- `AGENTS.md`, `README.md`, `docs/required-reading.md`, `docs/README.md`,
  `docs/napkin-lessons.md`, `.docs/software-overview.md`, `.docs/agents/README.md`
- moved: `docs/{agents,workflows,software-overview.md,limits.md,issues/templates}`
  → `.docs/…`; `docs/project/README.md` → `docs/README.md`
- `tests/test_install_agents.py`, `tests/test_doctor.py`

Issue 002 (installer ↔ source alignment) — IMPLEMENTED (pending review):
- `governancekit/install_agents.py` — new `_resolve_src()` reads kit docs from the
  source's `.docs/` (restructured source, AI-Agents commit 6a5e6ba) with fallback to
  `docs/` (legacy source); project seeds always from `docs/`. Wired into
  `_do_fresh`/`_do_upgrade`. Folder renamed `002-…-[draft]` → `[review]`.
- `tests/test_install_agents.py` — +2 tests (57 total, green).

WhatsApp notification (wa-hub / Nexo):
- `scripts/notify-nexo.sh` (new) — sends an operator DM as "*GovernanceKit* —"
  (identity via text signature; ensureSenderTag idempotent, no alias hijack).
  Config in `~/.config/wa-hub/governancekit.env` (0600, local-only) — currently an
  INTERIM shared key; proper provisioning requested in wa-hub issue 014.
- Completion DM sent (id 3EB06519843829755B7736).

Landing / docs pages:
- `docs/index.html` — new trilingual (PT/ES/EN) "Novidades / What's new" band for a
  semi-technical audience (benefit-first), nav link `#whatsnew`, button → melhorias.html
- `docs/melhorias.html` (new) — beautiful technical backlog page: what/why/how/impact/
  migration/roadmap, with a docs/ → .docs/ directory-diff signature. Reuses the brand
  tokens (Uruguay palette, Fraunces/Inter/JetBrains Mono). The roadmap has a "outras
  coisas" placeholder to extend. NOTE: mirror/link from the AI-Agents index later.

AI-Agents (source kit) — scaffolded, not implemented:
- `docs/issues/002-dotdocs-kit-layout-[draft]/` (epic + 3 tasks)

## Checks / Tests Executed

- `python3 -m pytest -q` -> PASS, 55 tests.
- Local integration (no network): `_do_fresh` + `_ensure_project_docs` on a fake
  source -> kit in `.docs/`, project files in `docs/`, readiness flag reset,
  `.gitignore` emits single `.docs/`.
- Legacy migration covered by `test_migrate_legacy_layout_moves_kit_and_promotes_project`.

## Security Impact

- mitigated security impact
- Secrets (`.credentials`, `handoff.md`) remain in the managed `.gitignore` section
  regardless of the track-kit-docs choice — verified by regression test.
- `.governancekit` stores only the boolean track preference; no secrets.

## Model / Migration Changes

- No DB/model migrations. Repo-layout migration only (docs → .docs), reversible via
  `.docs-migration-bak/` when the installer performs it on legacy projects.
