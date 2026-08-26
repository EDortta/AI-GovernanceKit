# Issue AC-23 — origem: GitHub `EDortta/AI-GovernanceKit#8`, 2026-08-13 (relato de campo do operador)

## AC-23 — três varreduras de placeholder, três escopos, e o `doctor` cego para o pior deles [alta]

### Contexto

Reproduzido em campo no projeto `wa-hub`, com `governancekit 0.3.0`. Depois de
`install-agents --upgrade` responder ao prompt e reportar sucesso:

```
$ grep -rn '{{[A-Z][A-Z0-9_]*}}' AGENTS.md .docs/
.docs/workflows/git-delivery.md:89:operador (`{{OPERATOR_NAME}}`)**.

$ governancekit doctor
[PASS] unfilled placeholders: all placeholders filled
```

`AGENTS.md` foi preenchido. `.docs/workflows/git-delivery.md` não. O `doctor` afirma que
está tudo preenchido.

O mesmo contrato é lido por **três** varreduras, cada uma com o seu escopo:

| onde | escopo | entra em diretório? | vê o arquivo quebrado? |
|---|---|---|---|
| `install_agents._fill_placeholders` | `result.paths_installed` | **não** | **não** |
| `doctor._check_unfilled_placeholders` | `_PLACEHOLDER_SCAN_PATHS` (6 arquivos de raiz) | n/a | **não** |
| `configure._scan` | `_FRESH_PATHS` | **sim** (`rglob`) | sim |

O ponto exato, em `install_agents.py`:

```python
for rel in installed_paths:
    path = root / rel
    if not path.is_file():
        continue          # <- .docs/workflows, .docs/agents, .credentials saem aqui
```

`paths_installed` **contém entradas de diretório** — a própria saída do comando as lista.
Toda entrada de diretório é descartada em silêncio, e nenhum arquivo abaixo dela é
varrido nem substituído.

### O concílio já tinha achado isto, e como pergunta

Na rodada 3 da crítica de `AC-1`, a lente **the migrator** escreveu:

> *"`_do_upgrade` devolve DIRETÓRIOS como entradas únicas (`installed = ['AGENTS.md',
> '.docs']`), que o `_fill_placeholders` pula em `install_agents.py:1716-1717` porque não
> são arquivos. Então a varredura do lado do alvo enxerga efetivamente só os arquivos de
> contrato da raiz."*

Ela não conseguiu produzir o resultado errado observável — o §2 manda escrever como
**pergunta** nesse caso, e foi o que ela fez. A `#8` é essa pergunta com o gatilho que
faltava. **Uma pergunta em aberto era um defeito vivo em produção**, o que é exatamente o
argumento do `council.md` §2 para escrevê-las em vez de descartá-las.

### O laço fechado que isto produz

1. o agente lê `.docs/workflows/git-delivery.md`, acha `{{OPERATOR_NAME}}` e **para** —
   o contrato manda parar diante de slot não preenchido
2. o agente recomenda `install-agents --upgrade`
3. o operador roda, responde o prompt, vê `Placeholders filled in: AGENTS.md`
4. o arquivo continua com o slot; o agente para de novo, com a mesma recomendação

O comando que os agentes indicam é justamente o único dos três que **não olha** para o
arquivo quebrado. E o arquivo que fica quebrado é o `git-delivery.md` §7b — o que proíbe
deploy autônomo, ou seja, o que nomeia quem precisa aprovar um deploy.

### Objetivo

Uma varredura de placeholder, com um escopo, lida pelos três chamadores.

### Escopo

- **Uma função de varredura compartilhada** por `install-agents`, `configure` e `doctor`,
  com a mesma guarda de symlink/`safe_regular_file` e o mesmo filtro `_is_text_file` que
  `configure._scan` já aplica. `doctor` deixa de ter `_PLACEHOLDER_SCAN_PATHS` próprio.
- É o gêmeo, uma camada acima, do que `AC-1` fez com a **regra de render**: lá eram três
  escritores com três cópias da política; aqui são três leitores com três escopos. O
  comentário de `_GITIGNORE_SECRETS` no mesmo arquivo já enuncia a regra:
  *"Two gates over one contract must read one list, or the newer one drifts and the tool
  ends up refusing what it produces."*
- Interage com `AC-15`: o remédio que o `doctor` nomeia funcionaria — mas o `doctor`
  **passa**, então ninguém chega à mensagem. Corrigir o escopo faz o check falhar, e aí o
  remédio de `AC-15` precisa estar certo.

### ARO

- **Assumption**: todo arquivo de texto instalado pelo kit pode carregar slot. É o que
  `configure._scan` já assume, e é o comportamento correto dos três.
- **Risk**: alargar o escopo do `doctor` pode reprovar alvos do parque que hoje passam —
  e vão reprovar **corretamente**, porque têm slot cru. Precisa de medição no parque antes
  do release, e o remédio tem de funcionar (`AC-15`).
- **Risk**: varrer `.docs/**` inteiro a cada `doctor` custa IO. Mitigação: é o que o
  `configure` já faz.
- **Owner**: a definir.

### Plano de teste

- Instalação limpa + resposta ao prompt ⇒ `grep -r '{{[A-Z]'` no destino **inteiro** volta
  vazio. O teste atual não pega porque exercita slot em arquivo de raiz.
- Alvo com slot cru sob `.docs/workflows/` ⇒ `doctor` **reprova**, e o comando que ele
  nomeia fecha o check.
- Os três chamadores, sobre a mesma árvore, devolvem o **mesmo** conjunto de arquivos.
- Mutação: devolver a `doctor` um escopo próprio ⇒ vermelho.

### DoD

- Uma varredura, um escopo, três chamadores.
- O laço fechado do relato de campo não se reproduz mais.
- `doctor` enxerga o que o instalador deixou para trás.
