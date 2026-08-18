<!-- forge:workflow
name: plan-phase
consumes: CONTEXT.md, .forge/state/packet-registry.json
produces: PLAN.md carrying required_lanes and mutation_risk, registered asset interfaces
-->

# Forge Plan Phase — workflow

## PRE — Forge

1. Confirm CONTEXT.md exists. Never plan a phase that has not been discussed.
2. Load the canonical packet registry. Reference existing packet IDs; never mint replacements.

## CORE — GSD

1. Run GSD's planner. Require every returned plan to carry `required_lanes`, `mutation_risk`, and any asset interface it produces or consumes.

## POST — Forge

1. Reject any plan that mutates Unreal content without declaring the project-exclusive lane.
2. Register new asset interfaces so the visual DAG can proceed against them.
3. Return any plan that declares no lane as incomplete.
4. Run `forge-plan-convergence` before execution on any non-trivial phase.
