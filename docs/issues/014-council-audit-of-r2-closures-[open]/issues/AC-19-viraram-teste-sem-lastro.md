# Issue AC-19 — origem: concílio de fechamentos, 2026-08-13 (lente: the claim auditor)

## AC-19 — a contagem "viraram teste" não tem lastro, e é a segunda vez [alta]

### Contexto

`council.md` §4 exige quatro contagens em `docs/napkin-lessons.md` e no `RESUME.md`
ativo: levantados / sobreviveram ao §2 / **viraram teste** / perguntas em aberto.

O que a prosa afirma:

- `napkin-lessons.md:117` — *"Viraram teste: 9 (todos verificados por mutação)"*
- `napkin-lessons.md:127` — *"13 viraram teste"*
- e o mesmo nos dois RESUMEs (`011:91`, `008:45`)

O que o repositório sustenta:

| fechamento | teste |
|---|---|
| `ade371f5#7` (`verify-elo4.sh`) | **nenhum** — `grep -rn 'verify-elo4' tests/` → vazio |
| `6bb1027e#4` (`validate-governance.sh`) | **nenhum** — só um comentário em `test_doctor_sending_email.py:215` |
| `ade371f5#2` | existe, não exercita o gatilho (`AC-11`) |
| `6bb1027e#1` | existe, assere o invariante (`AC-16`) |
| `6bb1027e#6` | existe, não lê a mensagem (`AC-17`) |
| `6bb1027e#9` | existe, ramo errado (`AC-18`) |
| `6bb1027e#3` | existe, asserção morta (`AC-4`) |

O número honesto é **no máximo 8/9 e 11/13**.

### Por que isto é alta, e não burocracia

É a **segunda vez**. A rodada 2 de 10/08 pegou exatamente este defeito, e a lição está
escrita em `docs/issues/011-…/RESUME.md:180`:

> *"registro com número inventado calibra o próximo concílio em ficção"*

A correção daquela vez consertou **os números**. Não consertou o **hábito** — contar
"fechado" como "virou teste". E o §4 diz por que isso importa: o registro é a única coisa
que pode substituir o palpite sobre gatilhos e número de membros. Um registro inflado não
é só impreciso; ele calibra o instrumento errado, para sempre.

### Objetivo

Que a contagem "viraram teste" seja derivada, não digitada — pelo mesmo princípio que a
épica `013` já aplicou ao snapshot de deriva: *"snapshot escrito à mão é só um segundo
lugar onde errar, com a autoridade de parecer evidência"*.

### Escopo

- Corrigir os números nos quatro lugares, com a divergência explicada, não apagada.
- **Separar "fechado" de "protegido"** (pergunta 4 do RESUME). Um achado fechado por
  reprodução — que o §2 aceita — está fechado e **não** está protegido contra
  recorrência. Duas colunas, não uma.
- `council --record` passa a exigir as quatro contagens. Hoje o JSON guarda só `findings`
  e `questions` (pergunta 3 do RESUME), e as contagens vivem só em prosa — que é
  exatamente onde a divergência mora. O gate não pode conferir o que não recebe.
- Onde der, **derivar**: o registro nomeia o teste de cada fechamento, e uma checagem
  confirma que o teste existe e que a suíte o coleta. Nome de teste que não existe é
  vermelho.
- Verificação por mutação continua sendo do programador; o registro só precisa saber se
  ela foi feita, e para qual teste.

### ARO

- **Assumption**: a inflação foi honesta — "fechei o achado" virou "virou teste" sem
  ninguém mentir. É por isso que a correção precisa ser estrutural e não uma advertência.
- **Risk**: exigir contagens no `--record` quebra o gate para rodadas em andamento.
  Mitigação: campo novo opcional por uma release, depois obrigatório.
- **Risk**: derivar o vínculo teste↔achado exige nomear testes no registro, e nome de
  teste muda. Aceitável: o vermelho quando o nome quebra é informação, não ruído.
- **Owner**: a definir.

### Plano de teste

- Registro com nome de teste inexistente ⇒ `council --record` recusa.
- Registro sem as quatro contagens ⇒ recusa (depois do período de transição).
- Achado fechado por reprodução ⇒ contabilizado como fechado e **não** como protegido.
- Os números dos quatro documentos batem com o que o repositório sustenta.

### DoD

- As quatro contagens são derivadas ou verificadas, nunca só digitadas.
- "Fechado" e "protegido" são colunas diferentes.
- Os números de 12/08 estão corrigidos, com a divergência registrada — não apagada.
- Esta épica registra `viraram teste: 0` ao abrir, e o número cresce por evidência.
