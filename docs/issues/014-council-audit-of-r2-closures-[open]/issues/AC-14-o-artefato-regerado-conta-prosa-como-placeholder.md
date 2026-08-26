# Issue AC-14 — origem: concílio de fechamentos, 2026-08-13 (lente: the migrator)

## AC-14 — o artefato que É o fechamento tem a mesma classe de defeito que ele fecha [média]

### Contexto

O achado `ade371f5#7` era sobre um `grep` do `verify-elo4.sh` que descartava o cabeçalho
`Replaced N kit file(s)` e colava o arquivo substituído sob `Preserved`. O fechamento:
*"filtro reescrito para mostrar todos os cabeçalhos; artefato regerado"*.

O filtro dos cabeçalhos foi de fato reescrito e está correto — conferido contra os cinco
cabeçalhos que `cli.py:660,672,683,690` imprime.

No **mesmo script**, uma segunda linha continua medida por um `grep` que não mede o que a
legenda diz (`scripts/verify-elo4.sh:27`). O artefato commitado como prova do fechamento
—`docs/issues/011-sending-email-canonico-[review]/elo4-verificacao.md:32-33` — imprime
duas linhas contraditórias em sequência:

```
placeholders crus no .kit-new: 1
.kit-new: RENDERIZADO
```

A contagem usa `grep -c "OPERATOR_NAME"`, que casa a **prosa** do `AGENTS.md`
(`` (`OPERATOR_NAME`, entre chaves duplas) ``, linha 88), não os placeholders `{{…}}`. O
número real é **0**.

### Reprodução

```
$ sed 's/{{OPERATOR_NAME}}/Esteban/g' AI-Agents/AGENTS.md > AGENTS.md.kit-new
raw {{OPERATOR_NAME}} actually left in the rendered .kit-new: 0
what scripts/verify-elo4.sh:27 measures and prints:
placeholders crus no .kit-new: 1
.kit-new: RENDERIZADO
--- the prose line it counts:
88:(`OPERATOR_NAME`, entre chaves duplas), inclusive em
```

### Objetivo

Que o artefato de verificação meça o que sua legenda afirma, e que artefato de
verificação passe pela mesma barra de evidência que o código.

### Escopo

- O `grep` conta `{{OPERATOR_NAME}}`, com as chaves — o que a legenda diz.
- Varrer o script inteiro por outras contagens cuja legenda não corresponda à medição.
  Esta é a segunda linha do mesmo arquivo com esse defeito; a terceira não pode aparecer
  num terceiro concílio.
- **Regerar o artefato** e conferir os números à mão uma vez. O artefato hoje documenta 6
  passos e o script ganhou um passo 7 em `6116eba` sem regeração — pergunta 11 do RESUME,
  que esta issue absorve.
- Escrever a regra: **artefato de verificação commitado como prova de fechamento é
  entrega, e responde ao §2 como qualquer outra.** Um número errado num artefato de prova
  é pior que nenhum artefato.

### ARO

- **Assumption**: o artefato é lido por humano e por agente como evidência. Se fosse
  descartável, não estaria commitado.
- **Risk**: rodar o script escreve num alvo e faz `git init` — cuidado para não escrever
  perto do worktree (ver `governancekit-worktree-gitfile-hazard`).
- **Risk**: regerar muda o artefato de uma épica em `[review]` (`011`). Ver com o
  operador se o artefato regerado entra na 011 ou vive na 014.
- **Owner**: a definir.

### Plano de teste

- Alvo com `.kit-new` totalmente renderizado ⇒ o script imprime `0`.
- Alvo com um `{{TOKEN}}` cru de verdade ⇒ imprime `1` e a legenda bate.
- O artefato regerado tem 7 passos e nenhuma linha contraditória.
- Mutação: voltar o `grep` sem chaves ⇒ o teste (ou a conferência escrita) acusa.

### DoD

- Toda contagem do script mede o que sua legenda afirma.
- O artefato está regerado e consistente com o script atual.
- A regra sobre artefato de verificação como entrega está escrita.
