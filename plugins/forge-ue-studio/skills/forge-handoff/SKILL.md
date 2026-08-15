---
name: forge-handoff
description: Pause or resume game project work across sessions without losing state. Use before a context reset and when returning to an interrupted project.
---

# Forge Handoff

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `pause-work.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. On `--resume`, run Forge Next first so routing comes from files rather than chat.

## CORE — GSD

1. Contain GSD's pause or resume workflow depending on mode.

## POST — Forge

1. Persist lane leases and editor state alongside context. A handoff that forgets a held write-lock strands the next session.
2. Record which runtime host produced the handoff. Qualification evidence does not transfer across hosts.
