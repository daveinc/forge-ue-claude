<!-- forge:workflow
name: milestone
consumes: .planning/ phase verification results, forge.py exec status (orders, blockers, blocked_lanes, terminal_states), .forge/acceptance/registry.json, .forge/capabilities/qualifications.json, the GDD decision ledger
produces: milestone artifacts (GSD's), plus the unresolved decisions, blocked lanes and unqualified routes carried into the next one
-->

# Forge Milestone — workflow

<purpose>
Open, close, audit or summarise a milestone — and make sure nothing Forge is holding gets archived
as if it were finished.
</purpose>

<core_principle>
GSD's phase status says the plans ran. It does not say the lanes are clean or the orders are closed.
A milestone completed over an order still in flight buries it.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Milestone administration writes planning artifacts, not game assets. But it must know what the lanes
are doing before it archives anything:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-milestone --apply
```

Naming no `--lane` records `holds_no_lane` against this run, and the same call reports what a dead
owner left standing. Anything under `quarantined` or `interrupted_release` is unfinished work — it
blocks `--complete` and belongs in the audit.
</step>

<step name="check_the_orders_closed">
**Skip if:** the mode is `--new`.

```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

Every order belonging to a phase in this milestone must rest at one of the payload's
`terminal_states`. `blockers` names the ones that do not:

| `kind` | Milestone verdict |
|---|---|
| — (order at `ACCEPTED` / `REJECTED`) | Closed. Carry the outcome into the summary |
| `order_dispatched` | **Not finished.** Either work is still running, or a session died without releasing. Resolve it before completing |
| `order_blocked` | Non-terminal by design. Carry it forward with its `remedy` rather than archiving it |
| `lane_quarantined` / `release_interrupted` / `lane_breaker` | Unfinished lane state. It belongs in the audit and it blocks `--complete` |

An order left at `DISPATCHED` forever is indistinguishable from work still running, so a milestone
that archives one loses it.

> **Why:** CHANGELOG.md 0.7.0 § *An order that finished says so*
</step>

<step name="confirm_verification">
**Skip if:** the mode is `--new`.

Confirm every phase in the milestone passed verification, and that its acceptance suites in
`.forge/acceptance/registry.json` have current evidence rather than evidence from before the last
change. A green plan status is not a verified phase — `forge-verify-work` owns that predicate.
</step>

<step name="run_gsd_milestone">
Run the matching GSD workflow for the requested mode: `--new`, `--complete`, `--audit`, or
`--summary`. GSD owns the archive, the version bump, PROJECT.md and the summary document.
</step>

<step name="carry_forward" priority="last">
Four things do not archive with the milestone, and each must be explicitly carried into the next:

| Carried | Read from | Why it cannot be dropped |
|---|---|---|
| Unresolved GDD decisions | The GDD decision ledger | A deferral that stops being visible is re-decided differently next milestone |
| Unqualified or stale capability routes | `.forge/capabilities/qualifications.json` | Qualification is host-scoped; a route qualified under a retired host is not qualified |
| Blocked lanes and quarantines | `blocked_lanes` and the lane `blockers` from `exec status` | A quarantined lane is not enterable by the next milestone either |
| `order_blocked` orders | `blockers` from `exec status` | They are resumable work, not failures |

Never close a milestone by marking any of these resolved. Carrying an unresolved item forward is the
honest close; resolving it to make the archive tidy is how the next milestone inherits a lie.
</step>

</process>
