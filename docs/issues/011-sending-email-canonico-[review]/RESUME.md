# RESUME — §Sending Email canônica (GK gh-7 / AI-Agents gh-5)

- work_id: WK-20260810-sending-email-canonico
- date: 2026-08-10
- status: `[review]` — duas rodadas de concílio. Dos 16 achados da rodada 2, **8
  fechados** por decisão do operador em 2026-08-10 (R2-1, R2-3, R2-4, R2-5, R2-6, R2-7,
  R2-12, R2-13, R2-14, R2-19); **6 em aberto**. `v1.2.0` publicada e a cadeia verificada
  ponta a ponta num alvo real.

## Next Step (DO THIS FIRST)

**Nenhum achado da rodada 2 continua aberto.** O que falta é decisão do operador: o
gate de concílio do commit de entrega do R2-16' (ver abaixo) e o item 4 do escopo.

> As duas linhas que este bloco trazia até 2026-08-12 — "decidir se `development` vai
> para `main`" e "Restam 5" — estavam vencidas há um dia. `main` recebeu
> `development` em `2767b4b`; `origin/main` está nesse commit, e `development` está à
> frente de `origin/development` pelo trabalho desta sessão, que **não** foi empurrado.
> E `711f853` fechou quatro dos cinco em 2026-08-11 sem passar por aqui. Um RESUME que
> lista como aberto o que já foi fechado custa o mesmo que uma contagem inventada:
> a próxima sessão planeja a partir dele. Corrigido, com o histórico à vista.
>
> A primeira redação desta correção dizia que as duas branches estavam "empurradas e em
> dia com `origin`" — escrito no commit que as deixava divergentes. O claim auditor do
> concílio pegou. Um parágrafo cuja tese é "não afirme estado sem olhar" afirmou estado
> sem olhar.

Fechados desde a última escrita deste arquivo:

- **R2-18** em 2026-08-11 (`b1c46ea`): gate de deriva entre os dois kits, com snapshot
  derivado do tarball verificado e asserções offline, cada direção verificada por
  mutação. Ver `docs/issues/013-kit-drift-gate-[finished]/`.
- **R2-2, R2-15, R2-16 (`configure`) e R2-11** em 2026-08-11 (`711f853`). **R2-17** foi
  reportado como NÃO reproduzível e não "consertado": os três callers de `_is_kit_owned`
  consomem o mesmo dicionário `cited_by`, cujas chaves são construídas com `.as_posix()`
  em `doctor.py:1222`. (A redação anterior dizia "o único caller … `doctor.py:1125`";
  são três callers e aquela linha é outra coisa. A substância se sustenta, a citação
  não — corrigido depois do concílio, que conferiu a citação em vez de acreditar nela.)
- **R2-16'** em 2026-08-12: o `_do_upgrade` deste runtime substituía todo arquivo de
  topo com um `shutil.copy2` nu — sem hash-check, sem stash, sem cópia de segurança —
  enquanto o instalador **shell**, que é a outra implementação do mesmo contrato e a
  que o kit deposita em todo alvo, protege o `AGENTS.md` desde 2026-07-23. Agora o
  runtime aplica a mesma tabela de decisão, e a paridade entre as duas listas é
  asserção lida do release pinado (`protected_root_files` no `_kit_snapshot.json`),
  não comentário. Verificado no elo 4: alvo real, `AGENTS.md` com regra de projeto,
  **dois** ciclos de `--upgrade` — o arquivo sobrevive aos dois e o manifesto nunca
  aprende o hash da versão do projeto, que é a poison que só aparece no segundo.
  Transcrição em `elo4-verificacao.md`, ao lado deste arquivo — a rodada anterior
  afirmou "verificado no elo 4" e não deixou artefato nenhum, e o concílio cobrou.

## Concílio — 2026-08-12, quatro lentes

**Levantados: 16 achados distintos + 12 perguntas. Sobreviveram ao §2: 16. Viraram
teste: 15. Aceitação de risco escrita: 1. Perguntas em aberto: 12.**

Lentes, selecionadas pelo §5 contra o *Target Project Checklist*: as três padrão
(*sweep skeptic*, *claim auditor*, *second caller*) mais **the migrator**, porque a
pergunta "cliente e servidor podem subir em qualquer ordem? há passo humano?" tem duas
respostas sim — o parque atualiza quando quer, e o merge do `.kit-new` é manual.

Todos os 16 foram **reproduzidos**, nenhum sobreviveu por concordância. O que a rodada
mostrou, em uma frase: **portei a tabela de decisão do instalador shell e não portei a
ordem em que ele a executa.**

| achado | o que era |
|---|---|
| SWEEP-2 / CALLER-3 / MIGR-1 / MIGR-5 | o alvo é comparado renderizado contra uma fonte crua. Alvo sem entrada no manifesto virava deriva falsa **permanente**; `configure` congelava o `AGENTS.md` para sempre; e o `.kit-new` que a mensagem manda mesclar saía com `{{OPERATOR_NAME}}` cru — segui-la reprovava o `doctor` |
| SWEEP-1 | a regra "arquivo mantido fica fora do manifesto" valia para arquivo de topo e não para arquivo de projeto dentro de pasta do kit: upgrade #1 preservava e anunciava, `_write_state` gravava no manifesto **rastreado**, upgrade #2 apagava em silêncio |
| SWEEP-3 | o `.kit-new` sobrevivia à de-adoção e, sendo cópia fiel de um contrato do kit, virava "citador" de todo caminho do kit — cada um passava de `remove` a `preserve` com a evidência falsa "hash difere do registrado" |
| CALLER-1 / MIGR-2 | o `.gk/.gitignore` é reescrito inteiro a cada run e perdia o `pre-migrate/` do shell — o backup dos contratos do projeto ficava a um `git add -A` de ser commitado |
| CALLER-2 / MIGR-4 | o `.gk/pre-upgrade/` nunca era limpo (o shell limpa a cada upgrade) nem anunciado: seguro que ninguém sabe que existe, e que o segundo upgrade sobrescreve |
| CALLER-4 / CLAIM-2 | o comentário que justificava o silêncio no caso "nenhum portador" era **falso** — o `AI-Agents manifest` só confere presença; ninguém reportava |
| CALLER-5 / MIGR-3 / MIGR-7 | severidade e remédio: o check era STOP incondicional onde o shell é opt-in (`--strict`); mandava rodar `--upgrade` prometendo um reparo que ele não faz; e, em alvo com migração pendente, nomeava um comando que estoura com `RuntimeError` |
| MIGR-6 | o shell avisa que o arquivo mantido ainda prescreve o transporte **retirado**; a CLI Python dizia só "o projeto mantém o contrato antigo" |
| CLAIM-1 | nenhum dos testes do item 4 passava pelo `run_doctor`: desregistrar o check deixava a suíte verde |
| CLAIM-3 / CLAIM-4 | duas afirmações minhas neste RESUME sem artefato: o estado de `origin` e a citação do R2-17 |

### Aceitação de risco escrita — SWEEP-4

`_do_fresh --force` continua apagando um `AGENTS.md` editado, sem `.kit-new`, sem cópia
em `.gk/pre-upgrade/` e sem aviso. **Não corrigido, deliberadamente:** `--force` é
documentado como "overwrite existing kit files", é o modo que o operador escolhe quando
quer reinstalar em vez de atualizar, e o instalador shell faz `rm -rf` no mesmo caso —
mudar um lado só recriaria a divergência que esta entrega existe para fechar. O
comentário do `_PROTECTED_FILES`, que afirmava a proteção sem qualificar o modo, foi
estreitado para `--upgrade`. Fechar isto de verdade é uma entrega nos **dois**
repositórios, com release do AI-Agents, e é decisão do operador.

## Concílio — rodada 2, duas lentes

**Levantados: 9. Sobreviveram ao §2: 9. Viraram teste: 9 (todos verificados por
mutação). Perguntas em aberto: 7.** Dez fechamentos da rodada 1 foram confirmados por
execução, não por leitura.

**Três dos nove eram regressões das minhas próprias correções**, e é o argumento inteiro
para a segunda rodada existir:

- **R2U-1 (segurança).** O `_prerender_source` montava a tabela de tokens com **toda**
  chave do estado, sem filtro, e substituía em sequência no mesmo buffer. Um valor
  guardado que *contém* um token era expandido pela passada seguinte: com
  `ORG_NAME = "{{PIX_PAYLOAD}}"` no `manifest.json` — a metade que a equipe **compartilha
  e commita** — o segredo local da vítima entrava num arquivo do kit e, com `--track`,
  ficava a um `git add` do repositório. Agora é uma varredura única de regex, filtrada
  aos placeholders declarados, com teto de tamanho. Não era alcançável no release
  pinado; estava a um placeholder compartilhável de ser.
- **R2F-1.** Renderizar a fonte fez o `.kit-new` passar a carregar o nome do operador,
  e ele não estava no `.gitignore`: o valor que o `_OPERATOR_PLACEHOLDERS` existe para
  manter fora do git ficava visível no `git status`. Antes da correção o arquivo saía
  com o placeholder e não vazava nada.
- **R2F-2.** Pus o `rmtree` do `.gk/pre-upgrade/` no topo do `_do_upgrade`, que serve os
  dois modos, então um `--docs-only` apagava os backups que um `--upgrade` completo
  acabara de fazer dos contratos de raiz — que ele nunca toca.

E três correções de julgamento:

- **R2F-3.** Eu tinha carvado uma exceção de severidade decidida por *substring*: bloqueia
  se o corpo "ainda prescreve" um transporte retirado. Substring não distingue prescrever
  de **proibir** — a lente produziu um projeto cuja seção BANE o helper retirado e que era
  bloqueado por dizer isso, com saída nenhuma além de apagar a própria proibição. É o
  quinto detector textual deste kit falhando como os quatro anteriores, na entrega cuja
  nota de design explica por que não escrever um. O check agora afirma só o que prova.
- **R2F-4.** O remédio prometia um `.kit-new` para o portador `.docs/workflows/sending-email.md`,
  que **não** é protegido: quem seguisse a instrução perdia a seção (o upgrade substitui e
  guarda a versão do projeto em `.gk/overwritten/`). A lente rodou o conselho e mediu a perda.
- **R2F-5.** A correção do `configure` era só para a frente: a população já configurada
  pelo `configure` antigo tem os arquivos renderizados, o scan não acha token nenhum, e
  nada era gravado. Agora um `--set` explícito é registrado mesmo sem token na árvore, que
  é o caminho de volta para essa população.

Mais **R2U-2** (o `_sync_dir` não tinha o short-circuit de identidade do `_replace_kit_file`,
então acusava o operador de ter editado à mão um arquivo que o próprio `configure` mudou, e
guardava um stash idêntico ao original), **R2U-3** (o `verify-elo4.sh` que eu entreguei
filtrava a saída de um jeito que mostrava um arquivo substituído sob o cabeçalho
"Preserved") e **R2U-4** (o remédio do check `host identity` nomeia um comando que, sem
TTY, sai 0 sem fazer nada — `configure && doctor` nunca terminava; agora nomeia as flags).

> **Os fechamentos da rodada 2 não foram auditados por concílio.** O §4 é explícito:
> duas rodadas, depois o operador, e não se roda uma terceira. Cada um tem teste
> vermelho sem a correção, e a verificação de ponta a ponta foi refeita no alvo real —
> mas ninguém além de mim olhou para eles.

### Aberto, com dono — e não é neste repositório

O `write_manifest` do `scripts/install-agents-kit.sh` pula os `DRIFTED` e **não** pula os
`PRESERVED`: o SWEEP-1 existe igual do lado shell, em release, e este repositório não
pode fechá-lo. É o espelho exato da lição de 2026-08-06 (a issue lida como fechada na
fonte enquanto o parque segue quebrado), então fica escrito aqui com o dono nomeado:
**AI-Agents**, e o elo é o `write_manifest`.

### Verificado no elo 4, não na fonte

`governancekit install-agents` num projeto novo, a partir da tag publicada:
`templates/` do projeto intacto e não reivindicado no manifesto, §Sending Email sem
transporte, índice do projeto e não do kit, `handoff.md` vazio, slot `SMTP_ACCOUNT`
ausente. É o que a lição de 2026-08-06 cobra: defeito que aparece em projeto governado
se verifica no projeto governado.

## Escopo da issue #7 — estado

| item | estado |
|---|---|
| 1. mesma seção nos dois kits, uma origem só | **fechado com gate** (2026-08-11). Era prosa pedindo "mude lá primeiro"; agora `tests/test_kit_drift.py` compara o digest do corpo aqui contra o da release pinada e fica vermelho se qualquer lado editar. |
| 2. remover `SMTP_ACCOUNT` do instalador | fechado. Fora do `_PLACEHOLDER_DESCRIPTIONS`; mantido no `_OPERATOR_PLACEHOLDERS` (verificado: removê-lo publica o valor legado no manifesto rastreado) e declarado em `_RETIRED_PLACEHOLDERS` (nunca perguntado, ainda substituído). |
| 3. reconciliar sintaxe de placeholder | fechado: `[OPERATOR_NAME]` → `{{OPERATOR_NAME}}`. |
| 4. o `doctor` audita a seção | **parcial.** Nenhum check audita a seção pelo nome. O que existe audita o índice para onde ela aponta e detecta contrato obsoleto que ainda a prescreve. É o único item do escopo que não fechou, e fechá-lo é decisão do operador: um check que lê a seção pelo nome é o quinto detector textual deste kit, e os quatro anteriores custaram um defeito de escopo cada. |

> Uma consequência do R2-16' cai exatamente aqui. O remédio que a mensagem do
> `local sources indexed` oferece ao alvo com contrato retirado — "adote a versão
> `.kit-new` ao lado, ou rode `install-agents --upgrade`" — pressupõe que arquivo
> protegido não é sobrescrito. Era verdade no instalador shell e falso neste runtime:
> quem seguisse o conselho pelo caminho Python perdia a edição em vez de recebê-la ao
> lado. O comentário do `doctor.py:1150` afirmava a garantia; nada a implementava
> aqui. Agora implementa.

## Council — rodada 1 (três lentes)

**Levantados: 16 (8 achados + 8 perguntas). Sobreviveram ao §2: 8. Viraram teste: 6.
Perguntas em aberto: 8.**

> Os números que este parágrafo trazia antes — "19 levantados, 19 sobreviveram, 11
> abertos" — eram inventados; nenhum dos três batia com o registro em `.gk/council/`.
> A rodada 2 pegou. §4 diz que este registro é o que substitui os palpites do contrato
> sobre gatilhos e número de membros: registro com número inventado calibra o próximo
> concílio em ficção.

O achado decisivo foi contra a própria correção: acrescentar `templates` ao
`_FRESH_PATHS`/`_UPGRADE_PATHS` **apaga a pasta `templates/` do projeto**. Três
camadas somadas — padrão nu no `.gitignore` (ignora em qualquer profundidade),
`rmtree` no `--force`, e poison do manifesto rastreado que faz o SEGUNDO upgrade
deletar os arquivos do projeto em silêncio, com o `remove-agents` depois planejando
removê-los a confiança 1.0. Revertido. E o motivo de ter acrescentado era falso: o
self-upgrade que ela consertaria já está bloqueado antes, porque o shell lê
`.credentials/identity.json` e o Python grava em `.gk/operator.json`.

Fechados com teste — **sete** testes novos, dos quais **seis** ficam vermelhos contra
`f17b302`. O sétimo, `test_a_retired_token_with_no_stored_value_is_not_reported_as_unknown`,
passa mesmo com o pacote inteiro revertido: ele guarda a propriedade, não a prova.
E de `f17b302`, dos oito testes que ela trouxe, seis ficam vermelhos; os dois que passam
nos dois lados são `test_a_genuinely_malformed_row_is_still_rejected` e
`test_an_ordinary_uncited_path_still_gets_the_indexing_hint` — guardas contra
correção-em-excesso. (A promessa de `c0a5c05` de que "o RESUME diz qual é qual" só passa
a ser verdade nesta linha.) Os seis mutação-verificados:
reversão do `templates` (lista + comportamento no `.gitignore`), token retirado ainda
substituído a partir do estado guardado, token retirado sem valor não vira "unknown",
e as três correções do `_WITHDRAWN_CITATIONS` — decidir por **quem cita** (arquivo do
kit vs do projeto), não dar `return` engolindo os outros caminhos, e não ficar calado
quando o caminho retirado está indexado.

Fechados sem teste: `docs/project-rules.md` citava `_SESSION_MEMORY_TEMPLATES`
(renomeado) e omitia a entrada nova.

## Aberto

1. **`DEFAULT_REF = v1.1.7`** e sem checksum de v1.1.8. Nada desta entrega chega a um
   usuário real antes de uma tag — e pior: num alvo instalado nesse ref, a dica nova
   do doctor manda rodar `--upgrade`, que reinstala o mesmo `AGENTS.md`. Conselho em
   laço, sem saída. **Aceitação de risco:** é lag de trabalho não lançado; a issue não
   fecha antes da tag, e a tag é decisão do operador.
2. **Os outros três worktrees deste repo** (`feature/uc-011/simplified-adoption-flow`,
   `uc-008`, `uc-010`) carregam a §Sending Email antiga — o `AGENTS.md:80` que a issue
   #7 cita por linha é o do adoption-flow. Merge de `development` resolve, mas o
   `uc-011` reintroduz o `_FRESH_PATHS` pré-correção se mesclar sem rebase.
3. **Sem gate de deriva entre os dois kits.** "Uma origem só" é prosa.
4. **`SMTP_DOMAIN`** continua no `_PLACEHOLDER_DESCRIPTIONS` e **fora** do
   `_OPERATOR_PLACEHOLDERS`: um valor guardado legado iria para o manifesto rastreado.
5. **Este repo não é alvo instalado** (`.gk/` só tem `council/`), então o
   `{{OPERATOR_NAME}}` do `AGENTS.md` nunca é renderizado e o check não-advisory
   `unfilled placeholders` reprova. Trocar `[...]` por `{{...}}` foi o certo pelo item
   3, mas deixou o `doctor` deste repo vermelho nesse check.
6. **A poison do manifesto** (`_write_state` varrendo o destino) é genérica, não é do
   `templates`: vale para qualquer arquivo do projeto dentro de `.docs/agents` etc.
7. **`CHANGELOG.md`** intocado; `[Unreleased]` vazio e a última entrada ainda cita
   v1.1.6.
8. O ramo morto `if seen_table_line and not found and not rejected` virou tripwire sem
   teste que o alcance.

## Council — rodada 2 (três lentes)

**Levantados: 35 (22 achados + 13 perguntas), 16 distintos depois de deduplicar.
Sobreviveram ao §2: 16. Fechados: 0. Abertos: 16.**

Pelo §4 a entrega para aqui: duas rodadas, depois o operador. Nada abaixo foi fechado.

### O grave — e não é neste repositório

**R2-1. O instalador shell tem o mesmo defeito de perda de dados, e sempre teve.**
`scripts/install-agents-kit.sh` do AI-Agents traz `templates` no `KIT_OWNED_PATHS`,
com `sync_dir "templates"` e `copy_path "templates"` — em `v1.1.7`, em `v1.1.8` e no
HEAD. O primeiro `--upgrade` instala o `templates/` do kit dentro do `templates/` do
projeto e grava os arquivos do projeto no `.gk/manifest.json`; o **segundo** apaga os
dois, em silêncio, sem backup. Reproduzido de ponta a ponta. Eu revertei essa entrada
do lado Python por causa dela — e o lado shell, que este instalador **deposita em todo
alvo**, nunca foi tocado. A reversão alcançou um dos dois instaladores.

**R2-2. O manifesto envenenado não tem reparo.** `_write_state(prune_missing=True)` só
descarta entrada cujo arquivo sumiu; os arquivos do projeto existem, então a entrada
sobrevive a todo upgrade. O `remove-agents` depois planeja removê-los como
`kit-owned-unchanged`, confiança 1.0, `requires_operator_review: false` — e o `apply`
remove. O `manifest.json` é a metade **rastreada** do estado: o veneno é commitado e
chega a todo clone. Atenuante honesto: `f17b302` nunca foi empurrado, então a população
vinda daqui pode ser vazia. A vinda do instalador shell (R2-1) não é.

### O que eu disse que tinha consertado e não consertei

**R2-3. `_RETIRED_PLACEHOLDERS` só chegou no `_fill_placeholders`.** O `configure.py`
ainda monta `_KNOWN_TOKENS` do `_PLACEHOLDER_DESCRIPTIONS`, então num alvo **sem valor
guardado** o `doctor` reprova NÃO-advisory mandando rodar `configure`, e o `configure`
ignora em silêncio. Pior: é **regressão** — antes desta entrega o `configure` conseguia
preencher. As três lentes acharam isso independentemente.

**R2-4.** O guard também não chegou ao relatório final: um upgrade não interativo com
outro token preenchido ainda imprime `Still unfilled (skipped): {{SMTP_ACCOUNT}}` —
exatamente o que o comentário da correção diz que não pode acontecer. O teste novo não
pega porque a fixture dele só tem o token retirado.

**R2-5.** `"blocked one step earlier anyway"` — a justificativa inteira para reverter em
vez de dar prefixo — é falsa num TTY: o `exit 8` é guardado por `if [[ ! -t 0 ]]`. Com
terminal, o instalador pergunta e o upgrade completa com exit 0.

**R2-6.** A correção "falha alto" do instalador shell não está em release nenhum
(`v1.1.7` e `v1.1.8` seguem com o `return 0` nu), então o comentário que reescrevi para
ser verdadeiro continua falso sobre o artefato que qualquer um obtém.

**R2-7.** E, mesmo no HEAD, o WARN é seguido sete linhas depois por
`preserved project-local: docs/required-reading.md` — sobre um arquivo que não existe.
O teste novo só grepa o WARN, então não vê a contradição.

### Registro e contagem — de novo

**R2-8.** Os números que este RESUME trazia da rodada 1 eram inventados (corrigidos
acima). **R2-9.** "Seis testes novos, todos vermelhos" — são sete, e um passa revertido.
**R2-10.** "O RESUME diz qual é qual" — não dizia; agora diz. **R2-11.** As entradas de
napkin não trazem nenhuma das quatro contagens que o §4 exige. **R2-12.** `f17b302`
disse "Suíte: 390 passando"; eram 388 passando + 2 skipped.

### Restantes

**R2-13.** Mensagem órfã: quando `unindexed` está vazio, o check devolve um texto que
começa em `SEPARATELY:` sem nada antes. **R2-14.** `cited.setdefault` grava o primeiro
citador, então um `AGENTS.md` legado mascara a declaração legítima do projeto e o
operador ouve "do NOT index those" sobre o transporte que ele mesmo declarou.
**R2-15.** No `DEFAULT_REF` o `_TEMPLATE_SEEDS` é no-op — `v1.1.7` não tem o template,
então alvo novo ainda recebe o `handoff.md` e o índice do próprio kit. **R2-16.** O
`configure` não persiste em `.gk/`, então o `--upgrade` seguinte desfaz o que ele fez.

Sem saída no remédio do `_WITHDRAWN_CITATIONS`: `.kit-new` **nunca** é escrito por este
instalador (só pelo shell), o `--upgrade` reinstala o contrato retirado porque nenhum
ref lançado tem a correção, e editar o `AGENTS.md` à mão é sobrescrito sem stash.

> **Superado em 2026-08-12** (o parágrafo acima é o registro da rodada 2 de 10/08 e fica
> como está). Este instalador **escreve** `.kit-new` desde o R2-16', editar o `AGENTS.md`
> à mão deixou de ser sobrescrito, e o remédio tem saída — nomeada pelo `doctor` e
> diferente por portador. O concílio de hoje cobrou a linha: um documento ativo que
> descreve o produto no passado é lido como se fosse o presente.
