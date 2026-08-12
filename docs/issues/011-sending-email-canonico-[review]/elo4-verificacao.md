# Verificação no elo 4 — alvo governado real, release pinado v1.2.1

Rodado em 2026-08-12 contra um alvo criado do zero, não no repositório-fonte.
O concílio cobrou este artefato: a rodada anterior afirmou "verificado no elo 4"
e não deixou nada que a próxima sessão pudesse reler. Script: `scripts/verify-elo4.sh`.

```
### 1. instalação limpa + identidade do operador
  AGENTS.md
Note: host identity not configured yet (missing: host_id). Run `configure` interactively or pass --operator-name/--host-id/--instance-path to set it.

### 2. o operador escreve regra no AGENTS.md e o projeto cria arquivo próprio dentro de .docs/agents/

### 3. upgrade #1
Preserved 1 project-authored file(s) inside kit directories (not shipped by this kit version):
  kept: .docs/agents/our-reviewer.md
Kept 1 protected file(s) that differ from what this kit installed — the new version is beside them, unmerged:
  kept: AGENTS.md -> new version at AGENTS.md.kit-new

### 4. upgrade #2 — a poison do manifesto só aparece aqui
Preserved 1 project-authored file(s) inside kit directories (not shipped by this kit version):
  kept: .docs/agents/our-reviewer.md
Kept 1 protected file(s) that differ from what this kit installed — the new version is beside them, unmerged:
  kept: AGENTS.md -> new version at AGENTS.md.kit-new

### 5. estado final
AGENTS.md: regra do operador INTACTA
.docs/agents/our-reviewer.md: arquivo do projeto INTACTO
manifesto reivindica o arquivo do projeto? False
manifesto aprendeu o AGENTS.md do projeto? True
placeholders crus no .kit-new: 1
.kit-new: RENDERIZADO

### 6. doctor
[PASS] AI-Agents manifest: all tracked kit paths present
[PASS] §Sending Email contract: canonical in .docs/workflows/sending-email.md
```
