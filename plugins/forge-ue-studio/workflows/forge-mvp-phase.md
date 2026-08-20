<!-- forge:workflow
name: mvp-phase
consumes: the GDD decision ledger, the ROADMAP.md phase entry, .forge/config.json (human_gates, allow_placeholder_art)
produces: .forge/acceptance/registry.json slice criteria, .forge/visual/registry.json asset interfaces
-->

# Forge Mvp Phase — workflow

<purpose>
Shape a phase as a vertical slice that is genuinely playable, and register the two things that make
it schedulable: what the slice will be graded on, and which asset interfaces it depends on.
</purpose>

<core_principle>
A slice that cannot be played is not a slice. Every split must leave a playable loop on both sides,
or it is not a split — it is a decomposition into two things neither of which proves anything.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Shaping a slice writes planning state and no game asset:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-mvp-phase --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="name_the_pillar">
Read the GDD decision ledger and the phase's entry in `ROADMAP.md`. Name the single gameplay pillar
this slice proves.

A slice proving two pillars is two slices. A slice proving none is a feature.
</step>

<step name="define_playable_concretely">
Write down all four before anything is planned. "Playable" without them is a word each reader fills
in differently:

| | The slice must state |
|---|---|
| Input | What the player presses or does |
| Mechanic under test | The one system this slice exists to evaluate |
| Feedback | What the player sees, hears and feels in response |
| Exit condition | Win, lose, or how the loop ends and restarts |
</step>

<step name="set_the_placeholder_budget">
`allow_placeholder_art` in `.forge/config.json` is `true`, which is a permission and not a default.

Split the slice's assets in two and say which is which:

- **May be greybox** — anything the slice does not test. Greybox here is correct, not a shortcut.
- **Must be real** — anything whose presentation *is* the thing under test. A slice testing whether an
  impact reads at gameplay distance cannot test it with a placeholder impact.

A slice with no real-asset half is testing mechanics only. Say so, rather than letting a passing
slice imply the presentation was proven.
</step>

<step name="run_gsd_mvp">
Relay GSD's MVP workflow. It owns the story prompt, the SPIDR splitting check and the handoff to
planning.

Reframe every story prompt as a player statement before showing it — what the player does, what they
experience, and why it matters to the loop.

Judge each split candidate by the core principle: reject any split that produces two non-playable
halves, whatever the splitting heuristic scored it.
</step>

<step name="register_the_acceptance">
Record the slice's acceptance in `.forge/acceptance/registry.json` as **two** criteria, not one:

| Half | Graded by |
|---|---|
| Mechanical | Automatable. The input produces the effect, the exit condition fires |
| Feel | A human. `game-feel` is in `human_gates` in `.forge/config.json`, and this workflow cannot sign it |

A slice registered with a mechanical criterion alone will be reported as passing while feeling wrong,
which is the one failure a vertical slice exists to catch.
</step>

<step name="register_the_asset_interfaces">
Register every asset interface the slice depends on in `asset_interfaces` in
`.forge/visual/registry.json`, marked placeholder-satisfiable where the placeholder budget allows it.

This is what lets visual work start in parallel: the visual lane builds against the registered
interface, and the slice runs against a placeholder that satisfies the same one. Unregistered, the
two lanes converge only at integration, where the mismatch is expensive.
</step>

<step name="hand_off" priority="last">
Hand off to `forge-plan-phase` without re-declaring the phase mode.

Never accept "the feature is implemented" as slice completion. Run it, then use
`forge-gameplay-gauntlet` for the bounded comparison the feel criterion needs.

Never let a slice grow to include work that does not serve the loop under test.
</step>

</process>
