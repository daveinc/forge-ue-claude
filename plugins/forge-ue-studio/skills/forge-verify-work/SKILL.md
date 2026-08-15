---
name: forge-verify-work
description: Validate completed game project work through UAT plus in-engine evidence. Use when a phase claims completion and before a milestone closes.
---

# Forge Verify Work

Delegation mode: **relay** — this workflow is interactive, so surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `verify-work.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Load the acceptance suites registered for this phase. Verification is graded against them, not against a generic definition of done.

## CORE — GSD

1. Relay GSD's UAT session. GSD's predicate is the authority for test pass/fail: it requires positive passing evidence and refuses a vacuous pass. Do not weaken or duplicate it.

## POST — Forge

1. Require in-engine evidence in addition to a passing UAT: PIE session outcome, fixed-condition frame captures, or a recorded playthrough of the affected loop.
2. A build that compiles and tests green is not a verified game phase. Feel and presentation are human gates and remain so.
3. Record residual risk explicitly.

## Note

This is the clearest case where GSD's behaviour is insufficient rather than wrong. Its gate stays authoritative; Forge adds a requirement on top.
