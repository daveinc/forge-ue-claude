---
name: forge-debug
description: Debug a defect with persistent state across context resets
---

<invocation>
- Invoked by naming `forge-debug`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Diagnose a crash, PIE failure, broken mechanic, or asset problem.

Delegation: relay. Orchestrator role: collect Unreal evidence first, relay GSD's debugging cycle, then require editor-closed reproduction.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-debug.md
@<gsd-core>/workflows/debug.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (evidence collection, reproduction lane, learning promotion thresholds).
</process>
