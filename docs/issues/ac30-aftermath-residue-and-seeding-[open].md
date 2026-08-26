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
