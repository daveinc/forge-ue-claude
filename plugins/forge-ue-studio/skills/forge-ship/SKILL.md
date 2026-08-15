---
name: forge-ship
description: Cook, package, verify, and open a PR for a verified milestone. Use when a milestone is ready to go out.
---

# Forge Ship

Delegation mode: **relay** — surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `ship.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## PRE — Forge

1. Confirm milestone verification passed. Refuse to ship an unverified milestone.

## CORE — GSD

1. Relay GSD's ship workflow for the review and PR mechanics.

## POST — Forge

1. Require build and package verification for the target platform before declaring the milestone shipped.
2. Record the built artifact's provenance and the engine version used.
