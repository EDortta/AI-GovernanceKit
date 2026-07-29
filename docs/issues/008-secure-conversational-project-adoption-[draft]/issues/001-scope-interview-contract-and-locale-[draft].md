# Task 001: Contrato da entrevista e idioma operacional

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: draft
- parent: 008-secure-conversational-project-adoption

## Context

No CodexBridgeMobile, o ambiente operacional escolhido é PT-BR, mas a proposta
do agente e seus rótulos foram emitidos em inglês. A pergunta final não exprime
uma decisão humana: `Domains (comma-separated...)` parece pedir que o operador
redigite a proposta inteira sem explicar o efeito de Enter.

O mesmo transcript mostrou uma sequência densa de prompts, sem linha em branco
entre respostas e sem explicação curta antes de cada coleta. Isso transfere para
o operador o trabalho de descobrir a gramática e a intenção do fluxo.

## Objective

Definir e implementar o contrato de locale e o roteiro de conversa antes de
tratar conteúdo, persistência ou adapters.

## In Scope

- Precedência documentada para idioma: configuração explícita do projeto,
  ambiente operacional/locale e fallback seguro.
- Prompt do agente exigindo a língua selecionada, inclusive domínios, evidências,
  perguntas abertas e mensagens de erro.
- Vocabulário de decisões explícitas por domínio: aceitar, editar, mesclar,
  descartar ou manter configuração anterior.
- Exibir o significado de Enter e o delta entre configuração existente e proposta.
- Um padrão de apresentação para cada pergunta: objetivo, exemplo válido quando
  houver formato, default/efeito de Enter e uma linha em branco antes do próximo
  passo independente.

## Out of Scope

- Traduzir documentos-fonte do projeto.
- Implementar validação de credenciais ou schema do modelo.

## ARO

Acceptance:
- Em `pt_BR`, não há texto de entrevista em inglês e não há pergunta CSV genérica.
- Um operador entende, sem consultar documentação externa, o que será salvo ao
  aceitar cada decisão.
- O transcript não apresenta dois pedidos independentes em linhas consecutivas
  sem separação visual.

Risk:
- Locale do shell pode estar ausente ou inconsistente; a precedência deve ser
  observável no output e coberta por teste.

Operations:
- Não persistir configuração enquanto o roteiro não terminar com confirmação
  explícita.

## Test Plan

- Testes unitários de precedência de locale e renderização PT-BR/EN/ES.
- Transcript determinístico do caso CodexBridgeMobile.
- Teste de regressão que proíbe `Domains (comma-separated` nos prompts localizados.
- Testes de renderização que exigem explicação e exemplo antes de entrada
  estruturada, e linha em branco entre passos.

## Definition of Done

- Contrato publicado e implementado.
- Testes passam e um revisor cético de UX aprova o transcript.
