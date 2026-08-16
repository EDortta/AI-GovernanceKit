set -u
cd /home/esteban/Sync/Projects/AI/GovernanceKit-main-merge
GK="PYTHONPATH=. python3 -m governancekit.cli"
T=$1; rm -rf "$T"; mkdir -p "$T"; git init -q "$T"

echo "### 1. instalação limpa + identidade do operador"
eval $GK --root "$T" install-agents --non-interactive --accept-generated --skip-project-configuration >/dev/null 2>&1
eval $GK --root "$T" configure --set OPERATOR_NAME=Esteban 2>&1 | tail -2

echo; echo "### 2. o operador escreve regra no AGENTS.md e o projeto cria arquivo próprio dentro de .docs/agents/"
printf '\n## Project rules\n\nreviewer: ana@example.org\n' >> "$T/AGENTS.md"
echo "REGRA DO PROJETO" > "$T/.docs/agents/our-reviewer.md"

echo; echo "### 3. upgrade #1"
eval $GK --root "$T" install-agents --upgrade --non-interactive --accept-generated --skip-project-configuration 2>&1 | grep -E "^(Preserved|Replaced|Kept|Backed up) |^  (kept|stashed|WARNING)" | head -12

echo; echo "### 4. upgrade #2 — a poison do manifesto só aparece aqui"
eval $GK --root "$T" install-agents --upgrade --non-interactive --accept-generated --skip-project-configuration 2>&1 | grep -E "^(Preserved|Replaced|Kept|Backed up) |^  (kept|stashed|WARNING)" | head -12

echo; echo "### 5. estado final"
grep -q "reviewer: ana" "$T/AGENTS.md" && echo "AGENTS.md: regra do operador INTACTA" || echo "AGENTS.md: REGRA PERDIDA"
[ -f "$T/.docs/agents/our-reviewer.md" ] && echo ".docs/agents/our-reviewer.md: arquivo do projeto INTACTO" || echo "arquivo do projeto PERDIDO"
python3 -c "
import json;d=json.load(open('$T/.gk/manifest.json'))['files']
print('manifesto reivindica o arquivo do projeto?', '.docs/agents/our-reviewer.md' in d)
print('manifesto aprendeu o AGENTS.md do projeto?', 'AGENTS.md' in d and d['AGENTS.md']!=__import__('hashlib').sha256(open('$T/AGENTS.md','rb').read()).hexdigest())"
grep -c "OPERATOR_NAME" "$T/AGENTS.md.kit-new" 2>/dev/null | xargs -I{} echo "placeholders crus no .kit-new: {}"
grep -q "Esteban" "$T/AGENTS.md.kit-new" && echo ".kit-new: RENDERIZADO" || echo ".kit-new: cru"
echo; echo "### 6. doctor"
eval $GK --root "$T" doctor 2>&1 | grep -iE "sending email|manifest" | head -4

echo
echo "### 7. adoção de contexto — alvo novo, com README, SEM provider de LLM"
# Caso separado: o alvo acima roda com --skip-project-configuration de propósito, então
# o passo de contexto nem executa nele. Aqui o que se verifica é o contrário: que a
# adoção escreve os dois documentos, deixa os flags em `no` e diz que o gate está fechado.
C="${T}-contexto"; rm -rf "$C"; mkdir -p "$C"; git init -q "$C"
printf '# Alvo\n\nUm serviço de cobrança para igrejas.\n' > "$C/README.md"
eval $GK --root "$C" install-agents --non-interactive --accept-generated 2>&1 \
  | grep -E "^  (wrote|kept|Seeded)|Start Gate|No provider is configured" | head -8
echo "  ---"
grep -m1 "project_context_ready" "$C/docs/software-overview.md"
grep -m1 "limits_ready" "$C/docs/limits.md"
kit=$(grep -c "universal, reusable agent-governance bundle" "$C/docs/software-overview.md" || true)
echo "  ocorrências do texto do kit: ${kit:-0} (esperado 0)"
eval $GK --root "$C" doctor 2>&1 | grep -E "readiness documents|software-overview" | head -3
