---
name: forge-retrospective
description: Run read-only failure forensics and extract evidence-backed learning
---

<invocation>
- Invoked by naming `forge-retrospective`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Explain what happened before changing it, then preserve only defensible learning.

Delegation: native for forensics, run for extraction. Orchestrator role: freeze repair, ground every anomaly in evidence, then quarantine new records.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-retrospective.md
@<gsd-core>/workflows/extract-learnings.md
@<forge-plugin-root>/references/delegation-contract.md
@<forge-plugin-root>/skills/forge-retrospective/references/promotion.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (read-only forensics, investigator independence, promotion thresholds, invalidation triggers).
</process>
