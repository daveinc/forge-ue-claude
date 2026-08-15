---
name: forge-ingest-docs
description: Ingest existing game design documents into planning state. Use when a project has design docs but no GSD project memory.
---

# Forge Ingest Docs

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `ingest-docs.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Locate design sources. Forge Next reports them in `signals.design_sources`.

## CORE — GSD

1. Contain GSD's document ingestion, including its conflict detection.

## POST — Forge

1. Fold accepted decisions into the GDD decision ledger.
2. Surface every LOCKED-vs-LOCKED conflict for a human ruling. Never auto-resolve a design conflict.
