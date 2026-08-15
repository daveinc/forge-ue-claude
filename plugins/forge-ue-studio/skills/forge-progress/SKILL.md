---
name: forge-progress
description: Check game project progress and advance the workflow. Use to see current phase state, what is complete, and the authoritative next action.
---

# Forge Progress

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `progress.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

_Nothing beyond the shared contract._

## CORE — GSD

1. Contain GSD's progress reporting. `.planning` is authoritative for phase status.

## POST — Forge

1. Add execution coverage: phases whose plans lack summaries.
2. Add capability staleness: routes qualified under a previous runtime host are no longer eligible.

## Note

Advisory only. This verb never mutates phase state.
