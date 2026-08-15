---
name: forge-milestone
description: Manage game project milestones — start, complete, audit, or summarise. Use at the boundaries between releases or vertical slices.
---

# Forge Milestone

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `complete-milestone.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Confirm every phase in the milestone has passed verification.

## CORE — GSD

1. Contain the matching GSD workflow for the requested mode: `--new`, `--complete`, `--audit`, or `--summary`.

## POST — Forge

1. Carry forward unresolved GDD decisions and unqualified capability routes into the next milestone rather than losing them at the boundary.
