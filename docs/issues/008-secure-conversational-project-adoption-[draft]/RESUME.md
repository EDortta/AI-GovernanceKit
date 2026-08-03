# Resume - WK-20260729-secure-project-adoption

## Current State

Implementação-base entregue e validada: locale operacional, diálogo guiado,
provider com finalidade/papel, defaults de sessão pendente, confinamento de
fontes, workspace temporária para o agente, schema estrito e slug Unicode.
No fluxo simplificado, o provider primário agora só enriquece a proposta após
consentimento explícito, identificado por provider/model; erro de resposta
também mantém essa identificação.
O upgrade anuncia a análise de drift/proposta antes de varrer arquivos e avisa
o limite de 90 segundos antes da consulta opcional ao provider.
A descoberta mostra apenas diretórios de primeiro nível e não entra em raízes
Git aninhadas, incluindo worktrees cujo `.git` é um arquivo.
Falhas de enriquecimento LLM são apresentadas como aviso destacado com
provider/model, causa traduzida, formato de evidência esperado e orientação de
aceitar somente a proposta determinística ou responder `n` para não escrever.
O épico permanece aberto: não há recuperação durável no meio da entrevista,
configuração de provider ainda ocorre depois de escolher o agente de escopo e o
modelo de dependências/sensibilidades de capacidades ainda não foi implementado.

## Next Step (DO THIS FIRST)

Revisar e publicar consentimento do provider/model, aviso de duração,
descoberta visível/confinada e explicação operacional de falhas LLM no fluxo
unificado de adoção; preservar a revisão humana e os documentos já aceitos.

## Gates

- Aprovação do operador para iniciar a implementação por task.
- Revisão adversarial de segurança, contrato e UX antes de fechar a epic.
- Testes automatizados e documentação EN/PT-BR/ES sincronizada.
