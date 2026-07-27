# WK-20260727-context-optimization

Interpret the canonical AI-Agents context manifest without duplicating policy.
Acceptance requires deterministic inspect/build commands, explicit mandatory
failures, optional omission warnings, provenance, duplicate reporting, stable JSON,
and regression tests. The primary risk is silent loss of a mandatory contract;
mandatory sources are therefore atomic and fail closed.

No embeddings, remote services, provider-specific routing, LLM summaries, or
external telemetry are introduced.

## Contract notes

- backward compatible: yes
- contract changed: yes (additive CLI surface)
- migration required: no
- downstream consumers affected: none unless they opt into the new commands
