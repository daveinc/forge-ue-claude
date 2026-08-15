---
name: forge-undo
description: Safely roll back committed game project work. Use to revert a phase or plan when execution went wrong.
---

# Forge Undo

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `undo.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Check the binary-asset lock. Reverting Unreal content while another lane holds the project-exclusive lease corrupts the working copy.
2. Identify dependent packets from the canonical registry before reverting.

## CORE — GSD

1. Contain GSD's undo, which owns the phase manifest and dependency checks.

## POST — Forge

1. Confirm the working copy still opens in the editor before declaring the rollback complete.
