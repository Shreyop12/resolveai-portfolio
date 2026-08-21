"use client";

import { Fragment, FormEvent, useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Workspace = { id: string; name: string; slug: string };
type Ticket = {
  ticket_id: string;
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
  status: string;
  priority: string;
};
type TicketNote = { id: string; author: "support_agent" | "system"; body: string; created_at: string };
type TicketDetail = Ticket & { notes: TicketNote[] };
type KnowledgeArticle = {
  article_id: string;
  title: string;
  category: string;
  body: string;
  status: string;
};
type KnowledgeDocument = { document_id: string; title: string; source_file_name: string; category: string; status: string; chunk_count: number };
type KnowledgeSearchResult = KnowledgeArticle & { score: number };
type HybridSearchResult = KnowledgeArticle & {
  fusion_score: number;
  keyword_rank: number | null;
  semantic_rank: number | null;
};
type TicketDraft = {
  draft_id: string;
  body: string;
  source_article_ids: string[];
  coordinator_trace: string[];
  status: string;
};
type TicketTriage = {
  assessment_id: string;
  decision: "draft_allowed" | "human_escalation";
  category: string;
  reason: string;
  agent_name: string;
  model: string;
};
type TicketGroundingReview = {
  review_id: string;
  decision: "grounded" | "needs_human_review";
  reason: string;
  source_article_ids: string[];
  agent_name: string;
  model: string;
};
type CoordinatorStage = {
  name: string;
  outcome?: string;
  elapsed_ms: number;
};
type CoordinatorRun = {
  run_id: string;
  status: "completed" | "blocked" | "failed";
  source_article_ids: string[];
  stages: CoordinatorStage[];
  agent_models: Record<string, string>;
  elapsed_ms: number;
};
type RetrievalEvaluationCase = {
  evaluation_id: string;
  query: string;
  expected_article_id: string;
};
type RetrievalEvaluationReport = {
  total_cases: number;
  hit_at_k: number;
  mean_reciprocal_rank: number;
  results: {
    evaluation_id: string;
    expected_article_id: string;
    retrieved_article_ids: string[];
    expected_rank: number | null;
  }[];
};
type DraftEvaluationCase = {
  evaluation_id: string;
  subject: string;
  message: string;
  expected_article_id: string;
};
type DraftEvaluationRun = {
  run_id: string;
  provider: string;
  model: string;
  status: "completed" | "failed";
  draft_body: string | null;
  review_decision: "grounded" | "needs_human_review" | null;
  review_reason: string | null;
  error_message: string | null;
  latency_ms: number;
  draft_generation_latency_ms: number | null;
  grounding_review_latency_ms: number | null;
  provider_attempts: { model: string; outcome: string; status_code: number | null }[];
  quality_decision: "passed" | "needs_human_review" | null;
  quality_reason: string | null;
  human_score: number | null;
};
type DraftEvaluationJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};
type DraftModelQualityMetric = {
  provider: string;
  model: string;
  is_active: boolean;
  active_role: string | null;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  grounding_pass_rate: number | null;
  human_scored_runs: number;
  average_human_score: number | null;
  average_latency_ms: number | null;
};
type DraftModelQualityReport = {
  total_runs: number;
  models: DraftModelQualityMetric[];
  active_models: { provider: string; model: string; role: string }[];
};
type DraftEvaluationExperiment = {
  experiment_id: string;
  name: string;
  case_ids: string[];
};
type ModelSelectionPolicy = { min_grounding_rate: number; min_average_human_score: number; max_average_latency_ms: number };
type ModelSelectionReport = { policy: ModelSelectionPolicy; recommendations: { provider: string; model: string; status: string; reasons: string[] }[] };

function latestRunsByProvider(runs: DraftEvaluationRun[]): DraftEvaluationRun[] {
  const latest: Record<string, DraftEvaluationRun> = {};
  for (const run of runs) {
    if (!latest[run.provider]) latest[run.provider] = run;
  }
  return Object.values(latest);
}

function formatDraftTiming(run: DraftEvaluationRun): string {
  const writer = run.draft_generation_latency_ms;
  const reviewer = run.grounding_review_latency_ms;
  const total = `${(run.latency_ms / 1000).toFixed(1)} s`;
  if (writer === null && reviewer === null) return `Total: ${total} (legacy run)`;
  const writerText = writer === null ? "Writer: not recorded" : `Writer: ${(writer / 1000).toFixed(1)} s`;
  const reviewerText = reviewer === null ? "Reviewer: not run" : `GPU reviewer: ${(reviewer / 1000).toFixed(1)} s`;
  return `${writerText} · ${reviewerText} · Active total: ${total}`;
}

function formatProviderTrail(run: DraftEvaluationRun): string | null {
  if (run.provider_attempts.length === 0) return null;
  const details = run.provider_attempts.map((attempt) => {
    if (attempt.outcome === "completed") return `${attempt.model} completed`;
    if (attempt.outcome === "rate_limited") return `${attempt.model} rate limited (429)`;
    if (attempt.outcome === "incomplete_response") return `${attempt.model} returned an incomplete response`;
    return attempt.status_code === null ? `${attempt.model} request failed` : `${attempt.model} failed (HTTP ${attempt.status_code})`;
  });
  return `Provider trail: ${details.join(" → ")}`;
}

function agentDisplayName(name: string): string {
  return name.replaceAll("_", " ");
}

function isKnowledgeGap(run: CoordinatorRun | undefined): boolean {
  return run?.status === "blocked" && run.source_article_ids.length === 0;
}

function renderInlineMarkdown(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={index}>{part.slice(2, -2)}</strong>
      : <Fragment key={index}>{part}</Fragment>,
  );
}

function renderDraftBody(body: string) {
  return body.trim().split(/\n\s*\n/).filter(Boolean).map((block, blockIndex) => {
    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    if (lines.every((line) => /^\d+\.\s+/.test(line))) {
      return <ol key={blockIndex}>{lines.map((line, lineIndex) => <li key={lineIndex}>{renderInlineMarkdown(line.replace(/^\d+\.\s+/, ""))}</li>)}</ol>;
    }
    if (lines.every((line) => /^[-*]\s+/.test(line))) {
      return <ul key={blockIndex}>{lines.map((line, lineIndex) => <li key={lineIndex}>{renderInlineMarkdown(line.replace(/^[-*]\s+/, ""))}</li>)}</ul>;
    }
    return <p key={blockIndex}>{lines.map((line, lineIndex) => <Fragment key={lineIndex}>{renderInlineMarkdown(line)}{lineIndex < lines.length - 1 && <br />}</Fragment>)}</p>;
  });
}

export default function HomePage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>("");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [reviewTicketId, setReviewTicketId] = useState<string | null>(null);
  const [reviewTicketDetails, setReviewTicketDetails] = useState<Record<string, TicketDetail>>({});
  const [articles, setArticles] = useState<KnowledgeArticle[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [lastSearch, setLastSearch] = useState<string>("");
  const [semanticResults, setSemanticResults] = useState<KnowledgeSearchResult[]>([]);
  const [lastSemanticSearch, setLastSemanticSearch] = useState<string>("");
  const [hybridResults, setHybridResults] = useState<HybridSearchResult[]>([]);
  const [lastHybridSearch, setLastHybridSearch] = useState<string>("");
  const [draftsByTicket, setDraftsByTicket] = useState<Record<string, TicketDraft>>({});
  const [triageByTicket, setTriageByTicket] = useState<Record<string, TicketTriage>>({});
  const [groundingReviewsByTicket, setGroundingReviewsByTicket] = useState<Record<string, TicketGroundingReview>>({});
  const [coordinatorRunsByTicket, setCoordinatorRunsByTicket] = useState<Record<string, CoordinatorRun[]>>({});
  const [evaluationCases, setEvaluationCases] = useState<RetrievalEvaluationCase[]>([]);
  const [evaluationReport, setEvaluationReport] = useState<RetrievalEvaluationReport | null>(null);
  const [draftEvaluationCases, setDraftEvaluationCases] = useState<DraftEvaluationCase[]>([]);
  const [draftEvaluationRunsByCase, setDraftEvaluationRunsByCase] = useState<Record<string, DraftEvaluationRun[]>>({});
  const [draftEvaluationJobsByCase, setDraftEvaluationJobsByCase] = useState<Record<string, DraftEvaluationJob[]>>({});
  const [draftModelQualityReport, setDraftModelQualityReport] = useState<DraftModelQualityReport | null>(null);
  const [selectedBenchmarkCaseIds, setSelectedBenchmarkCaseIds] = useState<string[]>([]);
  const [benchmarkExperimentName, setBenchmarkExperimentName] = useState<string>("");
  const [benchmarkExperiments, setBenchmarkExperiments] = useState<DraftEvaluationExperiment[]>([]);
  const [modelSelectionReport, setModelSelectionReport] = useState<ModelSelectionReport | null>(null);
  const [activeArea, setActiveArea] = useState<"desk" | "knowledge" | "lab">("desk");
  const [pendingActions, setPendingActions] = useState<Record<string, boolean>>({});
  const [isImportingDocument, setIsImportingDocument] = useState(false);
  const [message, setMessage] = useState<string>("");

  const isActionPending = (action: string) => Boolean(pendingActions[action]);

  async function runAction<T>(action: string, pendingMessage: string, failureMessage: string, work: () => Promise<T>) {
    setPendingActions((current) => ({ ...current, [action]: true }));
    setMessage(pendingMessage);
    try {
      return await work();
    } catch {
      setMessage(failureMessage);
      return undefined;
    } finally {
      setPendingActions((current) => ({ ...current, [action]: false }));
    }
  }

  async function loadWorkspaces() {
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces`);
    if (!response.ok) throw new Error("Could not load workspaces.");
    const nextWorkspaces = (await response.json()) as Workspace[];
    setWorkspaces(nextWorkspaces);
    setSelectedWorkspace((current) => current || nextWorkspaces[0]?.slug || "");
  }

  async function loadTickets(workspaceSlug: string) {
    if (!workspaceSlug) {
      setTickets([]);
      setCoordinatorRunsByTicket({});
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/tickets`);
    if (!response.ok) throw new Error("Could not load tickets.");
    const data = (await response.json()) as { items: Ticket[] };
    setTickets(data.items);
    const savedDrafts = await Promise.all(
      data.items.map(async (ticket) => {
        const draftResponse = await fetch(
          `${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/tickets/${ticket.ticket_id}/drafts`,
        );
        if (!draftResponse.ok) return [ticket.ticket_id, undefined] as const;
        const drafts = (await draftResponse.json()) as TicketDraft[];
        return [ticket.ticket_id, drafts[0]] as const;
      }),
    );
    setDraftsByTicket(Object.fromEntries(savedDrafts.filter(([, draft]) => draft)) as Record<string, TicketDraft>);
    const savedTriage = await Promise.all(
      data.items.map(async (ticket) => {
        const triageResponse = await fetch(
          `${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/tickets/${ticket.ticket_id}/triage`,
        );
        if (!triageResponse.ok) return [ticket.ticket_id, undefined] as const;
        const triage = (await triageResponse.json()) as TicketTriage | null;
        return [ticket.ticket_id, triage ?? undefined] as const;
      }),
    );
    setTriageByTicket(Object.fromEntries(savedTriage.filter(([, triage]) => triage)) as Record<string, TicketTriage>);
    const savedGroundingReviews = await Promise.all(
      data.items.map(async (ticket) => {
        const reviewResponse = await fetch(
          `${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/tickets/${ticket.ticket_id}/drafts/grounding-review`,
        );
        if (!reviewResponse.ok) return [ticket.ticket_id, undefined] as const;
        const review = (await reviewResponse.json()) as TicketGroundingReview | null;
        return [ticket.ticket_id, review ?? undefined] as const;
      }),
    );
    setGroundingReviewsByTicket(
      Object.fromEntries(savedGroundingReviews.filter(([, review]) => review)) as Record<string, TicketGroundingReview>,
    );
    const savedCoordinatorRuns = await Promise.all(
      data.items.map(async (ticket) => {
        const runResponse = await fetch(
          `${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/tickets/${ticket.ticket_id}/drafts/runs`,
        );
        if (!runResponse.ok) return [ticket.ticket_id, []] as const;
        return [ticket.ticket_id, (await runResponse.json()) as CoordinatorRun[]] as const;
      }),
    );
    setCoordinatorRunsByTicket(Object.fromEntries(savedCoordinatorRuns));
  }

  async function loadTicketDetail(workspaceSlug: string, ticketId: string) {
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/tickets/${ticketId}`);
    if (!response.ok) throw new Error("Could not load the human review details.");
    const detail = (await response.json()) as TicketDetail;
    setReviewTicketDetails((current) => ({ ...current, [ticketId]: detail }));
    return detail;
  }

  async function loadArticles(workspaceSlug: string) {
    if (!workspaceSlug) {
      setArticles([]);
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/knowledge-articles`);
    if (!response.ok) throw new Error("Could not load knowledge articles.");
    const data = (await response.json()) as { items: KnowledgeArticle[] };
    setArticles(data.items);
  }

  async function loadDocuments(workspaceSlug: string) {
    if (!workspaceSlug) { setDocuments([]); return; }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/knowledge-articles/documents`);
    if (!response.ok) throw new Error("Could not load knowledge documents.");
    setDocuments(((await response.json()) as { items: KnowledgeDocument[] }).items);
  }

  async function loadEvaluationCases(workspaceSlug: string) {
    if (!workspaceSlug) {
      setEvaluationCases([]);
      setEvaluationReport(null);
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/retrieval-evaluations`);
    if (!response.ok) throw new Error("Could not load retrieval evaluation cases.");
    setEvaluationCases((await response.json()) as RetrievalEvaluationCase[]);
  }

  async function loadDraftEvaluationCases(workspaceSlug: string) {
    if (!workspaceSlug) {
      setDraftEvaluationCases([]);
      setDraftEvaluationRunsByCase({});
      setDraftEvaluationJobsByCase({});
      setSelectedBenchmarkCaseIds([]);
      setBenchmarkExperiments([]);
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/draft-evaluations`);
    if (!response.ok) throw new Error("Could not load draft model evaluation cases.");
    const cases = (await response.json()) as DraftEvaluationCase[];
    setDraftEvaluationCases(cases);
    const savedRuns = await Promise.all(cases.map(async (evaluationCase) => {
      const runResponse = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/draft-evaluations/${evaluationCase.evaluation_id}/runs`);
      if (!runResponse.ok) return [evaluationCase.evaluation_id, []] as const;
      return [evaluationCase.evaluation_id, (await runResponse.json()) as DraftEvaluationRun[]] as const;
    }));
    const savedJobs = await Promise.all(cases.map(async (evaluationCase) => {
      const jobResponse = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/draft-evaluations/${evaluationCase.evaluation_id}/jobs`);
      if (!jobResponse.ok) return [evaluationCase.evaluation_id, []] as const;
      return [evaluationCase.evaluation_id, (await jobResponse.json()) as DraftEvaluationJob[]] as const;
    }));
    setDraftEvaluationRunsByCase(Object.fromEntries(savedRuns));
    setDraftEvaluationJobsByCase(Object.fromEntries(savedJobs));
  }

  async function loadDraftModelQualityReport(workspaceSlug: string) {
    if (!workspaceSlug) {
      setDraftModelQualityReport(null);
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/draft-evaluations/report`);
    if (!response.ok) throw new Error("Could not load draft model quality metrics.");
    setDraftModelQualityReport((await response.json()) as DraftModelQualityReport);
  }

  async function loadBenchmarkExperiments(workspaceSlug: string) {
    if (!workspaceSlug) {
      setBenchmarkExperiments([]);
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/draft-evaluations/experiments`);
    if (!response.ok) throw new Error("Could not load benchmark experiments.");
    setBenchmarkExperiments((await response.json()) as DraftEvaluationExperiment[]);
  }

  async function loadModelSelectionReport(workspaceSlug: string) {
    if (!workspaceSlug) { setModelSelectionReport(null); return; }
    const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${workspaceSlug}/model-selection-policy/report`);
    if (!response.ok) throw new Error("Could not load model-selection recommendations.");
    setModelSelectionReport((await response.json()) as ModelSelectionReport);
  }

  useEffect(() => {
    loadWorkspaces().catch((error: Error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    Promise.all([loadTickets(selectedWorkspace), loadArticles(selectedWorkspace), loadDocuments(selectedWorkspace), loadEvaluationCases(selectedWorkspace), loadDraftEvaluationCases(selectedWorkspace), loadDraftModelQualityReport(selectedWorkspace), loadBenchmarkExperiments(selectedWorkspace), loadModelSelectionReport(selectedWorkspace)]).catch(
      (error: Error) => setMessage(error.message),
    );
  }, [selectedWorkspace]);

  useEffect(() => {
    const hasActiveJob = Object.values(draftEvaluationJobsByCase).some((jobs) =>
      jobs.some((job) => job.status === "queued" || job.status === "running"),
    );
    if (!selectedWorkspace || !hasActiveJob) return;
    const timer = window.setInterval(() => {
      Promise.all([loadDraftEvaluationCases(selectedWorkspace), loadDraftModelQualityReport(selectedWorkspace)]).catch((error: Error) => setMessage(error.message));
    }, 3000);
    return () => window.clearInterval(timer);
  }, [selectedWorkspace, draftEvaluationJobsByCase]);

  async function createWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    return runAction("create-workspace", "Creating workspace…", "Workspace could not be created. Check the connection and try again.", async () => {
      const form = new FormData(formElement);
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: form.get("name"), slug: form.get("slug") }),
      });
      if (!response.ok) {
        setMessage("Workspace could not be created. The slug may already be in use.");
        return;
      }
      const workspace = (await response.json()) as Workspace;
      setWorkspaces((current) => [...current, workspace]);
      setSelectedWorkspace(workspace.slug);
      formElement.reset();
      setMessage(`Workspace “${workspace.name}” is ready.`);
    });
  }

  async function createTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    return runAction("create-ticket", "Creating ticket…", "Ticket could not be created. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: form.get("customerName"),
          customer_email: form.get("customerEmail"),
          subject: form.get("subject"),
          message: form.get("ticketMessage"),
          priority: form.get("priority"),
        }),
      });
      if (!response.ok) {
        setMessage("Ticket could not be created. Check the required fields.");
        return;
      }
      formElement.reset();
      await loadTickets(selectedWorkspace);
      setMessage("Ticket created. It is ready to assess.");
    });
  }

  async function createArticle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const formElement = event.currentTarget;
    return runAction("create-article", "Saving article draft…", "Article could not be saved. Check the connection and try again.", async () => {
      const form = new FormData(formElement);
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.get("title"),
          category: form.get("category"),
          body: form.get("body"),
        }),
      });
      if (!response.ok) {
        setMessage("Article could not be saved. Its title, category, and source text are required.");
        return;
      }
      formElement.reset();
      await loadArticles(selectedWorkspace);
      setMessage("Article saved as a draft. Publish it only after review.");
    });
  }

  async function importKnowledgeDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const document = form.get("knowledgeDocument");
    if (!(document instanceof File) || document.size === 0) {
      setMessage("Choose a TXT or Markdown document first.");
      return;
    }
    if (!/\.(txt|md|markdown)$/i.test(document.name) || document.size > 100_000) {
      setMessage("Import a TXT/Markdown document smaller than 100 KB.");
      return;
    }
    setIsImportingDocument(true);
    return runAction("import-document", "Importing document…", "The document could not be imported. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/documents/import-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_file_name: document.name, category: form.get("documentCategory"), content: await document.text() }),
      });
      if (!response.ok) {
        setMessage("The document could not be imported. Use a TXT or Markdown file with at least 20 characters.");
        return;
      }
      formElement.reset();
      await Promise.all([loadArticles(selectedWorkspace), loadDocuments(selectedWorkspace)]);
      setMessage("Document ingested into reviewable sections. Publish the source document before AI can use it.");
    }).finally(() => {
      setIsImportingDocument(false);
    });
  }

  async function publishDocument(documentId: string) {
    if (!selectedWorkspace) return;
    return runAction(`publish-document:${documentId}`, "Publishing document and creating embeddings…", "The document could not be published. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/documents/${documentId}/publish`, { method: "PATCH" });
      if (!response.ok) { setMessage("The document could not be published. Confirm Ollama is running to create its section embeddings."); return; }
      await Promise.all([loadArticles(selectedWorkspace), loadDocuments(selectedWorkspace)]);
      setMessage("Source document published. Its approved sections are now searchable by ResolveAI.");
    });
  }

  async function deleteDraftDocument(documentId: string) {
    if (!selectedWorkspace) return;
    return runAction(`delete-document:${documentId}`, "Deleting draft document…", "The draft could not be deleted. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/documents/${documentId}`, { method: "DELETE" });
      if (!response.ok) { setMessage("Only draft documents can be deleted."); return; }
      await Promise.all([loadArticles(selectedWorkspace), loadDocuments(selectedWorkspace)]);
      setMessage("Draft document and its internal sections were deleted.");
    });
  }

  async function publishArticle(articleId: string) {
    if (!selectedWorkspace) return;
    return runAction(`publish-article:${articleId}`, "Publishing article…", "The article could not be published. Check the connection and try again.", async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/${articleId}/status`,
        { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "published" }) },
      );
      if (!response.ok) {
        setMessage("This article cannot be published from its current state.");
        return;
      }
      await loadArticles(selectedWorkspace);
      setMessage("Article published. It is now an approved AI source.");
    });
  }

  async function searchKnowledge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const form = new FormData(event.currentTarget);
    const query = String(form.get("query") ?? "").trim();
    if (query.length < 2) {
      setMessage("Enter at least two characters to search the approved library.");
      return;
    }
    return runAction("search-keyword", "Searching approved sources…", "Knowledge search could not be completed. Check the connection and try again.", async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/search?q=${encodeURIComponent(query)}`,
      );
      if (!response.ok) {
        setMessage("Knowledge search could not be completed.");
        return;
      }
      const data = (await response.json()) as { query: string; items: KnowledgeSearchResult[] };
      setLastSearch(data.query);
      setSearchResults(data.items);
      setMessage(`${data.items.length} approved source${data.items.length === 1 ? "" : "s"} found.`);
    });
  }

  async function reindexKnowledge() {
    if (!selectedWorkspace) return;
    return runAction("reindex-knowledge", "Creating local search embeddings…", "Could not index the published sources. Check the connection and confirm Ollama is running locally.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/reindex`, {
        method: "POST",
      });
      if (!response.ok) {
        setMessage("Could not index the published sources. Confirm Ollama is running locally.");
        return;
      }
      const data = (await response.json()) as { indexed: number; model: string };
      setMessage(`${data.indexed} published source(s) indexed with the local ${data.model} model.`);
    });
  }

  async function searchSemantically(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const form = new FormData(event.currentTarget);
    const query = String(form.get("semanticQuery") ?? "").trim();
    if (query.length < 2) {
      setMessage("Enter at least two characters to search by meaning.");
      return;
    }
    return runAction("search-semantic", "Searching by meaning…", "Semantic search could not be completed. Check the connection and confirm Ollama is running locally.", async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/semantic-search?q=${encodeURIComponent(query)}`,
      );
      if (!response.ok) {
        setMessage("Semantic search could not be completed. Confirm Ollama is running locally.");
        return;
      }
      const data = (await response.json()) as { query: string; items: KnowledgeSearchResult[] };
      setLastSemanticSearch(data.query);
      setSemanticResults(data.items);
      setMessage(`${data.items.length} related source${data.items.length === 1 ? "" : "s"} found.`);
    });
  }

  async function searchHybrid(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const form = new FormData(event.currentTarget);
    const query = String(form.get("hybridQuery") ?? "").trim();
    if (query.length < 2) {
      setMessage("Enter at least two characters to combine the two search methods.");
      return;
    }
    return runAction("search-hybrid", "Combining keyword and meaning results…", "Hybrid search could not be completed. Check the connection and confirm Ollama is running locally.", async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/knowledge-articles/hybrid-search?q=${encodeURIComponent(query)}`,
      );
      if (!response.ok) {
        setMessage("Hybrid search could not be completed. Confirm Ollama is running locally.");
        return;
      }
      const data = (await response.json()) as { query: string; items: HybridSearchResult[] };
      setLastHybridSearch(data.query);
      setHybridResults(data.items);
      setMessage(`${data.items.length} combined source${data.items.length === 1 ? "" : "s"} found.`);
    });
  }

  async function generateDraft(ticketId: string) {
    if (!selectedWorkspace) return;
    return runAction(`generate-draft:${ticketId}`, "Coordinator is retrieving sources and reviewing a draft…", "ResolveAI could not create a grounded draft. Check the connection and try again.", async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/tickets/${ticketId}/drafts/generate`,
        { method: "POST" },
      );
      if (!response.ok) {
        await loadTickets(selectedWorkspace);
        setMessage("ResolveAI could not create a grounded draft. Assess the ticket first and add a relevant published source.");
        return;
      }
      const draft = (await response.json()) as TicketDraft;
      setDraftsByTicket((current) => ({ ...current, [ticketId]: draft }));
      await loadTickets(selectedWorkspace);
      setMessage("Coordinator completed: hybrid retrieval → grounded draft → human review.");
    });
  }

  async function assessTicket(ticketId: string) {
    if (!selectedWorkspace) return;
    return runAction(`assess-ticket:${ticketId}`, "Triage specialist is assessing this ticket…", "The triage specialist could not assess this ticket. Check the connection and try again.", async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/tickets/${ticketId}/triage`,
        { method: "POST" },
      );
      if (!response.ok) {
        setMessage("The triage specialist could not assess this ticket safely. A human should review it.");
        return;
      }
      const triage = (await response.json()) as TicketTriage;
      setTriageByTicket((current) => ({ ...current, [ticketId]: triage }));
      setMessage(
        triage.decision === "draft_allowed"
          ? "Assessment complete: AI may retrieve approved sources and prepare a human-reviewed draft."
          : "Assessment complete: AI stopped here and routed this ticket to a human support owner.",
      );
    });
  }

  async function reviewDraft(ticketId: string, decision: "approved" | "rejected") {
    if (!selectedWorkspace) return;
    const draft = draftsByTicket[ticketId];
    if (!draft) return;
    return runAction(`review-draft:${ticketId}`, decision === "approved" ? "Approving draft…" : "Rejecting draft…", "This draft could not be reviewed. Check the connection and try again.", async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/tickets/${ticketId}/drafts/${draft.draft_id}/review`,
        { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: decision }) },
      );
      if (!response.ok) {
        setMessage("This draft could not be reviewed. Refresh the ticket status and try again.");
        return;
      }
      const reviewed = (await response.json()) as TicketDraft;
      setDraftsByTicket((current) => ({ ...current, [ticketId]: reviewed }));
      await loadTickets(selectedWorkspace);
      setMessage(decision === "approved" ? "Draft approved. The ticket is now resolved." : "Draft rejected. The ticket returned to drafting.");
    });
  }

  async function openHumanReview(ticketId: string) {
    if (!selectedWorkspace) return;
    if (reviewTicketId === ticketId) {
      setReviewTicketId(null);
      setMessage("Human review minimized. The ticket remains open for a support owner.");
      return;
    }
    return runAction(`open-human-review:${ticketId}`, "Opening human review…", "Could not open the human review details. Check the connection and try again.", async () => {
      await loadTicketDetail(selectedWorkspace, ticketId);
      setReviewTicketId(ticketId);
      setMessage(
        isKnowledgeGap(coordinatorRunsByTicket[ticketId]?.[0])
          ? "Knowledge-gap review is open. No approved source supported an AI reply."
          : "Human review is open. AI drafting remains blocked for this ticket.",
      );
    });
  }

  function minimizeHumanReview(ticketId: string) {
    if (reviewTicketId !== ticketId) return;
    setReviewTicketId(null);
    setMessage("Human review minimized. The ticket remains open for a support owner.");
  }

  async function addHumanReviewNote(ticketId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const formElement = event.currentTarget;
    const body = String(new FormData(formElement).get("reviewNote") ?? "").trim();
    if (!body) return;
    return runAction(`add-review-note:${ticketId}`, "Saving internal note…", "Could not save the internal note. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/tickets/${ticketId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body, author: "support_agent" }),
      });
      if (!response.ok) {
        setMessage("Could not save the internal note. It must contain text.");
        return;
      }
      formElement.reset();
      await loadTicketDetail(selectedWorkspace, ticketId);
      setMessage("Internal note saved. It is visible only in this human review workflow.");
    });
  }

  async function resolveHumanReview(ticketId: string) {
    if (!selectedWorkspace) return;
    return runAction(`resolve-human-review:${ticketId}`, "Resolving human review…", "Could not resolve this ticket. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/tickets/${ticketId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "resolved" }),
      });
      if (!response.ok) {
        setMessage("This ticket cannot be resolved from its current status.");
        return;
      }
      await loadTickets(selectedWorkspace);
      setReviewTicketId((current) => current === ticketId ? null : current);
      setReviewTicketDetails((current) => {
        const { [ticketId]: _resolvedTicket, ...remaining } = current;
        return remaining;
      });
      setMessage("Human review completed. The ticket is resolved; no AI reply was generated.");
    });
  }

  async function createEvaluationCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const formElement = event.currentTarget;
    return runAction("create-retrieval-evaluation", "Saving retrieval evaluation…", "Could not add this evaluation. Check the connection and try again.", async () => {
      const form = new FormData(formElement);
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/retrieval-evaluations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: form.get("evaluationQuery"), expected_article_id: form.get("expectedArticleId") }),
      });
      if (!response.ok) {
        setMessage("Could not add this evaluation. The expected article must be published in this workspace.");
        return;
      }
      formElement.reset();
      await loadEvaluationCases(selectedWorkspace);
      setMessage("Evaluation case added. Run it to measure hybrid retrieval.");
    });
  }

  async function runEvaluation() {
    if (!selectedWorkspace) return;
    return runAction("run-retrieval-evaluation", "Running hybrid retrieval evaluation…", "Retrieval evaluation could not run. Check the connection and confirm Ollama is running locally.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/retrieval-evaluations/run`, {
        method: "POST",
      });
      if (!response.ok) {
        setMessage("Retrieval evaluation could not run. Confirm Ollama is running locally.");
        return;
      }
      setEvaluationReport((await response.json()) as RetrievalEvaluationReport);
      setMessage("Hybrid retrieval evaluation completed.");
    });
  }

  async function createDraftEvaluationCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const formElement = event.currentTarget;
    return runAction("create-draft-evaluation", "Saving comparison case…", "Could not add this lab case. Check the connection and try again.", async () => {
      const form = new FormData(formElement);
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/draft-evaluations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject: form.get("draftEvaluationSubject"),
          message: form.get("draftEvaluationMessage"),
          expected_article_id: form.get("draftEvaluationArticleId"),
        }),
      });
      if (!response.ok) {
        setMessage("Could not add this lab case. The source ID must be a published article in this workspace.");
        return;
      }
      formElement.reset();
      await loadDraftEvaluationCases(selectedWorkspace);
      setMessage("Synthetic lab case added. It cannot create a customer ticket or send a reply.");
    });
  }

  async function compareDraftModels(evaluationId: string) {
    if (!selectedWorkspace) return;
    return runAction(`compare-models:${evaluationId}`, "Queuing model comparison…", "The comparison could not be queued. Check the connection and confirm the ResolveAI worker is running.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/draft-evaluations/${evaluationId}/run`, {
        method: "POST",
      });
      if (!response.ok) {
        setMessage("The comparison could not be queued. Confirm the ResolveAI worker is running.");
        return;
      }
      const job = (await response.json()) as DraftEvaluationJob;
      setDraftEvaluationJobsByCase((current) => ({
        ...current,
        [evaluationId]: [job, ...(current[evaluationId] ?? [])],
      }));
      setMessage("Model comparison is queued. ResolveAI will refresh the result when the worker finishes.");
    });
  }

  function toggleBenchmarkCase(evaluationId: string) {
    setSelectedBenchmarkCaseIds((current) => current.includes(evaluationId)
      ? current.filter((id) => id !== evaluationId)
      : [...current, evaluationId]);
  }

  async function runBenchmarkBatch() {
    if (!selectedWorkspace || selectedBenchmarkCaseIds.length === 0 || benchmarkExperimentName.trim().length < 3) return;
    return runAction("run-benchmark", "Queuing named benchmark…", "The experiment could not be queued. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/draft-evaluations/experiments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: benchmarkExperimentName.trim(), evaluation_ids: selectedBenchmarkCaseIds }),
      });
      if (!response.ok) {
        setMessage("The experiment could not be queued. Each selected case needs a published source.");
        return;
      }
      const experiment = (await response.json()) as DraftEvaluationExperiment;
      await Promise.all([loadDraftEvaluationCases(selectedWorkspace), loadBenchmarkExperiments(selectedWorkspace)]);
      setBenchmarkExperimentName("");
      setSelectedBenchmarkCaseIds([]);
      setMessage(`Experiment “${experiment.name}” was saved with ${experiment.case_ids.length} benchmark case${experiment.case_ids.length === 1 ? "" : "s"}.`);
    });
  }

  async function saveModelSelectionPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspace) return;
    const form = new FormData(event.currentTarget);
    return runAction("save-model-policy", "Saving model-selection policy…", "Could not save the policy. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/model-selection-policy`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          min_grounding_rate: Number(form.get("minGroundingRate")) / 100,
          min_average_human_score: Number(form.get("minHumanScore")),
          max_average_latency_ms: Number(form.get("maxLatencySeconds")) * 1000,
        }),
      });
      if (!response.ok) {
        setMessage("Could not save the policy. Use 0–100% grounding, 1–5 score, and 1–600 seconds.");
        return;
      }
      await loadModelSelectionReport(selectedWorkspace);
      setMessage("Model-selection policy saved. The recommendations now use your guardrails.");
    });
  }

  async function scoreDraftEvaluation(evaluationId: string, runId: string, score: number) {
    if (!selectedWorkspace) return;
    return runAction(`score-evaluation:${runId}`, "Saving quality score…", "Could not save that quality score. Check the connection and try again.", async () => {
      const response = await fetch(`${API_BASE_URL}/api/v1/workspaces/${selectedWorkspace}/draft-evaluations/${evaluationId}/runs/${runId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ human_score: score }),
      });
      if (!response.ok) {
        setMessage("Could not save that quality score.");
        return;
      }
      const updated = (await response.json()) as DraftEvaluationRun;
      setDraftEvaluationRunsByCase((current) => ({
        ...current,
        [evaluationId]: (current[evaluationId] ?? []).map((run) => run.run_id === updated.run_id ? updated : run),
      }));
      await loadDraftModelQualityReport(selectedWorkspace);
      setMessage("Your human quality score was saved.");
    });
  }

  return (
    <main className="app-shell" data-area={activeArea}>
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">RESOLVEAI / SUPPORT OPERATIONS</p>
          <h1><span>Carefully</span> intelligent.<br />Decidedly human.</h1>
          <p className="hero-summary">A grounded AI workspace for support teams who want faster answers without giving up judgment.</p>
          <div className="hero-tags"><span>HYBRID RETRIEVAL</span><span>HUMAN REVIEW</span><span>MODEL LAB</span></div>
          <a className="demo-link" href="/demo">Take the guided demo <span aria-hidden="true">↗</span></a>
        </div>
        <div className="hero-console" aria-label="Workspace activity summary">
          <div className="console-topline"><span>LIVE WORKSPACE</span><span className="live-mark"><i aria-hidden="true" />SYSTEMS NOMINAL</span></div>
          <div className="console-orbit" aria-hidden="true"><b>AI</b><span>+</span><em>H</em></div>
          <div className="console-stats"><div><strong>{tickets.length}</strong><span>open<br />tickets</span></div><div><strong>{articles.length}</strong><span>approved<br />sources</span></div><div><strong>{draftModelQualityReport?.total_runs ?? 0}</strong><span>lab<br />runs</span></div></div>
          <p className="status"><span className="status-dot" aria-hidden="true" />Human review stays in control</p>
        </div>
      </header>

      {message && <p className="notice" role="status">{message}</p>}

      <nav className="product-nav" aria-label="ResolveAI areas">
        <div className="area-tabs"><button className={activeArea === "desk" ? "active" : ""} type="button" onClick={() => setActiveArea("desk")}>Support desk</button><button className={activeArea === "knowledge" ? "active" : ""} type="button" onClick={() => setActiveArea("knowledge")}>Knowledge</button><button className={activeArea === "lab" ? "active" : ""} type="button" onClick={() => setActiveArea("lab")}>AI lab</button></div>
        <label>Active workspace<select aria-label="Selected workspace" value={selectedWorkspace} onChange={(event) => setSelectedWorkspace(event.target.value)}><option value="">Choose a workspace</option>{workspaces.map((workspace) => <option key={workspace.id} value={workspace.slug}>{workspace.name}</option>)}</select></label>
      </nav>

      <section className="panel area-knowledge">
        <div className="section-heading">
          <div><p className="label">WORKSPACE SETUP</p><h2>Create a support workspace</h2></div>
        </div>
        <form className="compact-form" onSubmit={createWorkspace}>
          <input name="name" placeholder="Acme Support" minLength={2} required />
          <input name="slug" placeholder="acme-support" pattern="[a-z0-9]+(-[a-z0-9]+)*" minLength={2} required onChange={(event) => { event.currentTarget.value = event.currentTarget.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""); }} />
          <button type="submit" disabled={isActionPending("create-workspace")}>{isActionPending("create-workspace") ? "Creating…" : "Create workspace"}</button>
        </form>
      </section>

      <div className="workspace-grid area-desk">
        <section className="panel">
          <p className="label">STEP 2</p><h2>Log a customer ticket</h2>
          <p className="helper">This is the only action here: create a realistic sample request. It will appear in Open tickets beside this form, ready for assessment.</p>
          <form className="ticket-form" onSubmit={createTicket}>
            <input name="customerName" placeholder="Customer name" minLength={2} required disabled={!selectedWorkspace || isActionPending("create-ticket")} />
            <input name="customerEmail" type="email" placeholder="customer@company.com" required disabled={!selectedWorkspace || isActionPending("create-ticket")} />
            <input name="subject" placeholder="What does the customer need help with?" minLength={3} required disabled={!selectedWorkspace || isActionPending("create-ticket")} />
            <textarea name="ticketMessage" placeholder="Paste the customer’s question or issue here." minLength={3} required disabled={!selectedWorkspace || isActionPending("create-ticket")} />
            <select name="priority" defaultValue="normal" disabled={!selectedWorkspace || isActionPending("create-ticket")}>
              <option value="low">Low priority</option><option value="normal">Normal priority</option><option value="high">High priority</option><option value="urgent">Urgent priority</option>
            </select>
            <button type="submit" disabled={!selectedWorkspace || isActionPending("create-ticket")}>{isActionPending("create-ticket") ? "Creating ticket…" : "Create ticket"}</button>
          </form>
        </section>

        <section className="panel ticket-list">
          <div className="section-heading"><div><p className="label">STEP 3</p><h2>Open tickets</h2></div><span>{tickets.length} total</span></div>
          {tickets.length === 0 ? <p className="empty">Create a workspace, then log the first customer ticket.</p> : (
            <ul>
              {tickets.map((ticket) => <li key={ticket.ticket_id}>
                <div className="ticket-card"><div className="ticket-summary"><div><p className="ticket-id">{ticket.ticket_id}</p><h3>{ticket.subject}</h3><p>{ticket.customer_name} · {ticket.customer_email}</p></div><div className="badges"><span>{ticket.priority}</span><span>{ticket.status.replace("_", " ")}</span></div></div>
                {!draftsByTicket[ticket.ticket_id] && !triageByTicket[ticket.ticket_id] && <button type="button" className="draft-button" onClick={() => assessTicket(ticket.ticket_id)} disabled={isActionPending(`assess-ticket:${ticket.ticket_id}`)}>{isActionPending(`assess-ticket:${ticket.ticket_id}`) ? "Assessing…" : "Assess ticket"}</button>}
                {triageByTicket[ticket.ticket_id] && <div className="draft-card"><p className="label">TRIAGE SPECIALIST / {triageByTicket[ticket.ticket_id].decision.replaceAll("_", " ")}</p><p>{triageByTicket[ticket.ticket_id].reason}</p><p className="draft-meta">Category: {triageByTicket[ticket.ticket_id].category.replaceAll("_", " ")} · Model: {triageByTicket[ticket.ticket_id].model}</p></div>}
                {isKnowledgeGap(coordinatorRunsByTicket[ticket.ticket_id]?.[0]) && <div className="draft-card"><p className="label">KNOWLEDGE GAP / NO AI REPLY</p><p>No approved knowledge sources match this ticket, so ResolveAI will not draft a reply.</p><p className="helper">A support owner can handle the request and decide whether the handbook needs new guidance.</p></div>}
                {(triageByTicket[ticket.ticket_id]?.decision === "human_escalation" || isKnowledgeGap(coordinatorRunsByTicket[ticket.ticket_id]?.[0])) && <button type="button" className="draft-button" onClick={() => openHumanReview(ticket.ticket_id)} disabled={isActionPending(`open-human-review:${ticket.ticket_id}`)}>{isActionPending(`open-human-review:${ticket.ticket_id}`) ? "Opening review…" : reviewTicketId === ticket.ticket_id ? "Minimize review" : isKnowledgeGap(coordinatorRunsByTicket[ticket.ticket_id]?.[0]) ? "Open knowledge-gap review" : "Open human review"}</button>}
                {reviewTicketId === ticket.ticket_id && reviewTicketDetails[ticket.ticket_id] && <section className="human-review-card" aria-label={`Human review for ${ticket.ticket_id}`}><div className="section-heading"><div><p className="label">{isKnowledgeGap(coordinatorRunsByTicket[ticket.ticket_id]?.[0]) ? "KNOWLEDGE GAP / AI BLOCKED" : "HUMAN REVIEW / AI BLOCKED"}</p><h3>{isKnowledgeGap(coordinatorRunsByTicket[ticket.ticket_id]?.[0]) ? "Review missing handbook coverage" : "Review this escalation"}</h3></div><div className="review-header-actions"><span>{reviewTicketDetails[ticket.ticket_id].status.replace("_", " ")}</span><button type="button" className="minimize-button" onClick={() => minimizeHumanReview(ticket.ticket_id)} aria-label="Minimize human review">−</button></div></div><p className="helper">Customer request</p><p className="customer-message">{reviewTicketDetails[ticket.ticket_id].message}</p><p className="helper">{isKnowledgeGap(coordinatorRunsByTicket[ticket.ticket_id]?.[0]) ? "No approved handbook source matched this request. A support owner should handle it and decide whether the knowledge base needs new guidance." : "The support operator decides the response outside this AI drafting workflow. Internal notes are kept with the ticket."}</p><div className="review-notes"><p className="label">INTERNAL NOTES</p>{reviewTicketDetails[ticket.ticket_id].notes.length === 0 ? <p className="empty">No internal notes yet.</p> : <ul>{reviewTicketDetails[ticket.ticket_id].notes.map((note) => <li key={note.id}><strong>{note.author.replace("_", " ")}</strong><span>{new Date(note.created_at).toLocaleString()}</span><p>{note.body}</p></li>)}</ul>}</div><form className="ticket-form" onSubmit={(event) => addHumanReviewNote(ticket.ticket_id, event)}><textarea name="reviewNote" placeholder="Add an internal note for the support team" minLength={1} required disabled={isActionPending(`add-review-note:${ticket.ticket_id}`)} /><button type="submit" disabled={isActionPending(`add-review-note:${ticket.ticket_id}`)}>{isActionPending(`add-review-note:${ticket.ticket_id}`) ? "Saving note…" : "Add internal note"}</button></form>{ticket.status !== "resolved" && <button type="button" className="secondary-button" onClick={() => resolveHumanReview(ticket.ticket_id)} disabled={isActionPending(`resolve-human-review:${ticket.ticket_id}`)}>{isActionPending(`resolve-human-review:${ticket.ticket_id}`) ? "Resolving…" : "Mark human review resolved"}</button>}</section>}
                {draftsByTicket[ticket.ticket_id] && triageByTicket[ticket.ticket_id]?.decision === "human_escalation" && <p className="helper">This escalation was recorded after an existing draft and does not change that historical draft.</p>}
                {triageByTicket[ticket.ticket_id]?.decision === "draft_allowed" && (!draftsByTicket[ticket.ticket_id] || draftsByTicket[ticket.ticket_id].status === "rejected") && <button type="button" className="draft-button" onClick={() => generateDraft(ticket.ticket_id)} disabled={isActionPending(`generate-draft:${ticket.ticket_id}`)}>{isActionPending(`generate-draft:${ticket.ticket_id}`) ? "Drafting…" : isKnowledgeGap(coordinatorRunsByTicket[ticket.ticket_id]?.[0]) ? "Retry after publishing a source" : "Generate grounded draft"}</button>}
                {groundingReviewsByTicket[ticket.ticket_id] && <div className="draft-card"><p className="label">GROUNDING REVIEWER / {groundingReviewsByTicket[ticket.ticket_id].decision.replaceAll("_", " ")}</p><p>{groundingReviewsByTicket[ticket.ticket_id].reason}</p><p className="draft-meta">Checked sources: {groundingReviewsByTicket[ticket.ticket_id].source_article_ids.join(", ")} · Model: {groundingReviewsByTicket[ticket.ticket_id].model}</p></div>}
                {coordinatorRunsByTicket[ticket.ticket_id]?.[0] && <div className="draft-card"><p className="label">MASTER COORDINATOR / {coordinatorRunsByTicket[ticket.ticket_id][0].status}</p><p className="helper">This is a safe operational timeline: it records handoffs, timings, models, and approved source IDs—not prompts or private reasoning.</p><ol className="agent-timeline">{coordinatorRunsByTicket[ticket.ticket_id][0].stages.map((stage) => <li key={stage.name}><strong>{agentDisplayName(stage.name)}</strong> · {stage.outcome?.replaceAll("_", " ") ?? "completed"} · {stage.elapsed_ms} ms · {coordinatorRunsByTicket[ticket.ticket_id][0].agent_models[stage.name] ?? coordinatorRunsByTicket[ticket.ticket_id][0].agent_models[`${stage.name}_embedding`] ?? "local orchestration"}</li>)}</ol><p className="draft-meta">Run: {coordinatorRunsByTicket[ticket.ticket_id][0].run_id} · Total: {coordinatorRunsByTicket[ticket.ticket_id][0].elapsed_ms} ms · Sources: {coordinatorRunsByTicket[ticket.ticket_id][0].source_article_ids.join(", ") || "none"}</p></div>}
                {draftsByTicket[ticket.ticket_id] && <div className="draft-card"><p className="label">COORDINATOR DRAFT / {draftsByTicket[ticket.ticket_id].status.replace("_", " ")}</p><div className="draft-content">{renderDraftBody(draftsByTicket[ticket.ticket_id].body)}</div><p className="draft-meta">Sources: {draftsByTicket[ticket.ticket_id].source_article_ids.join(", ")} · Trace: {draftsByTicket[ticket.ticket_id].coordinator_trace.join(" → ")}</p>{draftsByTicket[ticket.ticket_id].status === "awaiting_review" && <div className="review-actions"><button type="button" onClick={() => reviewDraft(ticket.ticket_id, "approved")} disabled={isActionPending(`review-draft:${ticket.ticket_id}`)}>{isActionPending(`review-draft:${ticket.ticket_id}`) ? "Saving…" : "Approve draft"}</button><button type="button" className="secondary-button" onClick={() => reviewDraft(ticket.ticket_id, "rejected")} disabled={isActionPending(`review-draft:${ticket.ticket_id}`)}>{isActionPending(`review-draft:${ticket.ticket_id}`) ? "Saving…" : "Reject & revise"}</button></div>}</div>}</div>
              </li>)}
            </ul>
          )}
        </section>
      </div>

      <section className="panel knowledge-panel area-knowledge">
        <div className="section-heading">
          <div><p className="label">KNOWLEDGE ADMIN</p><h2>Import and approve trusted knowledge</h2></div>
          <span>{articles.length} articles</span>
        </div>
        <p className="helper">Import a policy or support decision, then have a human publish it. Only published content can become an AI source.</p>
        <div className="workspace-grid">
          <div><form className="ticket-form document-import" onSubmit={importKnowledgeDocument}><p className="label">IMPORT A DOCUMENT</p><input name="knowledgeDocument" type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" required disabled={!selectedWorkspace || isImportingDocument} /><input name="documentCategory" placeholder="Category, for example: Authentication" minLength={2} required disabled={!selectedWorkspace || isImportingDocument} /><button type="submit" disabled={!selectedWorkspace || isImportingDocument}>{isImportingDocument ? "Importing…" : "Import as draft"}</button></form><details className="manual-entry"><summary>Or create one article manually</summary><form className="ticket-form" onSubmit={createArticle}><input name="title" placeholder="Article title" minLength={3} required disabled={!selectedWorkspace || isActionPending("create-article")} /><input name="category" placeholder="Category, for example: Authentication" minLength={2} required disabled={!selectedWorkspace || isActionPending("create-article")} /><textarea name="body" placeholder="Write the approved troubleshooting or policy guidance (at least 20 characters)." minLength={20} required disabled={!selectedWorkspace || isActionPending("create-article")} /><button type="submit" disabled={!selectedWorkspace || isActionPending("create-article")}>{isActionPending("create-article") ? "Saving…" : "Save as draft"}</button></form></details></div>
          <div className="article-list">
            {documents.length > 0 && <><p className="label">SOURCE DOCUMENTS</p><ul>{documents.map((document) => <li key={document.document_id}><div><p className="ticket-id">{document.document_id} · {document.category}</p><h3>{document.title}</h3><p>{document.source_file_name} · {document.chunk_count} searchable section{document.chunk_count === 1 ? "" : "s"}</p></div><div className="article-actions"><span className="badges"><span>{document.status}</span></span>{document.status === "draft" && <div className="document-actions"><button type="button" onClick={() => publishDocument(document.document_id)} disabled={isActionPending(`publish-document:${document.document_id}`)}>{isActionPending(`publish-document:${document.document_id}`) ? "Publishing…" : "Publish document"}</button><button type="button" className="danger-button" onClick={() => deleteDraftDocument(document.document_id)} disabled={isActionPending(`delete-document:${document.document_id}`)}>{isActionPending(`delete-document:${document.document_id}`) ? "Deleting…" : "Delete draft"}</button></div>}</div></li>)}</ul></>}
            {articles.length === 0 ? <p className="empty">Import a handbook or add approved guidance before asking AI to draft replies.</p> : (
              <ul>
                {articles.filter((article) => !article.title.includes(" — ")).map((article) => <li key={article.article_id}>
                  <div><p className="ticket-id">{article.article_id} · {article.category}</p><h3>{article.title}</h3><p>{article.body}</p></div>
                  <div className="article-actions"><span className="badges"><span>{article.status}</span></span>{article.status === "draft" && <button type="button" onClick={() => publishArticle(article.article_id)} disabled={isActionPending(`publish-article:${article.article_id}`)}>{isActionPending(`publish-article:${article.article_id}`) ? "Publishing…" : "Publish"}</button>}</div>
                </li>)}
              </ul>
            )}
          </div>
        </div>
      </section>

      <section className="panel knowledge-panel search-panel area-knowledge">
        <div className="section-heading"><div><p className="label">STEP 5</p><h2>Search approved sources</h2></div><span>Keyword retrieval</span></div>
        <p className="helper">This search deliberately ignores drafts and archived articles. In the next phase, semantic search will complement it.</p>
        <form className="compact-form search-form" onSubmit={searchKnowledge}>
          <input name="query" placeholder="For example: enterprise SSO access" minLength={2} required disabled={!selectedWorkspace || isActionPending("search-keyword")} />
          <button type="submit" disabled={!selectedWorkspace || isActionPending("search-keyword")}>{isActionPending("search-keyword") ? "Searching…" : "Find sources"}</button>
        </form>
        {lastSearch && <div className="search-results"><p className="helper">Results for “{lastSearch}”</p>{searchResults.length === 0 ? <p className="empty">No published sources match yet.</p> : <ul>{searchResults.map((article) => <li key={article.article_id}><div><p className="ticket-id">{article.article_id} · {article.category}</p><h3>{article.title}</h3><p>{article.body}</p></div><span className="search-score">Match {article.score.toFixed(2)}</span></li>)}</ul>}</div>}
      </section>

      <section className="panel knowledge-panel search-panel area-knowledge">
        <div className="section-heading"><div><p className="label">STEP 6</p><h2>Search by meaning</h2></div><span>Local Ollama + pgvector</span></div>
        <p className="helper">Indexing turns approved source text into local meaning vectors. Semantic search can surface related guidance even when the words differ.</p>
        <div className="semantic-actions"><button type="button" onClick={reindexKnowledge} disabled={!selectedWorkspace || isActionPending("reindex-knowledge")}>{isActionPending("reindex-knowledge") ? "Indexing…" : "Index published sources"}</button></div>
        <form className="compact-form search-form" onSubmit={searchSemantically}>
          <input name="semanticQuery" placeholder="For example: company login is failing" minLength={2} required disabled={!selectedWorkspace || isActionPending("search-semantic")} />
          <button type="submit" disabled={!selectedWorkspace || isActionPending("search-semantic")}>{isActionPending("search-semantic") ? "Searching…" : "Find related sources"}</button>
        </form>
        {lastSemanticSearch && <div className="search-results"><p className="helper">Meaning-based results for “{lastSemanticSearch}”</p>{semanticResults.length === 0 ? <p className="empty">No indexed published sources match yet.</p> : <ul>{semanticResults.map((article) => <li key={article.article_id}><div><p className="ticket-id">{article.article_id} · {article.category}</p><h3>{article.title}</h3><p>{article.body}</p></div><span className="search-score">Similarity {article.score.toFixed(2)}</span></li>)}</ul>}</div>}
      </section>

      <section className="panel knowledge-panel search-panel area-knowledge">
        <div className="section-heading"><div><p className="label">STEP 7</p><h2>Combine both retrieval methods</h2></div><span>Hybrid / RRF</span></div>
        <p className="helper">Hybrid search rewards sources that independently rank well for exact words, meaning, or both. It does not add incompatible score types together.</p>
        <form className="compact-form search-form" onSubmit={searchHybrid}>
          <input name="hybridQuery" placeholder="For example: company SSO login problem" minLength={2} required disabled={!selectedWorkspace || isActionPending("search-hybrid")} />
          <button type="submit" disabled={!selectedWorkspace || isActionPending("search-hybrid")}>{isActionPending("search-hybrid") ? "Combining…" : "Combine sources"}</button>
        </form>
        {lastHybridSearch && <div className="search-results"><p className="helper">Fused results for “{lastHybridSearch}”</p>{hybridResults.length === 0 ? <p className="empty">No approved source matches yet.</p> : <ul>{hybridResults.map((article) => <li key={article.article_id}><div><p className="ticket-id">{article.article_id} · {article.category}</p><h3>{article.title}</h3><p>{article.body}</p></div><div className="rank-details"><span className="search-score">RRF {article.fusion_score.toFixed(3)}</span>{article.keyword_rank && <span>Keyword #{article.keyword_rank}</span>}{article.semantic_rank && <span>Meaning #{article.semantic_rank}</span>}</div></li>)}</ul>}</div>}
      </section>

      <section className="panel knowledge-panel search-panel area-knowledge">
        <div className="section-heading"><div><p className="label">STEP 8</p><h2>Measure retrieval quality</h2></div><span>Evaluation + safe traces</span></div>
        <p className="helper">Add a realistic customer question and the published article that a human says should answer it. ResolveAI then runs the same hybrid search used by the coordinator and reports whether the right source appeared in its top five.</p>
        <form className="compact-form search-form" onSubmit={createEvaluationCase}>
          <input name="evaluationQuery" placeholder="Customer-style question, for example: company SSO login fails" minLength={2} required disabled={!selectedWorkspace || isActionPending("create-retrieval-evaluation")} />
          <input name="expectedArticleId" placeholder="Published source ID, for example: KB-2026-1234ABCD" minLength={3} required disabled={!selectedWorkspace || isActionPending("create-retrieval-evaluation")} />
          <button type="submit" disabled={!selectedWorkspace || isActionPending("create-retrieval-evaluation")}>{isActionPending("create-retrieval-evaluation") ? "Saving…" : "Add evaluation"}</button>
        </form>
        <div className="semantic-actions"><button type="button" onClick={runEvaluation} disabled={!selectedWorkspace || evaluationCases.length === 0 || isActionPending("run-retrieval-evaluation")}>{isActionPending("run-retrieval-evaluation") ? "Evaluating…" : "Run evaluation"}</button></div>
        {evaluationCases.length > 0 && <p className="helper">{evaluationCases.length} saved evaluation {evaluationCases.length === 1 ? "case" : "cases"}. Expected source IDs: {evaluationCases.map((item) => item.expected_article_id).join(", ")}</p>}
        {evaluationReport && <div className="search-results"><p className="helper">{evaluationReport.total_cases} cases · Hit@5 {(evaluationReport.hit_at_k * 100).toFixed(0)}% · MRR {evaluationReport.mean_reciprocal_rank.toFixed(2)}</p><ul>{evaluationReport.results.map((result) => <li key={result.evaluation_id}><div><p className="ticket-id">Expected: {result.expected_article_id}</p><p>{result.expected_rank ? `Found at rank #${result.expected_rank}` : "Not found in the top five"}</p></div><span className="search-score">Retrieved: {result.retrieved_article_ids.join(", ") || "none"}</span></li>)}</ul></div>}
      </section>

      <section className="panel knowledge-panel search-panel area-lab">
        <div className="section-heading"><div><p className="label">STEP 9</p><h2>Compare draft models safely</h2></div><span>Configured writers</span></div>
        <p className="helper">This lab is your labelled benchmark dataset: each synthetic customer scenario is paired with the published source a human expects to answer it. A background worker runs slow model calls, so the browser is never held open.</p>
        <form className="ticket-form" onSubmit={createDraftEvaluationCase}>
          <input name="draftEvaluationSubject" placeholder="Synthetic ticket subject" minLength={3} required disabled={!selectedWorkspace || isActionPending("create-draft-evaluation")} />
          <textarea name="draftEvaluationMessage" placeholder="Synthetic customer question to give both writers" minLength={3} required disabled={!selectedWorkspace || isActionPending("create-draft-evaluation")} />
          <input name="draftEvaluationArticleId" placeholder="Published source ID, for example: KB-2026-1234ABCD" minLength={3} required disabled={!selectedWorkspace || isActionPending("create-draft-evaluation")} />
          <button type="submit" disabled={!selectedWorkspace || isActionPending("create-draft-evaluation")}>{isActionPending("create-draft-evaluation") ? "Saving…" : "Add comparison case"}</button>
        </form>
        {draftEvaluationCases.length > 0 && <div className="semantic-actions"><input value={benchmarkExperimentName} onChange={(event) => setBenchmarkExperimentName(event.target.value)} placeholder="Experiment name, for example: SSO benchmark v1" minLength={3} disabled={isActionPending("run-benchmark")} /><button type="button" onClick={runBenchmarkBatch} disabled={!selectedWorkspace || selectedBenchmarkCaseIds.length === 0 || benchmarkExperimentName.trim().length < 3 || isActionPending("run-benchmark")}>{isActionPending("run-benchmark") ? "Queuing…" : `Run named experiment (${selectedBenchmarkCaseIds.length})`}</button><p className="helper">Each selected case becomes its own durable job, so results remain comparable and traceable.</p></div>}
        {draftEvaluationCases.length > 0 && <div className="search-results"><ul>{draftEvaluationCases.map((evaluationCase) => {
          const latestJob = draftEvaluationJobsByCase[evaluationCase.evaluation_id]?.[0];
          const isActive = latestJob?.status === "queued" || latestJob?.status === "running";
          return <li key={evaluationCase.evaluation_id}>
            <div><label className="helper"><input type="checkbox" checked={selectedBenchmarkCaseIds.includes(evaluationCase.evaluation_id)} onChange={() => toggleBenchmarkCase(evaluationCase.evaluation_id)} /> Include in benchmark batch</label><p className="ticket-id">{evaluationCase.evaluation_id} · Source: {evaluationCase.expected_article_id}</p><h3>{evaluationCase.subject}</h3><p>{evaluationCase.message}</p></div>
            <button type="button" onClick={() => compareDraftModels(evaluationCase.evaluation_id)} disabled={isActive || isActionPending(`compare-models:${evaluationCase.evaluation_id}`)}>{isActionPending(`compare-models:${evaluationCase.evaluation_id}`) ? "Queuing…" : "Run both writers"}</button>
            {latestJob && <p className="helper">Worker job: {latestJob.status}{latestJob.error_message ? ` · ${latestJob.error_message}` : ""}</p>}
            <div className="draft-card"><p className="helper">Latest result per provider</p>{latestRunsByProvider(draftEvaluationRunsByCase[evaluationCase.evaluation_id] ?? []).map((run) => <div key={run.run_id}><p className="label">{run.provider} / {run.status} / {run.model}</p><p>{run.draft_body ?? run.error_message}</p>{formatProviderTrail(run) && <p className="helper">{formatProviderTrail(run)}</p>}{run.quality_decision && <p className="helper">Quality check: {run.quality_decision.replaceAll("_", " ")} · {run.quality_reason}</p>}<p className="draft-meta">{formatDraftTiming(run)} · Grounding: {run.review_decision?.replaceAll("_", " ") ?? "not run"} · {run.review_reason ?? ""}</p>{run.status === "completed" && <label className="helper">Your quality score <select value={run.human_score ?? ""} onChange={(event) => { const score = Number(event.target.value); if (score) scoreDraftEvaluation(evaluationCase.evaluation_id, run.run_id, score); }}><option value="">Choose 1–5</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option></select></label>}</div>)}</div>
          </li>;
        })}</ul></div>}
        {benchmarkExperiments.length > 0 && <div className="search-results"><p className="helper">Saved experiment snapshots</p><ul>{benchmarkExperiments.map((experiment) => <li key={experiment.experiment_id}><div><p className="ticket-id">{experiment.experiment_id}</p><h3>{experiment.name}</h3><p>Frozen cases: {experiment.case_ids.join(", ")}</p></div></li>)}</ul></div>}
      </section>

      <section className="panel knowledge-panel search-panel area-lab">
        <div className="section-heading"><div><p className="label">STEP 10</p><h2>Inspect model quality</h2></div><span>Synthetic lab only</span></div>
        <p className="helper">Compare actual resolved models using only synthetic evaluation runs. A missing human score means no person has rated that run yet; it is never counted as zero.</p>
        {!draftModelQualityReport || draftModelQualityReport.models.length === 0 ? <p className="empty">Run a synthetic comparison to begin collecting model-quality evidence.</p> : <div className="quality-table-wrap"><p className="helper">Current configuration: {draftModelQualityReport.active_models.map((model) => `${model.provider} / ${model.model} (${model.role})`).join(" · ")}. {draftModelQualityReport.total_runs} total synthetic runs. Active time is writer generation plus the grounding review; it excludes time waiting behind another GPU review.</p><table className="quality-table"><thead><tr><th>Provider / model</th><th>Status</th><th>Runs</th><th>Grounded</th><th>Human score</th><th>Avg. active time</th><th>Failures</th></tr></thead><tbody>{draftModelQualityReport.models.map((metric) => <tr key={`${metric.provider}-${metric.model}`}><td>{metric.provider}<br /><span>{metric.model}</span></td><td>{metric.is_active ? metric.active_role : "historical"}</td><td>{metric.total_runs}</td><td>{metric.grounding_pass_rate === null ? "not reviewed" : `${(metric.grounding_pass_rate * 100).toFixed(0)}% (${metric.completed_runs} completed)`}</td><td>{metric.average_human_score === null ? `not scored (${metric.human_scored_runs})` : `${metric.average_human_score.toFixed(1)} / 5 (${metric.human_scored_runs})`}</td><td>{metric.average_latency_ms === null ? "—" : `${(metric.average_latency_ms / 1000).toFixed(1)} s`}</td><td>{metric.failed_runs}</td></tr>)}</tbody></table></div>}
      </section>

      <section className="panel knowledge-panel search-panel area-lab">
        <div className="section-heading"><div><p className="label">STEP 11</p><h2>Apply a model-selection policy</h2></div><span>Human decision aid</span></div>
        <p className="helper">This policy evaluates only the current configured models from synthetic evidence. It never switches customer traffic automatically; historical models remain visible above as evidence.</p>
        {!modelSelectionReport ? <p className="empty">Loading model-selection evidence…</p> : <div className="search-results"><form className="compact-form search-form" onSubmit={saveModelSelectionPolicy}><label>Minimum grounding (%)<input name="minGroundingRate" type="number" min="0" max="100" step="1" defaultValue={(modelSelectionReport.policy.min_grounding_rate * 100).toFixed(0)} required disabled={isActionPending("save-model-policy")} /></label><label>Minimum human score<input name="minHumanScore" type="number" min="1" max="5" step="0.1" defaultValue={modelSelectionReport.policy.min_average_human_score.toFixed(1)} required disabled={isActionPending("save-model-policy")} /></label><label>Maximum speed (seconds)<input name="maxLatencySeconds" type="number" min="1" max="600" step="1" defaultValue={(modelSelectionReport.policy.max_average_latency_ms / 1000).toFixed(0)} required disabled={isActionPending("save-model-policy")} /></label><button type="submit" disabled={isActionPending("save-model-policy")}>{isActionPending("save-model-policy") ? "Saving…" : "Save policy"}</button></form><p className="helper">Policy: at least {(modelSelectionReport.policy.min_grounding_rate * 100).toFixed(0)}% grounded, {modelSelectionReport.policy.min_average_human_score.toFixed(1)}/5 human score, under {(modelSelectionReport.policy.max_average_latency_ms / 1000).toFixed(0)} seconds.</p><ul>{modelSelectionReport.recommendations.map((item) => <li key={`${item.provider}-${item.model}`}><div><p className="ticket-id">{item.provider} · {item.model}</p><h3>{item.status.replaceAll("_", " ")}</h3><p>{item.reasons.join("; ") || "Meets the current policy."}</p></div></li>)}</ul></div>}
      </section>
    </main>
  );
}
