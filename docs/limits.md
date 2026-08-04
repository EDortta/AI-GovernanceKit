# Agent Operational Limits

## Metadata

- work_id: WK-20260504-bootstrap-governancekit
- date: 2026-05-04
- owner: maintainer
- limits_ready: yes

This file defines hard boundaries for agent execution in this repository.

## Allowed

- Implement work explicitly requested by the user.
- Perform necessary supporting refactors required for safe implementation or testing.
- Update tests, docs, and issue artifacts directly related to requested work.
- Create CLI, runtime, MCP, IDE, or CI integration code only when covered by an active issue.
- Use official migration workflows if persistence is introduced later.

## Not Allowed

- Unrelated refactors or speculative improvements.
- Architecture expansion not required by the active issue.
- Silent API, schema, or interface contract changes.
- Creating empty or low-content GitHub/Jira issue or PR artifacts.
- Marking issues as solved, finished, or done without objective implementation evidence.
- Committing credentials, tokens, `.env*` files, caches, backups, or generated local runtime data.

## Branch and Workflow Constraints

- Never start implementation on `main` or `master`.
- Create or switch branches only with explicit human permission.
- Work must remain on the approved branch for the active issue.
- At each stage end, update `handoff.md`, the active epic `RESUME.md`, and `docs/napkin-lessons.md`.

## Security and Secrets

- Never expose secrets, tokens, credentials, or sensitive raw payloads in logs, code, commits, issue bodies, or responses.
- Runtime-impacting changes require a security review.
- Changes that execute shell commands, read files, write files, or call external services must document the security impact and validation approach.

## Current Boundary

The current approved work is bootstrap only. Runtime implementation starts in a later issue after the product boundaries and first executable slice are defined.

