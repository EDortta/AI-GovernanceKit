# Task 002: Leitura segura e validação da proposta

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: draft
- parent: 008-secure-conversational-project-adoption

## Objective

Confinar fontes ao projeto e aceitar somente propostas estruturadas, limitadas e
evidenciadas.

## In Scope

- Resolver cada fonte e exigir que permaneça sob o root após resolução de symlink.
- Rejeitar `..`, paths absolutos, links externos e referências não aprovadas.
- Schema estrito para resposta: chaves, tipos, tamanhos, domínios/capacidades
  únicos, evidência obrigatória e limites de volume.
- Validar que a evidência cita uma fonte realmente selecionada antes de exibir ou
  usar a proposta.
- Não imprimir output bruto do modelo nem stderr potencialmente sensível.

## ARO

Acceptance:
- Nenhum fixture adversarial lê arquivo externo ou persiste proposta inválida.

Risk:
- A validação não pode impedir documentação legítima dentro do root.

Operations:
- Falha apresenta diagnóstico sanitizado e instrução de recuperação, sem segredo.

## Test Plan

- Fixtures para traversal, symlink escape, JSON embrulhado, chaves extras,
  evidência falsa, excesso de tamanho e prompt injection em fonte.

## Definition of Done

- Guardas falham fechadas; revisão cética de segurança aprovada.
