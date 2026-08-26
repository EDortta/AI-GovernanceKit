# Plano unificado — GovernanceKit + AI-Agents

- work_id: `WK-20260813-plano-unificado`
- criado: 2026-08-13, por ordem do operador
- alvo de execução: `scripts/run_plan.py`, desarmado do boot ao terminar

Tudo que falta nos dois repositórios, numa ordem só. As dependências são reais — várias
issues se destravam ou mudam de forma dependendo do que já entrou.

---

## Decisão nova desta sessão: `manifest.override.json`

O operador definiu a separação que faltava:

| arquivo | o que carrega | destino |
|---|---|---|
| `.gk/manifest.json` | **a configuração do kit no projeto** | commitado, compartilhado |
| `.gk/manifest.override.json` | **dado sensível do operador local** | gitignorado, por máquina |

Isto resolve por desenho três achados que hoje são issues separadas:

- **`AC-20`** — o filtro assimétrico do `_read_state` deixa de ser remendo: o que é do
  operador não mora mais no arquivo compartilhado, então não há o que filtrar na leitura.
- **`AC-22`** — o hash de arquivo renderizado com dado pessoal sai do arquivo commitado.
- **`AC-13`** — o `--set` que gravava chave arbitrária no manifesto rastreado passa a ter
  um destino correto para o que é local.

E substitui `.gk/secrets.json`, que esta sessão descobriu não existir em projeto nenhum.
A regra fica: **o manifesto diz o que o kit é neste projeto; o override diz o que esta
máquina sabe.**

---

## Fase 0 — fechar o que está na árvore de trabalho (não commitado)

Já implementado nesta sessão, com concílio passado, **exceto** a última rodada:

| item | estado |
|---|---|
| `AC-1` render gate | concílio verde (4/4), 5 rodadas |
| `AC-2`/`AC-3`/`AC-4`/`AC-5` remove-agents | concílio verde (4/4), 3 rodadas |
| `AC-25` exfiltração por manifesto | corrigido, **rodada de confirmação pendente** |
| `AC-28` mailbox + retirada dos slots de doação | corrigido pós-concílio, **confirmação pendente** |
| retirada de `.docs/index.html` | implementado, **sem concílio** |

**Primeiro passo do script:** uma rodada de concílio sobre a árvore inteira, e a emenda
do `AC-28`, cujo texto descreve um desenho (`SMTP_ACCOUNT` de volta a
`_PLACEHOLDER_DESCRIPTIONS`) que não foi o implementado — `OPERATOR_EMAIL` em
`identity.json` é melhor e o registro precisa dizer isso, ou o próximo concílio lê deriva.

---

## Fase 1 — o override, porque destrava três issues

1. **`AC-29` (nova) — `manifest.override.json`.** Criar o arquivo, o leitor, a entrada no
   bloco gerenciado do `.gitignore`, e a migração: o que hoje está em `operator.json`
   e no que sobrou de `secrets.json` passa a viver ali. `_read_state` funde os dois com
   o override vencendo, e **nunca** escreve override no manifesto.
2. **`AC-21` — caminho de eliminação.** Depende de 1: com o override existindo, eliminar
   é remover chave de um arquivo local. Inclui `configure --unset` e a limpeza que a
   de-adoção não faz (`operator.json`, `override`, e o backup que hoje **copia** arquivo
   renderizado).
3. **`AC-20`, `AC-22`, `AC-13`** — reavaliar. Provavelmente encolhem para um teste cada,
   afirmando que dado de operador não alcança o arquivo commitado.

---

## Fase 2 — o defeito de campo, que tem gente parada

4. **`AC-23` (GitHub #8)** — três varreduras de placeholder com três escopos. `.docs/**`
   nunca é preenchido, o `doctor` diz `[PASS]`, e os agentes travam em `git-delivery.md`.
   Uma varredura, um escopo, três chamadores. **É o único com usuário bloqueado hoje.**
5. **`AC-15`** — remédios do `doctor` que não funcionam sem TTY. Anda junto: corrigir o
   escopo de `AC-23` faz o check falhar, e aí o remédio precisa estar certo.

---

## Fase 3 — a aposentadoria do bash (cruza repositório)

O operador liberou os dois repositórios e a aposentadoria.

6. **`AC-30` (nova) — aposentar `install-agents-kit.sh`.** Funde `AC-6` e `AC-10`, que
   deixam de ser "sincronizar o shell" e viram "o shell sai". Requisito acrescentado
   pelo operador: **o GovernanceKit remove as versões bash já instaladas** — mesmo
   mecanismo de `_WITHDRAWN_PATHS`, que a retirada do `index.html` acabou de estrear.
7. **`AC-7` + `AC-14`** — deixam de ser conserto de shell e viram **porte para Python**:
   `validate-governance.sh`, `verify-elo4.sh`, `merge-to-main.sh`. Os dois defeitos
   somem com a linguagem (`python3 -m` resolvendo do site-packages; `grep` contando
   prosa).
8. **`.credentials/.gitignore` não cobre `llm/`** — entra aqui, porque toca o AI-Agents.

---

## Fase 4 — o que o produto declara sobre si

9. **`AC-24`** — os seis slots de doação já saíram do código; falta a lista derivada
   (todo slot declarado aparece em algum arquivo do ref pinado) e a decisão escrita
   sobre os cinco não financeiros que também não são usados.
10. **`AC-27`** — a escolha de LLM por projeto é suportada e a interface a esconde.
    Inclui o caminho não interativo.
11. **`AC-28`** (emenda + o que falta) — instrução guiada em HTML, `SMTP_DOMAIN` como
    derivação já feita, `.credentials/README.md` nas três línguas.

---

## Fase 5 — os testes que não mordem

12. **`AC-11`**, **`AC-16`**, **`AC-17`**, **`AC-18`** — quatro instâncias de uma lição
    só: teste que existe não é teste que morde. Fazer juntos, com a lição escrita **uma**
    vez em `napkin-lessons.md`.
13. **`AC-26`** — o bloco do `.gitignore` cita os contratos de raiz, então a de-adoção
    nunca remove `AGENTS.md`. Inclui montar fixtures com `.gitignore` real, que é o que
    escondeu o defeito.
14. **`AC-8`**, **`AC-9`**, **`AC-12`** — symlink em `classify_document`, cópia antes de
    sobrescrever, migração dos backups.

---

## Fase 6 — o registro

15. **`AC-19`** — as quatro contagens derivadas, não digitadas, e `council --record`
    exigindo-as. **Por último de propósito:** ele mede o que as fases anteriores
    produziram, e medir antes de existir é o defeito que ele registra.
16. **Concílio geral final** — as cinco perguntas do operador: (a) o programador ganha
    token e celeridade; (b) sem repetições; (c) sem contradições; (d) inglês simplificado;
    (e) os agentes leem a documentação ou acham atalhos.

---

## Regras que valem para toda a execução

- **Nada de bash.** Decisão do operador. O runner é Python; os scripts portados são
  Python.
- **Cada issue:** implementar → concílio de quatro lentes → aplicar as críticas coerentes
  → concílio de novo → até verde → commit → merge em `development`.
- **Nunca `main`.** `main` recebe só produto, por `merge-to-main`, e nunca daqui.
- **Nunca tocar projeto de terceiro.** Os três alvos com `.docs/index.html` só ficam
  limpos quando o operador rodar `--upgrade` neles. O script não roda.
- **Versão:** um bump de sub-versão por fase concluída, não por issue.
- **O registro é derivado.** Toda contagem que o script escrever tem que sair de um
  comando, nunca de uma soma feita por um agente.
