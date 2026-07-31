# Task 008: Seleção de LLM antes do agente

## Objective

Permitir que a entrevista escolha e configure uma LLM API antes do agente de
análise, com recomendações compreensíveis de custo/profundidade e sem solicitar
ou gravar segredos na configuração versionável.

## Acceptance

- A entrevista explica opções grátis/baixo custo e afinidade básica/ampla,
  orientando o cadastro e a criação da API key no portal do provedor.
- Antes de pedir o nome, a entrevista lista Gemini, NVIDIA NIM e OpenAI como
  presets compatíveis com a API OpenAI, deixando explícito que outros endpoints
  compatíveis também podem ser informados manualmente.
- O operador pode usar uma variável de ambiente, referenciar um arquivo local
  existente ou criar `.credentials/llm/<provedor>.key` com colagem de entrada
  oculta. A configuração salva somente a referência; o arquivo é limitado ao
  checkout, não segue links para fora e usa permissões de dono.
- O marcador `manual` representa ausência de LLM, não aparece como configuração
  salva nem como um provedor com modelo ausente.
- Credenciais conhecidas já presentes em `.credentials/llm/` (incluindo NVIDIA
  NIM) são detectadas sem abrir ou exibir o segredo; o operador pode aceitar o
  preset de URL/modelo correspondente antes de cadastrar outro provedor.
- Antes da análise, a entrevista informa que o agente está lendo fontes
  aprovadas e pode levar até 90 segundos. Falhas de API classificam o status
  HTTP com orientação segura, sem imprimir a chave nem o corpo da resposta.
- `llm-api` aparece entre os agentes apenas com provider API completo e usa uma
  chamada OpenAI-compatible confinada às fontes aprovadas.
- Cursor com resumo multilinha válido não falha por limite artificial de uma
  linha; schema de domínios/evidências continua estrito.
