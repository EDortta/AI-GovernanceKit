# RESUME — Auditoria dos fechamentos das duas rodadas 2 (AC-1..AC-19)

- work_id: WK-20260813-council-audit-of-r2-closures
- date: 2026-08-13
- status: `[draft]` — Fase 0 (AC-1, AC-2/3/4/5, AC-25, AC-28) commitada em `development`
  (`74bfefa`, `3effe89`, 0.3.1→0.3.2, 2026-08-14). Execução noturna **desarmada pelo
  operador** — ver seção abaixo. Fase 1 (`CONFIRM-TREE`, AC-13/20/21/22/28-emenda/29,
  o `manifest.override.json`) sem código implementado.
- origem: pedido do operador, 2026-08-13 — `council.md` §4 `[DEFAULT] Whenever the operator asks`

## O que aconteceu

Em 2026-08-12 rodaram duas rodadas 2 de concílio, registradas em
`.gk/council/ade371f5….json` (12:47, 9 achados, fechados em `c7b2838`) e
`.gk/council/6bb1027e….json` (17:26, 13 achados, fechados em `6116eba`).

O operador pediu que os **22 fechamentos** fossem auditados por críticos **diferentes**
das lentes originais. As lentes originais eram *the fix auditor* e *the adversarial user
/ the operator at 17:00*. As três desta passada, escolhidas pelo §5 e pelo operador:

- **the claim auditor** — qual fechamento afirma algo sem artefato atrás?
- **the sweep skeptic** — a correção foi num lugar só quando o padrão vive em vários?
- **the migrator** — o que acontece com alvos já processados sob o comportamento antigo?

## Isto não é uma rodada 3

`council.md` §4 proíbe terceira rodada sobre achado ainda aberto: depois da rodada 2,
vai ao operador. O que autoriza esta passada é um gatilho diferente — o pedido do
operador — e o destino dela é o mesmo: **os achados vêm para cá, escritos, e a decisão
de escopo é do operador.** Nenhum crítico modificou código (§1).

## Resultado

**8 dos 22 fechamentos se sustentam. 14 têm defeito. 19 achados sobreviveram ao §2.**

As quatro contagens que o §4 exige, desta passada:

| contagem | número |
|---|---|
| levantados | 21 (claim 6 · sweep 7 · migrator 8) |
| sobreviveram ao §2 | **19** (2 eram o mesmo defeito por caminhos diferentes) |
| viraram teste | **0** — o concílio não conserta; as 19 issues abaixo é que o farão |
| perguntas em aberto | 14 |

`viraram teste: 0` é o número honesto no momento em que esta épica abre, e está escrito
assim de propósito: a issue `AC-19` existe porque a rodada anterior escreveu
`viraram teste: 9` e `13` sem que o repositório sustentasse.

## Os fechamentos que se sustentam (8)

Verificados por mutação que derruba o teste nomeado. São o padrão do que um fechamento
deveria ser:

`ade371f5#3` FORBIDDEN não bloqueia · `ade371f5#6` substituição do kit não vira hand-edit ·
`6bb1027e#0` `presets()` sobrevive ao catálogo ilegível · `6bb1027e#2` `.pre-draft` mais
antigo vence · `6bb1027e#5` teste de wheel deixa de pular · `6bb1027e#7` `about_to_write` ·
`6bb1027e#8` veredito de readiness · `6bb1027e#10` a oferta não afirma que fontes sobem.

## As 19 issues

| id | fechamento auditado | o que caiu | grav. |
|---|---|---|---|
| AC-1 | `ade371f5#0` | `_fill_placeholders` ficou fora do endurecimento: o segredo local ainda entra | **crítica** |
| AC-2 | `6bb1027e#3` | `apply` filtra `kit-owned-unchanged`; o plano emite `kit-seeded-unchanged` | alta |
| AC-3 | `6bb1027e#3` | evidência "byte for byte" sem comparar bytes, com revisão dispensada | alta |
| AC-4 | `6bb1027e#3` | a asserção que protege o arquivo do operador está fora do `with`: teste morto | alta |
| AC-5 | `6bb1027e#3` | população legada nunca adquire `seeded_credentials` (forward-only) | alta |
| AC-6 | `6bb1027e#3` | o instalador shell v1.2.1 apaga `seeded_credentials` do manifesto | alta |
| AC-7 | `6bb1027e#4` | o gate roda o `governancekit` do site-packages e sai 0 | alta |
| AC-8 | `6bb1027e#11` | `classify_document` ficou sem a guarda de symlink que o irmão ganhou | alta |
| AC-9 | `ade371f5#4` | sem entrada de manifesto o remédio sobrescreve sem stash nenhum | alta |
| AC-10 | `ade371f5#1`+`6bb1027e#12` | o shell reescreve o bloco do `.gitignore` sem `*.kit-new`/`*.pre-draft` | alta |
| AC-11 | `ade371f5#2` | o teste prova o parâmetro, nunca a ligação com `--docs-only` | média |
| AC-12 | `ade371f5#2` | a primeira corrida da versão nova apaga backups da semântica antiga, em silêncio | média |
| AC-13 | `ade371f5#5` | o ramo de retorno antecipado persiste o preset inteiro no manifesto rastreado | média |
| AC-14 | `ade371f5#7` | o artefato regerado conta prosa como placeholder cru | média |
| AC-15 | `ade371f5#8` | o check irmão `unfilled placeholders` mantém o remédio que não funciona sem TTY | média |
| AC-16 | `6bb1027e#1` | "teste em três locales" assere só nomes de preset, que são invariantes | média |
| AC-17 | `6bb1027e#6` | os testes do check só leem `passed`, nunca `message` | média |
| AC-18 | `6bb1027e#9` | nenhum teste exercita o ramo de revisão do prompt de consentimento | média |
| AC-19 | ambos | `viraram teste: 9` e `13` na prosa, sem lastro no repositório | alta |

## As 14 perguntas em aberto

Não bloqueiam (§2), mas ficam escritas — é assim que o próximo concílio ganha lente:

1. `_CREDENTIALS_SCAFFOLDING` (8 nomes à mão) não entrou no `_kit_snapshot.json`, e o
   repositório já institucionalizou o gate para exatamente esse padrão
2. o comentário que justifica `_MAX_PLACEHOLDER_VALUE = 4096` com *"the longest declared
   slot is an e-mail address"* é falso — `PIX_QR_BASE64` é slot declarado
3. `council --record` não guarda as quatro contagens; elas só existem em prosa, que é
   onde as divergências de `AC-19` moram
4. correção de script fechada por reprodução fecha o achado e **não** protege contra
   recorrência — a distinção entre "fechado" e "protegido" precisa aparecer na contagem
5. `free_models()` faz `int(m["context_length"])` fora do `except CatalogError`: um
   catálogo de forma diferente vira `KeyError`
6. `_read_state` descarta `_OPERATOR_PLACEHOLDERS` do manifesto herdado — é a comporta
   que fecha a porta de saída de `AC-5`/`AC-13` para alvos pré-split
7. `TimeoutExpired` no `_build_wheel` é tratado como "pip indisponível: pula", e um build
   que RODOU e travou é um resultado, não uma ausência
8. `_collect_providers` só tem ramos pt-BR e inglês; `es` cai em inglês (anterior a esta
   entrega, mas dentro do escopo do "teste em três locales")
9. `.gk/context-proposal/` e `.gk/remove-agents-plan.json` não entram no bloco gerenciado
   do `.gitignore`, ao contrário dos quatro irmãos de backup
10. a mensagem do `.pre-draft` promete cópia incondicionalmente, e na segunda aceitação
    nenhuma cópia é tirada
11. `docs/…/elo4-verificacao.md` documenta 6 passos; o script ganhou um passo 7 em
    `6116eba` e o artefato não foi regerado
12. o docstring de `presets()` ainda diz *"Every value here now has an origin and a
    date"*, afirmação que o CHANGELOG de `6116eba` retratou
13. `docs/<doc>.md.pre-draft` mora em `docs/` e `_candidate_paths` nunca varre `docs/`:
    prosa do operador sobrevive à de-adoção, e ninguém decidiu isso por escrito
14. quantos alvos do parque estão hoje na combinação que `AC-6` descreve é pergunta para
    o operador, não para o repositório

## Como cada issue fecha

Decisão do operador em 2026-08-13: cada uma é resolvida e depois submetida a uma
**crítica de quatro céticos**, um deles com lente de **LGPD**, e volta à resolução até
passar. O `council.md` §2 continua valendo: cada fechamento sai com teste que fica
vermelho sem a correção, ou com aceitação de risco escrita. Nada de "fixed" sem um dos
dois — que é precisamente o defeito que `AC-19` registra.

## AC-1 — fechada em 2026-08-13

Quatro céticos (LGPD, fix auditor, second caller, migrator), **cinco rodadas**, todos
devolvendo `pass` na última. 24 subagentes.

O desenho caiu **cinco vezes** antes de assentar, e cada queda foi medida:
varredura única → o valor não pode carregar token → a saída não pode ter token novo
(comparava conjunto) → queda por arquivo (assimetria entre irmãos) → queda por corrida
(raio de explosão) → **queda por arquivo E por token**.

O congelamento de arquivo protegido (`ade371f5#6`) chegou por **três portas diferentes** —
por arquivo, por corrida, e por contabilidade. Da terceira vez, três lentes independentes
o acharam com reproduções diferentes, e era uma linha escrita duas vezes.

**A matriz de mutação apontou verde quatro vezes** onde eu supunha cobertura. Cada uma
virou teste. É `AC-11`/`AC-17`/`AC-18` acontecendo ao vivo: teste que existe não é teste
que morde.

**Uma retratação registrada**: o fix auditor retirou por escrito o próprio achado da
rodada 2 depois de verificar que tinha reprodução e não tinha gatilho.

Verificação: **571 passed**, mutação vermelha por propriedade e por escritor.

### As quatro contagens de AC-1, sem inflar

| contagem | número | como foi obtido |
|---|---|---|
| achados levantados pelos quatro céticos | 21 | soma dos relatórios das 5 rodadas |
| retratados pelo próprio autor | 1 | o fix auditor, por escrito |
| viraram issue própria em vez de correção | 4 | `AC-20`, `AC-21`, `AC-22`, e um anexado a `AC-18` |
| escalados ao operador, sem correção aqui | 1 | o quarto escritor, `AC-6`/`AC-10` |
| **testes novos, cada um com mutação vermelha** | **63** | `git diff` de `tests/` + `test_render_gate.py` |
| suíte | **508 → 571** | `pytest` antes e depois |
| perguntas em aberto | 6 | |

A linha que importa é a dos **63 testes**, e ela é derivada do diff, não digitada — os
outros números são contagens de relatório, que é tudo o que eles podem ser. A tentação de
escrever "18 acharam, 18 viraram teste" foi real e o número teria sido inventado: um
achado pode virar zero testes (escalado), ou vários (a cadeia de composição virou cinco).
Contar achados como se fossem testes é literalmente o defeito que `AC-19` registra, e
quase o cometi no registro da issue que o descobriu.

### Condição de release herdada por AC-1

Parecer da lente de LGPD, aceito na época: `AC-1` tirou o filtro por `found` do `--set`,
o que abre entrada nova de dado financeiro sem slot, e isso exigiria `AC-21` na mesma
release.

**Revogado em 2026-08-13 por `AC-24`, e por um motivo melhor.** A pergunta do operador
("nem tinha noção de que temos financeiro aqui dentro") levou à medição: dos onze slots
declarados, **dez não são usados por arquivo nenhum**, e os cinco de pagamento são
resíduo do commit `a228889` — que limpou os dados do autor da landing page e declarou os
tokens como preenchíveis. Não existe uso legítimo a preservar.

Some com os slots e a condição evapora: não há entrada de dado financeiro para reter.
`AC-21` volta a ser higiene de ciclo de vida de estado — necessária, e não mais um portão
de release de `AC-1`. A ordem passa a ser `AC-21` antes de `AC-24`, porque tirar os slots
exige **eliminar** o que já foi coletado, não só parar de perguntar.

A lição, que vale além destas issues: a resposta certa para "temos um problema de
retenção deste dado" era **"por que estamos coletando este dado?"**, e nenhuma das cinco
rodadas de crítica fez essa pergunta. O operador fez, na primeira vez que leu o assunto.

### Abertas e não bloqueantes

- o gate de CI lê a árvore local, não o ref pinado que `_download` busca (precisa do
  `_kit_snapshot.json` da épica `013`)
- valor guardado acima de 1 MiB ainda des-renderiza alvo já renderizado — aceitação de
  risco escrita, contra medição
- o quarto escritor (`apply_identity` no `install-agents-kit.sh`) segue sem nenhuma das
  três camadas: `AC-6`/`AC-10`, escaladas ao operador

## Grupo remove-agents (AC-3 → AC-2 → AC-4 → AC-5) — 2026-08-13

Primeiro grupo julgado em conjunto, com veredito **por issue**. Duas rodadas de crítica
fechadas, a terceira em confirmação.

### O mecanismo, que era um só para as quatro

`AC-3` pedia comparação de bytes, e o comentário do próprio código proíbe gravar digest de
`.credentials/` no manifesto rastreado — hash de token de baixa entropia é oráculo. Então
a referência veio do **pacote do kit**: `_kit_snapshot.json` passou a carregar os digests,
derivados dos tarballs verificados por checksum.

Isso fechou quatro coisas com um mecanismo:

- **`AC-3`** — a comparação existe, e a evidência corresponde ao que o ramo verificou;
- **`AC-5`** — **dissolveu**. Eu ia criar comando de reparo para gravar a chave em alvos
  legados. Não precisa: identidade de bytes é evidência mais forte que nome em lista, e o
  alvo legado tem os bytes no disco. A chave virou opcional;
- **pergunta 1 do RESUME** — `_CREDENTIALS_SCAFFOLDING`, oito nomes à mão sem gate,
  retirada em favor do snapshot derivado;
- **`AC-2`** — o `apply` decide por `action`, não por `classification`.

### O que a crítica derrubou, em duas rodadas

| rodada | achado | quem |
|---|---|---|
| 1 | o ramo semeado calculava `referenced` e **descartava** — apagava sem revisão | fix auditor |
| 1 | `current hash differs` impresso para arquivo cujo hash **bate** | second caller |
| 1 | `.credentials/.gitignore` — controle de acesso — apagado como documentação | LGPD |
| 1 | plano da versão anterior aplicado verbatim, com a evidência falsa que `AC-3` aboliu | migrator |
| 1 | bytes de release **anterior** não reconhecidos → arquivo do kit fica no disco | migrator |
| 1 | `_write_state` carimbava `[]` e destruía o reparo do legado um comando depois | second caller |
| 2 | o aviso de fail-closed impresso **uma vez por candidato** (75 blocos, 17 KB) | fix auditor + second caller |
| 2 | truncar o histórico de digests era **invisível** para a suíte inteira | migrator |

### As três lições, e nenhuma é sobre remove-agents

1. **Repeti um defeito que eu mesmo tinha nomeado.** A rodada 4 do `AC-1` gastou uma
   correção inteira eliminando aviso repetido, e o docstring que escrevi lá diz que a
   repetição *"trains the reader to skip exactly the block that matters"*. Horas depois
   introduzi o mesmo ruído em outro arquivo. Nomear um defeito não imuniza contra ele.
2. **Duas correções minhas se cancelaram.** Tolerar snapshot antigo (correção de um
   achado) fez o `SnapshotError` parar de disparar justamente no caso para o qual o aviso
   (correção de outro achado) tinha sido escrito. Corrigir dois achados sem checar a
   interação entre as correções é uma terceira classe de defeito.
3. **Mock esconde lacuna de dado.** Duas rodadas seguidas: os testes mockavam a tabela de
   digests, então provavam que *a comparação funciona* e nada sobre *a tabela estar
   completa*. A mutação que truncava o histórico ficou verde na suíte inteira.

### Números deriváveis

Suíte **576 → 595**. Mutações do grupo: 15, todas vermelhas ao fim das duas rodadas — e
**quatro apontaram verde** ao longo do caminho, cada uma expondo um teste que não fixava
nada (`PLAN_VERSION - 1` relativo, snapshot sem o campo, histórico truncado, contagem do
aviso).

### Aberto, e registrado como issue

`AC-25` (exfiltração da chave do operador ao provider por manifesto envenenado — a lente
de LGPD chamou de *"a coisa mais grave que encontrei em todo este concílio"*, e não é
bloqueante para este grupo, medido) e `AC-26` (o bloco gerenciado do `.gitignore` cita os
contratos de raiz, então a de-adoção nunca remove `AGENTS.md`).

### Fechado em 2026-08-13 — os quatro céticos passaram as quatro issues

Três rodadas de crítica, veredito por issue, `pass` unânime na terceira. **595 passed**
(era 508 no início da épica). Mutações do grupo: 19, todas vermelhas ao fim — e **cinco
apontaram verde** ao longo do caminho, cada uma expondo um teste que não fixava nada.

O fix auditor mediu o antes e o depois no mesmo alvo:

| | antes | depois |
|---|---|---|
| blocos de aviso | 75 | **1** |
| linhas | 224 | **2** |
| bytes | 17.475 | **129** |
| leituras do snapshot | 75 | **1** |

A pergunta que ele tinha deixado ao lado do achado — releituras por candidato — fechou
pelo mesmo movimento, *"que é o sinal de que a correção foi na causa e não no sintoma"*.

**Next:** `AC-25` pela gravidade, e o parecer do operador sobre a aposentadoria do bash — que funde `AC-6`+`AC-10` e reabre `AC-7`/`AC-14`
como porte para Python.



---

## Sessão encerrada 2026-08-13 — execução noturna armada

`scripts/run_plan.py` executa `PLANO-UNIFICADO.md` sem assistência. Idempotente, sobrevive
a reboot (`@reboot` no crontab), desarma-se ao terminar.

**Parar:** `touch ~/.local/state/ai-agents/plan-run.STOP`
**Estado:** `python3 scripts/run_plan.py --status`
**Relatório:** `docs/issues/014-.../report.md`

### O que o script não faz, e por quê

- **Não força verde.** Após 4 rodadas de concílio marca `needs_operator` e segue. Toda
  issue desta sessão reprovou no primeiro concílio; várias levaram de três a cinco
  rodadas; e duas vezes uma lente pegou o autor afirmando o que o artefato não sustentava.
  Um laço que roda até ficar verde, sem ninguém lendo os achados, pode chegar lá
  enfraquecendo o teste. Nada dentro do laço distingue as duas coisas.
- **Nunca `main`**, nunca `merge-to-main`.
- **Nunca outro repositório.** Os três projetos com `.docs/index.html` só ficam limpos
  quando o operador rodar `--upgrade` em cada um.

**Next:** ler o `report.md` pela manhã. Um `needs_operator` é o script sendo honesto; um
`done` merece a mesma desconfiança que qualquer outro verde.

---

## Sessão encerrada 2026-08-14 — Fase 0 commitada, execução noturna achada quebrada

O operador leu o `report.md` e autorizou o conteúdo da árvore de trabalho ("isso é
trabalho que pode ir para a development"). Fase 0 (`AC-1`, `AC-2/3/4/5`, `AC-25`,
`AC-28`) foi commitada em `development`: `74bfefa` (o conteúdo) e `3effe89` (bump
0.3.1 → 0.3.2, um sub-versão por fase concluída — regra desta épica, confirmada pelo
operador). `pytest`: 636 passed antes e depois dos dois commits.

**Achado antes de commitar, relevante para retomar a execução noturna**: o
`plan-run.log` mostra **0 PASS em 200 veredictos** de concílio entre
2026-08-13T21:17 e 2026-08-14T11:37+, sem nenhum traceback/erro registrado, e os
mtimes de todo arquivo no working tree são de ANTES do início da execução (17:58–
18:16 do dia 13, contra início às 21:17). Ou seja: em 13+ horas rodando, o script não
produziu uma única mudança de arquivo nem um único PASS — nas seis issues que
tentou (`CONFIRM-TREE`, `AC-13`, `AC-20`, `AC-21`, `AC-22`, `AC-28-emenda`, `AC-29`),
não apenas nas difíceis. Isso não é o padrão desta épica (a sessão interativa que
fechou a Fase 0 teve PASS reais, com números — ver acima); é mais consistente com o
`claude -p` falhando de forma silenciosa no ambiente de cron/`@reboot` (auth ou env
ausente após reboot) do que com 200 rejeições de código genuínas.

O operador já desarmou o crontab (`#PARADO-20260814-operador#`). **Antes de rearmar**:
diagnosticar por que `claude()` (linha ~109 de `scripts/run_plan.py`) nunca retornou
texto começando com `PASS` — rodar `claude -p` manualmente no MESMO ambiente que o
cron usaria (sem TTY, sem o shell de login) é o primeiro passo, não assumir que o
código da Fase 1 está ruim.

**Next (DO THIS FIRST):** diagnosticar o `claude -p` em contexto de cron antes de
rearmar; só depois voltar a implementar `CONFIRM-TREE`/`AC-13`/`AC-20..22`/
`AC-28-emenda`/`AC-29` (o `manifest.override.json`, Fase 1 do `PLANO-UNIFICADO.md`).
