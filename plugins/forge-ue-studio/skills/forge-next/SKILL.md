---
name: forge-next
description: Detect project state, present the valid next actions, and dispatch exactly one
---

<invocation>
- Invoked by naming `forge-next`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Route any session to its correct next action.

This is a launcher only. It never does the work itself. It reads Forge readiness plus GSD's authoritative smart-entry snapshot, presents the situation-appropriate actions, and hands off to exactly one skill.
</objective>

<flags>
- `--auto` — dispatch the recommended action without asking.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-next.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (detection order, single dispatch, stop boundary).
</process>
