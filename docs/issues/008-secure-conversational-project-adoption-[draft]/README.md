# 008 - Adoção conversacional segura do projeto

- work_id: `WK-20260729-secure-project-adoption`
- status: started
- branch: `feature/project-scope-conversation`

Esta epic corrige o fluxo executado por `governancekit install-agents` e
`governancekit install-agents --upgrade`: depois de instalar o kit, o operador
escolhe um agente local, recebe uma proposta baseada na leitura obrigatória do
projeto e a confirma por uma conversa segura, compreensível e no idioma
operacional.

O fluxo atual demonstrou uma proposta útil para CodexBridgeMobile, mas falha em
dois contratos visíveis: respondeu em inglês apesar do ambiente PT-BR e terminou
com `Domains (comma-separated...)`, uma pergunta que não explica a decisão nem
permite revisar a proposta por domínio. Esta epic não aceita converter essa
conversa em uma coleta de CSV.

## Tarefas

1. `001-scope-interview-contract-and-locale-[draft].md`
2. `002-safe-reading-and-proposal-validation-[draft].md`
3. `003-agent-auth-and-credential-contract-[draft].md`
4. `004-domain-model-and-confirmation-dialogue-[draft].md`
5. `005-install-upgrade-and-documentation-parity-[draft].md`
6. `006-unicode-safe-issue-slugs-[draft].md`
7. `007-guided-input-and-recoverable-validation-[draft].md`
8. `008-llm-first-provider-selection-[draft].md`

Nenhuma task pode ser marcada concluída sem testes automatizados e revisão
adversarial de segurança, contrato e experiência conversacional.
