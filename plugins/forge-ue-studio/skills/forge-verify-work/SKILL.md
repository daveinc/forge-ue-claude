---
name: forge-verify-work
description: Validate completed work through UAT plus in-engine evidence. Use when a phase claims completion and before a milestone closes.
---

# Forge Verify Work

Delegation mode: **relay** — surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `verify-work.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Load the acceptance suites registered for this phase. Grade against them, never against a generic definition of done.

## CORE — GSD

1. Relay GSD's UAT session. It owns the pass/fail predicate; never weaken, duplicate, or re-derive it.

## POST — Forge

1. Require in-engine evidence on top of a passing UAT: PIE session outcome, fixed-condition frame captures, or a recorded playthrough of the affected loop.
2. Never accept a green build and green tests as a verified game phase. Keep feel and presentation human gates.
3. Record residual risk explicitly.
