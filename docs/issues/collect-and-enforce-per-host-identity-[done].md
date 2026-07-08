# Runtime deve coletar e exigir a identidade individual do programador/host

- work_id: WK-20260702-per-host-identity-runtime
- date: 2026-07-02
- solicitado por: [OPERATOR_NAME]
- lado do problema: **runtime CLI (AI-GovernanceKit)** — o "como"
- companheira: issue equivalente no **AI-Agents** (lado policy/contrato)

## Motivação

O contrato do policy pack passará a **exigir** identidade individual do
programador/host/instância (ver issue companheira em AI-Agents). Mas contrato
sem enforcement executável é ignorável: em projetos onde vários programadores
trabalham no mesmo projeto e **sobre a mesma branch** (ex.: simulador
jk-structure), a falta de identidade individual causa colisões silenciosas de
branch, portas e artefatos de runtime.

Hoje o kit já substitui placeholders como `[OPERATOR_NAME]` em `configure`, mas
**não coleta nem valida** identidade de host/instância, e o `doctor` não falha
quando ela está ausente ou desatualizada.

## Objetivo

Fazer o AI-GovernanceKit **pedir, persistir e validar** os campos de
individualização, tornando-os obrigatórios — de modo que nenhum host opere um
projeto governado sem identidade verificável.

## Escopo

- `governancekit/configure.py` — coletar os campos de identidade no setup
  (prompt interativo + flags não-interativas para CI), persistir em um arquivo
  de identidade local (gitignored, por instância).
- `governancekit/doctor.py` — adicionar checagem: identidade presente, completa
  e não obviamente obsoleta; emitir `[FAIL]` quando ausente/incompleta.
- `governancekit/resume.py` — exibir a identidade ativa (operator/host/branch)
  no início da sessão.
- Sem alterar o contrato em si (isso é a issue companheira do AI-Agents).

### Campos (alinhados ao schema do contrato)

`operator_name`, `host_id`, `instance_path`, `sibling_path`,
`assigned_ports`, `branch_ownership`.

### Comportamento requerido

- [MANDATORY] `configure` pergunta e grava esses campos; recusa concluir se
  faltarem os obrigatórios.
- [MANDATORY] Arquivo de identidade é **local/gitignored** (não vaza entre
  hosts) e nunca contém segredos.
- [MANDATORY] `doctor` retorna `[FAIL]` (e `ok:false` no `--json`) quando a
  identidade está ausente/incompleta; mensagem aponta como corrigir.
- [DEFAULT] Em projeto de branch compartilhada, `doctor`/`resume` avisam se a
  branch atual coincide com a de uma instância irmã declarada.

## Comportamento esperado

- Antes: `doctor` passa mesmo sem qualquer identidade de host; colisões
  silenciosas.
- Depois: setup coleta identidade; `doctor` barra ausência; `resume` mostra
  quem/qual host está ativo.

## Plano de teste

- `configure` não-interativo sem campos obrigatórios → erro claro.
- `doctor` sem arquivo de identidade → `[FAIL]`, `ok:false`.
- `doctor` com identidade completa → passa.
- `resume` imprime operator/host/branch ativos.
- Testes unitários em `tests/` cobrindo os três comandos.

## Impacto / Risco

- Novo estado local por instância (gitignored). Sem segredos.
- Depende do schema definido na issue companheira do AI-Agents — alinhar nomes
  de campo antes de implementar.

## Definition of Done

- `configure`/`doctor`/`resume` implementam coleta/validação/exibição.
- Arquivo de identidade gitignored e documentado.
- Testes passam; `doctor --json` reflete o novo gate.
- Referência cruzada para a issue companheira do AI-Agents.
- Status movido para `[review]` após aplicar.
