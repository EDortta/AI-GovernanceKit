# Issue AC-21 — origem: crítica de quatro céticos sobre AC-1, 2026-08-13 (lente: LGPD)

## AC-21 — a de-adoção não elimina dado pessoal, e multiplica as cópias [alta]

### Contexto

O comando cujo trabalho é *"não deixar nada para trás"* deixa todo o dado pessoal para
trás, e ainda cria uma cópia nova.

`build_removal_plan` monta o plano a partir de `files` do `.gk/manifest.json`, que nunca
contém `.gk/*`. Então nenhum caminho apaga `.gk/operator.json` (nome do operador,
caminho absoluto da máquina) nem `.gk/secrets.json` (chave PIX, nome do titular,
carteira ETH).

Pior: `apply_removal_plan` **copia** o `AGENTS.md` já renderizado — com o nome do
operador dentro — para `.gk/remove-agents-backup/<ts>/`. A de-adoção aumenta o número de
cópias do dado pessoal no disco.

Não existe comando de eliminação no kit.

### Reprodução

```
surviving files under .gk after `remove-agents`:
    .gk/.gitignore
    .gk/manifest.json
    .gk/operator.json
    .gk/remove-agents-backup/20260813T122741Z/AGENTS.md
    .gk/remove-agents-backup/20260813T122741Z/restore-manifest.json
    .gk/secrets.json

.gk/operator.json still on disk: {"metadata": {"OPERATOR_NAME": "Esteban Calegari",
                                               "PROJECT_ROOT": "/tmp/tmpqo1teqro"}, ...}
.gk/secrets.json still on disk:  {"metadata": {"PIX_HOLDER_NAME": "ESTEBAN CALEGARI DA SILVA",
                                               "PIX_PAYLOAD": "00020126PIXSECRET"}, ...}
```

### Objetivo

Que o operador consiga eliminar o que o kit guardou sobre ele, e que a de-adoção não
seja um caminho que **cria** cópia de dado pessoal sem dizer.

### Escopo

- Um caminho de eliminação explícito — `remove-agents --purge-state`, ou um comando
  próprio. Não pode ser o default silencioso: o backup existe para permitir arrependimento,
  e apagá-lo por padrão troca um problema por outro.
- O plano **nomeia** os arquivos de estado que sobreviverão, e diz que carregam dado
  pessoal. Hoje eles são invisíveis ao plano, então o operador não sabe que existem.
- O backup que copia arquivo renderizado avisa que está copiando dado pessoal, e o
  diretório tem retenção declarada (hoje: para sempre).
- Fora de escopo: o histórico do git. Um valor já commitado não é eliminável por este
  kit, e a issue não deve fingir que é — mas o `doctor` pode **detectar** e avisar.

### ARO

- **Assumption**: LGPD art. 16 (eliminação após o término do tratamento) se aplica ao
  que o kit guarda localmente sobre o operador. O operador é o titular e o controlador
  ao mesmo tempo na maioria dos casos, o que reduz o risco jurídico — mas não em equipe,
  que é exatamente onde `AC-20` mostra dado de terceiro entrando.
- **Risk**: apagar estado quebra o arrependimento (`restore-manifest.json`). Por isso a
  eliminação é explícita, não default.
- **Risk**: prometer "eliminado" quando o git ainda tem o valor é a classe de afirmação
  sem lastro que esta épica inteira audita. A mensagem tem de ser exata.
- **Owner**: o operador.

### Plano de teste

- `remove-agents plan` **nomeia** `.gk/operator.json` e `.gk/secrets.json` como estado
  que sobrevive.
- Com a flag de eliminação: os dois somem, e a saída diz o que foi eliminado.
- Sem a flag: continuam, e o operador foi avisado.
- O backup de arquivo renderizado é anunciado como contendo dado do operador.
- Mutação: remover o aviso ⇒ vermelho.

### DoD

- Existe caminho de eliminação, explícito e documentado.
- O plano não esconde mais o estado que sobrevive.
- Nenhuma mensagem afirma eliminação que o kit não pode entregar.
