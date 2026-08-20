<!-- forge:workflow
name: phase
consumes: ROADMAP.md, .forge/state/packet-registry.json, .forge/state/work-orders.json
produces: .forge/state/packet-registry.json (alias and derived_from records only)
-->

# Forge Phase — workflow

<purpose>
Add, insert, remove or edit a phase in the roadmap without breaking the one identity Forge owns: the
canonical packet ID that leases, routing decisions and job folders are all keyed on.
</purpose>

<core_principle>
GSD renumbers phases; Forge never renumbers a packet. A phase ID is a schedule position and may
move. A packet ID is an identity and may not.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Roadmap CRUD writes planning state, never a game asset:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-phase --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="read_the_registry_first">
Read `.forge/state/packet-registry.json` **before** any edit. Record `generation`, the current `packets`
list and the current `aliases` list, so the check after GSD's edit compares against a real prior
rather than against memory.
</step>

<step name="refuse_edits_to_work_in_flight">
Read `.forge/state/work-orders.json`. Refuse to remove or renumber a phase that has an order at
`DISPATCHED` or `BLOCKED` against it.

A removed phase whose order is still in flight leaves a lease held for a phase that no longer exists,
and nothing will release it — the release path needs the work order the removed phase carried.
Release or resolve the order first, through `forge-route-work`.
</step>

<step name="run_gsd_phase_crud">
Run GSD's phase CRUD. It owns phase-ID arithmetic entirely: decimal insertion, milestone-scoped
edits, and the renumbering that follows. Forge writes none of it.
</step>

<step name="check_packet_identity_survived">
Compare `.forge/state/packet-registry.json` against what `read_the_registry_first` recorded:

| Change | Verdict |
|---|---|
| A new entry in `packets` carrying `derived_from` naming its parent | Allowed |
| A new entry in `packets` with no `derived_from` | Refuse. Provenance is not optional for a derived packet |
| A new entry in `aliases` mapping an alias to an existing canonical ID | Allowed — display compatibility only |
| An existing `packets` entry whose `id` changed | **Refuse and revert.** This is the aliasing defect: routing decisions, leases and `.forge/jobs/<work-order>/` are all keyed on the old ID and none of them follow the rename |
| An existing entry removed | Refuse unless its order is closed and it has no dependents |

Check the result against its contract rather than reading it by eye:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind packet-registry --input <project-root>/.forge/state/packet-registry.json
```
</step>

<step name="report_the_reshuffle" priority="last">
Report which phase numbers moved and which packet IDs did not, side by side. That pairing is the
whole output of this workflow: anyone reading it afterwards needs to know a renumbering happened
*and* that nothing keyed on an ID was disturbed by it.
</step>

</process>
