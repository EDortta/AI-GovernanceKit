# Resume - WK-20260729-secure-project-adoption

## [2026-08-12] O caminho simplificado passa a redigir contexto de verdade

Reportado pelo operador a partir de uma instalação real (`IgrejaPequena`): o
`install-agents` terminou anunciando sucesso e deixou `docs/software-overview.md` e
`docs/limits.md` com o texto do PRÓPRIO KIT, flags em `no` — Start Gate fechado — sem
uma pergunta sobre domínios e sem nenhuma menção a LLM. Quatro causas independentes,
duas delas defeitos:

1. `apply_adoption_proposal` decidia por substring, e a prosa que o kit semeia explica
   o flag numa frase. A frase casava; nada era escrito; o fluxo dizia
   "existing project documents preserved" sobre a boilerplate do kit.
2. O gerador cravava `- project_context_ready: yes` no literal, ao lado dos
   "Known unknowns" — máquina abrindo o próprio Start Gate. O defeito 1 estava
   mascarando este: corrigir só o gate teria feito o kit marcar `yes` de verdade em
   todo o parque.
3. A oferta de LLM era pulada em silêncio quando não havia provider configurado.
4. A entrevista de domínios está atrás de `--advanced` desde `ccfa200` (2026-08-02),
   por decisão desta épica — mas nada anunciava a porta.

**Decisão do operador (2026-08-12):** o conteúdo deve ser gerado a partir do README e
das fontes, em discussão; `no` + aviso é o piso, não a meta. E a ausência de provider
tem de ser **dita**, não silenciada — "o operador fica sem saber do potencial e dá-se
por bem servido quando na realidade podemos oferecer bem mais".

**Entregue:** o `install-agents` passou a rodar o mesmo passo do `author-context`
(`_context_step`), com ramo determinístico quando não há provider, consentimento
explícito quando há, e veredito lido do disco. A política `[MANDATORY]` de
`credentials-operations.md:29` — projeto operável em modo manual — vira teste
executável em `tests/test_cli_context_step.py`. O catálogo de modelos gratuitos entrou
como dado com proveniência (`_llm_catalog.json` + `scripts/refresh-llm-catalog.py
--check`), e os presets da entrevista passaram a ser derivados dele.

**Não implementado, deliberadamente:** tornar o LLM obrigatório. O operador lembrava de
uma decisão nesse sentido; o registro diz o oposto em quatro lugares
(`credentials-operations.md:29` `[MANDATORY]`, `epic.md:66` fora de escopo,
`napkin-lessons.md:27`, `handoff.md:541`). Reportado, e mantido o modo manual.

## Concílio — 2026-08-12, duas rodadas

**r1 (quatro lentes: sweep skeptic, claim auditor, second caller, the migrator): 22
achados + 14 perguntas, 22 sobreviveram ao §2, 20 viraram teste, 2 encaminhados ao
AI-Agents. r2 (fix auditor, adversarial user / operator at 17:00): 13 achados + 7
perguntas, 13 viraram teste.** Todos reproduzidos.

O que a rodada 1 mostrou, e não era o que eu esperava: o defeito mais grave não estava
na lógica de adoção, estava no **build**. `_llm_catalog.json` ficou fora do
`package-data` e o `scope_conversation` resolvia os presets em tempo de import — a
suíte inteira verde a partir da árvore, e o kit instalado morrendo no import. Duas
lentes construíram o wheel e acharam o mesmo traceback sem se falar.

Sete dos 35 achados das duas rodadas eram **regressões das minhas próprias correções**:
o rebaixamento silencioso do flag preservado, a perda dos três presets junto com o
catálogo, o `.pre-draft` de uma vaga só, o `remove-agents` cego ao andaime que o filtro
de manifesto criou, os caminhos de credencial no stdout, o catálogo de providers virando
inglês nas duas outras línguas, e o veredito que afirmava ter escrito um arquivo
preservado.

E três afirmações minhas caíram: o motivo que dei para o teste de `.gitignore` não ter
pego (ele **afirmava** o defeito como correto), "todos os presets agora têm origem"
(três são os mesmos valores, realocados) e uma mutação listada como verificada que
deixava a suíte verde. As três corrigidas no `CHANGELOG.md`, com o erro à vista.

> **Os fechamentos da rodada 2 não foram auditados.** O §4 é explícito: duas rodadas,
> depois o operador, e não se roda uma terceira. Cada um tem teste vermelho sem a
> correção e a verificação de ponta a ponta foi refeita em alvo real, mas ninguém além
> de mim olhou para eles.

### Aberto, com dono — AI-Agents

- **#9** — o `install-agents-kit.sh` reescreve o bloco `.gitignore` da raiz com os
  **mesmos marcadores** do instalador Python e só com os padrões de segredo, apagando
  dez regras, inclusive `*.kit-new`.
- **#10** — o `.gk/.gitignore` do shell não cobre `remove-agents-backup/`.

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

Executar uma atualização interativa real em checkout consumidor grande e revisar
o scan visível, o consentimento do LLM e qualquer aviso operacional antes de
iniciar os itens restantes do épico; preservar a revisão humana e documentos
já aceitos.

## Gates

- Aprovação do operador para iniciar a implementação por task.
- Revisão adversarial de segurança, contrato e UX antes de fechar a epic.
- Testes automatizados e documentação EN/PT-BR/ES sincronizada.
