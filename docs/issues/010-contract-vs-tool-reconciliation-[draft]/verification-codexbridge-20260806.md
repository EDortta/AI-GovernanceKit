# Verificação do parque instalado — `AI/CodexBridge`, 2026-08-06

Revisão **somente leitura**, a pedido do operador, depois que ele rodou
`governancekit install-agents --upgrade` no CodexBridge (`AGENTS.md` reescrito às 12:36).
Nada foi alterado naquele checkout.

Serve para fechar a lacuna que o `RESUME.md` apontava: as issues A1–A10/G1–G5 foram
escritas contra a instalação de 04/08 17:20, anterior ao trabalho daquele dia. Agora há
uma instalação **posterior** para conferir.

## Funcionou

**A1 — arquivos de prontidão são do projeto.** `docs/limits.md` (6.633 B) e
`docs/software-overview.md` (4.568 B) estão sob `docs/`. Não existe `.docs/limits.md`
nem `.docs/software-overview.md`.

**A migração reversa tratou o caso de conflito.** `.gk/readiness-migration/` contém
`limits.md` e `software-overview.md` — as cópias que estavam em `.docs/` foram postas de
lado porque `docs/` já tinha versões próprias. `docs/` venceu, nada foi perdido, e a
cópia perdedora ficou recuperável. É exatamente o desenho, exercitado num projeto real
com conflito real.

## Não funcionou — três defeitos vivos na instalação nova

**G2 confirmado, e mais estreito do que a issue supõe.**
`.docs/governancekit-integration.json` continua com mtime de **31/07 13:33** e declara
`"ref": "v1.1.6"`. O `AGENTS.md` ao lado foi reescrito **hoje às 12:36** pelo mesmo
upgrade. Não é incompatibilidade de faixa de versão: **o upgrade reescreve o contrato e
não toca no manifesto de integração**. Um projeto pode carregar contrato v1.1.7 e
declarar-se v1.1.6 indefinidamente, e nada reprova.

**A3 confirmado em campo.** O `.gitignore` do CodexBridge não tem nenhuma entrada
cobrindo `.env`. As únicas linhas próximas são `.venv/` e `venv/`. É o defeito que a
issue descreve, agora observado num projeto governado de verdade.

**O vazamento de memória de sessão não foi reparado — e não podia ter sido.**
`handoff.md` (576 linhas, 37 KB) e `docs/napkin-lessons.md` (77 linhas) do CodexBridge
são conteúdo do **AI/Agents**:

- o handoff cita `docs/index.html`, GitHub Pages `main:/docs`, links do EDortta, Pix,
  ETH, Ko-fi e exemplos de instalação `v1.1.4` — trabalho do repositório do kit,
  não do CodexBridge. 22 menções ao kit contra 2 ao próprio CodexBridge.
- o napkin abre com lições sobre orçamento de contexto e reserva declarada — a série do
  kit de 27/07.

Os dois têm mtime de **04/08**, e o upgrade de hoje não os tocou. Está correto que não
tenha tocado: são arquivos do projeto e o instalador não sobrescreve `docs/`. Os
templates que entraram em 04/08 impedem **novos** vazamentos; **não reparam este**.
Reparar exige decisão humana — o arquivo pode já ter recebido entradas legítimas do
CodexBridge por cima.

## Observado, sem juízo

`.docs/` e `.gk/` aparecem como **não rastreados** no `git status` do CodexBridge. O kit
está instalado e nunca foi commitado ali. Não é defeito do kit; é estado do projeto, e o
operador pode ter motivo. Registrado porque um `git add -A` naquele checkout arrastaria
o kit inteiro para dentro de um commit sem querer — que é precisamente o cenário da §7
proposta em C1.

## Efeito no placar

| Issue | Antes | Agora |
|---|---|---|
| **A1** | "falta confirmar contra o kit instalado" | **confirmado funcionando** |
| **A3** | confirmado por leitura de código | **confirmado em campo** |
| **G2** | "vale para a cópia instalada" | **causa isolada**: o upgrade não reescreve o manifesto |
| vazamento de sessão | corrigido na fonte | **CodexBridge segue contaminado**; reparo é decisão humana |
