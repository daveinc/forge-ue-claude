<!-- forge:workflow
name: route-work
seat: studio-director
consumes: .planning/ (GSD phase and plan state), .forge/state/packet-registry.json, .forge/state/route-decisions.json, .forge/state/leases.json, .forge/capabilities/registry.json, .forge/capabilities/qualifications.json, .forge/context/activation-policy.json, .forge/acceptance/registry.json
produces: .forge/state/route-decisions.json, .forge/state/work-orders.json, .forge/state/leases.json
never-reads: .forge/state/lifecycle.json
-->

# Forge Route Work — workflow

<purpose>
Fill the `studio-director` seat with the resident host: compile approved decisions into bounded
cross-department work, and never own implementation.
</purpose>

<core_principle>
Select optional occupants per attempt. Never assign a department to a provider. Never serialize
independent departments.
</core_principle>

<process>

<step name="load_state" priority="first">
Load: approved GDD decision IDs, GSD `.planning` phase and plan state, canonical packet registry,
dependency DAG, current revision, `.forge/capabilities/registry.json`,
`.forge/capabilities/qualifications.json`, `.forge/context/activation-policy.json`, lane leases,
budgets, acceptance registry.

**Skip if:** GSD reports no matching active execution stage — unless this is an explicitly read-only
bootstrap job.

Ignore `.forge/state/lifecycle.json`.
</step>

<step name="drain_in_flight">
Finish or unblock in-flight work before opening avoidable new work.
</step>

<step name="select_ready_work">
Find ready work with satisfied hard prerequisites and disjoint write sets.

Keep design, gameplay, visual, audio, research and QA lanes concurrent once their contracts exist.
</step>

<step name="decide_decomposition">
Decide whether the task is safely decomposable.

Keep on the resident host: unresolved design, novel architecture, cross-system integration, delicate
mutation, final synthesis.
</step>

<step name="record_route_decision">
Apply hard filters and rank offload routes using
[routing.md](../skills/forge-route-work/references/routing.md). Prefer a qualified free, local or
already-installed worker when resident-context, time or lane savings exceed handoff and verification
cost.

Run without `--apply` to preview. Then record:

```powershell
python <forge-plugin-root>/scripts/forge.py route --project <project-root> --request <request-path> --apply
```

`--apply` writes the decision to `.forge/state/route-decisions.json` under the canonical work order,
which is where `admit_packet` reads it from. **An unrun command here blocks `admit_packet`.**

> **Why:** CHANGELOG.md 0.5.0 § *A routing decision is state the executor reads, not a file an agent carries*
</step>

<step name="resolve_tool_access">
Apply the `required_tool_access` hard filter. Resolve every declared capability:

```powershell
python <forge-plugin-root>/scripts/forge.py route-status --project <project-root>
```

- Dispatch a capability served by a typed tool route only to an agent declaring it, and only while
  its contract reports the route bound.
- Dispatch on the declared fallback when a route is unbound, and record which route was taken.
- Never dispatch a packet whose capability resolves to nothing.
</step>

<step name="choose_unreal_lane">
**Skip if:** the work is not Unreal work.

Choose the route by the shape of the work, not by what happens to be running. `unreal_routing` in
[route-policy.json](../dependencies/route-policy.json) says which shape belongs to which lane.

| Shape | Lane |
|---|---|
| Batch import, retargeting, asset audits, LOD generation, bulk property edits, null-RHI-safe work, anything unsafe inside the editor tick | `lane.ue-editor-closed` |
| Discoverable inspection, bounded scene and Blueprint mutation, PIE and viewport evidence | `lane.ue-editor` |

- Neither lane is the other's fallback. Taking one refuses the other — never plan concurrent live
  and closed work on one project.
- For editor-closed work the result file is authoritative, never the exit code alone.
- Take lane, lease and isolation mode from the routing decision rather than transcribing them. A
  lease in no exclusive group is a misspelling, not protection.

Before taking `lane.ue-editor-closed`, read `ownership` on the route:

| `ownership` | Meaning | Action |
|---|---|---|
| `HELD` | An MCP handshake answered, or an Unreal editor process holds this `.uproject` | Do not take the lane |
| `FREE` | Neither is true | The lane is enterable |
| `UNDETERMINED` | Process inspection could not answer; the route reports `UNAVAILABLE_BLOCKING` | **Stop and ask the user** |

On `UNDETERMINED`: take neither lane and do not re-probe until it answers differently. Never treat a
silent MCP endpoint as proof the editor is closed. Resolving the process check is the fix.

`dispatch` enforces this rather than trusting the workflow: a packet whose capability sits on an
`UNAVAILABLE_BLOCKING` route is refused as `route_blocked`, separately from `route_unreachable`,
and the refusal carries the `human_action` describing what to resolve.

> **Why:** CHANGELOG.md 0.6.0 § *A silent editor is not a closed editor* · § *An editor answering is not this project's editor answering* — 0.4.0 § *The editor-closed Unreal API is a route, not a fallback string* — 0.4.1 § *Routing decides what a packet must hold, and acquiring checks it*
</step>

<step name="declare_isolation">
Declare isolation in the packet, taking lane, lease and isolation mode from the registry row:

| Writer | Isolation |
|---|---|
| Concurrent text and code writers | Clean-base Git worktree |
| Binary assets | LFS lock or project-exclusive lease |
| Reviewers | Read-only |

Name the base revision explicitly.

**Declaring is this step's whole job.** Establishing isolation belongs to `admit_packet`, never to
this workflow by hand.
</step>

<step name="resolve_work_order">
Resolve the work order through `.forge/state/packet-registry.json`. Reject unregistered IDs, preserve
the canonical ID, treat aliases as display compatibility only, and require derived packets to name
their parents.
</step>

<step name="compile_packet">
Compile an immutable minimal work packet: canonical work order, GSD phase and plan, revision, task
and complexity class, objective, non-goals, referrals, inputs, exact write scope, isolation, leases,
capabilities, context budget, output contract, acceptance, verification, evidence, invalidation
hashes.

Never forward the full GDD or the resident conversation.

Check it against its contract before dispatching:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind work-packet --input <packet-path>
```

`admit_packet` checks this contract again on the way in; running it here catches a malformed packet
while it is still cheap to fix.

> **Why:** CHANGELOG.md 0.5.0 § *Every verb is reachable from a workflow, and a guard keeps it that way*
</step>

<step name="admit_packet">
Admit the packet to execution. **This is the only way isolation is established** — an unrun command
means an unheld lease, whatever the packet says.

Run without `--apply` first to read the plan. Then:

```powershell
python <forge-plugin-root>/scripts/forge.py dispatch --project <project-root> --packet <packet-path> --apply
```

`dispatch` does all of this as one decision — nothing is acquired unless every check passed:
- checks the packet against `forge.work-packet/v1`
- proves every declared capability is reachable *right now*
- refuses when available routes have drifted from the ones the decision was scored against
- takes the leases and isolation
- records the order transition in `.forge/state/work-orders.json`

`exec acquire` remains for taking leases alone, under the same routing checks:

```powershell
python <forge-plugin-root>/scripts/forge.py exec acquire --project <project-root> --packet <packet-path> --apply
```

It finds the decision `record_route_decision` recorded, by the packet's own work order, and refuses:

| Refusal | Cause |
|---|---|
| `route_decision_missing` | The work order has no recorded decision |
| `route_decision_stale` | The decision is older than the freshness window in [route-policy.json](../dependencies/route-policy.json) |
| `lease_conflict` | The lane is held, or held in the same exclusive group |
| — | Fewer leases than routing resolved, weaker isolation than it requires, or any lane while tool access is degraded |

Re-run `record_route_decision` rather than working around a missing or stale decision. `--route <path>`
overrides the lookup for a decision held elsewhere and never relaxes it.

Treat a `lease_conflict` as binding — route elsewhere or wait. Never take a worktree or lock by hand,
and never proceed past a refusal.

> **Why:** CHANGELOG.md 0.6.0 § *Admission is one decision, not four steps with seams between them* — 0.5.0 § *A routing decision is state the executor reads, not a file an agent carries*
</step>

<step name="dispatch_agents">
Dispatch independent packets concurrently through the typed agent surface when it is available and
authorized, stopping related local work while agents run.

| Work | Agent |
|---|---|
| Build | `gameplay-engineer` |
| Visual | `visual-developer` or `dcc-artist` |
| Engine operation | `unreal-operator` |
| Research | `researcher` |
| Verification | `independent-verifier` — never the agent that produced the work |

Record `DEGRADED_INLINE` when dispatch is unavailable. Never describe inline work as delegated.

Give the verifier the requirement, artifact or diff, acceptance and evidence — never builder
reasoning.

> **Why:** CHANGELOG.md 0.2.0 § *Isolation is enforced by the runtime, not by workflow compliance*
</step>

<step name="check_attempt_result">
Require a structured attempt result separating observed facts, inferences, findings, touched
artifacts, evidence, verification, residual risk and next action.

Check each returned result before acting on it:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind attempt-result --input <result-path>
```

A result that omits its verification or evidence is not a result.
</step>

<step name="handle_failure">
Inspect actual artifacts before retry on failure.

Substitute a second occupant before changing competence scores when the brief or tool may be
defective.

Use `forge-retrospective` for inconsistent or repeated failures.
</step>

<step name="renew_lease">
**Skip if:** the job cannot outrun the two-hour TTL.

Any job that can — a cook, a mass retarget, a Nanite rebuild, a large import — must renew before
expiry:

```powershell
python <forge-plugin-root>/scripts/forge.py exec renew --project <project-root> --work-order <id> --apply
```

A lease whose owner process is still alive is never taken away; it is reported as `renewal_overdue`.
Renew anyway — liveness is only checkable from the machine that took the lease, and a lease taken
elsewhere is recovered once its grace window passes.

> **Why:** CHANGELOG.md 0.6.0 § *A lease is held by a process, not by a clock*
</step>

<step name="release_lease">
Persist transitions, deactivate packet-only surfaces, and release:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```

A failed outcome discards the worktree; a passed one keeps it for merge.

Read `lease_status` in the result:

| `lease_status` | Meaning | Action |
|---|---|---|
| `RELEASED` | Every external resource was freed | Done |
| `ORPHANED_EXTERNAL_LOCK` | An LFS lock or worktree survived; the write scope stays quarantined and no writer may take the lane | Clear it — never route around it |

```powershell
python <forge-plugin-root>/scripts/forge.py exec reconcile --project <project-root> --work-order <id> --apply
```

`reconcile` also recovers a lease left mid-release by a crashed session. The only ways out of a
quarantined lane are reconciling it or freeing the resource by hand.

Record every order transition in `.forge/state/work-orders.json` and stop at one of its declared
terminal states. Resume from that file and from `forge.py exec status`, never from chat memory.

> **Why:** CHANGELOG.md 0.6.0 § *A resource Forge could not free is not a resource it reports as free*
</step>

<step name="run_gsd_phase">
**Skip if:** any plan in the phase needs a typed tool route.

Run GSD's `execute-phase.md` while holding the leases from `admit_packet`. It owns wave scheduling,
plan dispatch and SUMMARY authorship.

Release through `release_lease` afterwards, including on failure, and verify completion through GSD's
own completion check.
</step>

<step name="escalate_gaps" priority="last">
Use `forge-capability-admin` to qualify or activate a route, and `forge-research` when no verified
capability closes a required step.

Block only the step that has no fallback.
</step>

</process>
