<!-- forge:workflow
name: onboard
consumes: existing project tree, Content/, Blueprint dependencies, enabled plugins
produces: codebase map, registered asset interfaces
-->

# Forge Onboard — workflow

## PRE — Forge

1. Run `forge-doctor` so capability routes are known before mapping begins.

## CORE — GSD

1. Run GSD's onboarding.

## POST — Forge

1. Extend the map beyond source: `Content/` asset classes, Blueprint dependencies, enabled plugins, and C++ module boundaries.
2. Register the asset interfaces the existing project already implies.
