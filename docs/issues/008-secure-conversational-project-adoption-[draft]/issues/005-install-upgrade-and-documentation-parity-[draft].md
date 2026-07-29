# Task 005: Instalação, upgrade e paridade documental

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: draft
- parent: 008-secure-conversational-project-adoption

## Objective

Aplicar o mesmo contrato em instalação, upgrade e sessão retomável, sem degradar
uso não interativo e com documentação equivalente em EN/PT-BR/ES.

## In Scope

- Cenários novo/existente para `install-agents`, `install-agents --upgrade` e
  `config-session start --interactive`.
- Opções explícitas para revisar agora, adiar e pular quando não houver TTY.
- Documentação e ajuda localizadas, inclusive credenciais, agente e decisões.
- Exemplos válidos e inválidos para providers, com explicação de finalidade,
  papel, modo, referência e recuperação de erro.
- Regressões de fresh install e upgrade separadas em todos os idiomas.

## ARO

Acceptance:
- Upgrade do CodexBridgeMobile apresenta proposta PT-BR e diálogo compreensível.
- Não-TTY não bloqueia nem simula aprovação.
- Upgrade com provider inválido preserva o progresso da conversa e permite
  corrigir apenas provider, sem rodar novamente a análise de escopo.

Risk:
- Divergência entre fluxos cria configuração inconsistente; compartilhar uma
  única máquina de estados/testes.

Operations:
- `--docs-only` e `--skip-project-configuration` preservam os limites atuais.

## Test Plan

- Matriz novo/existente x install/upgrade/session x TTY/não-TTY x PT-BR/EN/ES,
  incluindo provider válido, provider inválido e retomada.

## Definition of Done

- Testes e documentação em paridade; revisor cético de comportamento aprova.
