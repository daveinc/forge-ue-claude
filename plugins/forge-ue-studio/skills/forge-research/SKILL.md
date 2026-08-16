---
name: forge-research
description: Absorb a tool, API, model, or corpus into capability contracts, probes, and acceptance links
---

<invocation>
- Invoked by naming `forge-research`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Turn a source or tool into tested capability rather than prose knowledge.

Delegation: native. Orchestrator role: discover, get approval, classify in bounded packets, then contract and probe.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-research.md
@<forge-plugin-root>/skills/forge-research/references/absorption-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (approval before import, conflict staging, probe evidence, invalidation triggers).
</process>
