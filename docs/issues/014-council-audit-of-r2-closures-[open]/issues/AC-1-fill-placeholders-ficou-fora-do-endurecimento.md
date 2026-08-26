# Issue AC-1 — origem: concílio de fechamentos, 2026-08-13 (lente: the sweep skeptic)

> **Correção de diagnóstico, 2026-08-13, antes da implementação.** O texto abaixo
> prescreve *"`_fill_placeholders` passa a usar varredura única de regex"*. **Isso não
> fecha a cadeia**, e o escopo original teria entregue uma correção que parece completa e
> não é — exatamente o defeito que esta épica inteira audita. Fica escrito porque apagar
> o erro apagaria a lição.
>
> Medido:
>
> ```
> single-sweep result: 'Owner: PIX-SECRET-DO-NOT-COMMIT\n'
> still leaks: True
> ```
>
> A razão: quando `_fill_placeholders` roda, `{{PIX_PAYLOAD}}` **já é texto real do
> arquivo** — o estágio 1 o escreveu ali. Varredura única impede re-substituição *dentro
> de uma passada*; não impede o estágio seguinte de tratar o token injetado como
> placeholder legítimo. Cada estágio, isolado, está correto.
>
> A propriedade que fecha a cadeia é outra e não estava em nenhum dos dois:
> **um valor guardado nunca pode introduzir sintaxe de placeholder.** Ela corta o
> ataque na origem, independentemente de quantos estágios rodem depois — e é a única
> das quatro que não depende de contar estágios certo.
>
> O escopo real está em *Escopo (corrigido)*, no fim desta issue.

## AC-1 — o endurecimento do render parou no meio do pipeline [crítica]

### Contexto

O achado `ade371f5#0` era de segurança: um colega commita `.gk/manifest.json` com
`ORG_NAME = "{{PIX_PAYLOAD}}"` (metade **compartilhada** do estado), a vítima tem
`PIX_PAYLOAD` no `.gk/secrets.json` **local**, e a substituição sequencial expande o
token injetado na passada seguinte — o segredo local entra num arquivo do kit, tem o
hash gravado, e sob `--track` fica a um `git add` do repositório.

O fechamento registrado foi: *"varredura única de regex + filtro aos placeholders
declarados + teto de tamanho; três testes, todos vermelhos sem a correção"*.

Os três testes existem e mordem — verificado por mutação, uma por uma. **Mas o
endurecimento entrou em `_prerender_source` apenas.** O `run_install_agents` chama, na
ordem:

| passo | função | estado |
|---|---|---|
| `install_agents.py:447` | `_prerender_source` | endurecido em `c7b2838` |
| `install_agents.py:493` | `_fill_placeholders` | **intocado** |

E `_fill_placeholders` continua sendo exatamente o mecanismo que o achado descreve:

```python
new_text = text
for t, v in values.items():
    new_text = new_text.replace(f"{{{{{t}}}}}", v)
```

`install_agents.py:1744-1745`. Sem varredura única, sem filtro aos placeholders
declarados, sem teto de tamanho. O buraco não fechou — **mudou de estágio**.

### Reprodução

Chamando as funções reais na ordem real de `run_install_agents`:

```
estado logico visto pelo instalador: {'ORG_NAME': '{{PIX_PAYLOAD}}', 'PIX_PAYLOAD': 'PIX-SECRET-DO-NOT-COMMIT'}
apos _prerender_source (passada unica, CORRIGIDA):
    Owner: {{PIX_PAYLOAD}}
Placeholders filled in: .docs/donations.md
apos _fill_placeholders (linha 1745: str.replace sequencial):
    Owner: PIX-SECRET-DO-NOT-COMMIT
```

O `_prerender_source` corrigido faz o certo — deixa o token literal. O
`_fill_placeholders` seguinte o expande.

### Objetivo

Que as duas metades do mecanismo de render usem a mesma regra, e que a regra seja
verificada nas duas.

### Escopo

- `_fill_placeholders` (`install_agents.py:1735-1748`) passa a usar varredura única de
  regex, filtro aos placeholders declarados (`_PLACEHOLDER_DESCRIPTIONS` ∪
  `_RETIRED_PLACEHOLDERS`) e teto de tamanho — a mesma função de render que
  `_prerender_source` usa, não uma segunda cópia da regra.
- Extrair a regra para **um** ponto. Duas implementações da mesma política é o defeito
  que esta issue registra; consertar por cópia recria-o na próxima correção.
- `configure.py:264` tem o mesmo `str.replace` sequencial. Ali os valores vêm só do
  operador e não provei exploração — mas fica no escopo por simetria, ou sai com
  justificativa escrita.
- Fora de escopo: mudar `_MAX_PLACEHOLDER_VALUE`. Ver pergunta 2 do RESUME.

### ARO

- **Assumption**: todo caminho que escreve valor de estado em arquivo do kit deve passar
  pela mesma função. Não há caso legítimo de substituição sequencial aqui.
- **Risk**: um alvo cujo valor legítimo passe do teto para de ser preenchido. Mitigação:
  o teto já existe do outro lado; alinhar as duas metades **reduz** a divergência, não a
  cria. O risco real é o oposto — hoje elas discordam.
- **Risk**: `configure.py` compartilha a função e muda de comportamento para valores que
  o operador digitou. Mitigação: teste dos dois chamadores.
- **Owner**: a definir.

### Plano de teste

- O cenário completo do achado, ponta a ponta pelas funções reais na ordem de
  `run_install_agents`: manifesto compartilhado envenenado + segredo local ⇒ o arquivo
  final contém `{{PIX_PAYLOAD}}` literal, nunca o segredo.
- Placeholder não declarado presente no estado ⇒ não é substituído por
  `_fill_placeholders`.
- Valor acima do teto ⇒ recusado por `_fill_placeholders`, com a mesma mensagem do outro
  lado.
- Os três testes de `_prerender_source` continuam vermelhos sob as mutações de `c7b2838`.

### DoD

- Uma única função de render, usada pelos dois (ou três) chamadores.
- Cada uma das três propriedades tem teste que fica vermelho sem a correção — verificado
  por mutação, não afirmado.
- A reprodução acima, rodada de novo, devolve o token literal.

---

## Escopo (corrigido) — o que a implementação vai fazer

São **três** escritores com o mesmo padrão, não dois:

| escritor | varredura única | filtro de declarados | teto | valor não introduz sintaxe |
|---|---|---|---|---|
| `install_agents._prerender_source` | sim | sim | sim | **não** |
| `install_agents._fill_placeholders:1744` | não | sim (por construção) | não | **não** |
| `configure.run_configure:263` | não | sim (por `found`) | não | **não** |

A quarta coluna está vazia nos três, e é a que fecha a cadeia. As outras três reduzem
superfície e continuam valendo.

- **Uma tabela, uma sopradora.** `_render_table(known)` aplica as quatro regras e
  devolve o que pode ser substituído mais **a lista do que foi recusado e por quê**;
  `_render_text(text, table)` faz a varredura única. Os três escritores passam a usar as
  duas. Duas implementações da mesma política é o defeito que esta issue registra.
- **Recusa é visível.** Valor recusado é nomeado na saída, com o motivo. Trocar
  vazamento por silêncio é a forma de defeito que `6bb1027e#0` já pegou nesta mesma
  entrega — *"a correção trocou traceback por silêncio"*. Não repetir.
- A regra vale também para resposta digitada no terminal: ninguém tem razão legítima
  para digitar `{{TOKEN}}` como valor, e distinguir a origem do valor cria um segundo
  caminho para manter.

### Plano de teste (corrigido)

- **A cadeia de dois estágios, ponta a ponta**: manifesto compartilhado com
  `ORG_NAME = "{{PIX_PAYLOAD}}"` + segredo local ⇒ o arquivo final **não** contém o
  segredo, nos três escritores.
- Valor com sintaxe de placeholder ⇒ recusado, nomeado na saída, nada escrito.
- Valor acima do teto ⇒ recusado, nos três.
- Token não declarado no estado ⇒ nunca substituído, nos três.
- Varredura única: valor que contém texto de outro valor não é re-expandido.
- Mutação por propriedade e por escritor — 4 × 3 — e cada uma tem de derrubar um teste.

---

## Rodada 1 da crítica de quatro céticos — 2026-08-13

Lentes: **LGPD**, **the fix auditor**, **the second caller**, **the migrator**.
**Todos os quatro devolveram `fail`.** O que caiu, e o que foi feito:

| achado | lentes | resposta |
|---|---|---|
| A regra 4 protege o **valor**; a propriedade vive na **saída renderizada**. Três variantes compõem sintaxe a partir de valores que passam o portão — inclusive uma em que o valor é inocente e as chaves são do template (`{{{{ORG_NAME}}}}`) | fix auditor | `_render_text` passa a exigir que o render **não introduza token que o texto não carregava**. Não pergunta se o token tem valor agora — a primeira tentativa perguntava, e por isso deixava passar a variante A |
| `configure.py:227` persiste o preset **sem portão e sem aviso** quando o alvo não tem mais token cru | second caller, fix auditor, migrator | o preset é filtrado **uma vez**, antes de qualquer ramo |
| O teto de 4096 levado para os escritores do **alvo** fez um `--upgrade` **des-renderizar** arquivo já renderizado; `doctor` vira FAIL e oscila sob version skew | migrator, fix auditor, LGPD | o teto vira o que sempre deveria ter sido: um limite de DoS. 1 MiB, justificado por medição (QR de app de banco = 98.848 chars) |
| A recusa criava uma **caixa que não esvazia**: `--set` era filtrado por `t in found`, então valor envenenado era insubstituível | second caller | `--set` é resposta explícita e é registrada independentemente de `found` |
| Valor não-string no estado derruba o install com `TypeError` cru | fix auditor | recusado por nome |
| O prompt interativo oferecia o valor envenenado como **default**, e Enter o re-submetia | second caller, LGPD | default suprimido para o que o portão recusaria |
| Aviso duplicado por corrida, e aviso sobre slot que nenhum arquivo usa | fix auditor, migrator | só se reporta o que o texto renderizado carrega |
| A recusa não nomeava saída; a natural (colar à mão no arquivo rastreado) é pior sob LGPD | LGPD, migrator | a recusa nomeia os arquivos de estado e o comando |
| `doctor.py` mantinha um **terceiro** `_PLACEHOLDER_RE`, divergente (`{2,}` contra `+`) | second caller | uma definição, importada |

**Fora do escopo de AC-1, abertas como issues próprias** (achados da lente de LGPD, todos
reproduzidos): `AC-20` (o filtro do estado compartilhado não cobre
`_SENSITIVE_PLACEHOLDERS`), `AC-21` (não existe caminho de eliminação, e a de-adoção
multiplica cópias), `AC-22` (hash de arquivo renderizado com dado pessoal na metade
versionada).

Verificação desta rodada: **537 passed**, e **13/13 mutações vermelhas** — uma por
propriedade e uma por escritor, incluindo a que reintroduz o teto de 4096 e a que devolve
ao `doctor` o regex divergente.

### O que esta rodada ensina, e vale além desta issue

Três desenhos foram propostos para a mesma propriedade, e os dois primeiros pareciam
completos:

1. *varredura única* — correta por estágio, e o pipeline tem três estágios;
2. *o valor não pode carregar sintaxe* — correta sobre o valor, e as chaves podem vir do
   template;
3. *o render não pode introduzir token que o texto não tinha* — sobre o resultado.

O padrão: **os dois primeiros descrevem o mecanismo; o terceiro descreve o efeito.** Um
fechamento que descreve o mecanismo fecha o caminho que o autor imaginou. Só o que
descreve o efeito fecha os que ele não imaginou — e é a diferença entre as duas coisas
que esta épica inteira está medindo.

---

## Rodadas 2 a 5 da crítica — o desenho por eliminação

Cinco propriedades foram propostas para a mesma pergunta. As quatro primeiras leem como
completas, e cada uma caiu com medição, não com argumento:

| # | propriedade | quem derrubou, e com o quê |
|---|---|---|
| 1 | varredura única (o fechamento da rodada 2 de 12/08) | correta **por estágio**, e o pipeline tem três |
| 2 | o valor não pode carregar token completo | as chaves podem vir do **template**: `{{{{ORG_NAME}}}}` com o valor inocente `PIX_PAYLOAD` |
| 3 | a saída não pode ter token que a entrada não tinha | compara **conjunto**: o segredo é realojado dentro de um arquivo que já carregava o token — PIX no título |
| 4 | posicional + queda **por arquivo** | irmão cru ao lado de renderizado ⇒ fonte e alvo discordam ⇒ deriva, `.kit-new`, arquivo protegido congelado (`ade371f5#6`) |
| 5 | posicional + queda **por corrida** | raio de explosão: um arquivo componível em qualquer lugar da árvore congela `AGENTS.md` de todo alvo sem entrada de manifesto |
| **6** | **posicional + queda por arquivo E por token** | — |

**O padrão, e é o que esta issue tem a ensinar:** as propriedades 1 e 2 descrevem o
*mecanismo*; a 3 descreve um *sintoma*; só a 6 descreve o *efeito*. Um fechamento que
descreve o mecanismo fecha o caminho que o autor imaginou.

E o congelamento chegou **três vezes por portas diferentes** — por arquivo, por corrida,
e por contabilidade (a poda do `table` pela união, que alimentava a persistência: valor
no disco, ausente do estado). Da terceira vez, três lentes independentes o acharam com
reproduções diferentes, e era **uma linha escrita duas vezes**.

### Três camadas, cada uma no nível certo

1. **valor** — `_render_table` recusa `{{` ou `}}`; nenhum slot declarado precisa de chave
2. **texto distribuído** — `tests/test_render_gate.py` roda a propriedade real contra a
   árvore que `_prerender_source` renderiza, e **falha** (não pula) sem o corpus
3. **runtime** — `_render_file_text`: nenhum casamento na saída pode sobrepor texto vindo
   de um valor substituído; queda por arquivo e por token, até ponto fixo

### O que a crítica pegou além da cadeia

- **Vazamento de valor real**: `parse_set_pairs` ecoava o argumento cru e `cli.py:877`
  chamava `parser.error` num escopo sem `parser` — um `--set` mal digitado imprimia o
  payload PIX dentro de um traceback. Fechado: `rc=2`, saída limpa, zero eco.
- **E a regressão do meu próprio conserto**: o aviso novo protegia o *valor* e ecoava a
  *chave*, que é o mesmo texto livre do operador. Fechado por forma de token.
- Regressão do teto (4096 nos escritores do alvo des-renderizava arquivo já renderizado);
  `result.values` contando resposta gravada em vez de variável preenchida; `--set` com
  chave desconhecida sumindo em silêncio, depois abortando a corrida inteira, até
  assentar em **nomear e continuar**.

### Verificação

**571 passed.** Matriz de mutação vermelha para cada propriedade e cada escritor.

A matriz apontou **verde quatro vezes** onde eu supunha cobertura — `_prerender_source`
sem teste de queda de token, o `already`, o caminho de erro da CLI, e a proteção contra
ecoar a chave. Cada uma virou teste. É a lição de `AC-11`/`AC-17`/`AC-18` acontecendo ao
vivo: **teste que existe não é teste que morde**, e só a mutação distingue os dois.

### Uma retratação, registrada porque o instrumento depende dela

O *fix auditor* afirmou na rodada 2 que a correção plantava o próprio gatilho — que
`_prerender_source` renderizaria `governancekit/` e `tests/` do tarball. Verifiquei:
`REPO = "EDortta/AI-Agents"`, `src_root` só vem de `_download`, não há origem local, e o
AI-Agents não contém nenhum dos dois diretórios. Ele montara a árvore à mão. Confrontado,
**verificou por conta própria e retirou o achado por escrito**, chamando-o de *"reprodução
sem gatilho — o defeito exato que a minha lente existe para pegar"*.

A **classe** que ele apontou era real e virou a camada 2. Um cético que se retrata com
verificação vale mais que um que nunca erra: `council.md` §2 diz que confiança de agente
não é evidência, e isso vale nos dois sentidos.

### Aberto, e não é para esta issue resolver

- **`--unset` / `AC-21`** — decisão do operador, nos termos da lente de LGPD: adiar é
  defensável **condicionado** a `AC-21` sair na mesma release que a mudança do `--set`;
  senão, restaurar o filtro por `found` até lá.
- **O gate de CI lê a árvore local, não o ref pinado** que `_download` busca. Fechar isso
  exige o mecanismo do `_kit_snapshot.json` (épica `013`) e é outra entrega.
- **O quarto escritor** (`apply_identity`, `install-agents-kit.sh:606-665`) segue sem
  nenhuma das três camadas. `AC-6`/`AC-10`, bloqueadas em decisão de escopo cruzando
  repositório.
