# Issue AC-15 — origem: concílio de fechamentos, 2026-08-13 (lentes: sweep skeptic + migrator)

## AC-15 — o check irmão continua nomeando o comando que não funciona sem TTY [média]

### Contexto

O achado `ade371f5#8` era: *"o remédio nomeia um comando que sem TTY sai 0 sem fazer
nada; o laço nunca termina e o check fica vermelho para sempre"*. O fechamento consertou
`_check_host_identity`, que hoje nomeia as flags — verificado rodando o laço inteiro:
`doctor` → `configure --operator-name … --host-id … --instance-path …` → `doctor` termina.

`_check_unfilled_placeholders`, **60 linhas acima no mesmo módulo** (`doctor.py:379`),
continua nomeando o `configure` nu:

```
[FAIL] unfilled placeholders: kit not configured — run 'governancekit --root T configure'
       to fill: AGENTS.md: {{OPERATOR_NAME}}
```

Sem TTY esse comando não preenche nada. Atenuante honesto: aqui ele sai `rc=1` dizendo
`Still unfilled`, em vez do `rc=0` mudo do irmão — o laço **quebra**, mas o operador (ou
o agente) fica sem o comando que fecha o check.

E o resgate existe: `configure --set TOKEN=valor` funciona, e foi criado por
`ade371f5#5`. Ele **não é nomeado por nenhuma mensagem visível ao operador** —
`grep -rn 'configure --set' governancekit/` só casa comentário de código.

### Reprodução

```
step 1 doctor: ('unfilled placeholders', False, "… run 'governancekit --root … configure' to fill: AGENTS.md: {{OPERATOR_NAME}}")
   configure (no TTY, no flags) -> unfilled=['OPERATOR_NAME'] changed=[]
step 2 doctor: (idêntico)

# o resgate existe e não é anunciado:
configure --set: found_tokens=[] changed=[]
  operator.json now: True {'metadata': {'OPERATOR_NAME': 'Esteban'}, 'state_version': 1}
plain configure (no TTY, no --set): operator.json: False
```

### Objetivo

Que todo remédio nomeie um comando que termina o laço no ambiente em que o check falhou.

### Escopo

- `_check_unfilled_placeholders` nomeia `configure --set TOKEN=valor` (ou as flags
  equivalentes), no padrão de `_FLAGS` que `doctor.py:306-316` já adotou.
- **Varrer todos os remédios do `doctor`** pela mesma pergunta: *o comando que este
  remédio nomeia termina o laço num host sem TTY?* A lista sai escrita. Esta é a segunda
  vez que a resposta é "não" em módulos vizinhos.
- Um teste genérico é possível e vale mais que N testes específicos: para cada
  `CheckResult` que falha e nomeia comando, o comando existe e aceita as flags citadas.
- Casa com `AC-5` e `AC-13`: a população legada precisa **descobrir** a porta de saída, e
  hoje ela só existe no código.

### ARO

- **Assumption**: hosts sem TTY são caso normal (CI, agentes). O próprio achado original
  partiu daí.
- **Risk**: um teste genérico sobre texto de remédio é frágil (parsing de mensagem).
  Mitigação: os remédios passam a carregar o comando em campo estruturado, não só em
  prosa — muda mais código, e resolve a classe.
- **Owner**: a definir.

### Plano de teste

- Laço completo sem TTY para `unfilled placeholders`: `doctor` → comando nomeado →
  `doctor` verde.
- O mesmo laço para cada check que nomeia comando.
- Mutação: voltar o `configure` nu ⇒ teste vermelho.

### DoD

- Todo remédio nomeia um comando que fecha o check sem terminal.
- A varredura de todos os remédios está registrada.
- O resgate `--set` é descobrível a partir da mensagem de erro.
