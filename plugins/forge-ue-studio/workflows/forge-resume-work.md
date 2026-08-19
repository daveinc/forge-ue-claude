<!-- forge:workflow
name: resume-work
consumes: .forge/jobs/<work-order>/, .forge/state/work-orders.json, .forge/state/leases.json, .forge/runtime.json, doctrine/procedures.json
produces: recovered lane leases, a supervision entry in .forge/state/work-orders.json, and the reopened job folder handed to whoever continues
never-reads: .forge/state/lifecycle.json (deprecated history)
-->

# Forge Resume Work — workflow

<purpose>
Restore an interrupted session from disk to the point the interrupted worker was actually standing
at, then hand that point to whoever continues.
</purpose>

<core_principle>
The job folder is the restore point. `.forge/jobs/<work-order>/` holds what the worker was handed —
brief, packet, context packages, result — so it is stronger evidence than any handoff record, which
is what someone remembered to write down. Take routing from persisted state, never from what the
previous session said.
</core_principle>

<process>

<step name="detect" priority="first">
```powershell
python <forge-plugin-root>/scripts/forge.py next --project <project-root>
```

Route and **stop** on `forge-not-adopted`, `forge-bootstrap-incomplete` and `host-surfaces-stale` —
there is nothing to resume into until the control plane is current. On `gsd-unavailable`, run
`forge-doctor`: the job folders below can still be read, but nothing can be restarted against a
phase state that has no authority.

> **Why:** CHANGELOG.md 0.4.0 § *`forge-next` stops offering choices that are not choices*
</step>

<step name="read_machine_state">
The machine may not be the machine that was interrupted. Two commands answer that; neither is the
handoff record.

```powershell
python <forge-plugin-root>/scripts/forge.py host status --project <project-root>
```

`active_host` is who is running now and `history` is every assignment `.forge/runtime.json` has
recorded. A host change since the interrupted work was dispatched makes its qualification evidence
stale: re-probe through `forge-capability-admin` before any offload route, and never carry a
qualification across a host swap. `surfaces` reading `STALE` or `MISSING` is `forge-runtime`'s.

```powershell
python <forge-plugin-root>/scripts/forge.py verify --project <project-root>
```

`state_version` `NEWER` means `.forge` was written by a newer Forge — **stop and upgrade** rather
than resuming against state this Forge cannot read. `MIGRATABLE` means the listed migrations run
first.

> **Why:** CHANGELOG.md 0.6.0 § *`.forge` state has a version that means something*
</step>

<step name="find_the_interruption">
`.forge/state/work-orders.json` says what was happening when the session ended. Read it by status —
the file declares its own `terminal_states`, and everything else is unfinished:

| Status | What it means | What resume does with it |
|---|---|---|
| `DISPATCHED` | The order was admitted and never released. This is the interruption | Reopen its job folder. There may be more than one |
| `BLOCKED` | Admission refused on a lane whose ownership could not be settled | Present its `human_action`. Never re-attempt the same entry to see if it works this time |
| `ACCEPTED`, `REJECTED` | Terminal. The order finished and said so | Carry it forward as history. Read `lane_exit` for what it left the lane in |

Then read two more keys in the same file:

- `supervision` — the last entries name which workflow declared what, including a run that declared
  `holds_no_lane`. This is where the previous session's intent is recorded rather than remembered.
- `blocked_lanes` — a `consecutive` count against a lane means repeated failed entries. Resuming
  into it is how a loop restarts.

An order at `DISPATCHED` whose worker died leaves no `result.json` and no release. That is the case
this workflow exists for; a clean `ACCEPTED` order needs no resuming.

> **Why:** CHANGELOG.md 0.7.0 § *An order that finished says so* — § *A failure inside a lane is a fact Forge holds*
</step>

<step name="reopen_the_job">
Open `.forge/jobs/<work-order>/` for every order `find_the_interruption` returned. It is keyed on the
canonical work order and nothing above it, so one order has exactly one folder.

| File | What it restores |
|---|---|
| `brief.md` | What the worker was actually reading: objective, `Opened by`, ordered steps with their capability, the tool and route table as it resolved at dispatch, non-goals, acceptance, verification, evidence |
| `packet.json` | The `forge.work-packet/v2` — task class, revision, write scope, isolation mode and base revision, leases, context budget, `invalidation_hashes` |
| `context/*.json` | One file per referral. This is what was handed over, so a thin brief is a checkable claim rather than a suspicion |
| `result.json` | Present only if a release filed one. `result_source: release-observation` means the release wrote what it observed and the worker returned nothing |

Hand the folder itself to whoever continues, never a summary of it. Re-read what the packet says
before trusting it:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind work-packet --input <project-root>/.forge/jobs/<work-order>/packet.json
```

A folder with no lease behind it is a dispatch that was refused, kept on purpose as the record of
what was attempted. It grants nothing — `.forge/state/leases.json` remains the only authority on
what is held.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The job tree*
</step>

<step name="recover_lanes">
Declare the lanes the interrupted orders were working in, taken from each order's `lanes` field and
each packet's `leases`:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-resume-work --lane <lane> --apply
```

`--lane` is repeatable. Declaring them is what recovers a lease whose owner exited and reports what
that owner left standing. **This run takes no lease of its own** — the lease is taken again by
`dispatch` when `forge-route-work` re-admits the packet. When no interrupted order names a lane,
declare none, and `holds_no_lane` is recorded for this run rather than silence.

| Answer | What it means | Action |
|---|---|---|
| `enterable` | Nothing holds the lane | The work can be resumed there |
| `blocked` | A live holder has it | Someone else is working. Resume elsewhere or wait — never take it anyway |
| `renewal_overdue` | The owner is alive and past its TTL | The interrupted session is not dead. Leave it alone |
| `quarantined` | A holder exited without freeing an LFS lock | Nothing may be resumed onto that lane until it is reconciled |
| `interrupted_release` | A session died mid-release | Same answer; `exec reconcile` is the only thing that frees it |
| `abandoned_workspaces` | A dead worker's worktree survives with uncommitted work | The lane is free. Salvage the workspace by hand before it is overwritten — it holds work no result file records |

A refusal reading `lane_abandoned` is not `lease_conflict`: nobody is working, someone died holding
it, and Forge could not return the lane to a clean state on its own.

```powershell
python <forge-plugin-root>/scripts/forge.py exec reconcile --project <project-root> --work-order <id> --apply
```

Read `.forge/state/leases.json` for anything the supervisor did not resolve. An `ACTIVE` lease past
its `expires_at` whose owner is gone is recovered by the sweep above; one inside its window needs an
explicit decision before you touch it. Never delete a lease by hand.

> **Why:** CHANGELOG.md 0.7.0 § *A lane a worker died in is not a lane Forge reports as free* — § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="confirm_editor_state">
**Skip if:** no reopened packet declares an Unreal lane.

```powershell
python <forge-plugin-root>/scripts/forge.py route-status --project <project-root>
```

The `unreal-python` row's `ownership` is what says whether an editor holds this `.uproject` right
now: `HELD` means it does and the editor-closed lane is not takeable, `FREE` means neither an MCP
handshake nor a process claims it, and `UNDETERMINED` means ownership could not be settled and
`blocked_lane.posture` decides. Never read a silent endpoint as a closed editor — check
`endpoint_disagreement` and `engine_settings` on the row first.

Compare the routes reachable now with the tool and route table `brief.md` recorded at dispatch. A
route that has since become unbound invalidates the steps that named it; those steps are recompiled
through `forge-route-work`, not improvised around.

> **Why:** CHANGELOG.md 0.6.0 § *A silent editor is not a closed editor* — § *An editor answering is not this project's editor answering*
</step>

<step name="check_context_still_holds">
A restored packet is only resumable if what it was built from still stands.

- `invalidation_hashes` in `packet.json`: any input that has changed since dispatch invalidates the
  packet. Send it back through `forge-route-work` to be recompiled — never resume a packet whose
  inputs moved under it.
- The procedure it was built from may have changed since the job was written:

  ```powershell
  python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
  ```

  Compare its `steps`, `acceptance`, `verification` and `evidence` with what `brief.md` carries. A
  difference means the brief is stale doctrine, and the procedure wins. A `null` procedure means the
  job was improvised when it was opened, which the order's `procedure.procedured: false` already
  records — resume it knowing that.
- The design context the remaining steps need: `.planning/` for the phase this order belongs to, and
  the design corpus `signals.design_sources` named at `detect`. Where the corpus does not answer what
  a remaining step requires, route it to `forge-discuss-phase`, or `forge-ingest-docs` when the
  answer exists in documents Forge has not read. Never invent the answer to resume faster.
</step>

<step name="run_gsd_resume">
**CORE — GSD's workflow, unmodified.** Run GSD's resume workflow. It owns phase state and decides
where work restarts.

Give it the reopened job folder as the working context, not a retelling of it. Forge supplies what
the interrupted work consisted of and what state it left behind; GSD decides which phase and plan
that resumes.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *What crosses, and in which direction*
</step>

<step name="hand_off" priority="last">
```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

Nothing may remain `quarantined`, and no lease may be held by this run. Then take the next action
from the detector rather than from this workflow's own reasoning:

```powershell
python <forge-plugin-root>/scripts/forge.py next --project <project-root>
```

Hand control to the action it recommends and **stop**. Where the resumed order still needs
dispatching, that action is `forge-route-work`, which re-admits the packet and takes the lease this
workflow deliberately did not.

Exit paths that are not a hand-off: a `NEWER` `state_version` stops at `read_machine_state`; an
abandoned or quarantined lane stops at `recover_lanes` with `exec reconcile` named; an invalidated
packet stops at `check_context_still_holds` and goes to `forge-route-work` to be recompiled.
</step>

</process>
