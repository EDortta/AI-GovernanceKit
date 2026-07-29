# Task 003: Contrato de agente, autenticação e credenciais

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: draft
- parent: 008-secure-conversational-project-adoption

## Objective

Configurar e validar o agente/provedor antes da análise, sem ler, copiar ou
registrar qualquer segredo.

## In Scope

- Inventário de adapters cuja semântica somente-leitura seja comprovável.
- Escolha de agente e provedor antes da primeira invocação.
- Registro auditável de nome, modo, referência de credencial, papel e resultado
  de validação, sem valor de segredo.
- Distinção explícita entre finalidade humana do provider (por exemplo, geral,
  raciocínio ou rápido) e papel de roteamento (`primary`, `fallback`, `optional`);
  finalidade não pode ser encaixada silenciosamente no campo de papel.
- Falha fechada quando a credencial/referência/validação exigida estiver ausente.
- Contrato para projetos que escolhem não usar LLM.

## ARO

Acceptance:
- Um agente usado nunca é persistido como provider `manual` por default.
- Stderr/output de CLI não vaza para terminal, logs ou config.
- A tela explica papel, modo e referência antes da resposta e oferece um exemplo
  válido localizado; o operador não precisa conhecer uma gramática com `:`.

Risk:
- Flags de segurança variam por versão do CLI; adapters devem ser testados contra
  a ajuda da versão suportada ou retirados da lista.

Operations:
- Nenhuma credencial é transmitida pelo GovernanceKit; a referência local é
  validada conforme adapter e política.

## Test Plan

- Testes de comando por adapter, ausência de credencial, falha de validação e
  redaction.

## Definition of Done

- Política de credenciais satisfeita e revisão cética de contrato aprovada.
