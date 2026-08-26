# Issue AC-9 — origem: concílio de fechamentos, 2026-08-13 (lente: the migrator)

## AC-9 — o remédio destrói o texto do projeto que promete guardar [alta]

### Contexto

O fechamento de `ade371f5#4` reescreveu o remédio do check `§Sending Email` para o
portador `.docs/workflows/sending-email.md`, e o remédio hoje afirma
(`doctor.py:718-728`):

> *the kit's version replaces it and yours is stashed under `.gk/overwritten/` for
> comparison*

Em `_sync_dir` (`install_agents.py:1036-1053`) o stash só acontece quando
`known.get(rel)` **não é None** — isto é, quando existe entrada no `.gk/manifest.json`
para aquele arquivo. Sem entrada:

- o arquivo do projeto é sobrescrito
- **nenhuma** cópia em `.gk/overwritten/`
- **nenhuma** cópia em `.gk/pre-upgrade/` (esse só existe em `_replace_kit_file`)

E quem não tem entrada de manifesto? Exatamente a população que este check foi escrito
para achar — o comentário em `doctor.py:650-653` diz isso. O instalador shell imprime
literalmente `WARN: python3 not found — skipping .gk/manifest.json`, e qualquer
instalação pré-manifesto tem a mesma forma.

**Seguir a instrução do kit destrói o texto do projeto**, e a instrução promete o
contrário.

### Reprodução

```
=== legacy: no manifest entry
  result.overwritten_edits : []
  file now on disk         : '# Sending Email\n\nKIT v1.2.1 canonical body.\n'
  .gk/overwritten/ copy    : False
  .gk/pre-upgrade/ copy    : False
  project text recoverable : False
=== current: manifest entry present
  result.overwritten_edits : ['.docs/workflows/sending-email.md']
  .gk/overwritten/ copy    : True
  project text recoverable : True
```

### Objetivo

Que nenhum arquivo do projeto seja sobrescrito sem cópia, independentemente de haver
entrada no manifesto — e que o remédio só prometa o que o código faz.

### Escopo

- `_sync_dir` guarda cópia **antes de sobrescrever**, sempre. A ausência de entrada de
  manifesto significa "não sei o que é este arquivo", que é razão para guardar **mais**
  cuidado, não menos. Hoje significa o contrário.
- O remédio do `doctor` descreve o que vai acontecer no estado real do alvo. Se o alvo
  não tem manifesto, ou o texto muda, ou o comando passa a se comportar como o texto diz
  (preferível).
- Varrer os outros ramos que decidem por `known.get(rel) is not None` — a pergunta é se
  algum outro caminho de escrita herda a mesma assimetria.
- Casa com `AC-5` e `AC-6`: os três são "a população sem estado completo cai num ramo que
  ninguém projetou para ela".

### ARO

- **Assumption**: guardar cópia de tudo que se sobrescreve é barato. `.gk/` é
  gitignorado e os backups já são limpos por upgrade (ver `AC-12`).
- **Risk**: guardar sempre aumenta `.gk/overwritten/`. Aceitável, e é o mesmo custo que
  a população com manifesto já paga.
- **Risk**: interação com `AC-12` — se o `rmtree` de backups roda antes, a cópia nova
  pode ser apagada na corrida seguinte. As duas issues precisam ser lidas juntas.
- **Owner**: a definir.

### Plano de teste

- Alvo **sem** entrada de manifesto + `--upgrade` que substitui o arquivo ⇒ o texto do
  projeto é recuperável em `.gk/overwritten/`.
- `result.overwritten_edits` lista o arquivo nos dois casos (com e sem manifesto).
- O texto do remédio corresponde ao comportamento nos dois casos.
- Mutação: voltar a condicionar o stash a `recorded is not None` ⇒ teste vermelho.

### DoD

- Nenhuma sobrescrita sem cópia, provado nos dois estados de manifesto.
- O remédio não promete o que não acontece.
- Teste verificado por mutação.
