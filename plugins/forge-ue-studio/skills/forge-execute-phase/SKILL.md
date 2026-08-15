---
name: forge-execute-phase
description: Execute the plans in a phase under Unreal lane control. Use when plans are approved and work should begin, including wave-based parallel execution.
---

# Forge Execute Phase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `execute-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Resolve each plan's required capabilities: `python <forge-plugin-root>/scripts/forge.py mcp-status --project <project-root>`. Take the lane and isolation mode from that resolution, never from a judgement call.
2. Acquire the lease for every resolved lane and record it in `.forge/state/leases.json`. Send a capability reporting `UNAVAILABLE_OPTIONAL` down its declared fallback; never drop it silently.
3. Verify the clean base revision. Give concurrent text and code writers clean-base Git worktrees, and binary assets an LFS lock or the project-exclusive lease.
4. Route each plan through `forge-route-work`. Send a plan needing a typed tool route to the agent declaring that capability — `unreal-operator` for the editor lane, `dcc-artist` for the authoring lane — never to a general-purpose executor.

## CORE — GSD

1. Contain GSD's executor for plans needing no typed tool route. It owns wave scheduling, plan dispatch, and SUMMARY authorship.

## POST — Forge

1. Release every lease, including on failure.
2. Record attempt results with observed facts separated from inference, naming the route actually taken for every capability that had a fallback.
3. Verify phase completion by invoking GSD's own completion check.
4. Hold the write-lock across GSD's steps: acquire in PRE, release in POST, and never let a delegated agent acquire it independently.
