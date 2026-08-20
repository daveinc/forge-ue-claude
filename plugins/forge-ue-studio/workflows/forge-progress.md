<!-- forge:workflow
name: progress
consumes: .planning/ (authoritative for phase status), .forge/state/work-orders.json, .forge/state/leases.json, .forge/capabilities/qualifications.json
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
Add what `.planning` does not carry, read from `.forge/state/work-orders.json`:

| In the ledger | Report it as |
|---|---|
| An order resting at `DISPATCHED` | Still in flight, or abandoned by a session that never released — say which, from `supervision` |
| An order at `BLOCKED` | Not finished and not failed. Name its lane and its `human_action` |
| `ACCEPTED` / `REJECTED` | Closed. These are the only outcomes that mean work ended |
| `lane_exit` on a closed order | What a next session must do with that lane before planning onto it |

Then add the phases whose plans have no SUMMARY, from `.planning`.

`BLOCKED` is deliberately non-terminal: report it as resumable work, never as a failure.

> **Why:** CHANGELOG.md 0.7.0 § *An order that finished says so* — § *A failure inside a lane is a fact Forge holds*
</step>

<step name="report_capability_staleness" priority="last">
Read `.forge/capabilities/qualifications.json` and report every route whose evidence was recorded
under a host other than the one now assigned. Routing rejects such a route; a progress report should
say so before a phase is planned against it.

Name the remedy — requalify through `forge-capability-admin` — without performing it.
</step>

</process>
