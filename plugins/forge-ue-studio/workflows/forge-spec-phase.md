<!-- forge:workflow
name: spec-phase
consumes: the ROADMAP.md phase entry, the GDD decision ledger, .forge/visual/registry.json, plugins/forge-ue-studio/doctrine/procedures.json
produces: SPEC.md (GSD's), with Forge's ambiguity severities applied
-->

# Forge Spec Phase — workflow

<purpose>
Say what this phase delivers, and score what is still unsaid — against decisions this game has
already made, not against a blank slate.
</purpose>

<core_principle>
An ambiguity that touches an art/gameplay interface is high severity whatever a generic scorer
returned, because it is the one kind that silently invalidates work already running in another lane.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Specifying a phase writes no game asset:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-spec-phase --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="load_the_prior">
Read the phase's entry in `ROADMAP.md` and the GDD decision ledger.

A question the ledger already answers is not an ambiguity — it is a decision the spec should cite.
Scoring against a blank slate re-opens settled design every phase, which is the failure this step
exists to prevent.

Read `asset_interfaces` in `.forge/visual/registry.json` too. An interface already registered
constrains this phase whether or not the phase entry mentions it.
</step>

<step name="run_gsd_spec">
Relay GSD's spec workflow. It owns SPEC.md, its structure, and its own ambiguity scoring.
</step>

<step name="check_the_shape_is_known">
For each kind of Unreal work the spec commits to, check that doctrine covers it:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
```

| Answer | What it means for the spec |
|---|---|
| A procedure | The shape is known. Its `acceptance` and `evidence` are what this phase will be graded against — the spec should not contradict them |
| `resolution.nearest` non-empty | The spelling is off. Fix it here, not at dispatch |
| `procedure` is `null` | No doctrine covers this shape. That is itself an ambiguity: record it as one, and say the phase will run undoctrined |

Do not invent a task class to make this step answer. The catalogue is a closed list of eight, and a
shape outside it is a gap to record, not a name to make up.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The procedure layer*
</step>

<step name="apply_forge_severities" priority="last">
Re-grade what came back. Raise to high severity, whatever the relayed workflow scored it:

- Any ambiguity about an art/gameplay interface — scale, pivot, collision, skeleton, sockets,
  material slots, animation events, LODs, budgets. Visual and gameplay lanes run concurrently against
  these, so an unresolved one is not one phase's problem but two lanes' rework.
- Any ambiguity about which lane the work lands on. Editor-open and editor-closed are mutually
  exclusive through the project super-lock, so a phase that has not decided cannot be scheduled
  beside anything.

Never silently defer either. An unresolved art/gameplay interface is stated in SPEC.md as unresolved
or it is not deferred at all.
</step>

</process>
