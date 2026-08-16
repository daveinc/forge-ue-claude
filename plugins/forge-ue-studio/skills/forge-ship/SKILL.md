---
name: forge-ship
description: Cook, package, verify, and open a PR for a verified milestone
---

<invocation>
- Invoked by naming `forge-ship`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Deliver a build, not only a merged branch.

Delegation: relay. Orchestrator role: confirm verification, relay GSD's ship workflow, then require build and package evidence.
</objective>

<flags>
- `--pr` — open the PR branch without re-running the cook and package gates.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-ship.md
@<gsd-core>/workflows/ship.md
@<gsd-core>/workflows/pr-branch.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (verification precondition, packaged-build evidence, artifact provenance).
</process>
