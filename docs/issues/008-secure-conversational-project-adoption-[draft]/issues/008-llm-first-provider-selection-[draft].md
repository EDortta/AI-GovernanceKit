# Task 008: Seleção de LLM antes do agente

## Objective

Permitir que a entrevista escolha e configure uma LLM API antes do agente de
análise, com recomendações compreensíveis de custo/profundidade e sem solicitar
ou persistir segredos.

## Acceptance

- A entrevista explica opções grátis/baixo custo e afinidade básica/ampla, com
  links oficiais de cadastro/preços atualizáveis.
- O operador informa somente nome, URL, modelo e referência de variável; a chave
  é criada/exportada fora do GovernanceKit.
- `llm-api` aparece entre os agentes apenas com provider API completo e usa uma
  chamada OpenAI-compatible confinada às fontes aprovadas.
- Cursor com resumo multilinha válido não falha por limite artificial de uma
  linha; schema de domínios/evidências continua estrito.
