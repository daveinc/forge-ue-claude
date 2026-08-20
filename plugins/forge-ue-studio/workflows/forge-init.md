<!-- forge:workflow
name: init
consumes: .forge/state/packet-registry.json, .forge/directives.md, .forge/config.json (human_gates), .planning/
produces: compact GDD, decision ledger, .forge/acceptance/registry.json, .forge/visual/registry.json, .forge/state/packet-registry.json, .forge/mcp.json
never-reads: .forge/state/lifecycle.json (deprecated history)
-->

# Forge Init — workflow

<purpose>
Take a greenfield project from nothing to inception artifacts, then stop.
</purpose>

<core_principle>
Never run phase discussion, planning, routing, implementation or verification here. Never dispatch a
walking-skeleton packet.
</core_principle>

<process>

<step name="entry_gate" priority="first">
```powershell
scripts/forge.py next --project <root>
```

Run this before interpreting or changing project state.

When the recommended action is not `forge-init`, dispatch it and **STOP**. Continue only on
`greenfield-ready`. Never invoke Forge Init recursively.

Read the host's project instruction file, `.forge/state/packet-registry.json`,
`.forge/directives.md` and current `.planning` artifacts.

Run `gsd-new-project` without `--auto`, preserving its questions, agent dispatch, approvals, commits,
state files and stop points.
</step>

<step name="declare_no_lane">
Inception writes design and planning artifacts, never a game asset, so it holds no lane:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-init --apply
```

Naming no `--lane` records `holds_no_lane` against this run. That is the honest answer even though
this workflow writes the packet registry and the route declarations: packet identity is protected by
the registry's own rules rather than by a lease, and neither file is contended by a concurrent writer.

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="classify_environment">
Run `forge-doctor`. Record verified and assumed facts separately.

A greenfield project has no `.uproject` yet, so `engine_association` comes back an **unknown rather
than a shortfall**, and nothing may be refused on it. Record it as an open decision — which engine
version this game targets is a mandate question, and `resolve_mandate` is where it gets answered.
</step>

<step name="declare_routes">
Declare the typed tool routes this game will use:

```powershell
python <forge-plugin-root>/scripts/forge.py mcp add --project <project-root> --id <provider> --command <exe> --arg <arg> --apply
```

Run `route-status` to confirm each route before depending on it. Declare capabilities, lane and
fallbacks in the entry for any provider outside the shipped catalog. Amend the set later through
`forge-capability-admin`.
</step>

<step name="resolve_mandate">
Ask one highest-value question at a time, resolving mandate, audience, platforms, camera, core loop,
progression, tone, scope, content boundaries, references, performance envelope, business constraints
and decision owners. Offer concrete options without forcing the framing.

Record every unknown as an explicit hypothesis, deferral or spike. Never silently choose one, and
never let changeable art block the playable contract.
</step>

<step name="diverge_before_locking">
Run a divergent design pass before locking the compact GDD. Generate materially different core-loop,
progression, narrative and production options, test them against the mandate, and keep rejected
tradeoffs in the decision ledger.
</step>

<step name="produce_inception_artifacts">
Produce the compact GDD with stable section IDs, the decision ledger, and the acceptance spine.

The spine is registered, not narrated: write each suite into `.forge/acceptance/registry.json` with
its `id` and `purpose`. Those IDs are what `forge-verify-work` grades a phase against later, and a
criterion that lives only in the GDD is graded by nobody.

Link large lore, research and references as sources rather than worker payload. A worker receives its
objective, the relevant GDD IDs, its inputs and its acceptance — never the interview.
</step>

<step name="develop_visual_direction">
Develop the first visual pillars, negative references, character/world sheets and storyboard
candidates on the resident host. Offload bounded alternatives to qualified workers; preserve prompt,
model/source, licence and date.

Obtain human approval for the primary visual direction — `primary-visual-direction` is in
`human_gates` in `.forge/config.json` and this workflow cannot sign it.

Then register replacement-safe asset interfaces in `asset_interfaces` in
`.forge/visual/registry.json`: scale, pivot, skeleton, sockets, collision, material slots, animation
events, LODs and budgets. Record prompt, model or source, licence and date under `provenance`.

Registering them here is what makes `compile_workstreams` below possible at all — concurrent
departments synchronise through registered interfaces, and an interface described only in the GDD
synchronises nothing.
</step>

<step name="compile_workstreams">
Compile concurrent playable, visual, narrative, audio, research and QA workstreams, synchronized only
through requirements, accepted decisions and asset interfaces.

Register each canonical packet ID once in `.forge/state/packet-registry.json`. An alias requires an
explicit alias record; a new packet requires `derived_from` provenance.
</step>

<step name="converge">
Run `forge-plan-convergence` on the inception artifacts.
</step>

<step name="re_detect">
Re-run the detector once inception artifacts are persisted:

```powershell
scripts/forge.py next --project <root>
```

Take the next action from GSD smart-entry; never hardcode a phase number or command.
</step>

<step name="stop" priority="last">
**STOP.** Require a fresh task and present `forge-next`.
</step>

</process>

## Gates

- Never auto-approve the mandate, primary visual direction, subjective art, game feel or release.
- Never start full production while a decision that changes architecture or content scope is
  implicit.
- Never present a project packet as a Forge workflow step.

| Identifier | Scope |
|---|---|
| `FI-*` | Forge bootstrap and inception controls |
| GSD's identifiers | Lifecycle |
| Registered IDs such as `P0`/`V0` | Production packets |
