<!-- forge:workflow
name: undo
consumes: the GSD phase manifest, .forge/state/packet-registry.json, .forge/state/leases.json, .forge/state/work-orders.json, .gitattributes
produces: reverted commits, and a working copy proven to still open
-->

# Forge Undo — workflow

<purpose>
Roll back a phase's or a plan's commits without taking a lane another writer holds, and without
leaving a project that no longer opens.
</purpose>

<core_principle>
A revert is a write. Binary Unreal content cannot be merged, so a revert that lands while another
lane holds the project-exclusive lease does not conflict — it silently wins, and the other writer's
work is gone.
</core_principle>

<process>

<step name="take_the_lanes_this_writes" priority="first">
This workflow writes tracked files, so it holds real lanes. Declare them and read the answer:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-undo --lane project-files --lane generated-assets --apply
```

Add `--lane build-config` when the revert touches `Config/`, `*.uproject` or build scripts, and
`--lane ue-editor-closed-api` when it reverts cooked or generated content that only the closed editor
can rebuild.

| Answer | Action |
|---|---|
| `enterable` | Proceed |
| `blocked` / `lease_conflict` | A live writer holds it. **Stop.** Never revert past a held lease |
| `lane_abandoned` / `quarantined` | A holder died with an LFS lock still taken. Clear it with `exec reconcile` first — a revert over a locked binary fails halfway |
| `abandoned_workspaces` | A dead worker's worktree holds uncommitted work that this revert will make unmergeable. Salvage it before continuing |
| `interrupted_release` | `exec reconcile` before anything |

> **Why:** CHANGELOG.md 0.7.0 § *A lane a worker died in is not a lane Forge reports as free*
</step>

<step name="identify_the_binary_half">
Read `.gitattributes` and list which of the commits' touched paths are `lockable` or `binary`.

That set is the part that cannot be reverted by merge and must be reverted by exclusive ownership.
If it is non-empty and any lane above was not clean, stop here rather than reverting the text half
and leaving the assets behind.
</step>

<step name="identify_dependents">
Read `.forge/state/packet-registry.json`. Find every packet whose `derived_from` names a packet in
the range being reverted, and every alias pointing into it.

Reverting a parent whose derived packets are already dispatched orphans them: their job folders still
name inputs the revert removes. Read `.forge/state/work-orders.json` and refuse while any dependent
order rests at `DISPATCHED` or `BLOCKED`.
</step>

<step name="run_gsd_undo">
Run GSD's undo. It owns the phase manifest, the commit selection and its own dependency checks.
Forge supplies the two checks above, which the manifest has no way to make.
</step>

<step name="prove_the_project_still_opens">
A green git revert is not a rolled-back Unreal project. Reverting a `.uasset` to a revision whose
referenced asset no longer exists leaves a project that opens with missing references, and nothing in
the commit graph says so.

Confirm the working copy still opens — an editor load, or a `ue.python.commandlet` asset-audit pass
on the closed lane — before declaring the rollback complete. Where neither is available, say the
rollback is unverified rather than complete.
</step>

<step name="release_what_was_taken" priority="last">
Release the lanes, including on failure:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```

A failed revert that keeps its lanes blocks every writer behind it. Read `lease_status` in the
result: `ORPHANED_EXTERNAL_LOCK` means an LFS lock survived and the write scope stays quarantined
until `exec reconcile` clears it.

> **Why:** CHANGELOG.md 0.6.0 § *A resource Forge could not free is not a resource it reports as free*
</step>

</process>
