# Epic 008: Adoção conversacional segura do escopo do projeto

## Metadata

- work_id: WK-20260729-secure-project-adoption
- date: 2026-07-29
- status: started
- owner: [OPERATOR_NAME]
- implementation branch: feature/project-scope-conversation

## Context

`install-agents` e `install-agents --upgrade` devem iniciar a adoção do projeto,
não apenas copiar o kit. Após escolher um agente local, o operador deve receber
uma proposta de domínios existentes, baseada exatamente nas fontes que os agentes
devem ler, e revisá-la em conversa antes de qualquer configuração persistida.

O ensaio real em CodexBridgeMobile demonstrou que a análise pode identificar
domínios úteis, evidências e perguntas abertas. Também demonstrou falhas de
contrato: o texto foi emitido em inglês no ambiente operacional PT-BR e a última
pergunta pediu uma lista CSV de domínios sem dizer se Enter aceita, substitui ou
mescla a proposta. A implementação atual ainda permite traversal de fontes,
aceita JSON de modelo de forma permissiva, expõe output bruto e executa a análise
antes de registrar/validar o provedor e a credencial usados.

Uma segunda execução completou domínios e capacidades, mas exigiu auxílio externo
para interpretar a coleta de providers. O prompt aceitou
`openai:::general, gemini:::reasoning, nvidia:::fast`, embora o quarto campo seja
um papel de roteamento e aceite somente `primary`, `fallback` ou `optional`.
Ao falhar no final, encerrou todo o fluxo depois de dezenas de respostas, sem
explicar o formato antes da pergunta, sem separar visualmente os passos e sem
recuperação no próprio campo inválido.

## Objective

Entregar uma entrevista de adoção segura, localizada e auditável para projetos
novos e existentes, executada tanto na instalação quanto no upgrade, na qual o
operador entende e decide cada alteração proposta para o modelo do projeto.

## In Scope

- Detectar o idioma operacional e manter prompts, proposta, confirmações e erros
  nesse idioma; PT-BR é a expectativa quando essa for a configuração local.
- Escolher explicitamente agente e provedor antes da análise, sem revelar segredo.
- Apresentar alternativas de LLM por faixa de custo e profundidade, orientar o
  cadastro/API e coletar apenas referências seguras de credenciais já exportadas.
- Oferecer `llm-api` como agente de análise quando houver provider compatível
  configurado, sem excluir os agentes locais autenticados.
- Restringir a leitura a fontes aprovadas dentro do root do projeto.
- Validar a proposta do modelo por schema estrito e evidência rastreável.
- Substituir a entrada CSV ambígua por diálogo de revisão por domínio e
  capacidade, com decisão explícita de manter, aceitar, editar, mesclar ou
  descartar.
- Explicar cada coleta antes de solicitá-la, com exemplo válido localizado e
  espaçamento entre perguntas; não expor sintaxe compacta como interface padrão.
- Coletar providers como decisões guiadas (nome, finalidade, papel, modo e
  referência), validar no passo e permitir correção/retomada sem nova análise.
- Modelar proprietário primário, dependências e sensibilidades de capacidades.
- Aplicar o mesmo contrato em instalação nova, upgrade e `config-session`.
- Cobrir adapters, idioma, credenciais, paths, schema, UX e documentação EN/PT-BR/ES.
- Corrigir a geração de slug Unicode que produziu `ado-o` para `adoção`.

## Out of Scope

- Enviar credenciais a um serviço remoto ou armazenar valores secretos.
- Tornar um LLM obrigatório quando nenhum agente/provedor configurável estiver
  disponível.
- Alterar o produto analisado ou inferir sua arquitetura sem confirmação humana.
- Transformar a entrevista em implementação automática do projeto.

## Acceptance

- Um projeto PT-BR recebe a proposta e todas as perguntas em PT-BR; a escolha de
  idioma é visível, determinística e testada.
- A proposta informa fontes/evidências e é revisada por decisões legíveis; não há
  prompt CSV genérico como `Domains (comma-separated...)`.
- Antes de cada resposta, o operador vê uma explicação curta, exemplo válido e o
  efeito de Enter; há uma linha em branco entre solicitações independentes.
- Provider é configurado sem exigir que o operador decodifique
  `NAME[:MODE[:CREDENTIAL_REF[:ROLE]]]`; `primary`, `fallback` e `optional` são
  explicados e validados imediatamente.
- Um erro de validação não perde projeto, proposta, domínios ou capacidades já
  confirmados e retorna ao passo inválido com mensagem localizada e acionável.
- Nenhum path fora do root, inclusive por `..` ou symlink, é lido ou passado ao
  agente.
- Respostas de modelo inválidas, excessivas ou sem evidência válida falham sem
  persistência e sem ecoar conteúdo bruto/sensível.
- O agente/provedor usado é registrado sem segredo, com modo, referência de
  credencial e resultado de validação; configuração incompleta falha fechada.
- A configuração persistida preserva domínios, capacidades, dependências,
  sensibilidades, evidência e decisões do operador.
- O comportamento é equivalente em instalação, upgrade e sessão retomável, com
  documentação sincronizada nos três idiomas.
- Três revisores céticos independentes aprovam segurança, contrato e UX antes da
  conclusão da epic.

## Dependencies and Risks

- Depende das políticas instaladas em `.docs/agents/credentials-operations.md`,
  `.docs/agents/domains-and-capabilities.md` e `.docs/agents/security-standards.md`.
- Cada CLI tem semântica própria de modo somente-leitura; um adapter sem garantia
  verificável não pode ser oferecido como agente de entrevista.
- A configuração antiga deve migrar de forma compatível e nunca aceitar defaults
  silenciosos que substituam a decisão do operador.
