---
name: forge-plan-convergence
description: Challenge and revise a phase plan through bounded, source-grounded review cycles
---

<invocation>
- Invoked by naming `forge-plan-convergence`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Converge on an executable plan without an endless review loop.

Delegation: native. Orchestrator role: ground every citation, count findings per cycle, revise, and escalate on a stall.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-plan-convergence.md
@<forge-plugin-root>/skills/forge-plan-convergence/references/cycle-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (reviewer independence, source grounding, cycle bounds, human escalation).
</process>
