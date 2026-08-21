# ResolveAI

ResolveAI is an AI customer-support copilot. It helps support teams find approved knowledge-base sources, draft grounded responses, and route uncertain answers to a human reviewer.

## Current phase

**Phase 19 — Portfolio Polish** is complete. ResolveAI now has repeatable synthetic experiments, human-controlled model-selection rules, a documented safe path to hosting, and an interview-ready system walkthrough.

Read the [product brief](docs/resolveai-product-brief.md) for the user workflow, design principles, and planned scope.

Start with the [guided demo](docs/guided-demo.md) to learn the architecture by running one complete workflow before reading the code.

Read the [deployment guide](docs/deployment-guide.md) before deploying: it explains the service boundary, secret handling, migrations, and why local Ollama cannot serve public users by itself.

Use the [portfolio walkthrough](docs/portfolio-walkthrough.md) to understand the architecture, lead a demo, and practice explaining the project in an interview.

## Run locally

```bash
copy .env.example .env
docker compose up --build
```

- Web: http://localhost:3000
- API health: http://localhost:8000/api/v1/health
- API docs: http://localhost:8000/docs

## Test the API

```bash
cd apps/api
uv run pytest
```

## Legacy development note

The local Docker database keeps its existing development credentials and data while the product pivot is in progress. We will replace the legacy incident-specific schema deliberately in the support-workspace phase, rather than deleting data or changing credentials silently.

## Support workspace API

- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces`
- `POST /api/v1/workspaces/{workspace_slug}/tickets`
- `GET /api/v1/workspaces/{workspace_slug}/tickets`
- `GET /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}`
- `PATCH /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/status`
- `POST /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/notes`

## Approved knowledge-base API

- `POST /api/v1/workspaces/{workspace_slug}/knowledge-articles`
- `POST /api/v1/workspaces/{workspace_slug}/knowledge-articles/documents/import-text`
- `GET /api/v1/workspaces/{workspace_slug}/knowledge-articles/documents`
- `PATCH /api/v1/workspaces/{workspace_slug}/knowledge-articles/documents/{document_id}/publish`
- `GET /api/v1/workspaces/{workspace_slug}/knowledge-articles`
- `GET /api/v1/workspaces/{workspace_slug}/knowledge-articles/{article_id}`
- `PATCH /api/v1/workspaces/{workspace_slug}/knowledge-articles/{article_id}/status`
- `GET /api/v1/workspaces/{workspace_slug}/knowledge-articles/search?q=...`
- `GET /api/v1/workspaces/{workspace_slug}/knowledge-articles/semantic-search?q=...`
- `GET /api/v1/workspaces/{workspace_slug}/knowledge-articles/hybrid-search?q=...`
- `POST /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/drafts/generate`
- `GET /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/drafts`
- `PATCH /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/drafts/{draft_id}/review`
- `GET /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/drafts/runs`
- `GET /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/drafts/grounding-review`
- `POST /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/triage`
- `GET /api/v1/workspaces/{workspace_slug}/tickets/{ticket_id}/triage`
- `POST /api/v1/workspaces/{workspace_slug}/knowledge-articles/reindex`
- `POST /api/v1/workspaces/{workspace_slug}/retrieval-evaluations`
- `GET /api/v1/workspaces/{workspace_slug}/retrieval-evaluations`
- `POST /api/v1/workspaces/{workspace_slug}/retrieval-evaluations/run`
- `POST /api/v1/workspaces/{workspace_slug}/draft-evaluations`
- `GET /api/v1/workspaces/{workspace_slug}/draft-evaluations`
- `POST /api/v1/workspaces/{workspace_slug}/draft-evaluations/{evaluation_id}/run`
- `POST /api/v1/workspaces/{workspace_slug}/draft-evaluations/batch-run`
- `POST /api/v1/workspaces/{workspace_slug}/draft-evaluations/experiments`
- `GET /api/v1/workspaces/{workspace_slug}/draft-evaluations/experiments`
- `GET /api/v1/workspaces/{workspace_slug}/draft-evaluations/report`
- `GET /api/v1/workspaces/{workspace_slug}/draft-evaluations/{evaluation_id}/jobs`
- `GET /api/v1/workspaces/{workspace_slug}/draft-evaluations/{evaluation_id}/runs`
- `PATCH /api/v1/workspaces/{workspace_slug}/draft-evaluations/{evaluation_id}/runs/{run_id}`
- `GET /api/v1/workspaces/{workspace_slug}/model-selection-policy`
- `PUT /api/v1/workspaces/{workspace_slug}/model-selection-policy`
- `GET /api/v1/workspaces/{workspace_slug}/model-selection-policy/report`

Articles begin as drafts. A published article is the only lifecycle state that a later retrieval-and-drafting phase may use as a source. An archived article must return to draft before it can be published again. The Knowledge area ingests a TXT or Markdown handbook as one source document, then creates heading-aware chunks internally for retrieval. A person publishes the source document before its chunks can be retrieved by AI.

Semantic search is served locally by Ollama's `embeddinggemma` model. The coordinator drafts with local `qwen3:4b`, but it receives only hybrid-retrieved approved sources. Every generated draft enters `awaiting_review`; an approved draft resolves its ticket and a rejected draft returns it to drafting.

## Retrieval evaluation and safe traces

An evaluation case is a human-labelled check: a realistic customer question plus the published source article that should answer it. Running the evaluation uses the same hybrid retrieval path as the coordinator and reports:

- **Hit@5** — how often the expected source appeared in the first five results.
- **MRR** (mean reciprocal rank) — a score that is higher when the expected source appears closer to first place.

Each coordinator attempt also records a run ID, outcome, selected source IDs, stage timings, and model names. It intentionally does **not** store customer prompts or private model reasoning. Historical drafts created before Phase 7 will not have a run record; future coordinator attempts are logged automatically.

## Triage and human escalation

Before a new draft is allowed, a ticket must have a `draft_allowed` triage assessment. The triage specialist returns only a structured decision, category, and short safe reason. It has deterministic safety checks for sensitive requests such as refunds, account deletion, credential changes, security incidents, and privacy requests. Those tickets are escalated without reaching retrieval or the drafting model. If the local model cannot return a valid assessment, ResolveAI fails closed and escalates the ticket instead.

## Grounding review

After the draft writer proposes a reply, a separate grounding reviewer receives that reply and the exact approved source packet. It returns `grounded` only when the reply stays within those sources. Otherwise it returns `needs_human_review`; ResolveAI records the outcome, blocks the workflow, and does **not** create a draft that could be approved accidentally. As with triage, invalid or unavailable local-model output fails closed to human review.

## Model routing, Gemini, and OpenRouter fallback

The default configuration remains completely local:

- Triage specialist: Ollama `qwen3:4b`
- Draft writer: Ollama `qwen3:4b`
- Grounding reviewer: Ollama `qwen3:4b`
- Embeddings: Ollama `embeddinggemma`

For the recommended hosted configuration, Gemini is the primary provider for triage, draft writing, and grounding review. OpenRouter remains an independent fallback if Gemini is unavailable or rate-limited:

```bash
RESOLVEAI_DRAFT_PROVIDER=gemini
RESOLVEAI_AGENT_PROVIDER=gemini
RESOLVEAI_GEMINI_API_KEY=your_gemini_key_here
RESOLVEAI_GEMINI_MODEL=gemini-3.5-flash-lite
RESOLVEAI_OPENROUTER_API_KEY=your_openrouter_key_here
RESOLVEAI_OPENROUTER_DRAFT_MODEL=openai/gpt-oss-20b:free
```

The keys are never committed: `.env` is ignored by Git and the API reads them only at runtime. `gemini-3.5-flash-lite` is the default because this project has a 500-RPD free quota, compared with 20 RPD for the quality-first Flash model. Triage and grounding review use schema-constrained JSON responses and still validate every result in application code. If Gemini fails, ResolveAI tries OpenRouter; if both hosted providers fail, the ticket fails closed to human review. Free tiers improve learning and demo resilience, but are rate-limited and are not an SLA for private production customer data. You can return to a fully local writer by setting both providers to `ollama`.

## Draft Model Evaluation Lab

Create a synthetic scenario and select one published source article. ResolveAI gives the exact same scenario and source packet to two independently configured writers, then uses the configured grounding reviewer to check both replies. Local Docker compares Ollama with OpenRouter; the hosted Gemini configuration compares Gemini with the configured OpenRouter model. Each result records provider, resolved model, latency, reviewer outcome, and an optional human quality score from 1 to 5. These lab records are intentionally separate from support tickets and can never be approved or sent to a customer.

Clicking **Run both writers** now returns immediately with a durable job record. Redis is the short-lived work mailbox; PostgreSQL stores the job state permanently. The `worker` Docker service claims queued jobs, performs the slow writer/reviewer work, and saves `completed` or `failed`. If the worker restarts, unfinished jobs are re-queued from PostgreSQL. The page checks the saved job state every three seconds while work is active.

Local Ollama writing is allowed up to five minutes by default (`RESOLVEAI_OLLAMA_CHAT_TIMEOUT_SECONDS=300`). A timeout now says that the model needed more time, rather than incorrectly claiming Ollama is not running.

## Multi-agent orchestration timeline

For each ticket, the **master coordinator** applies a fixed, safe workflow: triage specialist → hybrid retrieval → grounded draft writer → grounding reviewer. The ticket page displays the latest coordinator run as a timeline. It records only the operational facts needed to understand or debug the handoffs: stage name, outcome, timing, model name, and approved source IDs. Customer prompts and private model reasoning are never recorded in this timeline.

## Model quality dashboard

The dashboard groups only synthetic lab runs by the actual resolved provider and model. For each group it reports total runs, completed runs, failures, grounding pass rate, average human score, number of human-scored runs, and average latency. Unscored runs are excluded from the average score instead of being treated as zero. This evidence can guide model selection, but it is not a guarantee of performance on every real support question.

## Benchmark batch experiments

Each synthetic comparison case is a human-labelled benchmark item: it contains a scenario and the published source expected to answer it. Select several items and choose **Run selected benchmark cases**. ResolveAI creates one durable background job for each selected item, rather than combining scenarios into one prompt. That preserves per-case results, lets one failure remain visible, and gives the model-quality dashboard a fairer sample over time.

## Named experiment snapshots

Give a selected group of synthetic cases a meaningful name, such as `SSO benchmark v1`. ResolveAI saves the frozen set of case IDs as an experiment, then queues independent durable jobs for those cases. That makes a later dashboard comparison meaningful: you know which benchmark set produced the evidence instead of relying on memory or a changing selection.

## Model-selection policy

The final dashboard step is a human decision aid, not automated routing. You choose minimum grounding, human-score, and latency guardrails. ResolveAI compares each observed provider/model against those guardrails and explains any missing evidence or failed threshold. It does not switch production traffic or approve customer replies automatically.
