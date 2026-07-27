# Context benchmark

Measured 2026-07-27 with `cl100k_base` tokenizer estimate:

| Repository | Broad comparable contracts | Compiled implementation | Reduction |
|---|---:|---:|---:|
| AI-Agents | 24,530 | 15,253 | 37.8% |

For implementation plus runtime risk, the hardened compiler selects 19,221 tokens
from a usable budget of 21,000 while preserving a 1,000-token reserve.

Only AI-Agents currently has the v1.1.3 context manifest and complete contract
layout. The requested three-project comparison was not fabricated: dependent
projects must first upgrade normally. Add their measurements here after upgrade.
Counts are tokenizer-specific estimates, not universal model billing counts.
