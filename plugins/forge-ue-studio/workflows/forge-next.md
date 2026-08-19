<!-- forge:workflow
name: next
consumes: .planning/ (GSD snapshot), .forge/state/work-orders.json, .forge/state/leases.json, .forge/state/packet-registry.json, .forge/visual/registry.json
produces: one dispatch, and a supervision entry in .forge/state/work-orders.json recording holds_no_lane
never-reads: .forge/state/lifecycle.json (never used to override GSD, never mutated)
-->

# Forge Next — workflow

<purpose>
Bring the control plane to a state work can actually run in, then offer the next step this game
needs — and only the steps that are reachable from where the project currently stands.
</purpose>

<core_principle>
Never infer state from the conversation, and never perform the routed work here. An action Forge has
not checked is reachable is not an action Forge offers; presenting one is how a session discovers a
held lane by colliding with it.
</core_principle>

<process>

<step name="detect" priority="first">
1. Resolve the current project root. Never infer state from the conversation.
2. Run the read-only detector:

   ```powershell
   python <forge-plugin-root>\scripts\forge.py next --project <project-root>
   ```

3. Parse the `forge.smart-entry/v1` result. `situation`, `actions`, `signals`, `execution_coverage`,
   `warnings` and `suppressed_actions` are the whole input to every step below.
4. Treat `.planning` and the GSD snapshot as authoritative for phase status. Never use
   `.forge/state/lifecycle.json` to override GSD, and never mutate it.
5. Present commands from `actions` verbatim; they are already spelled for the assigned host.
6. Surface every `warnings` entry verbatim, then continue. Put a partially executed phase from
   `execution_coverage` to the user as a question, never as an error.
7. On detector failure, run `forge-doctor`. Never guess the active phase.

> **Why:** CHANGELOG.md 0.4.0 § *`forge-next` stops offering choices that are not choices*
</step>

<step name="reach_working_state">
Four situations are not a menu. Route each and **stop** — nothing below applies until the control
plane can hold work.

| `situation` | Route | Why nothing else can be offered |
|---|---|---|
| `forge-not-adopted` | `forge-bootstrap` | There is no `.forge`, so no lane, lease or route exists to check an action against |
| `host-surfaces-stale` | `forge-runtime` | The rendered surfaces do not match `.forge` canon, so a command spelled from them may not be the command that runs |
| `forge-bootstrap-incomplete` | `forge-bootstrap --resume` | Capability evidence is unfinished; every reachability answer below would be a guess |
| `gsd-unavailable` | `forge-doctor` | Phase state has no authority, and Forge does not substitute its own |

Otherwise confirm the state below the detector is readable before trusting it:

```powershell
python <forge-plugin-root>/scripts/forge.py verify --project <project-root>
```

`state_version` `NEWER` means `.forge` was written by a newer Forge — **do not operate on it**;
upgrade Forge. `MIGRATABLE` means the listed migrations run before any action is offered. A `checks`
entry reading `MISSING` is re-applied through `forge-bootstrap`, never by hand.

> **Why:** CHANGELOG.md 0.6.0 § *`.forge` state has a version that means something*
</step>

<step name="enter_lane_system">
Enter the lane system before deciding what to offer, and declare that this run takes nothing:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-next --apply
```

Naming no `--lane` records `holds_no_lane` — a launcher that dispatches and stops legitimately holds
nothing, and saying so is what distinguishes it from a workflow that never considered the question.
The same call recovers every lease whose owner exited, which is the difference between a lane that is
free and a lane that only looks free.

What comes back is an input to `check_reachability`, not a report to skip past:

| In the report | What it costs an action |
|---|---|
| `quarantined` | A holder exited without freeing an LFS lock. Every action that would write that lane is unreachable until `exec reconcile` runs |
| `interrupted_release` | A session died mid-release. Same answer, same remedy |
| `abandoned_workspaces` | A dead worker's worktree survives with uncommitted work. The lane is free; the workspace is a human action to name, not a blocker to route around |
| `renewal_overdue` | The owner is alive and past its TTL. Work is running — offer nothing that contends with it |

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="check_reachability">
Check every candidate action against state before it reaches the user. This is a Forge-side check on
lanes, leases and routes; it never second-guesses GSD's phase logic, which stays authoritative.

```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

```powershell
python <forge-plugin-root>/scripts/forge.py route-status --project <project-root>
```

Then read `.forge/state/work-orders.json` directly for what neither command reports:

| Read | Makes an action unreachable when |
|---|---|
| `exec status` → `active`, `lane_groups` | The action's lane, or any lane in its exclusive group, is held right now |
| `exec status` → `quarantined` | An external resource survived a release on that lane. `exec reconcile --work-order <id> --apply` is the only way out, and it is `forge-route-work`'s to run |
| `route-status` → `routes[].status`, `routes[].capabilities` | A capability the action needs resolves to no bound route and the row names no fallback |
| `work-orders.json` → `orders[]` at `DISPATCHED` | Work is in flight on that order. Finishing or unblocking it comes before opening more |
| `work-orders.json` → `orders[]` at `BLOCKED` | The order carries a `human_action`. Present that, not the action that would fail again |
| `work-orders.json` → `blocked_lanes[<lane>].consecutive` | The breaker has counted repeated failed entries into that lane. Offering it again is how a loop starts |
| `work-orders.json` → `orders[]` at `ACCEPTED` or `REJECTED` | Nothing — these are the terminal states, and an order resting here is finished, not running |

An action that fails any of these is still shown, and shown as unreachable, with the state that
blocks it and the remedy named. Never present it as a choice, and never silently drop it — a
disappeared action reads as work that was never needed.

> **Why:** CHANGELOG.md 0.7.0 § *A failure inside a lane is a fact Forge holds* — § *An order that finished says so*
</step>

<step name="offer_next_step">
**Skip if:** `situation` is `greenfield-ready` — there is no game state yet, and `forge-init` is the
whole answer.

Order what remains by what this game needs next, not by what the detector happened to list first:

1. **Drain what is in flight.** A `DISPATCHED` order or a live lease is work someone started. Finish
   or unblock it before opening avoidable new work.
2. **Clear what is blocked.** A `BLOCKED` order's `human_action`, a quarantined lane, an abandoned
   workspace. These do not clear themselves and they block everything routed onto that lane.
3. **Finish the partially executed phase.** `execution_coverage` names each phase whose plans lack
   summaries, and GSD does not block completion on it. A phase at `partial` is the strongest
   candidate for the next step, and it is put to the user as a question.
4. **Take GSD's recommended action.** For a project with planning state, the `recommended` action
   from the snapshot is the schedule speaking, and the schedule is GSD's.
5. **Close the skeleton.** Read `.forge/state/packet-registry.json` for canonical production packets
   with no phase covering them, and `.forge/visual/registry.json` → `asset_interfaces` for a
   contract nothing has produced against yet. Either is a gap between what the game was designed to
   need and what has been built, and it is the answer when the roadmap has run out but the skeleton
   has not.

Where the step ahead is Unreal work, name what it will take before offering it:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
```

`lanes` and `packets` say whether that step is one packet or two, and `capabilities` is what
`check_reachability` weighed the routes against. A `null` procedure means no doctrine covers the
shape — offer it, and say it will be planned unprocedured.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The procedure layer*
</step>

<step name="present_and_dispatch">
1. Show the summary and ordered actions, recommended first, with the unreachable ones grouped below
   them and each carrying its blocking state.
2. List `suppressed_actions` below the Forge actions as available in GSD, each with its reason and
   its `run_directly` spelling. Never present one as a routed action.
3. Let the user select unless `--auto` was supplied. Print a numbered list and stop for a reply when
   no interactive question tool exists.
4. Display the chosen command before dispatch.
5. Dispatch exactly one skill, then stop.
6. Never perform the routed work here, and never chain a second command.
7. Run a GSD command directly when the user asks for one, after naming what the Forge route would
   have added.
8. Refuse to dispatch an action `check_reachability` marked unreachable, including under `--auto`.
   Present its remedy instead and stop.
</step>

<step name="forge_init_integration" priority="last">
1. Return control to Forge Init when the recommended command is `forge-init`. Never invoke Forge Init
   recursively.
2. Otherwise dispatch the recommended action and stop Forge Init.
3. Route an incomplete Forge control plane through `forge-bootstrap` or `forge-bootstrap --resume`
   before any design or production work.
</step>

</process>
