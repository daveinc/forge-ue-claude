---
name: forge-phase
description: Add, insert, remove, or edit phases in a game project roadmap. Use when the plan of record changes shape.
---

# Forge Phase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `add-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Load the canonical packet registry before any mutation.

## CORE — GSD

1. Contain GSD's phase CRUD. It owns phase-ID arithmetic, including decimal insertion and milestone-scoped roadmap edits. Do not reimplement either.

## POST — Forge

1. Verify no canonical packet ID was replaced. A new alias requires an explicit `alias` to `canonical` record; a genuinely new packet requires `derived_from` provenance.
2. Replacing an established packet ID is the failure that caused the RunnerRoyale drift incident. Refuse it.
