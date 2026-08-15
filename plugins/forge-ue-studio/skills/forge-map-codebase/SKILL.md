---
name: forge-map-codebase
description: Analyse an Unreal codebase and produce structured planning intel. Use before planning work in unfamiliar or inherited code.
---

# Forge Map Codebase

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `map-codebase.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

_Nothing beyond the shared contract._

## CORE — GSD

1. Contain GSD's codebase mappers.

## POST — Forge

1. Add Unreal-specific structure: module boundaries, Blueprint and C++ split, `Content/` organisation, and which assets are binary-locked.
