# Forge Route Work — workflow

Fill the `studio-director` seat with the resident host: compile approved decisions into bounded cross-department work and never own implementation. Select optional occupants per attempt; never assign a department to a provider and never serialize independent departments.

## Dispatch workflow

1. Load the approved GDD decision IDs, GSD `.planning` phase and plan state, canonical packet registry, dependency DAG, current revision, `.forge/capabilities/registry.json`, `.forge/capabilities/qualifications.json`, the phase activation policy at `.forge/context/activation-policy.json`, lane leases, budgets, and acceptance registry. Route only when GSD reports the matching active execution stage, or for an explicitly read-only bootstrap job. Ignore `.forge/state/lifecycle.json`.
2. Finish or unblock in-flight work before opening avoidable new work.
3. Find ready work with satisfied hard prerequisites and disjoint write sets.
4. Keep design, gameplay, visual, audio, research, and QA lanes concurrent once their contracts exist.
5. Decide whether the task is safely decomposable. Keep unresolved design, novel architecture, cross-system integration, delicate mutation, and final synthesis on the resident host.
6. Apply hard filters and rank offload routes using [routing.md](../skills/forge-route-work/references/routing.md). Prefer a qualified free, local, or already-installed worker when resident-context, time, or lane savings exceed handoff and verification cost. Then record the decision:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py route --project <project-root> --request <request-path> --apply
   ```

   Run it without `--apply` first to read the decision. `--apply` writes it to `.forge/state/route-decisions.json` under the canonical work order, which is where step 10 reads it from. A decision that is not recorded cannot authorise an acquisition, so an unrun command here blocks step 10 rather than letting it proceed unchecked.
7. Apply the `required_tool_access` hard filter. Resolve every declared capability through `python <forge-plugin-root>/scripts/forge.py route-status --project <project-root>`. Dispatch a capability served by a typed tool route only to an agent declaring it, and only while its contract reports the route bound. Dispatch on the declared fallback when a route is unbound, and record which route was taken. Never dispatch a packet whose capability resolves to nothing.
8. For Unreal work, choose the route by the shape of the work, not by what happens to be running. The live typed route and the editor-closed API are peers on mutually exclusive lanes: `unreal_routing` in [route-policy.json](../dependencies/route-policy.json) says which shape belongs to which. Batch import, retargeting, asset audits, LOD generation, bulk property edits, null-RHI-safe work and anything unsafe inside the editor tick go to `lane.ue-editor-closed`; discoverable inspection, bounded scene and Blueprint mutation, PIE and viewport evidence go to `lane.ue-editor`. Neither is the other's fallback. For editor-closed work the result file is authoritative, never the exit code alone. Routing names the lane, lease and isolation mode its decision implies; take those into the packet rather than transcribing them, and treat a lease reported in no exclusive group as a misspelling rather than as protection. Taking one lane refuses the other, so never plan concurrent live and closed work on one project.

   Before taking `lane.ue-editor-closed`, read `ownership` on the route. `HELD` means an editor has the project: an MCP handshake answered, or an Unreal editor process holds this `.uproject`. `FREE` means neither is true and the lane is enterable. `UNDETERMINED` means process inspection could not answer, and the route reports `UNAVAILABLE_BLOCKING`: **stop and ask the user**. Do not take either lane, do not re-probe until it answers differently, and do not treat a silent MCP endpoint as proof the editor is closed — a frozen editor stops answering while still holding every file it has open, which is exactly when a commandlet would corrupt the project. Resolving the process check is the fix; the user decides what to do if it cannot be resolved.
9. Declare isolation in the packet, taking lane, lease and isolation mode from the registry row: a clean-base Git worktree for concurrent text and code writers, an LFS lock or project-exclusive lease for binary assets, read-only isolation for reviewers. Name the base revision explicitly. Declaring isolation is this step's whole job; establishing it belongs to step 10 and never to this workflow by hand.
10. Admit the packet to execution with one command, which is also the only way isolation is established:

    ```powershell
    python <forge-plugin-root>/scripts/forge.py dispatch --project <project-root> --packet <packet-path> --apply
    ```

    `dispatch` checks the packet against `forge.work-packet/v1`, proves every capability it declares is reachable *right now* rather than trusting what routing recorded, refuses when the routes available have drifted from the ones the decision was scored against, takes the leases and isolation, and records the order transition in `.forge/state/work-orders.json` — as one decision. Nothing is acquired unless every check passed, and nothing is recorded unless it was acquired, so there is no step between them for a check to be skipped in. Run it without `--apply` first to read the plan.

    `exec acquire` remains for taking leases alone, and applies the same routing checks: `python <forge-plugin-root>/scripts/forge.py exec acquire --project <project-root> --packet <packet-path> --apply`. It finds the decision step 6 recorded, by the packet's own work order, and refuses a packet declaring fewer leases than routing resolved, weaker isolation than it requires, or any lane while tool access is degraded. A work order with no recorded decision is refused as `route_decision_missing`, and a decision older than the freshness window in [route-policy.json](../dependencies/route-policy.json) as `route_decision_stale`, because the routes it scored can have swapped availability since; re-run step 6 rather than working around either. `--route <path>` overrides the lookup for a decision held elsewhere, and never relaxes it. It resolves the base revision, refuses a lane already held or held in the same exclusive group, creates the worktree, takes each `git lfs lock`, and rolls back every completed step if a later one fails. Run it without `--apply` first to read the plan. Treat a `lease_conflict` as binding: route the work elsewhere or wait. Never take a worktree or lock by hand, and never proceed past a refusal. This command is the only way isolation is established, so an unrun command means an unheld lease, whatever the packet says.
11. Resolve the work order through `.forge/state/packet-registry.json`. Reject unregistered IDs, preserve the canonical ID, treat aliases as display compatibility only, and require derived packets to name their parents.
12. Compile an immutable minimal work packet: canonical work order, GSD phase and plan, revision, task and complexity class, objective, non-goals, referrals, inputs, exact write scope, isolation, leases, capabilities, context budget, output contract, acceptance, verification, evidence, and invalidation hashes. Never forward the full GDD or the resident conversation. Check it against its contract before dispatching it, since a malformed packet is cheapest to catch before an agent has acted on it:

    ```powershell
    python <forge-plugin-root>/scripts/forge.py validate --kind work-packet --input <packet-path>
    ```

    Step 10 checks this contract again on the way in. Running it here is how a malformed packet is caught while it is still cheap to fix, rather than at admission.
13. Dispatch independent packets concurrently through the typed agent surface when it is available and authorized, stopping related local work while agents run. Record `DEGRADED_INLINE` when dispatch is unavailable; never describe inline work as delegated. Give the verifier the requirement, artifact or diff, acceptance, and evidence — never builder reasoning.
14. Require a structured attempt result separating observed facts, inferences, findings, touched artifacts, evidence, verification, residual risk, and next action. Check each returned result against `forge.attempt-result/v1` with `python <forge-plugin-root>/scripts/forge.py validate --kind attempt-result --input <result-path>` before acting on it; a result that omits its verification or evidence is not a result, and reading it as one is how an unverified claim enters the record. Dispatch build work to `gameplay-engineer`, visual work to `visual-developer` or `dcc-artist`, engine operation to `unreal-operator`, and research to `researcher`. Give verification to `independent-verifier`, never to the agent that produced the work.
15. Inspect actual artifacts before retry on failure. Substitute a second occupant before changing competence scores when the brief or tool may be defective. Use `forge-retrospective` for inconsistent or repeated failures.
16. Keep the lease alive while the work runs. Any job that can outrun the two-hour TTL — a cook, a mass retarget, a Nanite rebuild, a large import — must renew before it expires:

    ```powershell
    python <forge-plugin-root>/scripts/forge.py exec renew --project <project-root> --work-order <id> --apply
    ```

    A lease whose owner process is still alive is never taken away, so an unrenewed lease does not lose its lane on this machine. It is reported as `renewal_overdue` instead, which is a worker that stopped reporting rather than one that finished. Renew anyway: liveness is only checkable from the machine that took the lease, and a lease taken elsewhere is recovered once its grace window passes.
17. Persist transitions, deactivate packet-only surfaces, and release leases with `python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply`. A failed outcome discards the worktree; a passed one keeps it for merge. Read `lease_status` in the result: `RELEASED` means every external resource was freed, and `ORPHANED_EXTERNAL_LOCK` means an LFS lock or worktree survived, so the write scope stays quarantined and no writer may take the lane. Clear it, and never route around it:

    ```powershell
    python <forge-plugin-root>/scripts/forge.py exec reconcile --project <project-root> --work-order <id> --apply
    ```

    `reconcile` also recovers a lease left mid-release by a crashed session. A quarantined lane is Forge reporting external state it could not change, so the only ways out are reconciling it or freeing the resource by hand. Record every order transition in `.forge/state/work-orders.json` and stop at one of its declared terminal states. Resume from that file and from `forge.py exec status`, never from chat memory. A lease left held is recovered on expiry by the next acquire, so a crashed session blocks the lane only until then.
18. Run GSD's `execute-phase.md` for a phase whose plans need no typed tool route, while holding the leases from step 10. It owns wave scheduling, plan dispatch, and SUMMARY authorship. Release through step 16 afterwards, including on failure, and verify completion through GSD's own completion check.
19. Use `forge-capability-admin` to qualify or activate a route, and `forge-research` when no verified capability closes a required step. Block only the step that has no fallback.
