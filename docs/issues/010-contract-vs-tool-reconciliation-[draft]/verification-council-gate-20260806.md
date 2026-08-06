# Verificação do gate de council — 2026-08-06

`WK-20260806-council-commit-gate`. Fecha a **D1** e o `not validated:` que
`.docs/agents/council.md` carregava desde 2026-07-01.

## Ponta a ponta, num repositório de rascunho

Com o `pre-commit` do kit instalado, em ordem, cada passo verificado pelo `git commit`
real e não por inspeção:

| Passo | Resultado |
|---|---|
| commit trivial (`app.py`) | passa — nenhum gatilho |
| altera `.docs/agents/reviewer.md`, sem council | **bloqueado**: `council gate: shared-contract: this delivery needs a council round` |
| grava rodada 1 com um achado **aberto** | ainda bloqueia: *"§2 requires a failing test or a written risk acceptance"* |
| fecha o achado com um teste | `satisfied`; o commit passa |
| emenda o mesmo arquivo depois do council | **bloqueado de novo** — o fingerprint mudou |
| `--waive "   "` | recusado: *"A waiver needs a reason"* |
| `--waive "typo em comentário…"` | passa, e o motivo fica no registro |
| rodada 2 com achado aberto | **bloqueado** com escalação: *"stop and take them to the operator; do not run another round"* |
| gravar rodada 3 | recusado na gravação: *"round must be between 1 and 2"* |
| `doctor` sem nada staged | `council gate` advisory e silencioso; `doctor` continua `ok` |
| registro ilegível | advisory, nunca trava o commit |

## O defeito que a implementação encontrou

**O `pre-commit` que o kit instala nunca reprovou nada pelo `doctor`.** Dois defeitos
somados, ambos fatais isoladamente:

1. o hook chama `python3 -m governancekit.cli`, e `cli.py` **não tinha guarda
   `if __name__ == "__main__"`** — o módulo importava, não imprimia nada e saía `0`;
2. o veredito era lido por `python3 - <<'PY'`, e **o heredoc substitui o pipe como
   stdin** — o leitor nunca via o relatório, de qualquer forma.

Sobreviveram porque `tests/test_hooks.py` só afirmava sobre o **texto** do script
(*"a string `governancekit pre-commit blocked` está no arquivo"*), o que passa para um
hook que nunca bloqueia.

Corrigido em `cli.py` e `hooks.py`, com um teste que **executa** o hook. Verificado por
**mutação**: desligando a guarda `__main__`, o teste falha; restaurada, passa. A guarda
ficou em `cli.py` além de `__main__.py` de propósito — assim conserta os hooks já
gravados em repositórios que não dá para reinstalar daqui.

Consequência para o parque: todo projeto que rodou `install-hooks` estava sem a metade
`doctor` do hook. A metade que varre caminho de segredo é shell puro e sempre funcionou.

## A primeira rodada de council, contra esta própria entrega

Três lentes padrão de §3, **duas rodadas**: 3 achados na rodada 1, mais 2 na rodada 2 —
estes últimos encontrados **usando o próprio gate sobre a entrega**. Todos os 5
fechados, 4 com correção e 1 com aceitação de risco escrita. 4 perguntas em aberto.

**second caller** — `scripts/install-agents-kit.sh:746` e
`governancekit/install_agents.py:789` escrevem o mesmo `.gk/.gitignore` com listas
**diferentes**. O shell não tinha `council/` (os registros entrariam no índice) nem
`operator.json` (identidade por máquina). É literalmente o precedente que dá nome a esta
lente: *o instalador tem dois caminhos de cópia*. Fechado: as listas coincidem.

**claim auditor** — o gate novo em `AGENTS.md` §7 afirmava lisamente que *"o `pre-commit`
reprova"*. `install-hooks` é opt-in e `install-agents` não o chama, então a frase era
falsa exatamente onde mais importa. Fechado: o contrato passa a dizer `doctor` reprova e
o `pre-commit` **onde `install-hooks` rodou**, e `_check_council_gate` aponta o comando
quando o hook falta.

**sweep skeptic** — `.docs/agents/README.md` é um segundo índice do mesmo arquivo e
continuava descrevendo o council só por **tópico**, que é a falha de descoberta que a
própria D1 relata. Fechado: nomeia o momento e o comando.

### Rodada 2 — os dois que só apareceram ao usar a ferramenta

**sweep skeptic** — o gatilho `not-validated` casava por **substring** e disparou sobre
`docs/napkin-lessons.md:47`, uma frase que **ensina** o marcador: *"caso contrário
escrever `not validated: <o quê>`"*. É a mesma classe do bug de substring do
`_check_ready_flag` corrigido nesta mesma sessão, e da lição de 24/07 sobre documentar
um mecanismo de substituição escrevendo o padrão substituível literalmente. **Terceira
ocorrência do mesmo defeito neste kit.** Fechado: regex ancorada em início de linha,
com teste dos dois lados — a prosa não dispara, a linha real dispara.

**second caller** — nenhum gatilho §4 detectável cobre o **próprio código do kit**. Esta
entrega alterou `install_agents.py` e `hooks.py`, que chegam a todo projeto governado no
próximo upgrade, e `governancekit council` naquele checkout reportou `no-trigger`. Raio
de alcance maior que uma edição de contrato, e passa sem council.

Fechado com **aceitação de risco escrita** (§2 permite, `/AGENTS.md` §9), não com
correção: um gatilho sobre o fonte do kit dispararia em **todo** commit do kit, que é
exatamente o ruído contra o qual a B1 alerta. §4 declara os gatilhos provisórios e manda
corrigi-los pelos registros. Este é o primeiro registro. A decisão fica para quando
houver alguns — que é o mecanismo funcionando como escrito, e não uma desculpa.

### Perguntas deixadas em aberto (§2: sem resultado errado observável, não é achado)

- O gate funciona antes do primeiro commit de um repositório — verificado, `git diff
  --cached` responde contra a árvore vazia. Sem efeito errado, fica como pergunta.
- `remove_agents.py` não sabe de `.gk/council/`. Hoje `.gk/` inteiro está fora do
  inventário que ele varre, então não há efeito errado; se essa exclusão mudar, os
  registros viram lixo órfão.
- O limiar de 12 arquivos que detecta `mechanical-sweep` é um chute declarado. Só
  registros de rodadas reais podem corrigi-lo — que é exatamente o que §4 diz.
- A rodada 1 achou 3; a rodada 2 achou mais 2, e as duas vieram de **rodar a ferramenta
  contra a própria entrega**. Isso sugere uma lente que o §3 não lista: *use o que você
  acabou de construir, no caso que você acabou de construir*. Fica como pergunta porque
  n=1 — precedente, não evidência, exatamente como o §3 diz das outras três.

## Uma aspereza de uso, encontrada ao usar

§4 exige o registro em prosa (`docs/napkin-lessons.md`, `RESUME.md`) **e** o registro
mecânico. A prosa faz parte da entrega, então escrevê-la **muda o diff staged e invalida
a rodada recém-gravada**. A ordem correta é: council → correções → prosa → `--record`.
Está certo que seja assim (o registro tem de descrever o que vai ser commitado), mas não
é óbvio, e quem inverter a ordem vai levar um bloqueio que parece um bug.

## Escopo não coberto, dito em voz alta

- O gatilho *release/tag que muda gate* (§4) é operação de tag e não alcança um
  `pre-commit`. O comando imprime isso toda vez, em vez de omitir.
- Sem `governancekit` importável, o hook não bloqueia — cadeia quebrada não é commit
  quebrado. É decisão deliberada, e significa que o gate não é uma barreira contra quem
  não quer passar por ele. Ele nunca foi desenhado para isso: §1 do `council.md` diz que
  o council produz achados, nunca decisões.
- `CodexBridge` e `CodexBridgeMobile` carregam cópias instaladas e só recebem tudo isto
  pelo upgrade.
