# RESUME — Cadeia de versões AI-Agents ↔ GovernanceKit (lado GovernanceKit)

- work_id: WK-20260811-version-chain-coordination
- date: 2026-08-11
- status: `[review]` — código pronto e verde; **instalação local ainda não feita**, e é
  ela que dispara o efeito descrito abaixo.
- gêmea: `AI/Agents .../docs/issues/010-version-chain-coordination-[review]/RESUME.md`

## Regra que originou o trabalho

Decisão do operador em 2026-08-11: quando a tag de um dos dois kits avança, a versão do
outro acompanha. O `0.2.3` tinha 45 commits sob `[Unreleased]` e o AI-Agents já estava
em `v1.2.0`.

## Entregue

- `DEFAULT_REF` `v1.2.0` → `v1.2.1`, com `ccf9ed69…` pinado e o tarball conferido
  (contrato e `REF` lidos de dentro dele antes de pinar)
- `pyproject.toml` e `governancekit/__init__.py`: `0.2.3` → `0.3.0`
- 6 arquivos de teste que declaravam `>=0.2.2,<0.3.0` → `>=0.2.2,<0.4.0`; o caso
  negativo `>=9.0.0,<10.0.0` de `test_integration.py:45` ficou intacto
- 4 landing pages deste repo que citavam `v1.2.0`
- `CHANGELOG`: `[Unreleased]` → `[0.3.0]`, com a nota de upgrade

`pytest`: 400 passed, 6 subtests.

## O erro da rodada 1, corrigido na rodada 2

A rodada 1 concluiu que publicar o range permissivo `>=0.2.2,<0.4.0` no AI-Agents
`v1.2.1` evitaria o `[FAIL]` nos 4 projetos `existing` do parque. **Está errado.** Cada
projeto carrega a SUA cópia de `.docs/governancekit-integration.json`, e os 4 estão em
kit `v1.1.6`, cujo contrato diz `>=0.2.2,<0.3.0`. Nenhum range publicado hoje alcança
um arquivo que já está no disco deles.

Verificado, não deduzido:

```
GK 0.3.0 × contrato >=0.2.2,<0.3.0  ->  INCOMPATIBLE
GK 0.3.0 × contrato >=0.2.2,<0.4.0  ->  ok
```

O que o range permissivo comprou de fato: para um projeto **já em `v1.2.1`**, os dois
kits passam a ser atualizáveis em qualquer ordem — `0.2.3` e `0.3.0` servem os dois.
Isso é real e vale a release. O que ele **não** comprou: proteção para o parque velho.

Lição de método, e é a segunda vez neste trabalho: o range vive no projeto governado,
não no kit. Alterar o kit não altera o parque instalado — só o upgrade altera.

## Council — rodadas

**Rodada 1: levantados 4, sobreviveram 2, viraram teste 0, perguntas abertas 1.**
**Rodada 2: 1 achado — contra a própria conclusão da rodada 1 (acima). Fechado por
verificação executada, não por leitura.**

Pergunta aberta das duas rodadas: continua sem gate de deriva entre os dois kits — o
`R2-18` do épico 011. Este trabalho é a terceira vez que a ausência dele custa uma
rodada.

## Next Step (DO THIS FIRST)

**Decisão do operador, pendente:** instalar `0.3.0` localmente faz os 4 projetos
`existing` (`jk-structure`, o worktree `--WK-20260807-sec0024-produtor`,
`CodexBridgeMobile`, `ledgerlab`) reprovarem no `doctor` de forma não-advisory até que
o kit de cada um suba para `v1.2.1`. Caminho limpo: upgradar os 4 primeiro, depois
instalar. `jk-structure` tem trabalho vivo e é projeto de produção.

Depois: merge `development` → `main` (46 commits) e tag `v0.3.0`.

## Não validado

`not validated:` o `doctor` de um projeto real em `v1.2.1` sob GovernanceKit `0.3.0`.
A previsão é `[PASS]`; a checagem de range foi verificada isoladamente, o `doctor`
inteiro não.
