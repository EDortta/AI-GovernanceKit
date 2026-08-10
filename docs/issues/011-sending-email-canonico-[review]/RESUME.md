# RESUME — §Sending Email canônica (GK gh-7 / AI-Agents gh-5)

- work_id: WK-20260810-sending-email-canonico
- date: 2026-08-10
- status: `[review]` — duas rodadas de concílio. Dos 16 achados da rodada 2, **8
  fechados** por decisão do operador em 2026-08-10 (R2-1, R2-3, R2-4, R2-5, R2-6, R2-7,
  R2-12, R2-13, R2-14, R2-19); **6 em aberto**. `v1.2.0` publicada e a cadeia verificada
  ponta a ponta num alvo real.

## Next Step (DO THIS FIRST)

Decidir se `development` deste repositório vai para `main` (hoje 45 commits atrás) e se
é empurrado. O AI-Agents já foi: `main` + `v1.2.0` publicadas.

Depois, os **6 achados restantes** da rodada 2: R2-2 (manifesto envenenado sem reparo),
R2-16' (`_do_upgrade` sobrescreve arquivo de topo sem hash-check nem stash), R2-15
(`configure` não persiste em `.gk/`), R2-11 (napkin sem as contagens do §4), R2-17
(`_is_kit_owned` sem `as_posix()`), R2-18 (sem gate de deriva entre os dois kits).

### Verificado no elo 4, não na fonte

`governancekit install-agents` num projeto novo, a partir da tag publicada:
`templates/` do projeto intacto e não reivindicado no manifesto, §Sending Email sem
transporte, índice do projeto e não do kit, `handoff.md` vazio, slot `SMTP_ACCOUNT`
ausente. É o que a lição de 2026-08-06 cobra: defeito que aparece em projeto governado
se verifica no projeto governado.

## Escopo da issue #7 — estado

| item | estado |
|---|---|
| 1. mesma seção nos dois kits, uma origem só | fechado no `AGENTS.md` deste repo, byte a byte igual ao corpo canônico do AI-Agents, mais uma nota de origem. **Sem gate de deriva** — é prosa que pede "mude lá primeiro". |
| 2. remover `SMTP_ACCOUNT` do instalador | fechado. Fora do `_PLACEHOLDER_DESCRIPTIONS`; mantido no `_OPERATOR_PLACEHOLDERS` (verificado: removê-lo publica o valor legado no manifesto rastreado) e declarado em `_RETIRED_PLACEHOLDERS` (nunca perguntado, ainda substituído). |
| 3. reconciliar sintaxe de placeholder | fechado: `[OPERATOR_NAME]` → `{{OPERATOR_NAME}}`. |
| 4. o `doctor` audita a seção | **parcial.** Nenhum check audita a seção pelo nome. O que existe audita o índice para onde ela aponta e detecta contrato obsoleto que ainda a prescreve. |

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
