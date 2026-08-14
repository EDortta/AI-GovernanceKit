# Issue AC-8 — origem: concílio de fechamentos, 2026-08-13 (lente: the sweep skeptic)

## AC-8 — a guarda de symlink foi para um irmão só, e o install desta entrega aborta [alta]

### Contexto

O achado `6bb1027e#11` era: *"README.md como symlink ⇒ `author-context` morre com
traceback cru de `UnsafePathError`"*. O fechamento guardou `find_description`
(`context_authoring.py`), com teste que morde.

`classify_document`, **30 linhas acima, no mesmo módulo**, faz a mesma chamada sem
guarda:

```python
path = safe_path(root, root / rel)      # context_authoring.py:116
```

E é pior que o achado original, porque `classify_document` tem dois chamadores:

- `context_authoring.py:211` (`build_authoring_plan`) — o mesmo `author-context`
- `adoption.py:174` (`apply_adoption_proposal`) — o **`install-agents` desta mesma
  entrega**, que aborta no meio do passo de adoção

O gatilho é comum: monorepo com `docs/ -> ../shared/`, ou
`docs/software-overview.md` apontando para um documento compartilhado.

### Reprodução

```
$ ln -s ../shared/overview.md T/docs/software-overview.md
$ governancekit --root T author-context
  File ".../context_authoring.py", line 211, in build_authoring_plan
    state = classify_document(root, rel)
  File ".../context_authoring.py", line 116, in classify_document
    path = safe_path(root, root / rel)
governancekit.path_safety.UnsafePathError: refusing symlink below --root: …/docs/software-overview.md
rc=1
$ python3 -c 'adoption.apply_adoption_proposal(...)'  -> mesmo UnsafePathError (adoption.py:174)
```

### Objetivo

Que um symlink em documento de readiness produza um veredito, nunca um traceback — em
todos os caminhos que classificam documento.

### Escopo

- `classify_document` trata `UnsafePathError`/`OSError` e devolve um estado que o
  chamador saiba exibir, com a mesma semântica que `find_description` adotou: o symlink
  não é tratado como documento do projeto, e o comando continua.
- Varrer **todos** os chamadores de `safe_path` em `governancekit/` — esta é a segunda
  vez que a mesma guarda falta num irmão. A lista sai escrita, mesmo que curta.
- Decidir e escrever o que um symlink significa aqui: *"não é descrição do projeto"* é a
  decisão que `find_description` já tomou; `classify_document` deve tomar a mesma, e a
  razão precisa estar num comentário, não implícita.
- Teste que cobre o caminho do `install-agents`, não só o do `author-context` — o achado
  original só cobriu um dos dois.

### ARO

- **Assumption**: recusar symlink é a política certa (`path_safety` existe por isso). A
  issue é sobre **como** a recusa chega ao operador, não sobre relaxá-la.
- **Risk**: engolir `OSError` largo demais esconde um disco quebrado. Mitigação:
  capturar estreito e distinguir na mensagem.
- **Risk**: um projeto real que usa symlink para `docs/` fica sem readiness e não entende
  por quê. Mitigação: a mensagem nomeia o arquivo e diz que symlink não é lido.
- **Owner**: a definir.

### Plano de teste

- `docs/software-overview.md` symlink + `author-context` ⇒ rc=0, veredito legível.
- O mesmo symlink + `install-agents` (caminho `apply_adoption_proposal`) ⇒ não aborta.
- `README.md` symlink continua coberto pelo teste de `6bb1027e#11`.
- Mutação: remover a guarda nova ⇒ os dois testes ficam vermelhos.

### DoD

- Nenhum caminho que classifica documento morre com traceback por symlink.
- A varredura de chamadores de `safe_path` está registrada.
- Teste cobre os **dois** chamadores, verificado por mutação.
