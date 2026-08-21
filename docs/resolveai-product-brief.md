# ResolveAI product brief

## Problem

Support teams repeatedly answer questions that are already covered by product guides, policies, and help-center articles. Searching those sources takes time, and an unsupported AI answer can create customer or policy risk.

## Product promise

ResolveAI helps a support agent prepare a grounded response. It does not send messages autonomously.

```text
Support ticket
    ↓
Find approved knowledge-base sources
    ↓
Draft a response with citations
    ↓
Human approves, edits, rejects, or escalates
```

## Initial users

- Support agents who need a faster first draft.
- Support leads who need consistent policy application.
- Knowledge-base owners who need visibility into missing or weak documentation.

## Product principles

1. **Grounded answers:** Every meaningful claim must link to an approved source.
2. **Human control:** AI drafts; a human decides what reaches a customer.
3. **Explicit uncertainty:** Low-confidence answers escalate instead of pretending certainty.
4. **Measurable quality:** Evaluation fixtures will measure retrieval, citations, and draft quality.
5. **Tenant boundaries:** One organization must never retrieve another organization’s knowledge.

## Planned learning path

1. Support tickets and workspaces
2. Knowledge-base articles
3. Keyword, semantic, then hybrid search
4. Grounded AI drafts
5. Human review and feedback
6. Master coordinator and specialist agents
7. Evaluations, traces, and portfolio polish

## Out of scope for the first release

- Automatically sending customer messages
- A large multi-agent system before the retrieval baseline is measurable
- Live integrations with CRM or help-desk vendors
