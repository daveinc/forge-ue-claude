---
name: forge-discuss-phase
description: Gather phase context for a game project through adaptive questioning before planning. Use when starting a new phase, when requirements are unclear, or when gameplay and art decisions must be settled before a plan exists.
---

# Forge Discuss Phase

Delegation mode: **relay** — this workflow is interactive, so surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `discuss-phase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Read `.forge/directives.md` and the GDD decision ledger. Load the phase entry from the roadmap.
2. Identify which departments this phase touches (gameplay, visual, audio, narrative, QA) so questions can be scoped.
3. Read `.forge/capabilities/registry.json` and run `python <forge-plugin-root>/scripts/forge.py mcp-status --project <project-root>`. Do not raise options that depend on an unqualified provider or an unbound typed tool route.

## CORE — GSD

1. Relay GSD's discussion. Reframe each question in game terms before presenting it: pillars affected, player-facing outcome, art/gameplay interface at stake, which lane owns the work.
2. Ask one high-value question at a time. Never batch.
3. Pass answers back down verbatim. The relayed workflow owns the context artifact it writes; do not author or edit it from here.

## POST — Forge

1. Record any decision that constrains an asset interface in the GDD ledger, not only in CONTEXT.md.
2. List unresolved decisions explicitly. An unresolved art/gameplay interface blocks parallel DAGs and must be surfaced, not deferred silently.

## Note

Discussion is where Forge diverges most from generic planning. A web feature has no art/gameplay interface to negotiate; a game phase almost always does.
