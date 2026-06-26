# AGENTS.md


## Prefixo obrigatório nas mensagens ao operador

Toda mensagem de texto enviada diretamente ao operador ([OPERATOR_NAME]) **deve começar
com "[OPERATOR_NAME], "** — incluindo a vírgula e o espaço.

Aplica-se a: respostas no chat, resumos de sessão, perguntas de clarificação.
Não se aplica a: tool calls, conteúdo de arquivos, corpos de issue/PR.


Universal operating contract for this repository.

Instruction precedence:
1. system/runtime instructions
2. this `AGENTS.md`
3. local user preferences

## Required Context

Before implementation starts, agents must read:

- `docs/software-overview.md`
- `docs/limits.md`

Implementation may start only when:

- `docs/software-overview.md` contains `project_context_ready: yes`
- `docs/limits.md` contains `limits_ready: yes`

## Project Purpose

AI GovernanceKit is a runtime orchestration toolkit for agentic software delivery. It should remain tool-agnostic and reusable across coding agents, IDEs, shells, and CI systems.

## Engineering Rules

- Prefer secure, correct, maintainable changes over speed.
- Keep scope tight to the active issue.
- Preserve backward compatibility unless explicitly changed by the issue.
- Do not introduce hidden behavior or undocumented side effects.
- Add or update tests when behavior changes.
- Do not commit secrets, credentials, caches, backups, or local runtime artifacts.

## Branch Rules

- Do not start implementation on `main` or `master`.
- Create or switch branches only with explicit human permission.
- Use `feature/uc-<NNN>/<short-description>` for local tracker work.

## Session Rules

At the end of each implementation stage/session, update:

- `handoff.md`
- the active epic `RESUME.md`
- `docs/napkin-lessons.md`

The active `RESUME.md` must contain exactly one clear `Next Step (DO THIS FIRST)`.

## Security

Runtime-impacting changes require a security review covering input validation, injection, authorization, authentication, data exposure, logging, error handling, privilege escalation, and privacy impact where applicable.



---

## Sending Email

When a task requires sending email, credentials and mechanism live in `~/.config/email/` — **local-only, never tracked in any repo**.

| File | Purpose |
|------|---------|
| `~/.config/email/credentials.conf` | SMTP account (`[SMTP_ACCOUNT]`) + Gmail app password |
| `~/.config/email/send.py` | CLI/script helper — reads credentials automatically |

```bash
# Plain text
python3 ~/.config/email/send.py --to dest@example.com --subject "Assunto" --body "Corpo"

# HTML body
python3 ~/.config/email/send.py --to dest@example.com --subject "Assunto" --body "<b>ok</b>" --html

# Multiple recipients
python3 ~/.config/email/send.py --to a@x.com --to b@x.com --subject "Assunto" --body "Corpo"

# Body from stdin
echo "Corpo" | python3 ~/.config/email/send.py --to dest@example.com --subject "Assunto"
```

Never hardcode or commit credentials. Always read from `~/.config/email/credentials.conf`.

