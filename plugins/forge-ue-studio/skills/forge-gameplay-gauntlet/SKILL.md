---
name: forge-gameplay-gauntlet
description: Run a bounded adversarial improvement loop against a named reference or feel rubric
---

<invocation>
- Invoked by naming `forge-gameplay-gauntlet`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Improve the playable game rather than disconnected assets.

Delegation: native. Orchestrator role: freeze the rubric, fan out bounded alternatives, score them blind, and integrate only the winner.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-gameplay-gauntlet.md
@<forge-plugin-root>/skills/forge-gameplay-gauntlet/references/round-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (fixed capture conditions, critic independence, round bounds, human feel gate).
</process>
