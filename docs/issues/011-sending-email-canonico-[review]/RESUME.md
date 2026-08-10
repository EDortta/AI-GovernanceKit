# RESUME — §Sending Email canônica (GK gh-7 / AI-Agents gh-5)

- work_id: WK-20260810-sending-email-canonico
- date: 2026-08-10
- status: `[review]` — implementado e com a rodada 1 de concílio fechada.
  **Rodada 2 NÃO rodou.** Pelo §4 do `council.md` a entrega não está gateada até ela
  rodar contra as correções abaixo.

## Next Step (DO THIS FIRST)

Rodar a **rodada 2 do concílio** contra `HEAD`, com as mesmas três lentes, focada nas
correções da rodada 1 — especialmente na reversão do `templates` e nas três correções
do `_WITHDRAWN_CITATIONS`, que são código novo escrito sob pressão de achado.

## Escopo da issue #7 — estado

| item | estado |
|---|---|
| 1. mesma seção nos dois kits, uma origem só | fechado no `AGENTS.md` deste repo, byte a byte igual ao corpo canônico do AI-Agents, mais uma nota de origem. **Sem gate de deriva** — é prosa que pede "mude lá primeiro". |
| 2. remover `SMTP_ACCOUNT` do instalador | fechado. Fora do `_PLACEHOLDER_DESCRIPTIONS`; mantido no `_OPERATOR_PLACEHOLDERS` (verificado: removê-lo publica o valor legado no manifesto rastreado) e declarado em `_RETIRED_PLACEHOLDERS` (nunca perguntado, ainda substituído). |
| 3. reconciliar sintaxe de placeholder | fechado: `[OPERATOR_NAME]` → `{{OPERATOR_NAME}}`. |
| 4. o `doctor` audita a seção | **parcial.** Nenhum check audita a seção pelo nome. O que existe audita o índice para onde ela aponta e detecta contrato obsoleto que ainda a prescreve. |

## Council — rodada 1 (três lentes)

**Levantados: 19. Sobreviveram ao §2: 19. Fechados: 8. Abertos: 11.**

O achado decisivo foi contra a própria correção: acrescentar `templates` ao
`_FRESH_PATHS`/`_UPGRADE_PATHS` **apaga a pasta `templates/` do projeto**. Três
camadas somadas — padrão nu no `.gitignore` (ignora em qualquer profundidade),
`rmtree` no `--force`, e poison do manifesto rastreado que faz o SEGUNDO upgrade
deletar os arquivos do projeto em silêncio, com o `remove-agents` depois planejando
removê-los a confiança 1.0. Revertido. E o motivo de ter acrescentado era falso: o
self-upgrade que ela consertaria já está bloqueado antes, porque o shell lê
`.credentials/identity.json` e o Python grava em `.gk/operator.json`.

Fechados com teste (seis testes novos, todos verificados vermelhos contra `f17b302`):
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
