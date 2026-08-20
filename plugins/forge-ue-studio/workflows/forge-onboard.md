<!-- forge:workflow
name: onboard
consumes: forge.py survey (.uproject, Content/, Config/, Source/*.Target.cs), Source/*/*.Build.cs, .forge/state/install-state.json, .forge/state/packet-registry.json, .forge/visual/registry.json, doctrine/procedures.json
produces: the task classes this project already implies, .forge/state/packet-registry.json entries, .forge/visual/registry.json asset interfaces
never-reads: .forge/state/lifecycle.json (deprecated history)
-->

# Forge Onboard — workflow

<purpose>
Bring Forge up to date with a game that already exists, until the project is resumable: what the
machine can reach, what the project already contains, which task classes that implies, and which of
them the design corpus can still describe.
</purpose>

<core_principle>
Onboarding reads the project and writes only Forge's own registries. Never author `Content/`, never
write `.planning` — GSD's onboarding writes that, from the task classes this workflow resolved.
Recognising what the project implies is the contribution; a project mapped to no task class has not
been onboarded, it has been listed.
</core_principle>

<process>

<step name="entry_gate" priority="first">
Take the situation from state, never from the request:

```powershell
python <forge-plugin-root>/scripts/forge.py next --project <project-root>
```

`forge.smart-entry/v1` decides whether onboarding is even the right verb:

| `situation` | Action |
|---|---|
| `existing-project-unplanned` | Continue. This is what this workflow is for |
| `existing-design-unplanned` | Continue, and carry `signals.design_sources` into `assess_design_context` |
| `forge-not-adopted` | `forge-bootstrap`, then **stop** — there is no `.forge` to write into |
| `forge-bootstrap-incomplete` | `forge-bootstrap --resume`, then **stop** |
| `host-surfaces-stale` | `forge-runtime`, then **stop** |
| `gsd-unavailable` | `forge-doctor`, then **stop**. CORE cannot run without GSD |
| any `gsd-*` with actions | The project already has planning state. Hand to `forge-next` and **stop** — onboarding would open a second history |

> **Why:** CHANGELOG.md 0.4.0 § *`forge-next` stops offering choices that are not choices*
</step>

<step name="declare_no_lane">
This run holds no lane. Say so rather than staying silent, and sweep the lane system on the way past:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-onboard --apply
```

Naming no `--lane` records `holds_no_lane` for this run in the `supervision` log of
`.forge/state/work-orders.json`. A `quarantined`, `interrupted_release` or `abandoned_workspaces`
entry means an earlier session died inside this project: report it before mapping anything, because
what it left behind is part of the state this workflow claims to have caught up with. Never clear one
here — `exec reconcile` is `forge-route-work`'s.

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="read_machine_state">
Two questions, two files, and neither is answered by looking at the project tree.

```powershell
python <forge-plugin-root>/scripts/forge.py verify --project <project-root>
```

`uproject` and `project_stage` say whether this is an Unreal project at all. `checks` lists every
canon file `MISSING` or `LOCAL_VARIANT`. Read `state_version` before trusting anything below it:
`MIGRATABLE` means `.forge` predates this Forge and its listed migrations run first, and `NEWER`
means it was written by a newer Forge — **stop and upgrade**, because a map written against state
this Forge cannot read is worse than no map.

```powershell
python <forge-plugin-root>/scripts/forge.py route-status --project <project-root>
```

`routes[].capabilities` and `routes[].status` are what makes a task class *doable* rather than merely
implied. A class whose capabilities resolve to no bound route is still recorded in
`resolve_task_classes` — it is a real thing this project needs — and marked unreachable, with the
route that would serve it named. Run `forge-doctor` when a route this project depends on is unbound;
never re-probe it by hand here.

> **Why:** CHANGELOG.md 0.6.0 § *`.forge` state has a version that means something*
</step>

<step name="read_project_state">
Read the project itself. One command reads most of it, and it counts rather than impressions:

```powershell
python <forge-plugin-root>/scripts/forge.py survey --project <project-root>
```

| In `forge.environment-snapshot/v1` | What it settles |
|---|---|
| `unreal.engine_association` | The engine version every route's `requires_engine` is checked against. A source-build GUID is an unknown, not a shortfall — say so and carry on |
| `unreal.plugins`, and the `python_script_plugin`, `editor_scripting_utilities`, `control_rig`, `native_mcp_declared` and `vibeue_declared` flags beside it | The enabled set. The first two decide whether the editor-closed lane exists at all; the rest decide which live routes do |
| `unreal.modules` | The C++ module boundaries, each with its `type` and `loading_phase`, read from the descriptor rather than from a `Source/` walk |
| `content.top_level_names`, `content.top_level`, `content.totals` | The shape of what this project already contains: the project's own folder vocabulary and the `.uasset`/`.umap` distribution across it. Record the folder names as read rather than renaming them into Forge's |
| `content.import_sources` | Import sources sitting beside their assets, counted by extension |
| `content.signals` | Default map, default game mode, `Source/*.Target.cs` build targets, and whether `Binaries`, `Saved`, `Intermediate` or `DerivedDataCache` show the project has been built |
| `content.implies`, `content.undetermined` | The task classes the tree settles, and the ones it cannot — carried into `resolve_task_classes` |
| `content.not_opened` | What this report deliberately did not read. Quote it when reporting; a count is not a claim about an asset |
| `content.truncated`, `content.scanned_files` | Whether the walk hit its file limit. `true` makes every count below it a floor, not a total |

Two reads the survey does not do, and they stay yours:

| Read | For |
|---|---|
| `Source/*/*.Build.cs` | What each module actually depends on. A module in `unreal.modules` with no `Build.cs` is a stale descriptor, and is a finding |
| `Config/DefaultEngine.ini`, `Config/DefaultGame.ini` beyond the default map and game mode | The platform and rendering settings a later cook inherits |

`content.present` reading `false` is an absence to report, not a failure. A Blueprint-only project has
no `Source/` and no modules and is not defective; a project with neither `Content/` nor a `.uproject`
is not an Unreal project and `verify` already said so.
</step>

<step name="resolve_task_classes">
This is the step that makes onboarding Forge's rather than a directory listing, and `survey` has
already done the mapping against the **closed** catalogue in
[procedures.json](../doctrine/procedures.json). Take `content.implies` and `content.undetermined` as
they came; never invent a class to cover an observation, and report an observation no class covers as
a gap.

| From the survey | What it is | What onboarding does with it |
|---|---|---|
| `content.implies[]` | A task class the tree settles on its own, each with the `evidence` that settled it | Claim it, and carry its `evidence` verbatim into the report |
| `content.undetermined[]` | A task class the tree cannot settle, each with the `needs` that would and `settled_by` naming what resolves it | Record it as undetermined. It is not absent, and it is not claimed |

The five it can settle are `asset-audit` — which always applies, because finding out what a project
already contains is onboarding's entire job — `batch-import` from import sources beside their assets,
`world-blockout` from `.umap` levels, `pie-verification` from a default map and game mode a session
can enter, and `cook-and-build-preparation` from build targets or evidence the project has been
built. The three it cannot are `ik-retarget`, `lod-generation` and `bulk-property-edit`: each needs an
asset opened, the survey opens none, and `settled_by` names `asset-audit` as the class that resolves
them. **That is why `asset-audit` is first work and not a formality** — running it is what turns three
undetermined classes into answers.

Read each class you claimed before claiming it:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
```

| In the answer | What it means here |
|---|---|
| `procedure` is `null` | The class name is wrong. `resolution.nearest` gives the declared ones — fix the spelling rather than recording an unprocedured class |
| `steps` | What a phase of this kind consists of. This is what CORE hands GSD |
| `lanes`, `packets`, `packet_split` | Whether the work splits across the two mutually exclusive Unreal lanes. Record the split now; it is the reason a later phase is two packets and not one |
| `capabilities` | Check each against `route-status` from `read_machine_state`, and against `unreal.engine_association` from `read_project_state` — a route's `requires_engine` is checked against that version. An implied class with no bound route is recorded as implied-and-unreachable, never dropped |

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The procedure layer* — § *Recommended, not done here*
</step>

<step name="assess_design_context">
A task class Forge can name and the design corpus cannot describe is a phase that will be improvised
later. Check now, while the answer is cheap.

Read `signals.design_sources` from the `forge.smart-entry/v1` payload at `entry_gate` — the design
corpus under `Docs/Design`, `docs/design` or `Design` — together with any `.planning/PROJECT.md` and
`.planning/ROADMAP.md` GSD's onboarding produces at CORE.

For each class from `resolve_task_classes`, ask whether the corpus answers what its `steps` need:
which skeleton is canonical for `ik-retarget`, which asset classes and budgets bound `lod-generation`
and `bulk-property-edit`, what a level is for in `world-blockout`, what a session must demonstrate in
`pie-verification`.

| When it does not | Action |
|---|---|
| Design documents exist outside the corpus Forge found | `forge-ingest-docs` against that path, then re-read |
| The corpus exists and is silent on this class | Record the gap as an open decision and route it to `forge-discuss-phase` when that phase is planned. Never answer it here |
| No corpus at all | Report it. Onboarding still completes — an existing game is evidence in its own right — but every class it produced is marked as inferred from the tree and not from a stated design |

Never infer a design decision from an asset. What `Content/` proves is what was built, not what was
intended.
</step>

<step name="run_gsd_onboarding">
**CORE — GSD's workflow, unmodified.** Run GSD's onboarding, handing it the `steps` and `non_goals`
of the classes `resolve_task_classes` resolved as the request. GSD owns the codebase map, the phase
numbering, `.planning` and every artifact in it; Forge owns what a phase of this kind consists of.

Give it what the procedures say, never a step list composed in this session.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *What crosses, and in which direction*
</step>

<step name="register_skeleton">
Record what the project implies where Forge's own state keeps it, so the next session reads it rather
than re-deriving it:

- `.forge/visual/registry.json` → `asset_interfaces`: one entry per asset contract the existing
  project already fixes — skeleton, sockets, scale, collision, material slots, animation events,
  budgets. These are read out of what exists, so they are constraints and not proposals.
- `.forge/state/packet-registry.json`: register a canonical production packet per task class this
  project needs, once. Reference an existing ID rather than minting a replacement, and give any
  derived packet its `derived_from` provenance.

Check the registry against its contract before anything routes against it:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind packet-registry --input <project-root>/.forge/state/packet-registry.json
```
</step>

<step name="confirm_resumable" priority="last">
Onboarding is finished when the detector says the project has somewhere to go:

```powershell
python <forge-plugin-root>/scripts/forge.py next --project <project-root>
```

| Answer | Meaning |
|---|---|
| A `gsd-*` situation carrying actions | Resumable. Hand control to the recommended action and **stop** |
| `existing-project-unplanned` still | CORE did not produce planning state. Report what GSD returned; never write `.planning` to make this pass |
| `gsd-unavailable` | The map stands, the schedule does not. Route to `forge-doctor` and **stop** |

Then confirm this run left nothing held:

```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

`active` must not name `forge-onboard`. It never should — this workflow takes no lease — and an entry
that does means something else in this session dispatched, which is a finding and not a tidy-up.

**STOP.** Dispatch exactly one action and let it own the work.
</step>

</process>
