<!-- forge:workflow
name: progress
consumes: .planning/ (authoritative for phase status), forge.py exec status (orders, blockers, jobs, supervision), .forge/capabilities/qualifications.json
produces: .forge/state/work-orders.json (the supervision log only) — never phase state
-->

# Forge Progress — workflow

<purpose>
Report where this game actually stands: GSD's phase status, plus the two things GSD cannot see —
work orders that never closed, and capability evidence that went stale.
</purpose>

<core_principle>
Reporting only. Never mutate phase state from this verb, and never infer progress from conversation
memory when a state file answers the question.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
A progress report reads and never writes production state, so it holds no lane. Record that rather
than staying silent:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-progress --apply
```

Naming no `--lane` records `holds_no_lane` against this run. The same call reports anything a dead
owner left standing — `quarantined`, `abandoned_workspaces`, `interrupted_release` — which belongs in
a progress report because it is work that will not finish on its own.

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="report_phase_status">
Run GSD's progress reporting. `.planning` is authoritative for phase status and Forge never
contradicts it.
</step>

<step name="report_execution_coverage">
Add what `.planning` does not carry. One call answers all of it — do not open the ledger by hand:

```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

`blockers` is the report. Each entry names what holds, what it holds and the remedy that clears it:

| `kind` | Report it as |
|---|---|
| `order_dispatched` | Admitted and never released. Still running, or abandoned — `supervision` says which |
| `order_blocked` | Not finished and not failed. The entry's `remedy` is the order's own `human_action` |
| `lane_held` | A live owner is working. Not a fault |
| `renewal_overdue` | The owner is alive and past its TTL. Not a fault — do not disturb it |
| `lane_quarantined` / `release_interrupted` | Work that will not finish on its own. `exec reconcile` is the exit |
| `lane_breaker` | Entry into that lane has failed enough times running that Forge stopped offering it |

An order at a `terminal_states` value — `ACCEPTED` or `REJECTED` — is finished and is deliberately not
a blocker. `lane_exit` on such an order says what a next session must do with its lane.

`jobs` lists every job folder on disk with whether its `brief`, `packet`, `result` and `context` are
present. A folder with a brief and no result is work someone was handed and never returned.

Then add the phases whose plans have no SUMMARY, from `.planning`.

`order_blocked` is deliberately non-terminal: report it as resumable work, never as a failure.

> **Why:** CHANGELOG.md 0.7.0 § *An order that finished says so* — § *A failure inside a lane is a fact Forge holds*
</step>

<step name="report_capability_staleness" priority="last">
Read `.forge/capabilities/qualifications.json` and report every route whose evidence was recorded
under a host other than the one now assigned. Routing rejects such a route; a progress report should
say so before a phase is planned against it.

Name the remedy — requalify through `forge-capability-admin` — without performing it.
</step>

</process>
