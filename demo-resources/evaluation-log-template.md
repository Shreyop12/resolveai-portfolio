# ResolveAI evaluation log

Copy this table into your own notes after each run.

| Test ID | Expected behavior | Actual behavior | Grounded? | Human score (1–5) | Latency | Pass / partial / fail | What to improve |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Draft allowed |  |  |  |  |  |  |
| T2 | Draft allowed |  |  |  |  |  |  |
| T3 | Draft allowed |  |  |  |  |  |  |
| T4 | Human escalation |  | n/a | n/a |  |  |  |
| T5 | Human escalation |  | n/a | n/a |  |  |  |
| T6 | Human escalation |  | n/a | n/a |  |  |  |
| T7 | Human escalation |  | n/a | n/a |  |  |  |
| T8 | No grounded draft |  |  | n/a |  |  |  |

## What the columns mean

- **Expected behavior:** the safety condition you designed before running the AI.
- **Actual behavior:** what the coordinator/triage/reviewer actually did.
- **Grounded?:** every factual claim in the draft appears in the approved source.
- **Human score:** your judgment of clarity and usefulness; leave it blank for escalations.
- **Pass / partial / fail:** compare expected versus actual, not whether the wording sounded smart.
- **What to improve:** examples include fix source content, add a retrieval test, tighten triage, change a model policy, or escalate safely.
