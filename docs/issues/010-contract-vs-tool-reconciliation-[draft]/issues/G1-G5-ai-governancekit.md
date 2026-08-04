# Issues — repositório `AI-GovernanceKit`

Cinco issues. Metadados comuns a todas:

- work_id: `WK-20260804-governancekit-contract-reassessment`
- date: 2026-08-04
- owner: Esteban D.Dortta
- parent epic: `epic.md` — Reconciliar contrato AI-Agents e ferramenta GovernanceKit
- versão observada: GovernanceKit `0.2.3`, executada em `AI/CodexBridge` em 2026-08-04

---

## G1 — `doctor` deve reprovar incoerência entre o texto instalado e o que ele verifica [crítica]

### Objective

Esta é a issue que impede a recorrência de toda a classe de defeitos deste épico.

Hoje o `doctor` verifica **o estado do disco** contra as regras que ele conhece. Não
verifica se o **contrato instalado no mesmo repositório** descreve as mesmas regras.
Quando os dois divergem, o `doctor` devolve `PASS` para um repositório em que o
`AGENTS.md` manda parar.

### Evidência — `AI/CodexBridge`, 2026-08-04 17:26

```
$ governancekit doctor
[PASS] docs/software-overview.md: contains `project_context_ready: yes`
[PASS] docs/limits.md: contains `limits_ready: yes`
[PASS] AI-Agents integration contract: AI-Agents contract v1.1.6 is compatible with GovernanceKit 0.2.3

$ ls .docs/software-overview.md .docs/limits.md
ls: cannot access '.docs/software-overview.md': No such file or directory
ls: cannot access '.docs/limits.md': No such file or directory

$ grep -c 'docs/limits\.md' AGENTS.md      # §1b: "If either file is missing: Stop implementation."
4
```

O agente que obedece o contrato para. A ferramenta que audita o contrato passa. E é o
próprio `doctor` que carimba `[PASS]` na linha de compatibilidade entre as duas versões
que discordam.

Aqui o `doctor` passa **por acaso**: os arquivos existiam em `docs/` porque foram
escritos ali manualmente, por conta própria, antes de qualquer migração.

### In Scope

Nova verificação `contract coherence`: para cada caminho que o `doctor` verifica, se
algum arquivo do kit instalado (`AGENTS.md`, `.docs/**`, o bloco gerenciado de
`docs/required-reading.md`) referenciar um caminho **diferente** para o mesmo
conceito, isso é `FAIL`.

Mínimo viável para o defeito de hoje:

```
[FAIL] contract coherence: AGENTS.md:99 requires `.docs/software-overview.md`,
       doctor verifies `docs/software-overview.md` — the Start Gate points at a
       path this release migrated away from
```

Cobrir pelo menos: os dois arquivos de readiness, o arquivo de identidade (A5/G3), e o
caminho do monitor de atividade (A7).

### Out of Scope
- Corrigir o texto — é A1, no repositório AI-Agents.
- Verificação semântica genérica do contrato. O alvo aqui é um conjunto pequeno e
  nomeado de caminhos load-bearing.

### ARO
- **Acceptance:** com o texto de hoje instalado, `doctor` devolve `FAIL`. Com o texto
  de A1 instalado, `PASS`.
- **Risk:** falso positivo em prosa que cita o caminho antigo como exemplo histórico
  (CHANGELOG, artigo explicando a migração). Restringir a verificação aos arquivos que
  são contrato (`AGENTS.md`, `.docs/agents/`, `.docs/workflows/`, `.docs/context-manifest.yaml`,
  bloco gerenciado do `required-reading.md`), deixando `.docs/articles/` fora ou em
  `HINT`.
- **Operations:** G1 sozinho reprova todas as instalações existentes. Precisa sair no
  mesmo ciclo que A1, ou entrar primeiro como `HINT` e virar `FAIL` no release seguinte.

### Test Plan
- Fixture com `AGENTS.md` apontando `.docs/` e arquivos em `docs/` → `FAIL`.
- Fixture coerente → `PASS`.
- Fixture com o caminho antigo citado apenas num artigo → não falha (ou falha como
  `HINT`, conforme a decisão de escopo).

### Security
Indireto e relevante: o `PASS` do `doctor` é o sinal em que o operador confia para
concluir que o projeto está governado. Um `PASS` sobre um gate inoperante é pior que
nenhum sinal.

### Privacy
Personal data impact: não.

### DoD
- Verificação implementada, com o conjunto de caminhos load-bearing nomeado em um só
  lugar do código.
- Fixtures dos três casos no CI.

---

## G2 — A checagem de compatibilidade é só numérica [alta]

### Objective

```
[PASS] AI-Agents integration contract: AI-Agents contract v1.1.6 is compatible with
       GovernanceKit 0.2.3
```

Foi essa linha que carimbou verde a divergência de G1. A checagem compara faixas de
versão declaradas em `.docs/governancekit-integration.json`:

```json
{"ai_agents": {"repo": "EDortta/AI-Agents", "ref": "v1.1.6"},
 "governancekit": {"version_range": ">=0.2.2,<0.3.0",
                   "required_features": ["version-reporting", "doctor-advisory", "install-agents-manifest"]}}
```

Nada nessa estrutura descreve **onde ficam os arquivos**. A migração de readiness
mudou um contrato de caminho sem mudar nenhum número que a checagem observa.

Nota lateral: o `--version` reporta `AI-Agents project: v1.1.7` e o `.gk/manifest.json`
diz `ref: v1.1.7`, enquanto o contrato de integração diz `v1.1.6`. A instalação de
hoje trouxe o v1.1.7 sem atualizar o arquivo que declara qual ref está em uso — a
checagem valida uma versão que não é a instalada.

### In Scope
- Acrescentar às `required_features` (ou a um bloco `paths`) o contrato de caminho:
  onde ficam readiness, identidade e monitor. A compatibilidade passa a exigir
  coincidência de caminho, não só de número.
- Corrigir a atualização de `ref` no `governancekit-integration.json` durante o
  `install-agents` — hoje o manifesto e o contrato de integração ficam dessincronizados.

### Out of Scope
- A verificação de coerência contra o texto — é G1. Esta issue é sobre o
  arquivo de contrato entre os dois componentes.

### ARO
- **Acceptance:** instalar AI-Agents v1.1.7 (que ainda diz `.docs/`) sobre
  GovernanceKit 0.2.3 (que usa `docs/`) resulta em incompatibilidade declarada, não em
  `[PASS]`.
- **Risk:** endurecer a checagem antes de A1 sair bloqueia a combinação hoje em campo.
  Sequenciar depois de A1 e A2.

### Test Plan
- Matriz de duas versões incompatíveis por caminho → `FAIL`.
- `install-agents` → `ref` no `governancekit-integration.json` bate com o
  `.gk/manifest.json`.

### Security
Não aplicável diretamente.

### Privacy
Personal data impact: não.

### DoD
- Contrato de integração descreve caminhos; `ref` sincronizado na instalação.

---

## G3 — `install-agents` termina deixando a identidade obrigatória ausente [alta]

### Objective

`AGENTS.md` §8b é `[MANDATORY]`: *"Before any action, read/establish this instance's
identity file. If it is absent → **STOP**. Do not inspect, branch, edit, or commit
until identity is established."*

A instalação de hoje terminou com sucesso e deixou o arquivo ausente. O `doctor`
detecta — o que é um ganho real desta versão — mas ninguém para:

```
[FAIL] host identity: .governancekit-identity.json missing or unreadable —
       run 'governancekit configure' to collect operator_name, host_id and instance_path
```

Ou seja: o instalador produz, por construção, um repositório em que o contrato manda o
agente não fazer nada. Todo projeto recém-instalado nasce nesse estado.

Agravante: o instalador **coletou e usou** dados de operador — os slots `{{…}}` do
`AGENTS.md` foram preenchidos com nome e e-mail a partir de `.gk/operator.json`. A
informação estava à mão; o arquivo que o contrato exige simplesmente não foi escrito.

### In Scope
- `install-agents` chama (ou oferece) `configure` quando a identidade não existe, e o
  resultado da instalação relata explicitamente o estado da identidade.
- Consolidar a identidade num arquivo só, alinhado com A5 — `.gk/operator.json` já tem
  `OPERATOR_NAME`; faltam `host_id`, `instance_path`, `sibling_path`, `assigned_ports`,
  `branch_ownership`.
- Ou documentar `.gk/operator.json` como sendo o arquivo de identidade, e A5 alinha o
  contrato a ele. O importante é que existam **um nome e um schema**, não dois.

### Out of Scope
- O texto de §1a/§8b — é A5.

### ARO
- **Acceptance:** após `install-agents` em repositório limpo, `doctor` não reporta
  `[FAIL] host identity`, ou a instalação avisa em alto e bom som que o passo
  `configure` é obrigatório antes de qualquer trabalho.
- **Risk:** `configure` interativo em instalação não-interativa (CI, script). Prever
  modo não-interativo com valores derivados (`hostname`, `pwd`) e marcação de
  "provisório" para o que exigir humano.
- **Operations:** `host_id` e `assigned_ports` são justamente os campos que não podem
  ser adivinhados em projetos de branch compartilhada — que é o cenário que §8b existe
  para proteger.

### Test Plan
- Instalação limpa não-interativa → identidade mínima criada, `doctor` limpo.
- Instalação em projeto com identidade legada → nada é sobrescrito.

### Security
Direto: §8b existe para tornar auditável "qual host fez o quê" em projetos de branch
compartilhada. Sem o arquivo, a auditoria não existe.

### Privacy
Personal data impact: **sim** — `operator_name`. Garantir que o arquivo permaneça
não rastreado (hoje `.gk/operator.json` está no `.gitignore` gerenciado e em modo 600;
preservar as duas propriedades).

### DoD
- Nenhuma instalação bem-sucedida termina num estado que o contrato define como STOP.

---

## G4 — Não há trilha de aplicação: o kit muda sob o agente sem registro [média]

### Objective

O kit chega por pasta sincronizada e é aplicado por execuções que não deixam
histórico. Durante **uma única sessão de trabalho** neste projeto, em 2026-08-04:

- 11:45 — o kit aparece inteiro e altera o `.gitignore`, arquivo rastreado;
- 12:54 — `.docs/limits.md` e `.docs/software-overview.md` desaparecem;
- 17:20 — nova execução, novo `.gitignore`, novo `manifest.json`.

Do ponto de vista do agente, o repositório mudou sozinho duas vezes no meio do
trabalho. A única forma de reconstruir o que houve foi comparar `mtime` e ler o
código-fonte do pacote instalado — foi assim que se descobriu que 12:54 não era
apagamento, e sim a migração de readiness.

O `.gk/manifest.json` guarda 91 hashes e `ref: v1.1.7` — ótimo para integridade,
inútil para histórico: `metadata` está vazio, não há timestamp, não há host, não há
lista do que aquela execução tocou.

### In Scope
- `.gk/install-log.jsonl`, append-only, uma linha por execução:
  `{ts, host, gk_version, agents_ref, action, files_touched, notes}`.
- As `notes` já existem e hoje só vão para stdout — a migração de readiness produz
  exatamente as mensagens que deveriam estar no log:
  `"readiness: CONFLICT on limits.md — docs/limits.md kept as authoritative; the
  .docs/ copy is at .gk/readiness-migration/limits.md for review"`.
- Rastrear o log em git (como o `manifest.json`, e diferente do `operator.json`): é
  história do repositório, não estado local.
- `doctor` e `resume` podem citar a última entrada ("kit aplicado em <ts> por <host>").

### Out of Scope
- Rollback. O objetivo é saber o que aconteceu, não desfazer.

### ARO
- **Acceptance:** após duas execuções, o log tem duas entradas e permite reconstruir o
  que mudou em cada uma sem recorrer a `mtime`.
- **Risk:** ruído no diff a cada instalação. Uma linha por execução é aceitável.

### Test Plan
- Duas execuções seguidas → duas linhas; a segunda, idempotente, registra
  `files_touched: []`.

### Security
Indireto: modificação não registrada de arquivo rastreado por processo externo é
exatamente o que uma trilha de auditoria existe para tornar visível.

### Privacy
Personal data impact: baixo — `host` e possivelmente nome do operador. Se `operator_name`
entrar no log e o log for rastreado, usar apenas `host_id`.

### DoD
- Log implementado, rastreado, e citado por `doctor`/`resume`.

---

## G5 — CI não executa `doctor` depois de `install-agents` [alta]

### Objective

O defeito de A3 — o bloco `.gitignore` escrito pelo instalador que o próprio `doctor`
reprova — teria sido pego por **um teste de duas linhas**:

```
governancekit install-agents --target <fixture> --upgrade
governancekit doctor --root <fixture>   # deve terminar limpo
```

Seis minutos separaram, neste projeto, o instalador escrever o bloco (17:20) e o
`doctor` reprová-lo (17:26). Mesma ferramenta, mesma versão. Nenhum teste faz esse par.

### In Scope
- Teste de integração no CI: instalação limpa em fixture, seguida de `doctor`, falhando
  o build se o `doctor` reprovar qualquer coisa que a instalação era responsável por
  produzir.
- Distinguir os `FAIL` legítimos de projeto vazio (`docs/issues: missing`,
  `RESUME.md next step: no resume file found`) dos que são responsabilidade do
  instalador (`gitignore secrets`, `host identity`, `unfilled placeholders`,
  `AI-Agents manifest`, e o `contract coherence` de G1). Uma lista explícita de "o
  instalador deve deixar isto limpo" é o próprio contrato entre as duas metades.
- Rodar a mesma matriz também com `install-agents-kit.sh`, enquanto ele existir (A2).

### Out of Scope
- Cobertura de teste do `doctor` em si.

### ARO
- **Acceptance:** o defeito de A3, reintroduzido de propósito, quebra o CI.
- **Risk:** fixture divergindo de repositório real. Usar pelo menos duas: uma vazia e
  uma com projeto já governado por versão anterior.

### Test Plan
- Fixture vazia → só os `FAIL` da lista permitida.
- Fixture com kit v1.1.6 instalado → upgrade → `doctor` limpo.
- Regressão de A3: remover `.env` do bloco gerenciado → CI vermelho.

### Security
Direto: as verificações que o instalador precisa deixar limpas são, na maioria,
controles de segredo e de identidade.

### Privacy
Personal data impact: não — usar fixtures com valores sintéticos, nunca a identidade
real do operador.

### DoD
- Par `install-agents` + `doctor` no CI, com a lista de verificações que a instalação
  é responsável por deixar limpas declarada explicitamente.
