---
name: forge-visual-production
description: Produce concept boards, direction, meshes, rigs, animation, and Unreal art integration
---

<invocation>
- Invoked by naming `forge-visual-production`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Run art as a parallel studio department with replacement-safe placeholders.

Delegation: native. Orchestrator role: separate the visual capabilities, route each to a qualified lane, and hold the human approval gate.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-visual-production.md
@<forge-plugin-root>/skills/forge-visual-production/references/visual-routing.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (human approval of primary direction, asset-interface contracts, route qualification, evidence capture).
</process>
