---
name: forge-plan-phase
description: Create an executable phase plan declaring asset interfaces, required lanes, and mutation risk. Use after discussion is complete and before execution.
---

# Forge Plan Phase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `plan-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Confirm CONTEXT.md exists. Never plan a phase that has not been discussed.
2. Load the canonical packet registry. Reference existing packet IDs; never mint replacements.

## CORE — GSD

1. Contain GSD's planner. Require every returned plan to carry `required_lanes`, `mutation_risk`, and any asset interface it produces or consumes.

## POST — Forge

1. Reject any plan that mutates Unreal content without declaring the project-exclusive lane.
2. Register new asset interfaces so the visual DAG can proceed against them.
3. Return any plan that declares no lane as incomplete.
4. Run `forge-plan-convergence` before execution on any non-trivial phase.
