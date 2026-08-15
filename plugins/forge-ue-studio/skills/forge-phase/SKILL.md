---
name: forge-phase
description: Add, insert, remove, or edit phases in the roadmap. Use when the plan of record changes shape.
---

# Forge Phase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. GSD workflow: `add-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Load the canonical packet registry before any mutation.

## CORE — GSD

1. Contain GSD's phase CRUD. It owns phase-ID arithmetic, including decimal insertion and milestone-scoped edits.

## POST — Forge

1. Verify no canonical packet ID was replaced. Require an explicit `alias` to `canonical` record for an alias, and `derived_from` provenance for a new packet.
2. Refuse any edit that replaces an established packet ID.
