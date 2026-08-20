<!-- forge:workflow
name: plan-phase
consumes: CONTEXT.md, plugins/forge-ue-studio/doctrine/procedures.json, .forge/state/packet-registry.json, .forge/visual/registry.json, forge.py exec status (blockers, blocked_lanes)
produces: PLAN.md carrying required_lanes and mutation_risk (GSD's), registered asset interfaces, derived_from packet records
-->

# Forge Plan Phase — workflow

<purpose>
Decompose what this phase means into task classes from Forge's catalogue, hand GSD those steps as the
request, and refuse any plan that comes back without saying which lane it writes on.
</purpose>

<core_principle>
Forge owns what a phase of this kind consists of. GSD owns the phase number, the decomposition into
plans, the wave order and the SUMMARY. A request that resolves to a task class with no procedure is a
gap in the catalogue, never a licence to invent steps inline.
</core_principle>

<process>

## PRE — Forge

<step name="declare_no_lane" priority="first">
Planning writes planning state and no game asset. But it must know which lanes are currently
unavailable, because a plan scheduled onto a quarantined lane is a plan that cannot run:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-plan-phase --apply
```

Naming no `--lane` records `holds_no_lane` against this run.

Then read which lanes are actually plannable, joined into one answer:

```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

Plan around every lane named in `blockers` rather than onto it. `lane_quarantined` and
`release_interrupted` need `exec reconcile` before anything can run there; `lane_breaker` means entry
has failed enough times running that Forge stopped offering the lane, and planning onto it is how a
retry loop starts.

> **Why:** CHANGELOG.md 0.7.0 § *A failure inside a lane is a fact Forge holds*
</step>

<step name="require_a_discussed_phase">
Confirm CONTEXT.md exists. Never plan a phase that has not been discussed — planning an undiscussed
phase re-decides its design silently, inside a plan, where nobody reviews design.

Route to `forge-discuss-phase` instead.
</step>

<step name="resolve_the_request_into_task_classes">
A feature request resolves to a **set** of task classes with an order between them, not to one. "Add
a red magic spell" is a gameplay ability, Niagara systems, a cast animation with a notify, a socket,
hit handling, an input binding, audio cues and a material treatment — and the socket must exist
before either of the two parallel halves lands.

Deciding that decomposition is this step's job and no one else's. Pick from the catalogue's closed
list — `ik-retarget`, `world-blockout`, `batch-import`, `lod-generation`, `asset-audit`,
`bulk-property-edit`, `cook-and-build-preparation`, `pie-verification` — and record any part of the
request that resolves to none of them as an undoctrined gap rather than naming a new class here.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *Forge is the game planner*
</step>

<step name="read_the_procedure_for_each">
For every task class resolved above:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
```

| In the answer | What the plan takes from it |
|---|---|
| `steps[]` — `does`, `produces`, `capability` | The ordered work, handed to GSD as the request |
| `non_goals[]` | What this phase must not grow to include |
| `acceptance[]`, `verification[]`, `evidence[]` | What `forge-verify-work` will grade the phase against — write them into the plan now, not at verification |
| `lanes[]` and `packets` | How many packets this becomes. `packets` above 1 means the steps span mutually exclusive lanes |
| `packet_split[]` | Which numbered steps and capabilities belong to each packet |
| `resolution.nearest` non-empty | The task class is misspelt. Fix the spelling — a typo resolves to no procedure and nothing refuses it |
| `procedure` is `null` | No doctrine covers this shape. Plan without it and **record that the phase ran undoctrined** |

**Hand GSD's planner the procedure's `steps` and `non_goals` as the request.** That is the whole of
what crosses the boundary in this direction: it becomes GSD's plan, written by GSD. Nothing else in
the answer is GSD's to see — lanes, capabilities and packet identity never leave Forge.

`ik-retarget` is the worked case: five steps on the closed lane and two on the live one, so it plans
as two packets. Planning it as one silently drops the root-motion check — the step whose absence fails
no build.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The procedure layer*
</step>

<step name="preserve_packet_identity">
Read `.forge/state/packet-registry.json`. Reference existing packet IDs; never mint a replacement for
one that exists.

A genuinely new packet carries `derived_from` naming its parent. An alternative name for an existing
one is an `aliases` entry, not a second packet.
</step>

## CORE — GSD

<step name="run_gsd_planner">
Run GSD's planner with the procedure's `steps` and `non_goals` as the request. GSD owns PLAN.md, the
task breakdown, the dependency analysis and the wave order.

Require every returned plan to carry `required_lanes`, `mutation_risk`, and every asset interface it
produces or consumes.
</step>

## POST — Forge

<step name="reject_a_plan_that_names_no_lane">
Grade each returned plan before it is allowed to reach execution:

| Returned plan | Verdict |
|---|---|
| Declares `required_lanes` matching the capabilities its steps need | Accept |
| Mutates Unreal content and declares no project-exclusive lane | **Reject.** A lease in no exclusive group is a misspelling, not protection |
| Declares no lane at all | **Incomplete.** Return it — a plan with no lane cannot be scheduled beside anything |
| Declares both a live and a closed Unreal lane in one plan | Split it. The two are mutually exclusive through the project super-lock |

`dispatch` refuses a packet that takes a procedure's lane without declaring every capability the
procedure needs on that lane, under `procedure_uncovered`. Catching it here is cheaper than finding
out at admission.
</step>

<step name="register_asset_interfaces">
Register every asset interface the plans produce or consume in `asset_interfaces` in
`.forge/visual/registry.json`, with its scale, pivot, collision, skeleton, sockets, material slots,
animation events, LODs and budgets.

This is what lets the visual DAG proceed in parallel rather than waiting on the gameplay half.
</step>

<step name="converge" priority="last">
Run `forge-plan-convergence` before execution on any non-trivial phase. `plan_review.max_cycles` in
`.forge/config.json` bounds it.

Then hand the phase to `forge-route-work`, which compiles the packet from the same procedures this
step read.
</step>

</process>
