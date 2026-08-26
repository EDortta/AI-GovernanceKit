# RESUME — Cadeia de versões AI-Agents ↔ GovernanceKit (lado GovernanceKit)

- work_id: WK-20260811-version-chain-coordination
- date: 2026-08-11
- status: `[finished]` — `v0.3.0` publicada (`main` + tag), parque migrado e cópia
  local instalada. `governancekit --version` responde `0.3.0` / `v1.2.1`.
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

## Fechamento — 2026-08-11

O operador corrigiu o enquadramento: nenhum projeto consumidor gateia a release. O
acoplamento é só de máquina — o `governancekit` é um binário global, e é o design
pretendido. Merge (48 commits) e tag `v0.3.0` publicados sem depender de projeto nenhum.

Parque migrado para `v1.2.1`: **28 dos 29 projetos governados**, exceto
`YouBR/ZeeCred/jk-dashboard-backup`, excluído pelo operador. Depois disso a instalação
local ficou sem efeito colateral, e `doctor` responde `[PASS]` nos quatro `existing`.

A cópia instalada estava congelada em 2026-08-06 e não tinha `council.py`; agora é
byte a byte igual ao `main` tagueado.

## Validado em projeto governado — 2026-08-11

O par `CodexBridge` / `CodexBridgeMobile` foi escolhido pelo operador porque cobre os
dois caminhos do `doctor.py:239`: o primeiro não tem `project-config.json` (advisory),
o segundo tem `project_state: existing` (bloqueante). O `0.3.0` foi exercido a partir da
worktree via `PYTHONPATH`, sem instalar nada na máquina.

**Antes do upgrade**, com o kit velho:

| projeto | GK 0.2.3 | GK 0.3.0 |
|---|---|---|
| CodexBridge (sem project-config) | `[PASS]` | `[HINT]` — advisory |
| CodexBridgeMobile (`existing`) | `[PASS]` | `[FAIL]` — bloqueante |

Confirma a previsão do §`doctor.py:239` na íntegra, incluindo a diferença entre os dois
caminhos.

**Depois de `install-agents --upgrade`** para `v1.2.1`, nos dois projetos:

| projeto | GK 0.2.3 | GK 0.3.0 |
|---|---|---|
| CodexBridge | `[PASS]` v1.2.1 | `[PASS]` v1.2.1 |
| CodexBridgeMobile | `[PASS]` v1.2.1 | `[PASS]` v1.2.1 |

As duas colunas verdes são a prova executada de que o range permissivo entrega o que
foi comprado: **o projeto em `v1.2.1` aceita os dois runtimes**, então kit e ferramenta
podem subir em qualquer ordem.

O conjunto de `[FAIL]` de cada projeto foi comparado contra o estado pré-upgrade
restaurado do backup: **idêntico nos dois**. O que sobra (`required-reading.md` listando
documento ausente, épico ativo, identidade de host, marcador do `RESUME.md`) é higiene
pré-existente do projeto, não regressão desta entrega.

## Validado ponta a ponta

`jk-structure`, `ledgerlab` e `CodexBridgeMobile` — os `existing`, que são os que
reprovariam duro — respondem `[PASS]` sob a cópia instalada `0.3.0`.
