# Forge Ship — workflow

## PRE — Forge

1. Confirm milestone verification passed. Refuse to ship an unverified milestone.

## CORE — GSD

1. Relay GSD's ship workflow for the review and PR mechanics.
2. On `--pr`, run `pr-branch.md` alone. The cook and package gates below still apply before the milestone is called shipped.

## POST — Forge

1. Require build and package verification for the target platform before declaring the milestone shipped.
2. Record the built artifact's provenance and the engine version used.
