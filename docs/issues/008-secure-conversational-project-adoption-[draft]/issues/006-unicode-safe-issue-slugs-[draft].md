# Task 006: Slugs de issues seguros para Unicode

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: draft
- parent: 008-secure-conversational-project-adoption

## Context

O próprio `bootstrap-issue` gerou `008-ado-o-conversacional...` para o título
`Adoção conversacional...`, degradando um título PT-BR legítimo.

## Objective

Normalizar Unicode para ASCII previsível antes de gerar slugs, preservando
`adoção` como `adocao`.

## In Scope

- Normalização Unicode e testes com PT-BR, ES e caracteres combinados.
- Compatibilidade para títulos somente não ASCII e prevenção de slug vazio.

## ARO

Acceptance:
- `Adoção conversacional` gera `adocao-conversacional`.

Risk:
- Alterar o slug não pode renomear artefatos existentes.

Operations:
- Afeta apenas novas criações de issue.

## Test Plan

- Casos `Adoção`, `configuración`, composição Unicode e entrada sem ASCII.

## Definition of Done

- Testes de bootstrap passam sem regressão de paths existentes.
