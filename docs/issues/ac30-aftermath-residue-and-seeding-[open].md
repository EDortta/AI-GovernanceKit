# AC-30, o dia seguinte — resíduo no parque e lacuna de seeding

- work_id: WK-20260826-ac30-aftermath
- date: 2026-08-26
- origem: lente de segurança do mutirão de 2026-08-26 (lado AI-Agents), itens (b) e (c)
  do repasse; registrados aqui porque a correção é deste repositório.
- status: `[open]` — registrados, não implementados. O item (a) do mesmo repasse
  (o `refresh-kit-snapshot.py` morria com SystemExit quando o tarball não traz mais
  `scripts/install-agents-kit.sh`) foi corrigido na entrega
  `feature/mutirao-20260826-batch`.

## (b) `README.md` do kit não está em `_WITHDRAWN_PATHS`

`AC-30` retirou `scripts/install-agents-kit.sh` dos alvos via `_WITHDRAWN_PATHS` —
o mecanismo que alcança quem já tem a cópia. O instalador shell, porém, também
depositava outros arquivos que o instalador Python nunca escreve (o `README.md` do
próprio kit é o caso nomeado). Um alvo que passou pelo shell fica com esse resíduo
para sempre: nenhum dos dois mecanismos (parar de copiar; retirar) o alcança hoje.

**Cuidado de escopo:** `README.md` na raiz de um projeto é quase sempre DO PROJETO.
A retirada não pode ser por nome — precisa da mesma evidência de byte-identidade
contra o release pinado que `remove-agents` usa para `.credentials/` (snapshot de
digests), nunca um `rm` por caminho. Caso o custo disso não compense, a alternativa
honesta é o `doctor` DETECTAR e avisar, sem remover.

### DoD
- Ou o resíduo do shell installer é retirado com evidência de bytes, ou o `doctor`
  o nomeia como resíduo em HINT — decidido e escrito qual dos dois.

## (c) Ninguém mais semeia o bloco de leitura (`required-reading.kit-block.md`)

Com o shell installer retirado, nenhum instalador injeta o bloco gerenciado de
leitura obrigatória que ele escrevia. Projeto novo instalado só pelo caminho Python
nasce com o índice `docs/required-reading.md` do template neutro e sem o bloco do
kit — o agente não é apontado para os contratos instalados.

**Verificar antes de implementar** (lição de 2026-08-06: issue fechada na fonte,
parque quebrado): o que exatamente o bloco continha no release pinado, se o
template neutro de `v1.2.1` já cobre o essencial, e se o `doctor` já reprova a
ausência. A correção provável é o instalador Python passar a semear/atualizar o
bloco a partir do release pinado — com a regra de propriedade preservada
(`docs/` é do projeto; o bloco é gerenciado por marcadores).

### DoD
- Projeto novo instalado pelo caminho Python aponta o agente para os contratos do
  kit sem passo manual, ou o gap está aceito por escrito com o `doctor` avisando.

## (d) O teste de paridade do bloco `.gitignore` foi aposentado COM o instalador

`tests/test_doctor_gitignore.py` trazia `ShellInstallerWritesTheSameBlockTests`,
que comparava o bloco escrito pelo `install-agents-kit.sh` do checkout vizinho
contra `SECRET_IGNORE_PATTERNS`. Com o script retirado (AC-30; AI-Agents PR #19),
o teste caía num `skipTest` permanente com mensagem FALSA ("checkout is not
available" — o checkout existe; o script não). Detectado independentemente pelo
claim auditor do concílio de bloco de 2026-08-26 e pelo item 6 da "Coordenação
pendente" da épica 006 do AI-Agents. **Resolvido em 2026-08-26**: a classe foi
aposentada por escrito (tombstone no próprio arquivo), não deixada verde sem
testar nada.

## Regra do release único (coordenação com AI-Agents v1.3.0)

Quando o operador cortar a `v1.3.0` do AI-Agents (pós-merge da PR #19 de lá), o
bump do GovernanceKit tem de sair num ÚNICO release: `DEFAULT_REF=v1.3.0` +
checksum em `KNOWN_TARBALL_SHA256` + atualização das 4 páginas que citam o ref.
Um release intermediário apagaria o script dos alvos enquanto reinstala um
`AGENTS.md` de `v1.2.1` que manda rodá-lo. **O que esta entrega já deixou
pronto**: `refresh-kit-snapshot.py` sobrevive ao tarball sem o script (fallback
para `_PROTECTED_FILES`), a landing não ensina mais `curl|bash`, o teste que
exigia a URL do script agora afirma a ausência, `--allow-unverified` existe no
parser, e o teste de paridade foi aposentado. **O que fica para o bump**: o par
ref+checksum e as páginas — passo do operador, no checklist de corte de tag do
AI-Agents (épica 006 de lá, `tag-cut-checklist.md`). Nota de contexto: as tags
`v1.1.8`/`v1.2.0`/`v1.2.1` existem no origin; o pino atual `v1.2.1` está íntegro.
