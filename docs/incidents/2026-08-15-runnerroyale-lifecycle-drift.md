# RunnerRoyale lifecycle drift — 2026-08-15

Status: root cause accepted; smart-entry repair implemented
Severity: high  
Affected surface: Forge bootstrap, Forge Init, phase handoff, worker dispatch, packet identity

## Incident

During the first RunnerRoyale Forge run, the design DAG established playable packet IDs `P0` through `P8`. A later foundation plan introduced a different `W0` through `W11` namespace and the conversation described `W1 — UE Project Shell` as the next Forge step. `W1` was a project work packet, not a top-level Forge workflow step.

The run also continued from inception into planning and execution-oriented work without GSD's durable discuss → plan → execute → verify boundaries or fresh-context handoffs.

## Verified facts

- `D:\Unreal Projects\RunnerRoyale\Docs\Design\Production-DAGs.md` was created at `2026-08-15T04:20:27Z` and defines `P0` as the UE project shell.
- `D:\Unreal Projects\RunnerRoyale\Docs\Design\Foundation-Plan.md` was created at `2026-08-15T04:31:15Z` and defines `W1` as the UE project shell.
- RunnerRoyale contains only `Docs\`; it has no `.forge`, `.planning`, `.codex`, `.git`, or `.uproject` at the inspected root.
- Forge's installer rejected pre-project folders because `install_overlay()` required exactly one `.uproject`. The project therefore could not receive Forge state or project-local agents before Forge Init created the project shell.
- Forge Init step 9 instructed the host to run plan convergence and then dispatch the first packet in the same workflow. It did not require a durable handoff or a fresh task.
- Forge had no persisted phase-boundary state and no immutable canonical packet-ID registry.
- Forge's installation-agent document described agent waves, but the deterministic installer did not compile or dispatch those jobs.

## User-reported facts

- The local runtime presented “W1 — Project Shell” as the next Forge step.
- The runtime later identified the P0 → W1 replacement and the workflow-step/work-packet conflation as its own error.

The conversation transcript was not available as a versioned artifact, so the wording above is retained as user-supplied evidence rather than independently reconstructed history.

## GSD control comparison

| Control | GSD implementation | Forge implementation at incident | Result |
|---|---|---|---|
| Durable project memory | `.planning/PROJECT.md`, `ROADMAP.md`, `STATE.md`, phase artifacts | no pre-project overlay and no `.planning` bridge | missing |
| Discussion recovery | checkpoint after each area; canonical `CONTEXT.md` | chat-only Forge interview state | missing |
| Planning boundary | commits `PLAN.md`, `STATE.md`, and `ROADMAP.md`; presents next command | step 9 immediately chained convergence into routing | violated |
| Execution isolation | fresh executor agents read paths; orchestrator stops while they run | route guidance existed, but install/init did not require a dispatch result | unenforced |
| Phase transition | manual mode says “STOP. Do not auto-advance” | no equivalent fail-closed boundary | missing |
| Context reset | UAT and handoff files explicitly survive `/clear` | “resume from state” directive without a lifecycle state file | incomplete |
| Identity continuity | GSD phase/plan IDs are file-backed and reused | no canonical packet registry or alias rule | missing |

## Root cause

This was not primarily a naming mistake. Forge documented GSD compatibility but lacked a Forge smart-entry command that could combine project adoption state with GSD's authoritative phase state.

Three defects combined:

1. **Bootstrap deadlock:** the overlay required a `.uproject`, while Forge Init was responsible for reaching the project-shell packet.
2. **Missing smart entry:** Forge Init did not inspect GSD smart-entry or route existing documents/code before beginning inception, and there was no stable Forge resume command for fresh tasks.
3. **Missing identity invariant:** later plans could replace canonical packet IDs without an explicit alias/derivation record.

The absence of project-local agents explains why the expected studio delegation surface was also unavailable. The installation-agent wave table was descriptive, not executable orchestration.

## Ruled out

- GSD itself does not lack context preservation. Its installed Codex workflows persist discussion checkpoints, project state, plans, summaries, UAT state, and structured pause/resume handoffs.
- Breaking implementation into smaller packets was not the error. Replacing an established canonical ID and presenting a packet as a Forge step was the error.
- Large model context windows do not remove the need for phase state. GSD only relaxes `/clear` recommendations; it retains file-backed boundaries and fresh executor contexts.

## Repair contract

The repair must satisfy all of the following:

1. Install the Forge overlay into an existing pre-project directory before a `.uproject` exists.
2. Make GSD's `.planning` lifecycle the only phase engine; Forge skills enrich phase artifacts but do not replace discuss, plan, execute, or verify.
3. Add `$forge-next` as the machine-readable, read-only entry/resume router. It must combine Forge readiness with GSD smart-entry, dispatch exactly one command, and stop; GSD `.planning` remains the sole phase authority.
4. Never auto-chain Forge Init into packet execution in manual mode.
5. Keep Forge workflow step IDs and project packet IDs in separate namespaces.
6. Register canonical packet IDs once; aliases and derived packets must preserve provenance and cannot silently replace them.
7. Compile installation investigation into explicit bounded jobs and dispatch available typed agents when authorized; record any inline fallback as degraded execution.
8. Add regression coverage for pre-project installation, smart-entry adoption/bootstrap/document/GSD routing, deprecated lifecycle mutation, canonical-ID conflicts, and route requests for unregistered packets.

## Implemented correction

- `$forge-next` now detects missing adoption, incomplete bootstrap, existing design documents, existing Unreal/code, greenfield readiness, and active GSD state.
- `$forge-init` runs the detector first and dispatches its recommended action unless the project is truly greenfield-ready.
- GSD `smart-entry --json` supplies phase, recovery, and completion actions. Forge normalizes command spelling but does not replace the decision.
- `.forge/state/lifecycle.json` remains on disk for compatibility but is explicitly non-authoritative; mutation through the legacy lifecycle command is rejected.

## Untested before repair

- Fresh-task Forge/GSD coexistence after the new boundary is installed.
- Whether all Codex hosts expose typed project-local agents immediately or require a restart.
- Full Unreal project-shell creation from the pre-project state.
