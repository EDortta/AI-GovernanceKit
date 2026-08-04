# Issues de correção do kit — AI-Agents e AI-GovernanceKit

- work_id: `WK-20260804-governancekit-contract-reassessment`
- date: 2026-08-04
- owner: Esteban D.Dortta
- origem: reavaliação feita no projeto governado `AI/CodexBridge`
  (documento completo: `../governancekit-contract-reassessment.md`)

## O que é isto

Quinze issues prontas para serem abertas **nos repositórios do kit**, não no
CodexBridge. O CodexBridge foi apenas o projeto onde os defeitos apareceram.

Cada issue segue `.docs/issues/templates/task.template.md`. Os arquivos estão
agrupados por repositório de destino, um arquivo por repositório, para facilitar o
transporte. Se preferir a estrutura de pasta do kit (um arquivo por task), é só pedir.

| Arquivo | Destino | Issues |
|---|---|---|
| `epic.md` | — | contexto comum às duas frentes |
| `issues-ai-agents.md` | `EDortta/AI-Agents` | 10 (A1–A10) |
| `issues-ai-governancekit.md` | `AI-GovernanceKit` | 5 (G1–G5) |

## Versões em que os defeitos foram observados

- GovernanceKit `0.2.3`
- AI-Agents `v1.1.7` (manifesto `.gk/manifest.json`)
- contrato de integração declarado: `v1.1.6` (`.docs/governancekit-integration.json`)
- observação em `AI/CodexBridge`, instalação de 2026-08-04 17:20, `doctor` às 17:26

## Ordem sugerida

O par **A1 + G1** é o bloqueador: A1 corrige o texto, G1 impede a recorrência. Sem
os dois, todo o resto assenta sobre um gate que aponta para o lugar errado.

| Ordem | Issues | Por quê |
|---|---|---|
| 1 | **A1, A2, G1, G2** | contrato e ferramenta discordam sobre o caminho do gate (F0) |
| 2 | **A3, G5** | o instalador escreve um `.gitignore` que o próprio `doctor` reprova |
| 3 | **A5, G3** | identidade: quatro arquivos, nenhum deles o que o §8b exige |
| 4 | **A6** | ligar o §1b ao gate executável que já existe |
| 5 | **A4** | fronteira de repositório — independente de todos os outros |
| 6 | **A7** | caminho do monitor de atividade |
| 7 | **A8, A9, A10, G4** | consistência interna e rastreabilidade |

## Severidades

| Severidade | Issues |
|---|---|
| crítica | A1, A2, G1 |
| alta | A3, A4, A5, A7, G2, G3, G5 |
| média | A6, A8, A9, A10, G4 |
