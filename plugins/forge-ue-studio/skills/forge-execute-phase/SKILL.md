---
name: forge-execute-phase
description: Execute the plans in a game project phase under Unreal lane control. Use when plans are approved and work should begin, including wave-based parallel execution.
---

# Forge Execute Phase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `execute-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Resolve each plan's required capabilities against the typed tool routes: `python <forge-plugin-root>/scripts/forge.py mcp-status --project <project-root>`. The lane and isolation mode come from that resolution, not from a judgement call.
2. Acquire the lease for every resolved lane and record it in `.forge/state/leases.json`. A capability whose contract reports `UNAVAILABLE_OPTIONAL` takes its declared fallback route; it never silently drops.
3. Verify the clean base revision. Concurrent text/code writers get clean-base Git worktrees; binary assets get an LFS lock or the project-exclusive lease.
4. Route each plan through `forge-route-work` so bounded work reaches qualified providers. A plan needing a typed tool route goes to the agent that declares the matching capability — `unreal-operator` for the editor lane, `dcc-artist` for the authoring lane — never to a general-purpose executor.

## CORE — GSD

1. Contain GSD's executor for plans that need no typed tool route. It owns wave scheduling, plan dispatch, and SUMMARY authorship — do not reimplement any of them.

## POST — Forge

1. Release every lease, including on failure.
2. Record attempt results with observed facts separated from inference, naming the route actually taken for every capability that had a fallback available.
3. Verify phase completion by invoking GSD's own completion check rather than restating what it will accept.

## Note

The write-lock is held **across** GSD's steps, not around them: acquire in PRE, release in POST, and never let a delegated agent acquire it independently.
