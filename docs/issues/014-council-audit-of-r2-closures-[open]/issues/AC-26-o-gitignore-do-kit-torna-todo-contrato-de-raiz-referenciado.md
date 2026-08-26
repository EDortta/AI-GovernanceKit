# Issue AC-26 — origem: crítica do grupo remove-agents, 2026-08-13 (lente: the second caller)

## AC-26 — o kit se cita no `.gitignore` e a de-adoção nunca remove contrato de raiz [alta]

### Contexto

`_update_gitignore` escreve, no bloco gerenciado do `.gitignore` da raiz, os nomes
literais dos contratos que o kit instala:

```
AGENTS.md
.cursorrules
CLAUDE.md
.windsurfrules
GEMINI.md
```

`_referenced` procura o literal do caminho em todo arquivo de texto do projeto, e exclui
apenas `*.kit-new` e `.git`/`.gk`. O `.gitignore` não está excluído.

Resultado: **em todo alvo instalado**, cada contrato de raiz lê como `referenced`, o
guarda `and not referenced` desvia, e `remove-agents plan` devolve:

```
preserve: AGENTS.md    [kit-owned-but-referenced] (review required)
preserve: .cursorrules [kit-owned-but-referenced] (review required)
evidence: ['manifest records this path',
           'current file still matches the recorded install hash',
           'path is referenced elsewhere in the project']
```

Num projeto limpo, não modificado, com o hash batendo exatamente, **nenhum contrato de
raiz é removível**. É o sintoma de `6bb1027e#3` — *"a de-adoção deixa o andaime do kit no
disco"* — um diretório ao lado. E a evidência aponta, como razão para preservar, um
arquivo que **o próprio kit gerou**.

O docstring de `_referenced` já enuncia o princípio que isto viola:

> *"The kit quoting itself is not the project depending on it."*

A exclusão que existe (`*.kit-new`) foi escrita para um caso menor. O caso maior é
universal e ninguém o viu porque **os testes de remoção montam alvos sem `.gitignore`**.

### Por que não é achado contra `AC-2`/`AC-3`/`AC-4`/`AC-5`

Nenhum DoD do grupo é violado: o plano e o `apply` concordam (os dois preservam), e a
evidência é **literalmente verdadeira** — o `.gitignore` está no projeto e cita o caminho.
O defeito é anterior ao grupo e o grupo não o agrava. Ele só ficou visível porque
`AC-3` acrescentou a classe `kit-owned-but-referenced`, que o nomeia em vez de escondê-lo
sob `kit-owned-modified`.

### Objetivo

Que a citação que o kit faz de si mesmo não conte como dependência do projeto — em
`.gitignore` como já não conta em `*.kit-new`.

### Escopo

- `_referenced` ignora o bloco **gerenciado** do `.gitignore` da raiz. Não o arquivo
  inteiro: uma linha que o operador escreveu fora do bloco é dependência de verdade.
  Os marcadores do bloco já existem e são a fronteira natural.
- Varrer os outros arquivos que o kit escreve e que citam caminhos do kit —
  `docs/codemap.md`, `docs/required-reading.md`, o `README` semeado. Cada um é uma
  citação do kit sobre si mesmo, e o princípio vale para todos.
- **Os testes de remoção passam a montar alvo com `.gitignore` real.** Montar alvo sem
  ele é o que escondeu isto, e é a mesma classe de `AC-3`: o fixture não representava a
  população.
- Decidir e escrever o que `referenced` significa: *"algo que não é o kit aponta para
  este caminho"*. Hoje significa *"o literal aparece em algum arquivo de texto"*.

### ARO

- **Assumption**: o bloco gerenciado é sempre delimitado pelos marcadores. Se um
  instalador (o shell, por exemplo) escrever sem eles, a exclusão erra — ver `AC-10`.
- **Risk**: ignorar demais faz um caminho realmente citado passar por não citado, e aí a
  de-adoção apaga algo de que o projeto depende. Mitigação: excluir por bloco delimitado,
  nunca por nome de arquivo.
- **Risk**: alvos que hoje preservam tudo passam a oferecer remoção de verdade. É o
  comportamento correto e é mudança visível — pede nota de release.
- **Owner**: a definir.

### Plano de teste

- Alvo instalado, com `.gitignore` gerenciado real, hashes batendo ⇒ os contratos de raiz
  saem `remove`.
- Linha escrita pelo operador **fora** do bloco citando `AGENTS.md` ⇒ continua
  `referenced` e é preservado.
- `*.kit-new` continua excluído (o teste existente não pode regredir).
- Mutação: parar de excluir o bloco ⇒ vermelho.

### DoD

- A citação que o kit faz de si mesmo não conta como dependência do projeto.
- Os fixtures de remoção representam um alvo instalado de verdade.
- O significado de `referenced` está escrito.
