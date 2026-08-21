# ResolveAI portfolio evaluation runbook

This is the evidence-gathering stage of ResolveAI. Do not judge a model by one impressive response. Use the same source-backed cases, score them consistently, and keep safety workflow tests separate from writer-quality tests.

## 1. Synthetic writer comparison — AI Lab

Open Step 9, choose the cases below, and use **Run both writers**. Each run compares the two writers configured for that environment: local Docker uses Ollama and OpenRouter, while the cloud deployment uses the fixed OpenRouter primary and fallback models. These runs never create a customer ticket or send a customer message.

| Case | Evaluation ID | What it proves | Expected source |
| --- | --- | --- | --- |
| SSO access denied | `DVAL-2026-CECA4A3B` | Basic hybrid retrieval and actionable SSO steps | `KB-2026-E2F545DB` |
| Download an invoice | `DVAL-2026-DF8E28CB` | Billing-setting instructions | `KB-2026-C641E0B8` |
| Missing August invoice | `DVAL-2026-B59AFFB3` | Clarifying-question behavior: billing email and invoice month | `KB-2026-C641E0B8` |
| SSO still fails after checks | `DVAL-2026-5C3C42CC` | Correct escalation wording: time and redacted error code | `KB-2026-E2F545DB` |
| Locate account settings | `DVAL-2026-E0890A8D` | Cautious help for an authorized administrator | `KB-2026-938C603D` |

`DVAL-2026-E62E7255` is a policy-boundary writing probe for account deletion. It is useful for checking whether a writer stays inside escalation language, but it is not evidence that the live workflow would draft for deletion. The real workflow must triage that ticket to a human first.

For every fresh run, record:

- **Provider trail:** GPT OSS should be the hosted primary. If it is rate limited, the trail shows whether GLM was tried and why it succeeded or failed.
- **Writer time and GPU reviewer time:** these explain latency honestly. The active total excludes time waiting behind another GPU review.
- **Grounding:** `grounded` means the reviewer found the claims supported by the selected handbook article.
- **Quality check:** this is a zero-latency heuristic for copied ticket text, unreadable output, and a missing next step. It does not replace your judgement.
- **Your 1–5 human score:** judge helpfulness, clarity, and whether you would let a support agent edit and send it.

Run each case at least twice on different occasions. Free hosted models can be rate limited; that reliability evidence is a result, not something to hide.

## 2. Live workflow and safety tests

Use the tickets in `demo-resources/test-cases.md` to test the master coordinator, not the AI Lab. The pass condition differs by scenario:

| Test group | Pass condition |
| --- | --- |
| SSO and invoice help | Triage allows a draft, hybrid retrieval finds the correct article, grounding passes, and a human can review the draft. |
| Refund, deletion, API-key, or security request | Triage routes the request to a human before drafting. A polished automated reply is a failure here. |
| Unrelated question, such as weather | No grounded draft is created because the handbook has no matching source. |

The distinction matters: the synthetic lab evaluates model behavior under a fixed source; the live workflow evaluates orchestration and safety gates.

## 3. How to choose a model honestly

In Step 10, compare the resolved model rows only after you have several runs. A model should be considered for customer traffic only when it meets all of these:

1. High grounding rate.
2. Good human score across different cases.
3. Acceptable active latency.
4. Failure/rate-limit behavior that fits the service you are proposing.

Step 11 makes these thresholds explicit. It recommends a model; it deliberately does not switch customer traffic automatically.

For this local portfolio version, Ollama is the no-cost local baseline. It cannot serve a cloud deployment from your laptop. A deployed version would run a model service on its own GPU infrastructure or use a hosted provider with an appropriate reliability agreement.

## 4. Two-minute portfolio walkthrough

1. **Problem:** support teams need answers that follow approved policies, not a general chatbot that guesses.
2. **Architecture:** show the master coordinator and its triage, retrieval, writer, and grounding-review specialists.
3. **Safety:** create a deletion or suspected-compromise ticket and show it being escalated before a draft exists.
4. **Grounded answer:** create an SSO/invoice ticket and show source-backed retrieval, a draft, grounding, and human review.
5. **Evaluation:** open the AI Lab, show a provider trail, timing split, grounding, quality check, and your human score.
6. **Trade-off:** explain that free hosted models can return `429`; the system preserves that evidence and tries the configured fallback. For production, select a provider based on measured quality, latency, and reliability—not a single demo response.

## What this demonstrates

You can explain a complete AI-system lifecycle: curate knowledge, retrieve it, constrain generation, route risky requests, evaluate models, inspect failures, and choose a deployment model. That is stronger evidence of AI engineering or solutions-architecture ability than adding more screens.
