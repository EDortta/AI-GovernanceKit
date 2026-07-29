# Task 008: Seleção de LLM antes do agente

## Objective

Permitir que a entrevista escolha e configure uma LLM API antes do agente de
análise, com recomendações compreensíveis de custo/profundidade e sem solicitar
ou gravar segredos na configuração versionável.

## Acceptance

- A entrevista explica opções grátis/baixo custo e afinidade básica/ampla,
  orientando o cadastro e a criação da API key no portal do provedor.
- O operador pode usar uma variável de ambiente, referenciar um arquivo local
  existente ou criar `.credentials/llm/<provedor>.key` com colagem de entrada
  oculta. A configuração salva somente a referência; o arquivo é limitado ao
  checkout, não segue links para fora e usa permissões de dono.
- O marcador `manual` representa ausência de LLM, não aparece como configuração
  salva nem como um provedor com modelo ausente.
- `llm-api` aparece entre os agentes apenas com provider API completo e usa uma
  chamada OpenAI-compatible confinada às fontes aprovadas.
- Cursor com resumo multilinha válido não falha por limite artificial de uma
  linha; schema de domínios/evidências continua estrito.
