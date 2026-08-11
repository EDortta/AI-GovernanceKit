# RESUME — Gate de deriva entre os dois kits (R2-18)

- work_id: WK-20260811-kit-drift-gate
- date: 2026-08-11
- status: `[finished]` — entregue em `b1c46ea`, não lançado (fica no `[Unreleased]`)
- origem: `R2-18` da rodada 2 do concílio da épica 011

## O problema

Três coisas que este repositório afirma sobre o AI-Agents não eram verificadas por
nada: a release que ele pina, o range de versão que essa release declara, e o corpo da
`§Sending Email` de que ele carrega uma cópia. O que segurava as três era uma nota em
prosa pedindo "mude lá primeiro, depois espelhe aqui".

Prosa não fica vermelha. Em um único dia — 2026-08-11 — a deriva apareceu **três vezes**
e custou uma rodada de trabalho cada:

1. o range: um bump de versão aqui quase publicou um runtime que o contrato de todo
   projeto governado rejeitaria
2. o pin: `DEFAULT_REF` e a landing page deste repo discordavam do release
3. a seção: já tinha derivado antes por tradução (`## Enviar e-mail` escapou de uma
   varredura que procurava `Sending Email`)

## A forma da solução

Snapshot **derivado**, nunca digitado. Snapshot escrito à mão é só um segundo lugar
onde errar, com a autoridade de parecer evidência.

- `scripts/refresh-kit-snapshot.py` baixa o tarball pinado, confere o sha contra
  `KNOWN_TARBALL_SHA256` **antes de ler um byte do conteúdo**, e grava o que a release diz
- `governancekit/_kit_snapshot.json` guarda `agents_ref`, `governancekit_version_range`
  e o sha256 do corpo canônico da seção
- `governancekit/kit_drift.py` extrai o corpo pela **mesma regra** nos dois portadores —
  em AI-Agents a seção mora em `.docs/workflows/sending-email.md`, aqui no `AGENTS.md` —
  e descarta a nota de origem, que só existe na cópia
- `tests/test_kit_drift.py` compara este repo contra o snapshot, **sem rede**
- `--check` prova que o snapshot é atual sem confiar que quem bumpou o pin lembrou de
  atualizá-lo

## Verificação por mutação

Cada direção de deriva, uma a uma, contra o gate:

| mutação | teste que fica vermelho |
|---|---|
| `DEFAULT_REF` bumpado sem refresh | `test_the_snapshot_describes_the_release_this_runtime_pins` |
| range do snapshot estreitado para `<0.3.0` | `test_this_runtime_satisfies_the_range_the_pinned_contract_declares` |
| primeira frase da seção reescrita no `AGENTS.md` | `test_the_shared_section_here_still_matches_its_origin` |

E o `--check` com o digest adulterado sai `1`, nomeando os dois lados.

`pytest`: 408 passed, 6 subtests.

## Achado colateral

O `test_the_hook_does_not_block_when_the_toolchain_is_missing` limpava `PATH` e
`PYTHONPATH` para simular toolchain ausente e **nunca simulou nada**: o diretório *user
site* segue no `sys.path`, e este kit é instalado por usuário por decisão de projeto.
Passava porque a cópia instalada era velha demais para ter `council.py` e morria antes
de bloquear; consertar a instalação deixou o teste vermelho, e o vermelho era a verdade.
Isolado com `PYTHONNOUSERSITE`.

## Não validado

`not validated:` o gate nunca foi exercido contra uma release do AI-Agents **diferente**
da pinada. A prova de que ele pega deriva real de upstream só vem no próximo bump de
`DEFAULT_REF` — as mutações de hoje simulam as três direções, mas simulam.
