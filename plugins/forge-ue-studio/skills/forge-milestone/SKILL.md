---
name: forge-milestone
description: Start, complete, audit, or summarise a milestone. Use at the boundaries between releases or vertical slices.
---

# Forge Milestone

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `complete-milestone.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Confirm every phase in the milestone passed verification.

## CORE — GSD

1. Contain the matching GSD workflow for the requested mode: `--new`, `--complete`, `--audit`, or `--summary`.

## POST — Forge

1. Carry unresolved GDD decisions and unqualified capability routes forward into the next milestone.
