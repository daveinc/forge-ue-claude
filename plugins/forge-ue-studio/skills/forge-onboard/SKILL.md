---
name: forge-onboard
description: Onboard an existing Unreal project into Forge and GSD planning. Use when adopting a codebase that has no planning state.
---

# Forge Onboard

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `onboard.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Run `forge-doctor` first so capability routes are known before mapping begins.

## CORE — GSD

1. Contain GSD's onboarding.

## POST — Forge

1. Extend the map beyond source: `Content/` asset classes, Blueprint dependencies, enabled plugins, and C++ module boundaries.
2. Register the asset interfaces the existing project already implies.
