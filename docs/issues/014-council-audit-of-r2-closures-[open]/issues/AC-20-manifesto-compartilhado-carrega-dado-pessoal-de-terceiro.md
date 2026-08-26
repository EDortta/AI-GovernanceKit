# Issue AC-20 — origem: crítica de quatro céticos sobre AC-1, 2026-08-13 (lente: LGPD)

## AC-20 — o filtro do estado compartilhado é assimétrico e deixa passar dado pessoal de terceiro [alta]

### Contexto

`_read_state` remove `_OPERATOR_PLACEHOLDERS` do `.gk/manifest.json` herdado — o comentário
em `install_agents.py:1073-1074` diz por quê: *"a clone never inherits another
programmer's identity"*.

`_SENSITIVE_PLACEHOLDERS` **não** está nessa frase nem nesse filtro. E é a lista que
contém `PIX_KEY_UUID`, `PIX_HOLDER_NAME`, `PIX_PAYLOAD`, `PIX_QR_BASE64`,
`ETH_WALLET_ADDRESS`, `KOFI_HANDLE`.

Então: um colega commita o manifesto — por edição manual, por PR mesclado, por versão
antiga do kit, ou pelo instalador shell — com o nome completo e a chave PIX **dele**. A
vítima dá `git pull`, roda `install-agents --upgrade`, e o dado da outra pessoa:

1. entra no estado lógico da vítima,
2. é renderizado nos arquivos da vítima (que sob `--track` vão para o git **dela**),
3. é gravado no `.gk/secrets.json` **local** da vítima.

Sem uma linha impressa.

O gate de `AC-1` não pega e não deveria: dado real não carrega sintaxe de placeholder, é
curto, e é token declarado. Passa todas as regras porque **não é um ataque de
injeção — é o mecanismo funcionando como projetado**, sobre uma entrada que a divisão
operator/sensitive existe para não confiar.

### Reprodução

```
=== SENSITIVE tokens in the COMMITTED manifest are NOT filtered by _read_state ===
logical state the installer sees: {
  "PIX_HOLDER_NAME": "COLEGA FULANO DE TAL",
  "PIX_PAYLOAD": "00020126580014BR.GOV.BCB.PIX0136COLEGA",
  "ETH_WALLET_ADDRESS": "0xC01EGA0000000000000000000000000000000000"
}
OPERATOR_NAME filtered out?  True
PIX_HOLDER_NAME filtered out? False
victim's file after render: 'Titular: COLEGA FULANO DE TAL\nPIX: 00020126...'
victim's local .gk/secrets.json: {"metadata": {"ETH_WALLET_ADDRESS": "0xC01EGA...", ...}}
```

### Objetivo

Que a metade compartilhada do estado nunca entregue dado pessoal ou financeiro de uma
pessoa ao ambiente de outra.

### Escopo

- `_read_state` filtra `_SENSITIVE_PLACEHOLDERS` do manifesto herdado, pela mesma razão
  e no mesmo lugar em que já filtra `_OPERATOR_PLACEHOLDERS`.
- Quando o filtro descarta algo, **dizer**: o manifesto compartilhado carrega dado que
  não deveria, e quem deu `git pull` é quem pode avisar quem commitou.
- Escrever a regra de classificação. Hoje `KOFI_HANDLE` (nome de usuário público) está
  em `_SENSITIVE_PLACEHOLDERS` e `GITHUB_OWNER` está na metade compartilhada — a lista
  parece ter sido montada por *quem pode ler*, e sob LGPD a pergunta é *o que é*.
- Considerar o caminho de saneamento: um manifesto já commitado com dado de terceiro
  precisa de um comando que o retire, não só de um filtro na leitura.

### ARO

- **Assumption**: dado em `_SENSITIVE_PLACEHOLDERS` é sempre pessoal de **um**
  indivíduo, nunca da organização. `ORG_NAME` está fora da lista, o que sustenta isso.
- **Risk**: filtrar quebra um alvo que hoje depende de herdar esses valores. Improvável
  — herdar é justamente o defeito — mas precisa de medição no parque.
- **Risk**: o filtro é na leitura; o dado já commitado continua no histórico do git.
  Filtrar não é eliminar, e a issue não deve fingir que é. Ver `AC-21`.
- **Owner**: a definir. Decisão de classificação é do operador.

### Plano de teste

- Manifesto com os seis tokens sensíveis ⇒ nenhum entra no estado lógico.
- O descarte é reportado, nomeando os tokens (nunca os valores).
- `OPERATOR_NAME` continua filtrado (o teste existente não pode regredir).
- Mutação: remover `_SENSITIVE_PLACEHOLDERS` do filtro ⇒ vermelho.

### DoD

- Nenhum token sensível atravessa a metade compartilhada.
- A regra de classificação está escrita e justificada.
- O descarte é visível.
