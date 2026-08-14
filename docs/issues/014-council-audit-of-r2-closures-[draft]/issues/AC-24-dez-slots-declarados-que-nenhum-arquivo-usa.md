# Issue AC-24 — origem: pergunta do operador, 2026-08-13 ("nem tinha noção de que temos financeiro aqui dentro")

## AC-24 — o kit pergunta e guarda cinco identificadores de pagamento que nenhum arquivo usa [alta]

### Contexto

`_PLACEHOLDER_DESCRIPTIONS` declara **onze** slots. Medido contra a árvore que
`_prerender_source` de fato renderiza — o checkout do `AI-Agents`, que é o que
`_download` desempacota:

| slot | arquivos que o carregam |
|---|---|
| `OPERATOR_NAME` | **4** |
| `GITHUB_OWNER` | 0 |
| `PROJECT_SLUG` | 0 |
| `ORG_NAME` | 0 |
| `PROJECT_ROOT` | 0 |
| `PIX_KEY_UUID` | 0 |
| `PIX_HOLDER_NAME` | 0 |
| `PIX_PAYLOAD` | 0 |
| `PIX_QR_BASE64` | 0 |
| `KOFI_HANDLE` | 0 |
| `ETH_WALLET_ADDRESS` | 0 |

**Dez dos onze não são usados por nada.** Cinco deles são identificadores de pagamento,
e o instalador pergunta por eles a todo operador de todo projeto governado, guarda a
resposta em `.gk/secrets.json`, e não tem comando para apagá-la.

### De onde vieram

`git log -S'PIX_PAYLOAD'` dá um único ponto de entrada, e a mensagem do commit conta a
história inteira:

```
a228889  2026-06-26  Initial public release — PII-free

All personal names, emails, financial identifiers, and local paths
replaced with [PLACEHOLDER] tokens. Users fill values via install-agents.
```

Os arquivos desse commit que carregavam os tokens eram `docs/index.html` e
`docs/intro.html` — a **landing page do próprio GovernanceKit**, com a seção de doação
(PIX, Ko-fi, ETH) do autor.

Quer dizer: ao abrir o repositório, o autor limpou os **próprios** dados pessoais e
financeiros das páginas e os trocou por tokens. Isso está certo. O que aconteceu depois é
que os tokens foram **declarados como slots preenchíveis** — *"Users fill values via
install-agents"* — e a landing page não é instalada em projeto nenhum. Hoje ela tem os
valores reais de volta (`ko-fi.com/edortta`, *"PIX direto na minha chave"*), então nem lá
os tokens existem mais.

**O resíduo de uma limpeza pontual virou uma pergunta permanente do instalador.** O
operador não decidiu que o kit coletaria dado financeiro; ninguém decidiu. Ele se coou.

### Por que isto importa mais do que parece

Toda a discussão de LGPD que a crítica de `AC-1` levantou — retenção sem via de
eliminação, `--unset`, a condição de release amarrando `AC-1` a `AC-21` — existe **por
causa de slots que não fazem nada**. Some com os slots e:

- não há entrada de dado financeiro para reter, então `AC-21` deixa de ser condição de
  release de `AC-1` e volta a ser o que é: higiene de ciclo de vida de estado;
- `AC-22` (o hash de arquivo renderizado como oráculo) encolhe para o que sobrar de dado
  pessoal de verdade — `OPERATOR_NAME`;
- o prompt do `install-agents` para de pedir nove coisas que não vão a lugar nenhum.

Também explica um sintoma que a crítica mediu e não soube nomear: `PIX_QR_BASE64` é o
slot que estourava o teto de 4096 e virou "slot morto". Ele já era morto.

### Objetivo

Que o kit só declare slot que algum arquivo distribuído use, e que os dados já coletados
sob os slots que saírem sejam eliminados, não apenas ignorados.

### Escopo

- **Derivar, não digitar.** `_PLACEHOLDER_DESCRIPTIONS` não pode ser uma lista escrita à
  mão que diverge do que a árvore carrega — é o mesmo defeito de `AC-19`, `AC-23` e do
  gate de deriva da épica `013`. Um teste afirma que todo slot declarado aparece em ao
  menos um arquivo do ref pinado, e que todo token do ref está declarado.
- **Os cinco financeiros saem**, e o que já foi guardado sob eles é **eliminado** do
  estado dos alvos — não basta parar de perguntar. Este é o primeiro cliente concreto do
  mecanismo de `AC-21`, e a ordem natural passa a ser `AC-21` antes de `AC-24`.
- **Os outros cinco não usados** (`GITHUB_OWNER`, `PROJECT_SLUG`, `ORG_NAME`,
  `PROJECT_ROOT`, e o que sobrar) precisam de decisão caso a caso: podem estar previstos
  para uso futuro. `_RETIRED_PLACEHOLDERS` já existe exatamente para "para de perguntar,
  continua substituindo em arquivo legado" — é o caminho para os que não são sensíveis.
- Alvos legados podem ter arquivos de versões antigas do kit que carreguem os tokens. É
  por isso que a retirada usa `_RETIRED_PLACEHOLDERS` em vez de remoção seca, salvo para
  os financeiros, que devem sair **com** eliminação.

### ARO

- **Assumption**: o ref pinado é a fonte de verdade do que o kit usa. Se um projeto
  governado usa `{{ORG_NAME}}` em arquivo próprio, `configure._scan` não o alcança
  (só varre `_FRESH_PATHS`), então não há regressão silenciosa por essa via.
- **Risk**: eliminar dado guardado é irreversível. A eliminação precisa ser anunciada,
  e o operador precisa poder ver o que será apagado antes.
- **Risk**: um slot retirado hoje que volte a ser necessário amanhã custa uma release.
  Barato, comparado a coletar o que não se usa.
- **Owner**: o operador — é decisão sobre o que o produto coleta.

### Plano de teste

- Todo slot em `_PLACEHOLDER_DESCRIPTIONS` aparece em ao menos um arquivo do ref pinado.
- Todo `{{TOKEN}}` do ref pinado está declarado ou retirado.
- Alvo com valor financeiro guardado + o comando de eliminação ⇒ o valor some dos três
  arquivos de estado, e a saída diz o que apagou.
- Alvo legado com `{{PIX_PAYLOAD}}` num arquivo antigo ⇒ comportamento decidido e escrito
  (hoje: substituído por valor guardado; depois: ?).
- Mutação: declarar um slot que nenhum arquivo usa ⇒ vermelho.

### DoD

- Nenhum slot declarado sem uso, provado por teste derivado do ref pinado.
- Os identificadores de pagamento saíram, e o que foi coletado foi eliminado.
- A decisão sobre cada um dos outros cinco está escrita.

---

## Medição do parque, 2026-08-13 — o dado financeiro não existe

Provocado por uma segunda pergunta do operador: *"o que é isso de payload do PIX? Não faz
sentido. é um kit de desenvolvimento."*

```
$ find ~/Sync/Projects/AI -maxdepth 3 -name 'secrets.json' -path '*/.gk/*'
  (nenhum)

$ find ~/Sync/Projects/AI -maxdepth 3 -name 'operator.json' -path '*/.gk/*'
  CodexBridge/.gk/operator.json        -> ['OPERATOR_NAME', 'SMTP_ACCOUNT']
  CodexBridgeMobile/.gk/operator.json  -> ['OPERATOR_NAME', 'SMTP_ACCOUNT']
```

**`.gk/secrets.json` não existe em nenhum projeto governado.** Os seis slots roteados para
ele — `PIX_KEY_UUID`, `PIX_HOLDER_NAME`, `PIX_PAYLOAD`, `PIX_QR_BASE64`,
`ETH_WALLET_ADDRESS`, `KOFI_HANDLE` — são todos de doação, e nenhum foi respondido por
ninguém, em lugar nenhum.

Isso confirma a tese desta issue por medição em vez de leitura de código: os slots não são
"dado financeiro coletado", são **um formulário que ninguém preencheu porque não serve
para nada**. A conclusão prática fica mais simples do que a issue supunha — não há dado a
eliminar sob esses seis nomes; há um formulário a remover.

### Correção de enquadramento, e ela é minha

Todo o argumento de LGPD desta épica foi construído sobre dado financeiro, e eu ilustrei o
risco com fixtures carregando payload PIX. O operador perguntou por quê, eu medi, e a
resposta é que **o dado não existe**. O que existe, e é o que merecia o argumento desde o
começo, é bem menor e bem mais real:

- `.credentials/` — onde moram tokens de verdade (`programmer.token`, `identity.json`,
  `llm/*.key`);
- `.gk/operator.json` — nome do operador e caminho absoluto da máquina.

As correções continuam certas; a **narrativa** estava inflada, e uma narrativa inflada
calibra a próxima decisão errado — que é literalmente o que `AC-19` registra sobre
contagens inventadas, aplicado a argumentos em vez de a números.

### Achado colateral, para `AC-21`

`SMTP_ACCOUNT` está no `operator.json` de dois projetos e é um token **aposentado**
(`_RETIRED_PLACEHOLDERS`, 2026-08-10). A aposentadoria parou de perguntar e **não limpou o
que já estava guardado**. É o primeiro caso concreto e verificável de "resposta guardada
para um slot que não existe mais", e é o cliente natural do caminho de eliminação de
`AC-21` — antes e independentemente dos seis de doação.

---

## Decisão do operador, 2026-08-13 — os slots de doação saem, sem exceção

> *"Sobre o PIX e outras questões similares, não pode haver referência alguma. A não ser
> que você esteja confundindo a landing-page de agents e governancekit que sim tem
> informação para doações (três meios distintos)."*

Não havia confusão, e a distinção que ele nomeia é exatamente a certa:

| onde | o que fica |
|---|---|
| **landing pages** de `AI-Agents` e `GovernanceKit` (`docs/index.html`, `docs/intro.html`) | a seção de doação, com os **três meios reais** — não são instaladas em projeto nenhum |
| **o kit** — `_PLACEHOLDER_DESCRIPTIONS`, `_SENSITIVE_PLACEHOLDERS`, prompts, `.gk/secrets.json` | **nenhuma referência**, nem token, nem slot, nem descrição |

Os seis nomes saem: `PIX_KEY_UUID`, `PIX_HOLDER_NAME`, `PIX_PAYLOAD`, `PIX_QR_BASE64`,
`ETH_WALLET_ADDRESS`, `KOFI_HANDLE`.

**Saída seca, não aposentadoria.** `_RETIRED_PLACEHOLDERS` existe para "para de perguntar,
continua substituindo em arquivo legado" — e aqui não há arquivo legado a servir: a
medição do parque mostra `.gk/secrets.json` inexistente em todo lugar e zero arquivos do
ref carregando os tokens. Manter o nome em qualquer lista contraria *"não pode haver
referência alguma"*.

Com os seis fora, `_SENSITIVE_PLACEHOLDERS` fica vazia e `.gk/secrets.json` deixa de ser
um conceito do produto. Isso simplifica `AC-21` (não há o que eliminar sob esses nomes),
encolhe `AC-22` para `OPERATOR_NAME`, e tira do `install-agents` seis perguntas que nunca
serviram para nada.

**`SMTP_ACCOUNT` segue o caminho oposto** e por decisão da mesma mensagem: volta como slot
de verdade, com credencial e instrução guiada. Ver `AC-28`. As duas decisões juntas dizem
o critério que faltava — **o kit declara o que ele usa, e só isso**.
