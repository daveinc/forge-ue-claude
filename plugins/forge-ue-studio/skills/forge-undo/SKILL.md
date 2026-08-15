---
name: forge-undo
description: Roll back committed work. Use to revert a phase or plan when execution went wrong.
---

# Forge Undo

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `undo.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Check the binary-asset lock. Never revert Unreal content while another lane holds the project-exclusive lease.
2. Identify dependent packets from the canonical registry before reverting.

## CORE — GSD

1. Contain GSD's undo, which owns the phase manifest and dependency checks.

## POST — Forge

1. Confirm the working copy still opens in the editor before declaring the rollback complete.
