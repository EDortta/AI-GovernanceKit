# Issue AC-18 — origem: concílio de fechamentos, 2026-08-13 (lente: the claim auditor)

## AC-18 — o consentimento que nomeia o que sai não é exercitado por teste nenhum [média]

### Contexto

O achado `6bb1027e#9` era de privacidade: *"o consentimento diz 'a descrição deste
projeto' e o ramo de revisão manda o documento inteiro — onde moram DSN de produção e
caminho de vault"*. O fechamento: *"o prompt nomeia o que sai, incluindo os arquivos sob
revisão"*.

A correção existe (`cli.py:1340`): `if reviewed: what += f", plus the full text of …"`.

Nenhum teste a alcança. O único teste que toca o prompt (`tests/test_cli_help.py:181`)
exercita o ramo de **rascunho** e casa com o prefixo
`Send this project's description and detected evidence to openai / gpt-test?` — que a
versão **defeituosa** também produz.

### Reprodução

```
mutate cli.py: "    if reviewed:\n        what += f\", plus the full text of {', '.join(reviewed)}\"\n"
            -> "    if False:\n        pass\n"
pytest tests/       =>  506 passed, 2 skipped, 6 subtests passed in 16.56s
grep -rn 'full text of' tests/  =>  nenhum resultado
```

O gatilho do achado — documento em estado `authored`, provider configurado, ramo de
revisão, DSN de produção no payload — não é exercido por nada.

### Objetivo

Que o texto de consentimento que descreve o que sai do processo esteja protegido por
teste, e que a proteção cubra o payload, não só a frase.

### Escopo

- Teste que monta o gatilho do achado: documento `authored`, provider configurado,
  resposta `y`, `request_completion` mockado — e afirma **duas** coisas:
  1. o prompt nomeia os arquivos sob revisão;
  2. o payload capturado contém exatamente o que o prompt nomeou, e nada mais.
- A segunda asserção é a que importa e é a que falta em todo lugar: hoje o repositório
  testa o **texto** do consentimento, nunca a correspondência entre o texto e o que
  efetivamente sai pela rede. Consentimento cujo texto é testado e cujo payload não é,
  é a forma de defeito que este achado teve.
- Varrer os demais pontos onde o kit envia conteúdo para fora (`adoption.py`,
  `scope_conversation.py`) pela mesma pergunta.
- **Esta issue é a principal candidata da crítica de LGPD desta épica**: consentimento
  informado, minimização, e correspondência entre o que se declara e o que se transfere.

### ARO

- **Assumption**: o kit só envia o que o prompt nomeia. É exatamente isso que não está
  provado.
- **Risk**: mockar `request_completion` testa a intenção, não a rede. Aceitável: o ponto
  de captura é onde o payload é montado.
- **Risk**: a varredura pode achar outros pontos de envio sem consentimento
  correspondente — cada um vira issue própria.
- **Owner**: a definir.

### Plano de teste

- Ramo de revisão ⇒ o prompt nomeia os arquivos, e o payload contém só eles.
- Ramo de rascunho ⇒ o teste atual continua verde.
- Recusa (`n`) ⇒ nenhum payload é montado.
- Mutação: `if reviewed:` → `if False:` ⇒ **vermelho**. Critério de aceite.

### DoD

- A mutação fica vermelha.
- O teste afirma sobre o payload, não só sobre o prompt.
- A varredura dos pontos de envio está registrada.
