---
name: forge-handoff
description: Pause game project work before a context reset without losing state. Use when a session must end mid-phase. Resuming afterwards is forge-resume-work.
---

# Forge Handoff

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `pause-work.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Returning to the work is `forge-resume-work`.

## CORE — GSD

1. Contain GSD's pause workflow.

## POST — Forge

1. Persist lane leases and editor state alongside context, including every held write-lock.
2. Record which runtime host produced the handoff. Qualification evidence does not transfer across hosts.
