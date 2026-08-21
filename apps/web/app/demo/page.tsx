"use client";

import { useState } from "react";

const chapters = [
  {
    number: "01",
    label: "The trusted source",
    title: "Start with knowledge—not a prompt.",
    description: "A support lead deliberately writes and publishes a troubleshooting article. Only published articles may become AI sources.",
    takeaway: "This is RAG with a safety boundary: the model gets approved information, not an unrestricted company wiki.",
    workspaceStep: "In ResolveAI: Step 4 → create an article → Publish it.",
    color: "lime",
  },
  {
    number: "02",
    label: "The master agent",
    title: "One coordinator. Four specialist jobs.",
    description: "The master coordinator controls the sequence: triage, hybrid retrieval, grounded drafting, then grounding review.",
    takeaway: "Multi-agent design is not agents chatting randomly. It is clear ownership, narrow responsibilities, and safe handoffs.",
    workspaceStep: "In ResolveAI: Step 3 → Assess ticket → Generate grounded draft.",
    color: "blue",
  },
  {
    number: "03",
    label: "The retrieval engine",
    title: "Exact words + similar meaning.",
    description: "Keyword search finds identifiers such as SSO. Embedding search finds a customer who says their company cannot log in. Hybrid search fuses both rankings.",
    takeaway: "Hybrid search is often stronger than vector-only RAG because real support questions contain precise terms and paraphrases.",
    workspaceStep: "In ResolveAI: Steps 5–7 → try “SSO” and “company cannot log in”.",
    color: "orange",
  },
  {
    number: "04",
    label: "Evidence, not vibes",
    title: "Evaluate models separately from customers.",
    description: "Synthetic cases run in a durable background job. Compare model grounding, your human score, and latency before you choose a model.",
    takeaway: "The selection policy recommends models from evidence. It never silently changes customer-facing traffic.",
    workspaceStep: "In ResolveAI: Steps 9–11 → add a synthetic case → run both writers → score it.",
    color: "violet",
  },
];

export default function DemoPage() {
  const [activeChapter, setActiveChapter] = useState(0);
  const chapter = chapters[activeChapter];

  return (
    <main className="demo-shell">
      <nav className="demo-nav"><a href="/">← ResolveAI workspace</a><span>INTERACTIVE SYSTEM TOUR / 04 CHAPTERS</span></nav>
      <section className="demo-hero">
        <p className="eyebrow">RESOLVEAI / DEMO MODE</p>
        <h1>See the system<br /><span>before</span> you touch it.</h1>
        <p>This is a visual walkthrough of the AI-engineering decisions inside ResolveAI. Click each chapter, then use the exact hands-on instruction in the live workspace.</p>
      </section>

      <section className="demo-stage" aria-live="polite">
        <div className={`demo-stage-number ${chapter.color}`}>{chapter.number}</div>
        <div className="demo-stage-copy">
          <p className="eyebrow">{chapter.label}</p>
          <h2>{chapter.title}</h2>
          <p className="demo-description">{chapter.description}</p>
          <div className="demo-takeaway"><span>WHY IT MATTERS</span><p>{chapter.takeaway}</p></div>
          <div className="demo-action"><span>HANDS-ON NEXT</span><p>{chapter.workspaceStep}</p><a href="/">Open the live workspace →</a></div>
        </div>
        <div className="demo-diagram" aria-label="ResolveAI architecture">
          <div className="diagram-node source">PUBLISHED<br />SOURCE</div><i>→</i><div className="diagram-node master">MASTER<br />AGENT</div><i>→</i><div className="diagram-node review">HUMAN<br />REVIEW</div>
          <p>Approved knowledge enters the guarded workflow. A human always owns the final decision.</p>
        </div>
      </section>

      <section className="demo-chapters" aria-label="Demo chapters">
        {chapters.map((item, index) => <button className={index === activeChapter ? "active" : ""} key={item.number} type="button" onClick={() => setActiveChapter(index)}><span>{item.number}</span><strong>{item.label}</strong><small>{index === activeChapter ? "Viewing now" : "Open chapter"}</small></button>)}
      </section>

      <section className="demo-finish">
        <p className="eyebrow">YOU ARE READY</p><h2>Now run the workflow for real.</h2><p>The demo teaches the decisions. The workspace proves them with your local Docker services, real source articles, and actual model calls.</p><a href="/">Launch ResolveAI workspace <span aria-hidden="true">↗</span></a>
      </section>
    </main>
  );
}
