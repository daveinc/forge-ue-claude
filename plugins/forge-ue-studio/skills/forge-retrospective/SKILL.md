---
name: forge-retrospective
description: Perform read-only Forge failure forensics and extract evidence-backed decisions, lessons, patterns, surprises, failures, and reusable recipes. Use after failed or interrupted workflows, repeated retries, scope drift, inconsistent state, missing artifacts, regressions, completed phases, or when deciding whether a workflow/provider recipe should be promoted.
---

# Forge Retrospective

Explain what happened before changing it, then preserve only defensible learning.

## Workflow

1. Freeze repair work and inspect revision history, work orders, attempts, leases, capability snapshots, review cycles, phase artifacts, acceptance evidence, tool outputs and current filesystem state read-only.
2. Detect stuck loops, missing artifacts, partial-plan drift, abandoned work, interruption, scope drift, undeclared writes, stale capability evidence, test regression and broken handoffs.
3. Ground every anomaly in specific evidence. Mark root causes as hypotheses when proof is incomplete; redact secrets.
4. Write a forensic report with evidence summary, confidence, likely cause, ruled-out causes, untested explanations and recommended actions. `forensic-investigator` owns the pass, and owns it alone: the agent that produced the work under investigation must not conduct it. Do not repair during the forensic pass.
5. After an accepted phase or resolved incident, extract atomic learning records using [promotion.md](references/promotion.md).
6. Keep new records quarantined. Promote a recipe only after repeated independent success under a declared scope; retain failed attempts and contradictory evidence.
7. Invalidate learning after relevant environment, engine, provider, schema, hardware or workflow changes.
8. Keep production metrics in canonical JSON. When a human requests a portfolio, gate, staffing, cost, quality, or schedule view, generate a derived XLSX or CSV scorecard and visually verify it; never make the spreadsheet the hidden source of truth.
