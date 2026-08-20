<!-- forge:workflow
name: discuss-phase
consumes: .forge/directives.md, the GDD decision ledger, the ROADMAP.md phase entry, .forge/capabilities/registry.json, .forge/capabilities/detected.json, .forge/visual/registry.json
produces: GDD decision ledger (CONTEXT.md is GSD's)
-->

# Forge Discuss Phase — workflow

<purpose>
Ask what this phase still has not decided — in game terms, scoped to the departments it touches, and
only about options this project can actually build.
</purpose>

<core_principle>
Never raise an option that depends on an unqualified provider or an unbound route. A discussion that
settles on a capability the project does not have produces a plan that cannot run.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
A discussion writes planning state and no game asset:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-discuss-phase --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="load_the_prior">
Read `.forge/directives.md`, the GDD decision ledger, and the phase's entry in `ROADMAP.md`.

Read `asset_interfaces` in `.forge/visual/registry.json`. An interface already registered is a
constraint on this discussion, not a question to reopen — another lane is building against it now.
</step>

<step name="scope_to_departments">
Name which of gameplay, visual, audio, narrative and QA this phase touches, and scope every question
to them.

`parallel_departments` in `.forge/config.json` is the list. A question outside the phase's departments
is scope creep arriving as curiosity.
</step>

<step name="bound_the_options_to_what_exists">
Read `.forge/capabilities/registry.json` and `.forge/capabilities/detected.json`, then confirm what is
actually reachable right now:

```powershell
python <forge-plugin-root>/scripts/forge.py route-status --project <project-root>
```

- A route that is declared but `UNQUALIFIED` may not carry an option. Detection is not qualification.
- A route bound in the session but not for spawned agents is project scope working as declared — an
  option depending on it must say the work stays resident.
- Never present an option whose capability resolves to nothing.
</step>

<step name="run_gsd_discussion">
Relay GSD's discussion. It owns CONTEXT.md; **never author or edit it**.

Reframe each question in game terms before asking it: which pillar it affects, what the player
experiences differently, which art/gameplay interface is at stake, and which lane would own the work.

Ask one high-value question at a time. Never batch. Pass answers back down verbatim.
</step>

<step name="record_what_constrains_other_lanes" priority="last">
Record in the GDD decision ledger — not only in CONTEXT.md — every decision that constrains an asset
interface. CONTEXT.md is scoped to this phase; the ledger is what the next phase reads, and an
interface constraint outlives the phase that set it.

Surface unresolved decisions explicitly. An unresolved art/gameplay interface is stated as unresolved
or it is not deferred at all — it is just forgotten, and rediscovered when two lanes collide on it.
</step>

</process>
