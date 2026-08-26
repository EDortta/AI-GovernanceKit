# Issue AC-17 — origem: concílio de fechamentos, 2026-08-13 (lente: the claim auditor)

## AC-17 — o fechamento era sobre a mensagem, e nenhum teste lê a mensagem [média]

### Contexto

O achado `6bb1027e#6` era: *"o `doctor` reporta 'written by the project' sobre texto que o
gerador do kit acabou de escrever"*. O fechamento: *"a mensagem passa a afirmar só o que
o check sabe"*.

O fechamento é **sobre a mensagem**. Os dois testes do check —
`test_generated_content_is_not_reported_as_the_kits_own_description` e
`test_a_project_that_wrote_its_own_documents_passes` — só asseguram `result.passed`.
Nenhum lê `result.message`.

A metade classificatória do conserto tem teste. A metade que o fechamento nomeia, não.

### Reprodução

```
mutate doctor.py:890: 'no kit template text in the readiness documents'
                   -> 'written by the project'
pytest tests/  =>  506 passed, 2 skipped, 6 subtests passed in 21.25s
```

O `doctor` volta a imprimir `[PASS] readiness documents: written by the project` sobre
documento que o gerador determinístico acabou de escrever — o `wrong_outcome` literal do
achado — e a suíte inteira fica verde.

### Objetivo

Que um fechamento cuja tese é uma afirmação tenha teste sobre a afirmação.

### Escopo

- Os testes do check passam a afirmar sobre `result.message`, não só `result.passed`.
- Varrer os testes de `doctor` pela mesma forma. Este repositório já pagou por isto
  antes: o fecho de `D1` registra que `tests/test_hooks.py` só afirmava sobre o **texto**
  do script de hook e passava para um hook que nunca bloqueava, e chama isso de *"a lente
  do claim auditor de novo, e é a segunda vez no mesmo dia"*. Agora é a terceira, na
  direção oposta — o teste ignora o texto quando o texto **é** a entrega.
- A regra vale nos dois sentidos, e é o que precisa ficar escrito: **teste que afirma o
  que a entrega não promete, e teste que ignora o que a entrega promete, são o mesmo
  defeito.**
- Interage com `AC-15`: se os remédios passarem a carregar comando em campo estruturado,
  afirmar sobre eles fica menos frágil.

### ARO

- **Assumption**: a mensagem é entrega, não decoração. O achado original prova que sim —
  o dano era só a mensagem.
- **Risk**: asserção sobre texto quebra a cada ajuste de redação. Mitigação: afirmar
  sobre a propriedade (*não contém "written by the project" quando houve geração*), não
  sobre a frase inteira.
- **Owner**: a definir.

### Plano de teste

- Mutação que devolve `'written by the project'` ⇒ **vermelho**. Critério de aceite.
- Documento escrito pelo projeto ⇒ mensagem correspondente.
- Documento gerado pelo kit ⇒ mensagem que não credita ao projeto.
- Varredura dos testes de `doctor` registrada.

### DoD

- A mutação da mensagem fica vermelha.
- A regra dos dois sentidos está escrita em `napkin-lessons.md`, com o antecedente de
  `D1` citado.
