# Forge Phase — workflow

## PRE — Forge

1. Load the canonical packet registry before any mutation.

## CORE — GSD

1. Contain GSD's phase CRUD. It owns phase-ID arithmetic, including decimal insertion and milestone-scoped edits.

## POST — Forge

1. Verify no canonical packet ID was replaced. Require an explicit `alias` to `canonical` record for an alias, and `derived_from` provenance for a new packet.
2. Refuse any edit that replaces an established packet ID.
