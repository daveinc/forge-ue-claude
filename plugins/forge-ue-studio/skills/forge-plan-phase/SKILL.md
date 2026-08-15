---
name: forge-plan-phase
description: Create an executable plan for a game project phase, declaring asset interfaces, required lanes, and mutation risk. Use after phase discussion is complete and before any execution.
---

# Forge Plan Phase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `plan-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Confirm CONTEXT.md exists for the phase. Planning without settled discussion produces plans that churn.
2. Load the canonical packet registry. Plans reference existing packet IDs; they never mint replacements.

## CORE — GSD

1. Contain GSD's planner. Require the returned plans to carry, per plan: `required_lanes`, `mutation_risk`, and any asset interface the plan produces or consumes.

## POST — Forge

1. Reject any plan that mutates Unreal content without declaring the project-exclusive lane.
2. Register new asset interfaces so the visual DAG can proceed in parallel against them.
3. Run `forge-plan-convergence` before execution on any non-trivial phase.

## Note

A plan that does not declare its lane cannot be routed safely and cannot be parallelised. Treat a missing declaration as an incomplete plan.
