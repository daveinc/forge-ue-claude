<!-- forge:workflow
name: plan-phase
consumes: CONTEXT.md, .forge/state/packet-registry.json, doctrine/procedures.json
produces: PLAN.md carrying required_lanes and mutation_risk, registered asset interfaces
-->

# Forge Plan Phase — workflow

## PRE — Forge

1. Confirm CONTEXT.md exists. Never plan a phase that has not been discussed.
2. Load the canonical packet registry. Reference existing packet IDs; never mint replacements.
3. Resolve the phase's task class and read Forge's procedure for it:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
   ```

   Hand GSD's planner the procedure's `steps` and `non_goals` as the request. This is what Forge
   contributes to a phase GSD plans: GSD owns the phase number, the decomposition, the wave order and
   the SUMMARY; Forge owns what a phase of this kind consists of. A `null` procedure means no
   doctrine covers this shape — plan without it and record that the phase ran undoctrined.

   > **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *What crosses, and in which direction*

## CORE — GSD

1. Run GSD's planner over the procedure's steps as the request. Require every returned plan to carry `required_lanes`, `mutation_risk`, and any asset interface it produces or consumes.

## POST — Forge

1. Reject any plan that mutates Unreal content without declaring the project-exclusive lane.
2. Register new asset interfaces so the visual DAG can proceed against them.
3. Return any plan that declares no lane as incomplete.
4. Run `forge-plan-convergence` before execution on any non-trivial phase.
