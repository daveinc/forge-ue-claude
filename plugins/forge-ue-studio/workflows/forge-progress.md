<!-- forge:workflow
name: progress
consumes: .planning/ (authoritative for phase status), .forge/capabilities/qualifications.json
produces: nothing — reporting only, never mutates phase state
-->

# Forge Progress — workflow

## CORE — GSD

1. Run GSD's progress reporting. `.planning` is authoritative for phase status.

## POST — Forge

1. Add execution coverage: phases whose plans lack summaries.
2. Add capability staleness: routes qualified under a previous host.
3. Never mutate phase state from this verb.
