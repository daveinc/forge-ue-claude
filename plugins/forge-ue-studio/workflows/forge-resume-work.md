<!-- forge:workflow
name: resume-work
consumes: .forge/state/leases.json, .forge/runtime.json, the handoff record
produces: reclaimed or released lane leases
-->

# Forge Resume Work — workflow

## PRE — Forge

1. Run `forge-next` first. Take routing from persisted state, never from what the previous session said.
2. Route to `forge-runtime` and stop when the runtime block reports stale surfaces.
3. Read `.forge/state/leases.json` and reclaim or release every lane lease the interrupted session still holds. Release any `ACTIVE` lease past its `expires_at` as stale; anything inside its window needs an explicit decision before you touch it.

## CORE — GSD

1. Run GSD's resume workflow. It owns phase state and decides where work restarts.

## POST — Forge

1. Compare the host recorded in the handoff with `.forge/runtime.json`. On a difference, treat qualification evidence as stale and re-probe through `forge-capability-admin` before any offload route.
2. Confirm the recorded editor state — open project, held locks, in-flight builds — before resuming production work.
3. Hand control to the action `forge-next` recommends, then stop.
