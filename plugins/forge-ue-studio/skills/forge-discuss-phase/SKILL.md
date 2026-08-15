---
name: forge-discuss-phase
description: Gather phase context through adaptive questioning before planning. Use when starting a phase, or when gameplay and art decisions must be settled before a plan exists.
---

# Forge Discuss Phase

Delegation mode: **relay** — surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `discuss-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Read `.forge/directives.md`, the GDD decision ledger, and the phase entry from the roadmap.
2. Name the departments this phase touches — gameplay, visual, audio, narrative, QA — and scope questions to them.
3. Read `.forge/capabilities/registry.json` and `.forge/capabilities/detected.json`, then run `python <forge-plugin-root>/scripts/forge.py mcp-status --project <project-root>`. Never raise an option that depends on an unqualified provider or an unbound route.

## CORE — GSD

1. Relay GSD's discussion. Reframe each question in game terms first: pillars affected, player-facing outcome, art/gameplay interface at stake, owning lane.
2. Ask one high-value question at a time. Never batch.
3. Pass answers back down verbatim. Never author or edit the relayed workflow's context artifact.

## POST — Forge

1. Record every decision that constrains an asset interface in the GDD ledger, not only in CONTEXT.md.
2. Surface unresolved decisions explicitly. Never defer an unresolved art/gameplay interface silently.
