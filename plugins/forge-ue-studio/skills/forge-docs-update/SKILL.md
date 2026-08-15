---
name: forge-docs-update
description: Generate or update project documentation verified against the codebase. Use after significant implementation lands.
---

# Forge Docs Update

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `docs-update.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## CORE — GSD

1. Contain GSD's doc writers and verifier.

## POST — Forge

1. Keep the GDD ledger and asset-interface registry consistent with what the docs now claim.
