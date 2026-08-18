<!-- forge:workflow
name: map-codebase
consumes: source tree, Content/, .uproject plugins
produces: codebase map extended with Unreal structure
-->

# Forge Map Codebase — workflow

## CORE — GSD

1. Run GSD's codebase mappers.

## POST — Forge

1. Add Unreal-specific structure: module boundaries, the Blueprint and C++ split, `Content/` organisation, and which assets are binary-locked.
