# Resume - WK-20260729-secure-project-adoption

## Current State

Implementação-base entregue e validada: locale operacional, diálogo guiado,
provider com finalidade/papel, defaults de sessão pendente, confinamento de
fontes, workspace temporária para o agente, schema estrito e slug Unicode.
O épico permanece aberto: não há recuperação durável no meio da entrevista,
configuração de provider ainda ocorre depois de escolher o agente de escopo e o
modelo de dependências/sensibilidades de capacidades ainda não foi implementado.
O contrato de credencial anterior à análise foi concluído: perfis JSON são lidos
somente em memória e links sob `.credentials/` são aceitos no upgrade iniciado
pelo operador, preservando o confinamento das fontes.
O diálogo manual agora enumera referências locais de arquivos de credencial,
seleciona por padrão a de mesmo nome do provider e retém os providers detectados
que não foram editados como alternativas.

## Next Step (DO THIS FIRST)

Validar em um checkout consumidor a entrevista com `gpt-4o-mini` e o fallback
NVIDIA detectado; depois implementar o reconhecimento do checkout-fonte do
GovernanceKit no `doctor` e retomar a recuperação durável da task 007.

## Gates

- Aprovação do operador para iniciar a implementação por task.
- Revisão adversarial de segurança, contrato e UX antes de fechar a epic.
- Testes automatizados e documentação EN/PT-BR/ES sincronizada.
