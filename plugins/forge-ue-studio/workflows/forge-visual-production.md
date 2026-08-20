<!-- forge:workflow
name: visual-production
consumes: visual pillars, story beat, camera and use case, references, gameplay interface, platform budget, .forge/visual/registry.json, .forge/state/leases.json, plugins/forge-ue-studio/doctrine/procedures.json
produces: .forge/visual/registry.json (briefs, boards, asset_interfaces, provenance), the integrated asset, camera-locked evidence
-->

# Forge Visual Production — workflow

<purpose>
Take a visual requirement all the way to an asset that is integrated in Unreal and evidenced at
gameplay distance — across whichever of the Blender and Unreal routes this project actually has.
</purpose>

<core_principle>
Qualify each visual capability separately and never infer one from another. Never let a provider own
an art seat: `primary-visual-direction`, `subjective-art`, `likeness` and `appeal` are human gates,
and this workflow signs none of them.
</core_principle>

<process>

<step name="load_scope" priority="first">
Read only what bears on this asset: the relevant visual pillars, the story beat, the camera and use
case, the references, the gameplay interface it must satisfy, and the platform budget.

Read `asset_interfaces` in `.forge/visual/registry.json` first. An interface already registered for
this asset is the contract — gameplay work is running against it now, and this workflow satisfies it
rather than redefining it.
</step>

<step name="separate_capabilities">
Treat these as eight distinct capabilities: visual direction · prompt and reference decomposition ·
raster generation · video and previs planning · 3D construction · rigging and animation ·
integration · critique.

**Never infer one from another.** A provider that generates images is not thereby shown to generate
meshes, and a route qualified for one is unqualified for the rest until probed.

Confirm what is reachable right now rather than trusting the registry:

```powershell
python <forge-plugin-root>/scripts/forge.py route-status --project <project-root>
```
</step>

<step name="build_references">
Create licensed reference **and negative-reference** sets. The negative set is what makes a critique
falsifiable — without it, every generated candidate is arguably on-direction.

Use the resident host's visual generation for controlled art, photo and board candidates where it is
exposed, and visual-direction skills for character sheets, turnarounds, storyboards, shot cards and
continuity contracts.

Offload bounded variants to a qualified worker, and preserve prompt, model or source, licence and
date in `provenance` in `.forge/visual/registry.json`. A candidate with no provenance cannot be
shipped, because nobody can answer where it came from.
</step>

<step name="approve_direction">
**Stop for human approval of the primary direction.** `primary-visual-direction` is in `human_gates`
in `.forge/config.json`.

Never treat a generated concept as a shipping asset by default. This gate exists because everything
downstream is expensive and the approval is cheap.
</step>

<step name="declare_asset_interface">
Produce the orthographic and turnaround requirements, and register the asset interface in
`asset_interfaces` in `.forge/visual/registry.json`: scale, pivot, collision, skeleton, sockets,
material slots, animation events, LODs, budgets.

Register it **now**, before building. This is the contract the gameplay lane builds against in
parallel, and an interface registered after the mesh exists has already forced the other lane to wait.
</step>

<step name="choose_route">
Compare the available Blender and Unreal routes using
[visual-routing.md](../skills/forge-visual-production/references/visual-routing.md).

`visual_authoring_routes` in `.forge/config.json` names them and `allow_split_visual_route` permits a
split. Take a qualified worker or a split route when it improves context use, throughput or quality —
and record which route did what, because that is what `promote` credits.
</step>

<step name="take_the_authoring_lane">
Authoring writes generated content, so it holds a lane:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-visual-production --lane generated-assets --apply
```

Binary assets cannot be merged. `worker_isolation.binary_asset_default` in `.forge/config.json` is
`lfs-lock-or-project-exclusive`, so a concurrent writer on this lane is a lost afternoon rather than a
conflict marker.

| Answer | Action |
|---|---|
| `enterable` | Build |
| `blocked` / `lease_conflict` | Another writer holds it. Wait or take a different asset — never build over it |
| `quarantined` / `lane_abandoned` | A previous author died with an LFS lock taken. `exec reconcile` before authoring |
| `abandoned_workspaces` | A dead worker's worktree holds unmerged art. Salvage it first — it is the one recovery that loses data |

> **Why:** CHANGELOG.md 0.7.0 § *A lane a worker died in is not a lane Forge reports as free*
</step>

<step name="build">
Build blockout, mesh, UV and material, rig, skin and animation on the selected route, with a
checkpoint per asset class rather than one at the end.

Preserve native source and versioned export settings alongside the exported asset. An asset whose
`.blend` and export settings were not kept can only be revised by rebuilding it.
</step>

<step name="integrate">
Integration is Unreal work with a task class, so read its procedure rather than improvising:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class batch-import
```

Then take the Unreal lane the route needs — `ue-live-native-mcp`, `ue-live-python` or
`ue-editor-closed-api`. These are mutually exclusive with each other through the project super-lock,
so integration is one lane at a time:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-visual-production --lane ue-editor-closed-api --apply
```

For editor-closed work the **result file is authoritative, never the exit code alone** — an import
can exit zero having skipped what it could not load.

Run structural, animation, reference, memory and performance checks against the platform budget.

> **Why:** CHANGELOG.md 0.4.0 § *All three Unreal routes exist, and the verb that reports them says so*
</step>

<step name="evidence_at_gameplay_distance">
Capture camera-locked evidence — same camera, same lighting, same content, every time — so this
asset can be compared against its own next revision.

Capture it **at gameplay distance**, not in an asset viewer. An asset that reads correctly in the
content browser and disappears in play has failed, and only this capture catches it.

Compare objective requirements in visual QA — silhouette, budget, LOD behaviour, material slot
count. Leave subjective likeness, style and appeal to the human art owner and report on them without
closing them.
</step>

<step name="promote" priority="last">
Release every lane taken, including when integration failed:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```

Read `lease_status`: `ORPHANED_EXTERNAL_LOCK` means an LFS lock on the asset survived, and no other
author may take that path until `exec reconcile` clears it. Never route around a quarantined asset
path by writing a second copy.

Then promote, or fall back:

| Outcome | Action |
|---|---|
| Integrated and evidenced | Promote the asset manifest and credit the actual route that created and verified each artifact |
| Failed integration | Reactivate the last valid placeholder. The gameplay lane keeps running against the registered interface |

Invalidate gameplay work **only** when a declared asset interface changed — a new mesh satisfying the
same interface invalidates nothing, and treating it as if it did stops the other lane for no reason.

Use `forge-gameplay-gauntlet` for the bounded in-game comparison after integration.
</step>

</process>
