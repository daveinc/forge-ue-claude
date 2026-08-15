# GSD lifecycle bridge

GSD owns project and phase state. Forge reads GSD's state through `$forge-next`; it does not mirror or advance the phase machine.

| Situation | Authoritative durable state | Resume entry |
|---|---|---|
| Forge not adopted | project files and Forge detector | `$forge-next` routes to `$forge-bootstrap` |
| Forge bootstrap incomplete | `.forge/state/bootstrap-report.json` and capability evidence | `$forge-next` routes to `$forge-bootstrap --resume` |
| Existing docs without GSD state | source planning/design docs | `$forge-next` routes to `$gsd-ingest-docs` |
| Existing Unreal/code without GSD state | `.uproject`, `Source/`, repository evidence | `$forge-next` routes to `$gsd-onboard` |
| GSD project active or interrupted | `.planning/STATE.md`, roadmap, phase artifacts, GSD smart-entry snapshot | `$forge-next` dispatches the exact GSD action |
| Greenfield bootstrap complete | Forge readiness with no existing project corpus | `$forge-next` routes to `$forge-init` |

The legacy `install.ps1 -Mode Lifecycle` surface is status-only compatibility. Never use it to advance a Forge or GSD phase.

## Stop contract

GSD commands own their stop points and incremental checkpoints. At every explicit fresh-task boundary, persist the active command's artifacts, stop, and use `$forge-next` in the new task. `$gsd-pause-work` remains the mid-stage emergency handoff; Forge Next then detects the paused state through GSD smart-entry.

## Execution delegation

GSD execution owns phase-level agent orchestration. It passes file paths to fresh executors and the orchestrator stops while they work. Forge Route Work may select the occupant and compile a registered minimal work packet inside that execution contract; it does not permit the inception task to execute the packet.

If typed agents are unavailable or delegation was not authorized, follow the GSD runtime fallback and record `DEGRADED_INLINE`. Never claim equivalent multi-agent isolation.

## Identifier invariant

- Forge bootstrap/inception control: `FI-*`.
- GSD phase and plan: the IDs generated in `.planning/ROADMAP.md` and phase filenames.
- Project production packet: immutable IDs registered in `.forge/state/packet-registry.json`.

Packet refinement preserves the canonical ID or creates a derived child with provenance. It never renames an upstream packet because a later document prefers another prefix.
