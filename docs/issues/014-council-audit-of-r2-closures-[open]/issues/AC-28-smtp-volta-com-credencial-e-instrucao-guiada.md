# Issue AC-28 — origem: decisão do operador, 2026-08-13 ("precisamos dele sim")

> **EMENDA 2026-08-26 — o registro passa a descrever o que foi implementado.**
> O desenho abaixo ("SMTP_ACCOUNT sai de `_RETIRED_PLACEHOLDERS` e volta a
> `_PLACEHOLDER_DESCRIPTIONS`") **não** foi o entregue, e a diferença é decisão
> tomada na implementação da Fase 0 (`74bfefa`, 2026-08-14), não deriva:
>
> - `SMTP_ACCOUNT` **permanece retirado** (`install_agents.py`,
>   `_RETIRED_PLACEHOLDERS`) e permanece em `_OPERATOR_PLACEHOLDERS`, pelo motivo
>   já gravado ali: um valor legado nunca pode cair na metade rastreada.
> - O endereço do operador entrou como **`OPERATOR_EMAIL`** em
>   `.credentials/identity.json` (`values`), lido por `governancekit/mailbox.py`
>   (`_ADDRESS_VALUE = "OPERATOR_EMAIL"`), que ainda **lê** o `SMTP_ACCOUNT` órfão
>   legado (`_LEGACY_ADDRESS_VALUES`) sem nunca reescrevê-lo — o alvo respondido
>   antes da aposentadoria funciona sem nova pergunta, que era o caso de prova do
>   plano de teste abaixo.
> - `SMTP_DOMAIN` **não voltou**: o domínio é derivado da parte pós-`@` do
>   endereço, exatamente como o item 4 abaixo previa ("provavelmente é derivável").
>   Um slot, não dois.
> - A credencial continua **apontada, nunca guardada**: `refs.SMTP_TOKEN` →
>   `.credentials/smtp.token` (o split `values`/`refs` do `identity.json.example`).
> - A instrução guiada saiu em `docs/advanced-usage*.html`, offline — nos **três
>   arquivos de língua**, mas a seção `mail` em si está em inglês nos três
>   (registrado para que "três línguas" não vire claim sem lastro; traduzir é
>   pendência menor, não deriva). O exemplo dos três trazia o endereço pessoal
>   real do operador; trocado por `operator@empresa-exemplo.com.br` em 2026-08-26
>   (o histórico do git ainda o carrega — isto não é eliminação).
> - O que cruza repositório (`.credentials/README.md` nas três línguas do AI-Agents,
>   `identity.json.example`, `sending-email.md`) segue com o dono **AI-Agents** e
>   não é coberto por esta emenda.
>
> Um desenho melhor que o encomendado, registrado aqui para que o próximo concílio
> leia o delta implementação×texto como **decisão implementada**, não como drift.

## AC-28 — `SMTP_ACCOUNT` volta, com credencial e instrução guiada por domínio [alta]

> **Isto reverte uma decisão documentada.** `SMTP_ACCOUNT` e `SMTP_DOMAIN` foram
> aposentados em 2026-08-10 por `AI-Agents#5`, com a justificativa gravada em
> `_RETIRED_PLACEHOLDERS`: *"the canonical contract names no email transport, so nothing
> asks for this any more"*. A reversão é decisão do operador, tomada em 2026-08-13, e
> está escrita **como reversão** para que o próximo concílio não a leia como deriva.

### Por que a reversão não contradiz o contrato

`sending-email.md` diz:

> *Email transport, sender identity and recipient lists are **project-specific**. Never
> carry them over from another project, from a previous session, or from memory.*

O contrato manda o **projeto** declarar o seu transporte. A aposentadoria leu isso como
"o kit não precisa do slot" e removeu o **mecanismo** — deixando o projeto sem nada com
que declarar. Restaurar um slot **por projeto** serve o contrato em vez de brigar com ele:
o que o contrato proíbe é herdar de outro projeto, não é ter onde guardar o próprio.

A evidência de que a remoção deixou um buraco está no parque: `SMTP_ACCOUNT` continua no
`operator.json` de `CodexBridge` e `CodexBridgeMobile`, respondido antes da aposentadoria
e órfão desde então — sem slot que o consuma e sem comando que o limpe.

### O que a entrega precisa ter

**1. O slot volta.** `SMTP_ACCOUNT` sai de `_RETIRED_PLACEHOLDERS` e volta a
`_PLACEHOLDER_DESCRIPTIONS`. Fica em `_OPERATOR_PLACEHOLDERS` — é identidade de quem
envia, per-programmer, e não pertence à metade compartilhada do manifesto.

**2. A credencial.** O endereço não basta: enviar exige token. O mecanismo já existe e não
precisa ser inventado — `identity.json.example` separa `values` (literais) de `refs`
(**caminhos** para arquivos de credencial, nunca o segredo):

```json
{ "values": { "SMTP_ACCOUNT": "" },
  "refs":   { "SMTP_TOKEN": ".credentials/smtp.token" } }
```

O arquivo em si é `.credentials/smtp.token`, com as mesmas regras dos irmãos
(`programmer.token`, `reviewer.token`): local, nunca commitado, modo restrito ao dono.

**3. A instrução guiada, que é a parte nova.** O operador não deve precisar descobrir
sozinho como gerar uma senha de aplicativo. A instrução é **por domínio**: o kit já sabe o
endereço, então sabe o provedor.

- Um documento no repositório — HTML, aberto localmente — que recebe o domínio e mostra o
  caminho daquele provedor: Google (App Passwords), Microsoft 365, Zoho, cPanel, e um
  ramo genérico para SMTP próprio.
- Cada ramo termina no mesmo lugar: *"cole o token em `.credentials/smtp.token`"*.
- Sem enviar o domínio para lugar nenhum. É um documento estático que decide localmente.

**4. `SMTP_DOMAIN` fica em aberto.** Ele foi aposentado junto e o operador não o pediu de
volta. Provavelmente é derivável do endereço; se não for, precisa de decisão própria.

### Escopo cruzando repositório

Isto toca `AI/Agents`, que o operador liberou:

- `.credentials/README.md` (e as versões `-ptbr`/`-es`) ganham a linha do `smtp.token` —
  hoje listam `programmer.token`, `reviewer.token` e `jira.json`;
- `identity.json.example` ganha o par `values`/`refs`;
- o documento HTML de instrução;
- `sending-email.md` passa a nomear onde o projeto declara o transporte, em vez de só
  dizer que ele é project-specific.

E arrasta o `_kit_snapshot.json`: acrescentar arquivo a `.credentials/` muda a tabela de
digests semeados, que `AC-3` acabou de derivar. O refresh cobre isso, mas a ordem importa
— release do AI-Agents primeiro, depois o refresh.

### Um defeito vizinho que entra junto

O `.credentials/.gitignore` do release cobre `*.token`, `jira.json` e `identity.json` e
**não cobre o subdiretório `llm/`** — medido pela lente de LGPD na crítica do grupo
remove-agents. Como esta issue acrescenta arquivo àquele diretório, é o momento certo de
corrigir a regra em vez de acrescentar mais um caso especial.

### ARO

- **Assumption**: o token SMTP é per-programmer, não por projeto compartilhado. Duas
  pessoas no mesmo projeto enviam cada uma pela sua conta. Se não for assim, o slot muda
  de metade e a decisão precisa estar escrita.
- **Risk**: reverter uma aposentadoria de três dias atrás pode reabrir o que
  `AI-Agents#5` fechou. A épica `011` está em `[review]` e trata exatamente da
  `§Sending Email` — ler as duas juntas antes de mexer.
- **Risk**: instrução por domínio envelhece — provedores mudam a tela de senha de
  aplicativo. Mitigação: o documento leva a URL oficial do provedor, não a captura de
  tela do fluxo.
- **Risk**: um alvo legado tem `SMTP_ACCOUNT` guardado de antes da aposentadoria. Ele
  deve ser **reaproveitado**, não perguntado de novo — e é o caso que prova que a
  reversão está certa.
- **Owner**: o operador.

### Plano de teste

- Alvo novo: `install-agents` pergunta `SMTP_ACCOUNT`, e a resposta vai para
  `operator.json`, nunca para `manifest.json`.
- Alvo legado com `SMTP_ACCOUNT` órfão: o valor é reaproveitado sem nova pergunta.
- `.credentials/smtp.token` é ignorado pelo git — e `llm/` também.
- O documento de instrução decide o ramo pelo domínio, offline, sem requisição.
- `doctor` reporta conta declarada sem token, e o remédio nomeia o documento.
- Mutação: devolver `SMTP_ACCOUNT` a `_RETIRED_PLACEHOLDERS` ⇒ vermelho.

### DoD

- O projeto tem onde declarar o próprio transporte, e o contrato continua proibindo
  herdar de outro.
- O token mora em `.credentials/`, ignorado, e o estado guarda o **caminho**, nunca o
  segredo.
- O operador consegue gerar a credencial seguindo instrução do próprio kit.
- A reversão de `AI-Agents#5` está registrada com data e motivo.
