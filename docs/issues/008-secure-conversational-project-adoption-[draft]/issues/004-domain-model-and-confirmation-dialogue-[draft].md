# Task 004: Modelo de domínio e diálogo de confirmação

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: draft
- parent: 008-secure-conversational-project-adoption

## Objective

Persistir um modelo de projeto suficiente para governança e confirmar cada
mudança proposta sem apagar silenciosamente configuração anterior.

## In Scope

- Capacidade com domínio primário, dependências interdomínio, sensibilidades,
  evidência e decisão do operador.
- Migração compatível do formato atual e preview de delta.
- Confirmação por domínio/capacidade, incluindo proposta vazia, duplicada ou
  conflitante.
- Explicação contextual de domínio, capacidade e resumo antes de cada decisão;
  a confirmação de domínio reapresenta os candidatos que o agente encontrou e
  uma referência à documentação de configuração.
- A proposta rotula explicitamente a estrutura `domínio: capacidades` e
  esclarece que perguntas abertas são lacunas de evidência para revisão, não
  respostas salvas nem campos obrigatórios ocultos.
- Estado de entrevista serializável, sem segredos, para retomar após erro de
  validação sem descartar decisões já confirmadas.
- Garantia de que uma capability possui exatamente um domínio primário.

## ARO

Acceptance:
- Enter nunca substitui domínios existentes sem mostrar e confirmar o delta.
- O arquivo compartilhável contém decisões e metadados sem segredos.
- Erro de provider não obriga o operador a repetir domínios, capacidades ou
  resumo já aceitos.

Risk:
- Migração pode tornar configs existentes inválidas; oferecer preview e saída
  recuperável, não conversão silenciosa.

Operations:
- Aplicação continua submetida à aprovação da sessão configurável.

## Test Plan

- Migração v1/v2, merge, conflito, dependência cruzada, classificação sensível e
  retomada após falha de validação.

## Definition of Done

- Modelo e UX atendem `domains-and-capabilities.md` e testes passam.
