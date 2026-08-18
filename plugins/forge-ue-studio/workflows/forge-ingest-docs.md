<!-- forge:workflow
name: ingest-docs
consumes: design sources named in signals.design_sources
produces: GDD decision ledger
-->

# Forge Ingest Docs — workflow

## PRE — Forge

1. Locate design sources. Forge Next reports them in `signals.design_sources`.

## CORE — GSD

1. Run GSD's document ingestion, including its conflict detection.

## POST — Forge

1. Fold accepted decisions into the GDD decision ledger.
2. Surface every LOCKED-vs-LOCKED conflict for a human ruling. Never auto-resolve a design conflict.
