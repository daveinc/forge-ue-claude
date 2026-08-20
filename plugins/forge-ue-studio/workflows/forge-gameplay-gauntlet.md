<!-- forge:workflow
name: gameplay-gauntlet
consumes: a runnable loop, a named reference, the comparison rubric, the current baseline, .forge/config.json (human_gates), .forge/state/leases.json
produces: the winning change, a forge.attempt-result/v1, camera-locked evidence per alternative
-->

# Forge Gameplay Gauntlet — workflow

<purpose>
Decide which of several bounded alternatives actually feels better, by building them, playing them
under identical conditions, and letting a human call it.
</purpose>

<core_principle>
Never invent an automatic quality threshold. `game-feel` is in `human_gates` in `.forge/config.json`,
and the stop gate stays human-owned.
</core_principle>

<process>

<step name="require_the_round_be_decidable" priority="first">
Refuse to open a round without all six. Each missing one turns the comparison into an opinion:

| Required | Why the round is undecidable without it |
|---|---|
| A runnable loop | You cannot compare feel against something that does not run |
| A named target or reference | "Better" needs a direction |
| Comparison dimensions | Without them, whichever alternative is described last wins |
| Fixed capture conditions | Camera, input, hardware, content. Different conditions compare the conditions |
| The current baseline | Without it, the round cannot show it improved anything |
| A human-owned stop gate | Named person, named criterion |
</step>

<step name="freeze_the_rubric">
Freeze the comparison rubric before any alternative is built, and choose exactly **one** bottleneck.

A rubric edited mid-round grades earlier alternatives against criteria they were not built for. Keep
every unrelated system outside the round — a change to something the rubric does not score is a
confound, not a bonus.
</step>

<step name="take_the_lanes_the_round_needs">
Alternatives are built concurrently, so their write scopes must be disjoint and their lanes must be
held:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-gameplay-gauntlet --lane project-files --lane generated-assets --apply
```

Add `--lane ue-live-native-mcp` for the capture pass. **Capture is serial even when building is
parallel** — the live editor lane is exclusive with every other Unreal route through the project
super-lock, so alternatives are captured one after another on the same lane, under the same
conditions.

| Answer | Action |
|---|---|
| `enterable` | Proceed |
| `blocked` / `lease_conflict` | Another department is writing. Route the round later — never take the lane anyway |
| `quarantined` / `lane_abandoned` | `exec reconcile` first. A half-held lane produces captures nobody can trust |

> **Why:** CHANGELOG.md 0.7.0 § *A lane whose state is unknown refuses differently from one that is merely busy*
</step>

<step name="fan_out_alternatives">
Dispatch each alternative as its own bounded packet through `forge-route-work`, with a disjoint write
scope and a clean-base worktree. Overlapping write scopes make the round a merge exercise.

Close only the gaps that affect *this* comparison — use placeholders, or targeted
`forge-visual-production`, and nothing more. An alternative that also improved something the rubric
does not score has confounded its own result.
</step>

<step name="capture_identically">
Build and capture every alternative under the same camera, input, hardware and content conditions —
the ones frozen at `require_the_round_be_decidable`.

Record the conditions with the captures. A capture whose conditions are not recorded cannot be
compared against a later round.
</step>

<step name="judge_blind">
Give the play evidence and in-engine frames to `gameplay-critic`, isolated from the agents that built
the alternatives, and ask it to score harshly against the frozen rubric.

Run blind A/B whenever labels could bias judgment — which they can whenever one alternative is "the
current approach". Never hand the critic builder reasoning.
</step>

<step name="integrate_only_the_winner">
Integrate the winning change and discard the rest. Then run regression and performance checks: a
change that wins on feel and costs frame time has not won.

Record the attempt result, and check it:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind attempt-result --input <result-path>
```

Keep the losing alternatives' evidence. The round's value is the comparison, and a record holding
only the winner cannot explain why.
</step>

<step name="release_and_stop" priority="last">
Release every lane the round held, including on an inconclusive round:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```

A gauntlet abandoned mid-round with the editor lane held blocks every other department.

Stop when the human owner accepts the feel, the round limit is reached, or improvement stalls.
Escalate unresolved tradeoffs to that owner. **Never invent an automatic quality threshold** to close
a round that a person has not closed.
</step>

</process>
