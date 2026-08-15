---
name: forge-execute-phase
description: Execute the plans in a game project phase under Unreal lane control. Use when plans are approved and work should begin, including wave-based parallel execution.
---

# Forge Execute Phase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `execute-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Acquire the Unreal project write-lock if any plan declares `ue-project-exclusive`. Native MCP, live Python, editor-closed commandlets, and human editor work are mutually exclusive under it.
2. Acquire lane leases for every other declared lane and record them in `.forge/state/leases.json`.
3. Verify the clean base revision. Concurrent text/code writers get clean-base Git worktrees; binary assets get an LFS lock or the project-exclusive lease.
4. Route each plan through `forge-route-work` so bounded work reaches qualified providers.

## CORE — GSD

1. Contain GSD's executor. It owns wave scheduling, plan dispatch, and SUMMARY authorship.

## POST — Forge

1. Release every lease, including on failure. A leaked lease blocks the next session.
2. Record attempt results with observed facts separated from inference.
3. Report any plan left without a SUMMARY. GSD does not block completion on that.

## Note

The write-lock is held **across** GSD's steps, not around them: acquire in PRE, release in POST, and never let a delegated agent acquire it independently.
