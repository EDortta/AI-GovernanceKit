#!/usr/bin/env python3
"""Run PLANO-UNIFICADO.md unattended, idempotently, across reboots.

Invoked by an `@reboot` crontab line and by hand. Every decision it makes is written to
a state file before it acts, so a reboot in the middle of anything resumes at the next
undone step rather than repeating the last one.

WHAT IT DOES PER ISSUE
    implement -> council (4 lenses) -> apply -> council again -> ... -> commit -> merge

WHAT IT DELIBERATELY DOES NOT DO, AND WHY
    * never pushes to `main`, and never runs `merge-to-main`: `main` carries product,
      and this is the wrong actor to decide what ships;
    * never touches a repository outside the two named here — three governed projects
      carry a withdrawn file and cleaning them is the operator's call, not a script's;
    * never marks an issue done that its council did not pass. After MAX_ROUNDS it
      stops that issue, records `needs_operator`, and moves on. A loop that keeps going
      until green, with nobody reading the findings, can reach green by weakening the
      test instead of fixing the code, and nothing inside the loop can tell those apart.

THE HONEST LIMIT
    Every issue implemented in the session that produced this plan failed its FIRST
    council; several took three to five rounds; and twice a lens caught the author
    asserting something the artefact did not support. This script reproduces the
    mechanism, not the judgement. Read `report.md` in the morning before trusting a
    green.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENTS = REPO.parent / "Agents"
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
STATE_DIR = STATE_HOME / "ai-agents"
STATE_FILE = STATE_DIR / "plan-run.json"
LOG_FILE = STATE_DIR / "plan-run.log"
REPORT = REPO / "docs/issues/014-council-audit-of-r2-closures-[draft]/report.md"
STOP_FILE = STATE_DIR / "plan-run.STOP"

BRANCH = "development"
MAX_ROUNDS = 4
CLAUDE_TIMEOUT = 3600

LENSES = (
    ("LGPD", "dado pessoal e financeiro: o que é guardado, onde, e quem pode ler"),
    ("the fix auditor", "a correção fecha o achado, ou muda o defeito de lugar?"),
    ("the second caller", "qual é o próximo call site, leitor ou escritor que isto não cobre?"),
    ("the migrator", "o que acontece com alvos já processados sob o comportamento antigo?"),
)

# Phase -> ordered issue ids. Mirrors PLANO-UNIFICADO.md; the script never invents work.
PLAN: list[tuple[str, list[str]]] = [
    ("fase-0-fechar-arvore", ["CONFIRM-TREE", "AC-28-emenda"]),
    ("fase-1-override", ["AC-29", "AC-21", "AC-20", "AC-22", "AC-13"]),
    ("fase-2-campo", ["AC-23", "AC-15"]),
    ("fase-3-bash", ["AC-30", "AC-7", "AC-14", "CREDENTIALS-GITIGNORE-LLM"]),
    ("fase-4-produto", ["AC-24", "AC-27", "AC-28"]),
    ("fase-5-testes", ["AC-11-16-17-18", "AC-26", "AC-8", "AC-9", "AC-12"]),
    ("fase-6-registro", ["AC-19", "CONCILIO-GERAL"]),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{now()}  {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"started": now(), "issues": {}, "finished": False}


def save_state(state: dict) -> None:
    """Written BEFORE acting, so a reboot resumes rather than repeats."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def run(cmd: list[str], cwd: Path = REPO, timeout: int = 900) -> tuple[int, str]:
    try:
        done = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return done.returncode, (done.stdout + done.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s: {' '.join(cmd)}"


def claude(prompt: str) -> tuple[int, str]:
    """One headless Claude Code turn. The only place work is actually decided."""
    return run(["claude", "-p", prompt], timeout=CLAUDE_TIMEOUT)


def suite_passes() -> tuple[bool, str]:
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly"], timeout=1800)
    tail = "\n".join(out.strip().splitlines()[-3:])
    return code == 0, tail


def stopped() -> bool:
    if STOP_FILE.exists():
        log(f"STOP file present at {STOP_FILE} — standing down")
        return True
    return False


def implement(issue: str) -> tuple[int, str]:
    return claude(
        f"Leia docs/issues/014-council-audit-of-r2-closures-[draft]/PLANO-UNIFICADO.md e "
        f"implemente a issue {issue} no repositório {REPO}. Regras: sem bash (Python "
        f"apenas); cada correção sai com teste que fica VERMELHO sem ela, verificado por "
        f"mutação; não toque em nenhum repositório fora de {REPO} e {AGENTS}; não faça "
        f"commit. Ao terminar, responda em uma linha o que mudou."
    )


def council(issue: str, round_number: int) -> list[tuple[str, bool, str]]:
    verdicts: list[tuple[str, bool, str]] = []
    for lens, question in LENSES:
        code, out = claude(
            f"Você é um membro de concílio com UMA lente: **{lens}** — {question}. "
            f"Objeto: o `git diff` não commitado em {REPO}, referente à issue {issue}, "
            f"rodada {round_number}. Regras do council.md §2: um achado só sobrevive com "
            f"gatilho concreto, resultado errado observável, file:line e reprodução ou "
            f"teste vermelho; sem isso é PERGUNTA, e perguntas se escrevem. Proibido: "
            f"git de escrita em qualquer lugar, editar arquivo de qualquer repositório, "
            f"rodar o kit contra projeto real. Para testar mutação copie só governancekit/ "
            f"e tests/ para /tmp. Responda com a primeira linha sendo exatamente PASS ou "
            f"FAIL, e o resto sendo os achados."
        )
        text = (out or "").strip()
        passed = text.upper().startswith("PASS")
        verdicts.append((lens, passed, text[:4000]))
        log(f"    {lens}: {'PASS' if passed else 'FAIL'}")
    return verdicts


def apply_findings(issue: str, verdicts: list[tuple[str, bool, str]]) -> tuple[int, str]:
    findings = "\n\n".join(f"### {lens}\n{text}" for lens, ok, text in verdicts if not ok)
    return claude(
        f"Concílio sobre a issue {issue} em {REPO} devolveu os achados abaixo. Aplique os "
        f"que forem coerentes com o resto do projeto; para cada um que NÃO aplicar, "
        f"escreva o motivo no arquivo da issue. Cada correção sai com teste que fica "
        f"vermelho sem ela. Sem bash. Sem commit.\n\n{findings}"
    )


def commit_and_merge(issue: str) -> tuple[bool, str]:
    """Commit on `development`. Never `main`, never `merge-to-main`."""
    code, out = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = out.strip()
    if branch != BRANCH:
        return False, f"refusing to commit on branch {branch!r}; expected {BRANCH!r}"
    code, out = run(["git", "add", "-A"])
    if code != 0:
        return False, out
    code, out = run([
        "git", "commit", "-m",
        f"feat({issue}): implementado sob PLANO-UNIFICADO, concílio verde",
    ])
    if code != 0 and "nothing to commit" not in out:
        return False, out
    return True, out.strip().splitlines()[0] if out.strip() else "committed"


def restart_service() -> str:
    """Local reinstall — the 'deploy local' the operator authorised. Never remote."""
    code, out = run([sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"], timeout=900)
    return f"pip install -e . -> rc={code}"


def write_report(state: dict) -> None:
    lines = [
        "# Relatório da execução noturna",
        "",
        f"- gerado: {now()}",
        f"- estado: {'CONCLUÍDO' if state.get('finished') else 'em andamento'}",
        "",
        "| issue | estado | rodadas | nota |",
        "|---|---|---|---|",
    ]
    for issue, data in state.get("issues", {}).items():
        lines.append(
            f"| {issue} | {data.get('status', '?')} | {data.get('rounds', 0)} | "
            f"{str(data.get('note', ''))[:90]} |"
        )
    lines += [
        "",
        "## Leia antes de confiar num verde",
        "",
        "Este script reproduz o mecanismo do concílio, não o julgamento. Na sessão que",
        "produziu o plano, TODA issue reprovou no primeiro concílio, várias levaram de",
        "três a cinco rodadas, e duas vezes uma lente pegou o autor afirmando algo que o",
        "artefato não sustentava. Um `needs_operator` abaixo é o script sendo honesto;",
        "um `done` merece a mesma desconfiança que qualquer outro verde.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def disarm() -> str:
    """Remove the @reboot line. Idempotent: absent is success."""
    code, current = run(["crontab", "-l"], timeout=60)
    if code != 0:
        return "no crontab to disarm"
    kept = [line for line in current.splitlines() if "run_plan.py" not in line]
    if len(kept) == len(current.splitlines()):
        return "already disarmed"
    proc = subprocess.run(["crontab", "-"], input="\n".join(kept) + "\n", text=True)
    return f"disarmed (rc={proc.returncode})"


def arm() -> str:
    """Install the @reboot line. Idempotent."""
    code, current = run(["crontab", "-l"], timeout=60)
    lines = current.splitlines() if code == 0 else []
    if any("run_plan.py" in line for line in lines):
        return "already armed"
    lines.append(f"@reboot /usr/bin/env python3 {Path(__file__).resolve()} >> {LOG_FILE} 2>&1")
    proc = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    return f"armed (rc={proc.returncode})"


def work_one(issue: str, state: dict) -> None:
    entry = state["issues"].setdefault(issue, {"status": "pending", "rounds": 0})
    if entry["status"] in {"done", "needs_operator"}:
        return
    log(f"  issue {issue}: {entry['status']}")

    if entry["status"] == "pending":
        entry["status"] = "implementing"
        save_state(state)
        code, out = implement(issue)
        entry["note"] = out.strip().splitlines()[-1][:200] if out.strip() else ""
        entry["status"] = "council"
        save_state(state)

    while entry["status"] == "council" and entry["rounds"] < MAX_ROUNDS:
        if stopped():
            return
        entry["rounds"] += 1
        save_state(state)
        log(f"  council round {entry['rounds']}")
        verdicts = council(issue, entry["rounds"])
        if all(ok for _, ok, _ in verdicts):
            entry["status"] = "green"
            save_state(state)
            break
        apply_findings(issue, verdicts)
        save_state(state)

    if entry["status"] != "green":
        entry["status"] = "needs_operator"
        entry["note"] = f"council still failing after {entry['rounds']} rounds"
        save_state(state)
        log(f"  {issue}: needs_operator")
        return

    ok, tail = suite_passes()
    if not ok:
        entry["status"] = "needs_operator"
        entry["note"] = f"suite red: {tail}"
        save_state(state)
        return

    merged, note = commit_and_merge(issue)
    entry["status"] = "done" if merged else "needs_operator"
    entry["note"] = note
    save_state(state)
    if merged:
        log(f"  {issue}: {restart_service()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="store_true", help="install the @reboot entry and exit")
    parser.add_argument("--disarm", action="store_true", help="remove it and exit")
    parser.add_argument("--status", action="store_true", help="print state and exit")
    args = parser.parse_args()

    if args.arm:
        print(arm())
        return 0
    if args.disarm:
        print(disarm())
        return 0

    state = load_state()
    if args.status:
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0

    if state.get("finished"):
        log("plan already finished; disarming")
        print(disarm())
        return 0

    log(f"run starting — repo={REPO} branch target={BRANCH}")
    for phase, issues in PLAN:
        for issue in issues:
            if stopped():
                write_report(state)
                return 1
            log(f"[{phase}] {issue}")
            try:
                work_one(issue, state)
            except Exception as exc:  # noqa: BLE001 — one issue must not kill the night
                state["issues"].setdefault(issue, {})["status"] = "needs_operator"
                state["issues"][issue]["note"] = f"{type(exc).__name__}: {exc}"[:200]
                save_state(state)
                log(f"  {issue} raised {type(exc).__name__}: {exc}")
            write_report(state)

    outstanding = [
        issue for issue, data in state["issues"].items() if data.get("status") != "done"
    ]
    state["finished"] = not outstanding
    state["ended"] = now()
    save_state(state)
    write_report(state)

    if state["finished"]:
        log(f"plan complete — {disarm()}")
    else:
        log(f"{len(outstanding)} issue(s) need the operator; staying armed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
