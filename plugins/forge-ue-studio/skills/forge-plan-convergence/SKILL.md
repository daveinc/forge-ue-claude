---
name: forge-plan-convergence
description: Challenge and revise a Forge phase plan through bounded, source-grounded, independent review cycles with severity counts, stall detection, and human escalation. Use before executing non-trivial plans, after architecture or dependency changes, when reviewers disagree, or when a plan cites existing Unreal/code/assets that must be verified.
---

# Forge Plan Convergence

Converge on an executable plan without allowing endless review loops.

## Workflow

1. Require a plan with scope, dependencies, work packets, write sets, lanes, acceptance, verification, fallbacks, human gates, and declared new artifacts.
2. Select independent reviewers from currently qualified lanes. Keep at least one reviewer isolated from planner reasoning.
3. Ground every cited existing symbol, asset, plugin, API, path, capability and acceptance command against source or a verified registry. Exclude artifacts the plan explicitly says it will create.
4. Record findings by severity and return only current-cycle `HIGH` and actionable non-high counts. Preserve prior cycles as audit history without counting resolved findings again.
5. Revise the plan so every actionable finding becomes a task, acceptance item, verified closure, explicit deferral, or reasoned rejection.
6. Repeat until both current counts reach zero, the maximum cycle count is reached, or counts stop decreasing.
7. On stall, malformed reviewer output, unverifiable source, or cycle exhaustion, stop and present remaining concerns to the human owner. Never silently proceed.

Read [cycle-contract.md](references/cycle-contract.md) before creating or updating review state.
