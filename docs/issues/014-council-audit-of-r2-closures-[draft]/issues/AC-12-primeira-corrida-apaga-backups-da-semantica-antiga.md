# Issue AC-12 — origem: concílio de fechamentos, 2026-08-13 (lente: the migrator)

## AC-12 — a primeira corrida da versão nova apaga, em silêncio, backups da semântica antiga [média]

### Contexto

Antes de `c7b2838`, `.gk/pre-upgrade/` significava *"o estado antes de **qualquer**
upgrade"* — não havia `rmtree` (verificado em `git show c7b2838^:governancekit/install_agents.py`).
Depois, significa *"o estado antes **deste** upgrade"*.

Mudança de semântica de um artefato **persistido**, sem aviso de migração.

Num alvo que acumulou backups sob a semântica antiga, o primeiro `--upgrade` sob o kit
novo roda `shutil.rmtree` (`install_agents.py:804-807`) antes de qualquer escrita. Se
nada for substituído nessa corrida, `result.backed_up == []`, e a única mensagem que
menciona a limpeza (`cli.py:681-685`) é **condicionada a `result.backed_up`** — então a
CLI não imprime nada.

A única cópia de um arquivo editado à mão, num diretório gitignorado, é apagada em
silêncio total.

### Reprodução

```
before: ['GEMINI.md']       # .gk/pre-upgrade/GEMINI.md, gravado por um upgrade anterior
after : DIRECTORY GONE
result.backed_up: []        # → a CLI não imprime NADA sobre isso
```

### Objetivo

Que uma mudança de semântica de artefato persistido não apague dado sem o operador saber
— nem nesta, nem na próxima.

### Escopo

- A limpeza é anunciada **sempre que apaga algo**, não só quando a corrida também gravou
  backup novo. A mensagem hoje depende da variável errada.
- Migração única: na primeira corrida sob a semântica nova, o conteúdo pré-existente é
  movido para `.gk/pre-upgrade-legacy/` (ou equivalente) em vez de apagado, e a CLI diz
  onde foi. Uma vez, com marca no estado.
- Escrever a regra: **artefato persistido que muda de significado precisa de um passo de
  migração, mesmo que o formato não mude.** `design-standards.md` §4 já cobre o
  princípio; o que faltou foi alguém aplicar a §4 a uma mudança que não tocou schema.
- Interage com `AC-9`: se `AC-9` passa a guardar mais cópias, o `rmtree` alcança mais
  coisa. Ler as duas juntas.

### ARO

- **Assumption**: backups em `.gk/pre-upgrade/` têm valor para o operador. Se não
  tivessem, o diretório não existiria.
- **Risk**: guardar o legado para sempre faz `.gk/` crescer. Mitigação: migrar uma vez,
  marcar no estado, e limpar dali em diante com a semântica nova.
- **Risk**: alvo que nunca teve backup antigo paga o custo do caminho de migração à toa.
  Mitigação: o caminho só roda se houver conteúdo e não houver marca.
- **Owner**: a definir.

### Plano de teste

- Alvo com `.gk/pre-upgrade/` populado pela semântica antiga + primeiro `--upgrade` novo
  ⇒ conteúdo preservado sob o nome legado, e a CLI diz.
- Segundo `--upgrade` ⇒ semântica nova, limpeza normal, mensagem impressa.
- Corrida que apaga e não grava ⇒ **ainda assim** imprime.
- Mutação: condicionar de novo a mensagem a `result.backed_up` ⇒ teste vermelho.

### DoD

- Nada é apagado de `.gk/` sem uma linha na saída.
- O conteúdo da semântica antiga sobrevive à primeira corrida da nova.
- A regra sobre mudança de significado sem mudança de formato está escrita.
