<!-- forge:workflow
name: handoff
consumes: .forge/state/leases.json, editor state, .forge/runtime.json
produces: handoff context including held write-locks and the producing host
-->

# Forge Handoff — workflow

## CORE — GSD

1. Run GSD's pause workflow.

## POST — Forge

1. Persist lane leases and editor state alongside context, including every held write-lock.
2. Record which runtime host produced the handoff.
3. Point the user at `forge-resume-work` for the return.
