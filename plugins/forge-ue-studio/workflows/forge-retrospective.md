<!-- forge:workflow
name: retrospective
consumes: forge.py exec status (orders, supervision, blockers, blocked_lanes, jobs), .forge/state/route-decisions.json, .forge/jobs/<work-order>/, .forge/capabilities/qualifications.json, .forge/reviews/registry.json, .forge/acceptance/registry.json, revision history
produces: a forensic report, and quarantined entries in .forge/learnings/registry.json
-->

# Forge Retrospective — workflow

<purpose>
Find out what actually happened when work failed — read-only, from state rather than from anyone's
account of it — and turn what it taught into a learning record that survives the session.
</purpose>

<core_principle>
Never repair during the forensic pass, and never give the pass to the agent that produced the work
under investigation.
</core_principle>

<process>

<step name="freeze_and_declare_no_lane" priority="first">
Stop repair work before anything is read. A forensic pass over a tree someone is fixing measures the
fix.

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-retrospective --apply
```

Naming no `--lane` records `holds_no_lane` — and here that is a finding as much as a declaration:
this workflow must never take a lane, because taking one changes the state it exists to observe.

What comes back is evidence in its own right. `quarantined`, `abandoned_workspaces` and
`interrupted_release` each name a session that died holding something, which is one of the failure
shapes below.

> **Why:** CHANGELOG.md 0.7.0 § *A lane a worker died in is not a lane Forge reports as free*
</step>

<step name="read_the_state_not_the_story">
Start with the joined answer rather than opening four files and correlating them by hand:

```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

| In the payload | What it answers |
|---|---|
| `orders` | What was dispatched, what state each rests at, its `lanes`, `lease_status` and `lane_exit` |
| `supervision` | Every run that declared what it held — including the ones that declared `holds_no_lane` |
| `blockers` | The join: each entry's `kind`, `lane`, `work_order`, `detail` and `remedy` |
| `blocked_lanes` | Consecutive failed entries per lane, and which tripped the breaker |
| `jobs` | Every job folder on disk with whether `brief`, `packet`, `result` and `context` are present — including a folder whose acquisition failed, which the ledger does not know about |
| `active`, `quarantined`, `interrupted_release` | What was held, by whom, and what survived teardown |
| `terminal_states` | Which statuses mean the work ended, so nothing else is read as finished |

A job folder with a `brief` and no `result` is a worker that was handed something and returned
nothing. That is the single most diagnostic row in the payload.

Then open what only a file answers:

| Source | What it answers |
|---|---|
| `.forge/jobs/<work-order>/brief.md` and `context/` | What the worker was actually handed, as rendered at dispatch |
| `.forge/jobs/<work-order>/result.json` | What came back. `result_source: release-observation` means the release wrote what it observed because the worker filed nothing |
| `.forge/state/route-decisions.json` | Which route the work was scored onto, and when |
| `.forge/capabilities/qualifications.json` | Whether that route's evidence was current, and under which host |
| `.forge/reviews/registry.json` | Whether a review had already raised this |
| Revision history | What was written, and whether it stayed inside the packet's `write_scope` |

Read all of it before reading anyone's summary. The summary is what the failing session believed; the
ledger is what it did.
</step>

<step name="detect_the_known_shapes">
Look for each of these explicitly rather than waiting for one to be obvious:

stuck loops · missing artifacts · partial-plan drift · abandoned work · interruption ·
scope drift · undeclared writes · stale capability evidence · test regression · broken handoffs

Three are proved outright by what `read_the_state_not_the_story` returned: an `order_dispatched`
blocker with no matching `lane_held` is abandoned work; a write outside `packet.json`'s `write_scope`
is an undeclared write; a route whose qualification names a retired host is stale capability evidence.
</step>

<step name="ground_every_anomaly">
Ground every anomaly in specific evidence — a file, a line, a ledger entry, a revision.

Mark a root cause as a **hypothesis** whenever the proof is incomplete, and say what would confirm
it. A hypothesis promoted to a cause because it was the only one considered is how the same failure
recurs after a fix.

Redact secrets. Never persist a credential value into the report.
</step>

<step name="write_the_report">
Write the forensic report with: evidence summary, confidence, likely cause, ruled-out causes,
untested explanations, and recommended actions.

Give the pass to `forensic-investigator`, never to the agent that produced the work under
investigation. **Never repair during the forensic pass** — a repair changes the evidence for every
question not yet asked.
</step>

<step name="extract_learnings">
**Skip if:** this is a live incident with no accepted phase or resolved outcome yet.

Run GSD's `extract-learnings.md` after an accepted phase or a resolved incident, then shape its
result into atomic learning records using
[promotion.md](../skills/forge-retrospective/references/promotion.md).

Own the forensic pass natively; run only the extraction through GSD. GSD has no view of leases,
routes or lanes, which is where most of what went wrong here lives.
</step>

<step name="quarantine_before_promoting">
Write new records into `.forge/learnings/registry.json` **quarantined**.

`learning.promotion_requires_repeated_success` and `learning.minimum_independent_passes` in
`.forge/config.json` govern promotion: a recipe leaves quarantine only after that many independent
successes under a declared scope. `learning.failed_attempts_remain_visible` is `true` — retain failed
attempts and contradictory evidence rather than curating the record into a clean story.

Record the scope a learning is true within, including the lane it was proven on. A learning with no
lane in its scope will be applied to the lane it is false for.
</step>

<step name="invalidate_on_change" priority="last">
Mark learning stale after a relevant environment, engine, provider, schema, hardware or workflow
change. A recipe proven against a previous engine version is a hypothesis again.

Keep production metrics in canonical JSON — `production_scorecards.canonical_format` in
`.forge/config.json`. Generate a derived XLSX or CSV scorecard on request, verify it visually, and
never let the spreadsheet become the source of truth; `exports_are_derived` says so.
</step>

</process>
