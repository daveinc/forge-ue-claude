---
name: forge-progress
description: Report phase state, execution coverage, and the next action. Use to see what is complete and what comes next.
---

# Forge Progress

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `progress.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## CORE — GSD

1. Contain GSD's progress reporting. `.planning` is authoritative for phase status.

## POST — Forge

1. Add execution coverage: phases whose plans lack summaries.
2. Add capability staleness: routes qualified under a previous host.
3. Never mutate phase state from this verb.
