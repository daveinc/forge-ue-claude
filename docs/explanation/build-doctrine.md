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

## Forge is the game planner

That example starts after someone has already said the word *retarget*. Real requests do not arrive in task classes. A user says **"add a red magic spell"**, and that sentence is inert to GSD — it has no way to know what a spell is made of.

Forge does. A spell means a gameplay ability with its cost and cooldown, Niagara systems for the cast, the projectile and the impact, a cast animation with a notify, a socket on the character to spawn from, hit handling and damage application, an input binding, audio cues, and a red material and lighting treatment that still reads at gameplay distance. It also means the Niagara work and the animation work are separate lanes that can run in parallel, that the socket must exist before either lands, and that the ability should compile before the effect is worth authoring.

**Decomposing intent into that list is Forge's job and no one else's.** GSD then schedules the phases and records what happened. This is the whole reason build doctrine needs a home: without one, the decomposition is re-invented every session by whichever agent is holding the request, and it comes out different every time.

Doctrine therefore has two layers, and they are not the same thing.

| | Doctrine catalogue | Job brief |
|---|---|---|
| **What** | What a task class always means | What *this* job is, resolved for this project |
| **Lifetime** | Ships with the plugin, versioned in git | Written when a job lands, kept until swept |
| **Where** | `plugins/forge-ue-studio/doctrine/` | `.forge/jobs/` in the project |
| **Written by** | A human, deliberately | Forge, per job, from the catalogue plus the request |
| **Read by** | Forge, when planning and compiling a packet | The agent doing the work, GSD's included |

The catalogue is the closed vocabulary. The brief is what an agent actually opens.

## The procedure layer

Doctrine is enforceable only as data. Phase 1 builds it; this section is its contract, not its content.

**Where:** `plugins/forge-ue-studio/doctrine/procedures.json`, against `plugins/forge-ue-studio/schemas/procedure.schema.json` as `forge.procedure/v1`.

**Key:** `task_class` — the field `forge.work-packet/v2` already requires, that `route-policy.json` already scopes qualification by in `qualification.grant_scope`, and whose values (`ik-retarget`, `batch-import`, `lod-generation`) `unreal_routing` already names. The procedure layer introduces no key space; it fills the one already in use.

**Shape:** one entry per task class, supplying exactly the work-packet fields an agent currently improvises. What is stored is what a human writes; what is derived is what `procedure_for` computes from it and no one hand-maintains.

```
stored     task_class -> lane, capabilities[], steps[], non_goals[], acceptance[], verification[], evidence[]
           step       -> does, produces, capability
derived    capability_lanes{}, lanes[], packets, packet_split[]
           packet_split entry -> lane, capabilities[], steps[]
```

`lane` on a task class is not the lane the work runs on. It is where the bulk of it sits — a one-word label, useful for reading the catalogue and for checking it against `route-policy.json`'s `unreal_routing`, and never the authority on what a packet takes. **The authority is the step.** Each step names one capability, `route-registry.json` maps that capability to the route that serves it and so to its lane, and `procedure_for` resolves every step's capability through that map into `capability_lanes`. What falls out is the shape the work actually has: `lanes` is the distinct set the steps span, `packets` is how many there are, and `packet_split` says which capabilities and which numbered steps belong to each.

This is why `ik-retarget` is two packets and not one, and it is derived rather than declared. Its `lane` reads `lane.ue-editor-closed` and five of its seven steps do sit there on `ue.python.commandlet` and `ue.batch`; the PIE readback and the viewport capture name `ue.pie` and `ue.viewport`, which the registry serves from the live editor. Two lanes, mutually exclusive through the project super-lock, therefore two packets — and nothing had to say so, because the capabilities already did. `dispatch` reads the same derivation: a packet holding one of those lanes is refused when it omits a capability the procedure needs *on the lane it already took*, and admitted when it covers its own lane and leaves the other to its sibling packet.

No second vocabulary was introduced for this. A procedure names capabilities; lanes come from the registry that already owns them; the split follows from the lanes. The catalogue names capabilities, not tools. `route-registry.json` already maps a capability to the routes that serve it and the tool surface each exposes, so a second list of tool names here would be a second source of truth that drifts. The concrete tools appear in the brief, resolved through that registry at the moment the job is written — which is also the only moment the answer is true, since a route's availability depends on whether the editor is open.

A feature request resolves to a *set* of task classes, not one — the spell above is six or seven of them with an order between them. Resolving a request into that set is `forge-plan-phase`'s job, and what makes it doctrine rather than improvisation is that it must pick from the catalogue's closed list. A request that resolves to a task class with no procedure is a gap to fill in the catalogue, not a licence to invent steps inline.

Prose belongs in this document. The procedure file is what a packet compiler reads.

## The job tree

A brief that exists only in an agent's context is unobservable and unreproducible. Forge writes every job to disk, in a tree shaped so that an agent — Forge's or GSD's — opens exactly one folder and finds everything that job needs and nothing it does not.

```text
.forge/jobs/
  <verb>/                       one folder per Forge workflow: route-work, visual-production, …
    <work-order>/
      brief.md                  objective, ordered steps, tools and routes, non-goals,
                                acceptance, evidence — what the working agent reads
      packet.json               the forge.work-packet/v2 for this job
      context/                  each context package as its own file, one per referral
      result.json               the attempt result, written on release
```

Four things this settles:

- **The packet is already the brief's data half.** `forge.py dispatch --packet <path>` takes a file today, but nothing says where that file lives, so packets are written wherever the agent chose and then vanish. Giving them a canonical path is the change; the artifact is not new.
- **Context packages become files.** The minimal referrals a packet carries are assembled in context today and never observed. Writing each as its own file under `context/` makes what a worker was actually handed inspectable while Forge is still being developed, and turns "the brief was thin" into a checkable claim rather than a suspicion.
- **The verb folder is the index.** A job sits under the verb that dispatched it, so finding its brief needs no registry lookup. `.forge/state/work-orders.json` stays the ledger of *status*; the job folder holds the *content*.
- **Retention is keep-for-now.** Jobs are not deleted on completion. A `jobs.retention` key in `.forge/config.json` defaults to `keep`, and sweeping completed jobs past a window is a later phase — not built and not scheduled. Debuggability first; the sweeper is one function once the tree has proven its shape.

`.forge/jobs/` is canon rather than rendered: portable, host-neutral, and the evidence trail for what was asked of whom. `docs/reference/repository-layout.md` gains the directory when Phase 1 creates it.

## What consumes it, and what proves it

This repository's recurring defect is data declared and read by nothing: `tool_surface` went a release unread, and `requires_engine` in `route-registry.json` went two. A doctrine document with no consumer is the next instance of it.

Four consumers, in the order Phase 1 should land them:

1. **`forge-plan-phase` PRE** resolves the request into task classes from the catalogue and hands GSD's plan workflow their steps and non-goals. This is what gives a delegating workflow something of its own to contribute.
2. **`forge-route-work`'s `compile_packet`** fills `capabilities`, `acceptance`, `verification` and `evidence` from the procedure rather than from whatever the agent wrote, and writes the job folder — `brief.md`, `packet.json`, and one file per context package.
3. **`forge.py dispatch`** refuses a packet whose task class has a procedure that the packet's declared capabilities, verification or evidence do not cover, under a new `ERROR_REASON` entry. This is the guard that runs at runtime rather than at lint time.
4. **GSD's working agent** reads `brief.md` from the job folder. This is the hand-off: doctrine reaches the agent doing the work as a file, not as an instruction someone remembered to repeat.

Four checks in `validate_repo.py` prove consumption mechanically:

| Check | Fails when |
|---|---|
| Every procedure's lane and every capability it names exist in `route-registry.json` | A procedure names a route nothing serves |
| Every procedure carries at least one acceptance, verification and evidence line | A procedure is written but says nothing a packet can be checked against |
| `procedures.json` is read by at least one module under `plugins/forge-ue-studio/scripts/` | The layer decays into prose |
| `dispatch` writes a job folder, and `exec release` writes its `result.json` | The tree is specified but never populated |

The last two are the ones that matter. The first of them is the same shape as the existing guard that every verb be reachable from a workflow; the second is the same shape as the 0.7.0 fix for terminal states that had no writer. A job folder is easy to check for, which is the point of choosing a file tree over an in-context brief.

A fifth check belongs in that table one day and does not belong there yet: *every task class named in `unreal_routing.prefer_editor_closed_for` and `prefer_live_editor_for` has a procedure*. It would fail on a clean tree the day it was written, because `route-policy.json` names fifteen shapes of Unreal work and the catalogue covers eight of them — `ik-retarget`, `batch-import`, `lod-generation`, `asset-audit`, `bulk-property-edit` and `cook-and-build-preparation` on `lane.ue-editor-closed`, and `world-blockout` and `pie-verification` on `lane.ue-editor`. Shipping the guard would force the remaining seven procedures to be invented in one sitting to make a lint pass, which is exactly the improvisation the catalogue exists to stop.

So it is an aspiration, and the gap it aspires to close is named here rather than left to be rediscovered. Seven routing shapes have no procedure today:

| Lane the shape routes to | Shape with no procedure | Why |
|---|---|---|
| `lane.ue-editor-closed` | `null-rhi-safe-work` | Not a task class. A property of work: it needs no rendering device, so it survives `-nullrhi` |
| `lane.ue-editor-closed` | `deterministic-script` | Not a task class. A property of work: it is reproducible from a script and needs no human in the loop |
| `lane.ue-editor-closed` | `unsafe-inside-editor-tick` | Not a task class. A property of work: it would corrupt or stall a live editor's tick |
| `lane.ue-editor` | `schema-discoverable-inspection` | Not a task class. A property of the *route*: the native MCP server answers in discovery mode, which `route-registry.json` already states under `tool_surface` |
| `lane.ue-editor` | `typed-readback` | Not a task class. A way of reading state, which `unreal_routing.result_authority` already governs |
| `lane.ue-editor` | `viewport-evidence` | Not a task class. A kind of evidence. Every procedure that can produce one already names it under `evidence` |
| `lane.ue-editor` | `bounded-scene-or-blueprint-mutation` | Not a task class. A routing bucket joining two different jobs with an *or* and qualifying them with a bound. Its Blueprint half is `world-blockout`'s authoring steps; its scene half has no live call at all, which is why `world-blockout` splits to `lane.ue-editor-closed` to place an actor |

That is a different claim from the one this section used to make. Four of the eleven were task classes and are now written. The other seven are not work anyone requests — nobody says *today we are doing typed-readback* — and writing a procedure for each would put seven entries in a closed vocabulary that describe nothing, in a file where **a procedure that exists will be followed**. Padding the catalogue is worse than leaving it short.

The right fix is in `route-policy.json`, and it is a doctrine change rather than a lint fix, so it is proposed here and not applied:

- `unreal_routing.prefer_editor_closed_for` and `prefer_live_editor_for` should hold **task classes only**, and should be the list the fifth guard checks. On that reading they hold six and two entries respectively today, and the guard is shippable now.
- The three editor-closed properties belong under a sibling key — `unreal_routing.route_closed_when`, a list of *reasons* rather than shapes. They are what a router consults when a request resolves to a task class the catalogue does not cover, or to none: work that is null-RHI-safe, deterministic, or unsafe inside the editor tick takes the closed lane whatever it is called. Expressed as a step attribute they would also work — a step could carry `unsafe_inside_editor_tick: true` — but a step already names a capability, and the capability already implies the lane, so a second per-step lane signal would be a second source of truth.
- `schema-discoverable-inspection` should be deleted from the routing list outright. It restates `tool_surface` on the `unreal-native-mcp` row, which is where a reader already looks and where it is already true.
- `typed-readback` and `viewport-evidence` should become a `unreal_routing.live_lane_yields` note — what the live lane is *for* — rather than shapes of work. `result_authority` is the sentence they belong beside.
- `bounded-scene-or-blueprint-mutation` should be replaced by the real classes hiding inside it once someone writes them, and the bound should stay as prose about why they are safe on the live lane. Splitting it is the only entry on this list that costs new procedures.

Nothing may be deleted from `route-policy.json` to shorten the table without that argument being made first; a shape without a procedure is a procedure not yet written until someone shows it is not a shape. The seven above are the argument, made in writing, and the deletion is still not taken here.

`procedure_resolution` says all of this out loud on dispatch, under `procedured: false`, so a packet whose task class is one of the seven is visible in the ledger rather than indistinguishable from a doctrined one.

### `requires_engine` has a reader

`requires_engine` sat on three routes for two releases with nothing reading it, which is the defect this section opens by naming. It is read now, and by the reader this document proposed for it.

`engine_prerequisite_gaps` resolves each capability a packet declares to the route that serves it, and compares that route's `min_version` and `uproject_plugins` against the project's `EngineAssociation` and enabled plugin list — both of which Forge already knew how to read. `dispatch` calls it after the procedure gate and before it resolves the routing decision, so a project whose `.uproject` has no `PythonScriptPlugin` is refused as `engine_prerequisite_missing` with the route, the requirement and what was found, rather than taking a project-exclusive lease and failing in the step that needed the plugin.

Two things it deliberately does not claim. A project with no `.uproject` is an unknown, not a shortfall — Forge's own pre-project stage is exactly that. So is an `EngineAssociation` that is a source-build GUID rather than a version number: the version comparison is skipped and the plugin check still runs, because the plugin list is knowable when the engine version is not. A guard that refuses on what it cannot see is a guard that gets disabled.

## Recommended, not done here

- `forge-onboard` and `forge-resume-work` carry one-line CORE sections because they have nothing of their own to add. Once the procedure layer exists their PRE should carry doctrine — onboarding an existing project means recognising which task classes its `Content/` and modules already imply, and resuming means reopening the job folder the interrupted packet was working from, which is a stronger restore than the handoff record alone.
- Sweeping completed job folders is deliberately deferred. Everything stays on disk until the tree's shape is proven in use; a retention window and the sweep that honours it are a later phase, and the `jobs.retention` key exists so that phase changes a default rather than a design.

See [the delegation contract](../../plugins/forge-ue-studio/references/delegation-contract.md) and [how Forge works](how-forge-works.md).
