---
name: forge-debug
description: Systematically debug a game project defect with persistent state across context resets. Use for crashes, PIE failures, broken gameplay, or asset problems.
---

# Forge Debug

Delegation mode: **relay** — this workflow is interactive, so surface each question in game-dev framing and pass answers back down. Never black-box it. GSD workflow: `debug.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Collect Unreal-specific evidence first: crash logs, `Saved/Logs`, PIE output, and the exact reproduction lane (editor open, editor closed, packaged build).

## CORE — GSD

1. Relay GSD's debugging cycle. It owns hypothesis tracking and session state.

## POST — Forge

1. Reproduce editor-closed where possible before accepting a fix. Editor-open behaviour is not proof for a packaged build.
2. Promote a confirmed root cause to `.forge/learnings/` only after repeated evidence-backed success.
