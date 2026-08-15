---
name: forge-ship
description: Prepare a game project build for delivery — cook, package, verify, and open a PR. Use when a milestone is verified and ready to go out.
---

# Forge Ship

Delegation mode: **relay** — this workflow is interactive, so surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `ship.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Confirm milestone verification passed. Shipping an unverified milestone is refused.

## CORE — GSD

1. Relay GSD's ship workflow for the review and PR mechanics.

## POST — Forge

1. Shipping a game means a cooked, packaged build that launches, not only a merged branch. Require build and package verification for the target platform before declaring the milestone shipped.
2. Record the built artifact's provenance and the engine version used.
