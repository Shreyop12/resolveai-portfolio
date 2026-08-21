# Synthetic incident fixtures

Synthetic fixtures are deterministic, self-contained incident cases. They let us develop tools, agents, and evaluations without needing a live outage or a paid external integration.

## Fixture anatomy

Each folder in `fixtures/incidents/` represents one scenario:

| File | What it represents |
| --- | --- |
| `scenario.json` | The incident a user would submit. |
| `logs.json` | Timestamped application and infrastructure events. |
| `metrics.json` | Timestamped measurements that reveal impact. |
| `deployment.json` | Deployment timing, version, and relevant changed files. |
| `git_diff.patch` | The exact source/configuration change. |
| `expected_root_cause.json` | The ground-truth diagnosis used by future evaluations. |

## Grounding rule

Every ID listed in `expected_root_cause.json.evidence_ids` must exist in logs, metrics, or deployment metadata. The loader rejects a fixture with a dangling evidence reference.

## First scenario

`deployment_redis_misconfiguration` models a checkout deployment that changes `REDIS_URL` from `redis://...` to `redis//...`. The deployment completes at 14:31:51 UTC; Redis failures begin 15 seconds later; then the checkout 5xx rate rises from 0.2% to 38%.

This timing does not prove causation on its own. The Git diff and explicit Redis error provide the direct causal evidence. Future agents must cite both kinds of evidence: correlation and mechanism.
