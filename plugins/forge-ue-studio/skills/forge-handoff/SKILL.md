---
name: forge-handoff
description: Pause work before a context reset without losing state. Use when a session must end mid-phase.
---

# Forge Handoff

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `pause-work.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## CORE — GSD

1. Contain GSD's pause workflow.

## POST — Forge

1. Persist lane leases and editor state alongside context, including every held write-lock.
2. Record which runtime host produced the handoff.
3. Point the user at `forge-resume-work` for the return.
