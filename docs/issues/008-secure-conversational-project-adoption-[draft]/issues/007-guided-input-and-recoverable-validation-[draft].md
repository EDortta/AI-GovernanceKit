# Task 007: Entrada guiada e validação recuperável

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: draft
- parent: 008-secure-conversational-project-adoption

## Context

No upgrade real do CodexBridgeMobile, o operador completou oito domínios e suas
capacidades, informou três providers e só então recebeu:
`invalid provider role for 'openai': 'general'`. O prompt anterior não definiu
`ROLE`, não trouxe exemplo válido e não explicou que `general`, `reasoning` e
`fast` são finalidades, não os papéis aceitos pelo parser. O processo encerrou e
perdeu a possibilidade de corrigir o único campo inválido no lugar.

## Objective

Substituir a gramática compacta como interface interativa por uma coleta guiada,
validada no passo, com recuperação local e preservação segura do progresso.

## In Scope

- Cabeçalho curto antes de cada coleta explicando o que será decidido e por quê.
- Um exemplo válido localizado antes de qualquer entrada estruturada.
- Uma linha em branco entre solicitações independentes.
- Coleta de provider por campos/decisões legíveis: nome, finalidade opcional,
  papel de roteamento, modo e referência de credencial.
- Explicação de que há exatamente um `primary`; `fallback` assume quando o
  primário não puder atender; `optional` não participa do roteamento padrão.
- Validação imediata, erro localizado e loop no campo inválido.
- Estado de rascunho sem segredos para retomar uma entrevista interrompida;
  limpeza após aplicar, descartar ou expirar.

## Out of Scope

- Aceitar `general`, `reasoning` ou `fast` como aliases silenciosos de papel.
- Persistir valor de credencial ou output bruto de provider.
- Tentar inferir a intenção do operador a partir de um valor inválido.

## ARO

Acceptance:
- O operador consegue informar OpenAI como primário, Gemini como fallback e
  NVIDIA como opcional sem consultar ChatGPT, documentação externa ou código.
- Um papel inválido explica os valores aceitos e pede somente a correção daquele
  provider; domínios, capacidades e resumo permanecem intactos.
- O transcript tem explicação, exemplo e separação visual para toda entrada que
  não seja texto livre.

Risk:
- Rascunho pode conter nomes/evidências do projeto; deve obedecer o mesmo root,
  permissões e ciclo de limpeza da sessão configurável, sem segredo.

Operations:
- O CLI deve oferecer retomar, descartar ou reiniciar deliberadamente; nunca
  reaplicar rascunho sem mostrar seu estado.

## Test Plan

- Transcript PT-BR do cenário real, sem ajuda externa.
- Casos de `general`, `reasoning` e `fast` como finalidade válida, mas não como
  papel; teste de mensagem e retry local.
- Interrupção após domínios/capacidades, reinício e retomada sem nova chamada LLM.
- Espaçamento, exemplos e defaults em PT-BR/EN/ES.

## Definition of Done

- Fluxo não usa sintaxe colonizada como UI padrão.
- Falhas recuperam no passo correto, testes passam e o revisor cético de UX
  consegue completar o transcript sem consulta externa.
