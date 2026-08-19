# Build doctrine

Two different things are called planning, and Forge owns one of them.

## The split

The rule this repository states — *GSD owns `.planning`* — is true and incomplete. It is a claim about an artifact store and its file lifecycle. Read as *Forge does no planning*, it leaves Forge nowhere to keep the knowledge of how a game gets built, and a workflow with nothing of its own to contribute can only wrap a GSD call. That is measurable: `forge-onboard`'s entire CORE section is one line reading *Run GSD's onboarding*, `forge-resume-work`'s is *Run GSD's resume workflow*, and of 31 workflows only `forge-route-work` takes a lane lease or dispatches a packet.

| | Planning artifacts | Build doctrine |
|---|---|---|
| **What** | `.planning/`, ROADMAP.md, PLAN.md, SUMMARY.md, phase IDs, status transitions, the schedule | What a game of this kind needs built, in what order, with which capabilities and tools, and what evidence closes a step |
| **Owner** | GSD | Forge |
| **Written by** | GSD only, always through `gsd_run` | Forge, as versioned data in the plugin |
| **Kind of knowledge** | A state machine and a file lifecycle | An Unreal domain procedure |
| **When it is wrong** | Phases run out of order, or work is lost | A step ships without the evidence that would have caught it |

GSD decides *when* a phase runs and records what happened. Forge decides *what a phase of this kind consists of*. Neither answer is available from the other tool: GSD has no reason to know that retargeting is skeleton-compatibility, then IK Rigs, then an IK Retargeter, and Forge has no business renumbering a roadmap.

## What crosses, and in which direction

| Direction | What crosses | How |
|---|---|---|
| Forge → GSD | Procedure content: ordered steps, non-goals, acceptance and verification lines | As the request a delegating verb's PRE hands to the stock workflow. It becomes GSD's plan, written by GSD. |
| GSD → Forge | Phase and plan state, read-only | `smart-entry --json`, through `forge-next`. Forge never writes back. |
| Forge → Forge | Lanes, leases, capabilities, packet IDs, the acceptance registry, evidence | Never leaves Forge. GSD has no reason to see any of it and does not. |

Forge never writes `.planning`. GSD never reads `.forge`. The one code-level dependency stays a single subprocess call to `smart-entry`.

## The boundary, concretely

GSD plans a phase called *retarget the character animations*.

**GSD owns** that this is phase 4, that it decomposes into three plans, the wave each runs in, the SUMMARY that records it, the status transitions, and the commit trail. Forge writes none of it.

**Forge supplies**, before GSD plans, the procedure for this task class:

- Ordered steps — confirm the source and target skeletons are compatible; author or verify an IK Rig for each; author the IK Retargeter and its chain mapping; batch-retarget the sequences; re-point the Animation Blueprint; check root motion and pelvis translation on a locomotion loop.
- The lanes — the batch belongs on `lane.ue-editor-closed`, the loop check on `lane.ue-editor`. The two lanes are mutually exclusive, so this is two packets and not one.
- The capabilities each step needs — `ue.python.commandlet` and `ue.batch` for the retarget pass, `ue.pie` and `ue.viewport` for the check.
- Acceptance — every source sequence has a target asset, and no retargeted asset fails to compile.
- Evidence — a PIE capture of the retargeted locomotion loop, not a green exit code.

**Forge owns afterwards** the acceptance registry entry, the evidence check, and the in-engine verification that what GSD's SUMMARY claims is backed by something an engine produced.

What goes wrong without doctrine is the middle: an agent asked to plan a retarget phase invents a step list each time, and the step that gets dropped is the one whose absence does not fail a build — the root-motion check.

## The procedure layer

Doctrine is enforceable only as data. Phase 1 builds it; this section is its contract, not its content.

**Where:** `plugins/forge-ue-studio/doctrine/procedures.json`, against `plugins/forge-ue-studio/schemas/procedure.schema.json` as `forge.procedure/v1`.

**Key:** `task_class` — the field `forge.work-packet/v2` already requires, that `route-policy.json` already scopes qualification by in `qualification.grant_scope`, and whose values (`ik-retarget`, `batch-import`, `lod-generation`) `unreal_routing` already names. The procedure layer introduces no key space; it fills the one already in use.

**Shape:** one entry per task class, supplying exactly the work-packet fields an agent currently improvises.

```
task_class -> lane, capabilities[], steps[], non_goals[], acceptance[], verification[], evidence[]
step       -> does, produces, capability
```

Prose belongs in this document. The procedure file is what a packet compiler reads.

## What consumes it, and what proves it

This repository's recurring defect is data declared and read by nothing: `tool_surface` went a release unread, and `requires_engine` in `route-registry.json` is read by nothing today. A doctrine document with no consumer is the next instance of it.

Three consumers, in the order Phase 1 should land them:

1. **`forge-plan-phase` PRE** resolves the phase's task class and hands GSD's plan workflow the procedure's steps and non-goals as the request. This is what gives a delegating workflow something of its own to contribute.
2. **`forge-route-work`'s `compile_packet`** fills `capabilities`, `acceptance`, `verification` and `evidence` from the procedure rather than from whatever the agent wrote.
3. **`forge.py dispatch`** refuses a packet whose task class has a procedure that the packet's declared capabilities, verification or evidence do not cover, under a new `ERROR_REASON` entry. This is the guard that runs at runtime rather than at lint time.

Four checks in `validate_repo.py` prove consumption mechanically:

| Check | Fails when |
|---|---|
| Every task class named in `unreal_routing.prefer_editor_closed_for` and `prefer_live_editor_for` has a procedure | Doctrine falls behind routing |
| Every procedure's lane and every capability it names exist in `route-registry.json` | A procedure names a route nothing serves |
| Every procedure carries at least one acceptance, verification and evidence line | A procedure is written but says nothing a packet can be checked against |
| `procedures.json` is read by at least one module under `plugins/forge-ue-studio/scripts/` | The layer decays into prose |

The last one is the one that matters, and it is the same shape as the existing guard that every verb be reachable from a workflow.

## Recommended, not done here

- `requires_engine` is declared on three routes in `route-registry.json` and read by nothing. The procedure resolver is its natural reader: a procedure whose lane requires an engine version or `.uproject` plugin the project does not have should refuse before a lease is taken. Read it there, or delete it.
- `forge-onboard` and `forge-resume-work` carry one-line CORE sections because they have nothing of their own to add. Once the procedure layer exists their PRE should carry doctrine — onboarding an existing project means recognising which task classes its `Content/` and modules already imply, and resuming means restoring the procedure the interrupted packet was executing.

See [the delegation contract](../../plugins/forge-ue-studio/references/delegation-contract.md) and [how Forge works](how-forge-works.md).
