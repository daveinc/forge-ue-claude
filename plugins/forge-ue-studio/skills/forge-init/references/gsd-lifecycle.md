# GSD lifecycle bridge

Forge uses GSD's phase files and stop points directly. In manual mode, each row is a separate fresh Codex task.

| Task | Entry command | Forge lifecycle start | Required durable result | Forge lifecycle complete | Stop handoff |
|---:|---|---|---|---|---|
| 1 | `$forge-init` | `init-start` | `.planning/PROJECT.md`, `ROADMAP.md`, `STATE.md`; Forge GDD/DAG/registries | `init-complete` | `$gsd-discuss-phase 1` |
| 2 | `$gsd-discuss-phase N` | `discuss-start -Phase N` | phase `CONTEXT.md` plus GSD checkpoint/state update | `discuss-complete -Phase N` | `$gsd-plan-phase N` |
| 3 | `$gsd-plan-phase N` | `plan-start -Phase N` | verified phase `PLAN.md`, `STATE.md`, `ROADMAP.md` | `plan-complete -Phase N` | `$gsd-execute-phase N` |
| 4 | `$gsd-execute-phase N` | `execute-start -Phase N` | per-plan `SUMMARY.md`, commits and evidence from fresh executors | `execute-complete -Phase N` | `$gsd-verify-work N` |
| 5 | `$gsd-verify-work N` | `verify-start -Phase N` | completed phase `UAT.md` | `verify-complete -Phase N` | `$gsd-progress` and user decision |

The lifecycle command is:

```powershell
.\install.ps1 -Mode Lifecycle -ProjectPath <project> -LifecycleEvent <event> -Phase <N> -Apply
```

`-Phase` is omitted for bootstrap/init events. Preview without `-Apply` before each mutation when operating manually.

## Stop contract

When a complete event succeeds, `.forge/state/lifecycle.json` sets `requires_fresh_task: true` and records one exact `next_command`. The current task must return that command and stop. It must not call the next skill, dispatch its workers, or make more project changes.

GSD may maintain its own incremental checkpoints inside a task. Forge's boundary does not replace them. `$gsd-pause-work` remains the mid-stage emergency handoff and `$gsd-resume-work` remains the general session recovery command.

## Execution delegation

GSD execution owns phase-level agent orchestration. It passes file paths to fresh executors and the orchestrator stops while they work. Forge Route Work may select the occupant and compile a registered minimal work packet inside that execution contract; it does not permit the inception task to execute the packet.

If typed agents are unavailable or delegation was not authorized, follow the GSD runtime fallback and record `DEGRADED_INLINE`. Never claim equivalent multi-agent isolation.

## Identifier invariant

- Forge bootstrap/inception control: `FI-*`.
- GSD phase and plan: the IDs generated in `.planning/ROADMAP.md` and phase filenames.
- Project production packet: immutable IDs registered in `.forge/state/packet-registry.json`.

Packet refinement preserves the canonical ID or creates a derived child with provenance. It never renames an upstream packet because a later document prefers another prefix.
