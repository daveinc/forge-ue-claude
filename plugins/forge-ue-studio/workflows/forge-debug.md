<!-- forge:workflow
name: debug
consumes: Saved/Logs/, Saved/Crashes/, PIE output, the reproduction lane, .forge/learnings/registry.json
produces: a root cause with its reproduction lane named, and a quarantined entry in .forge/learnings/registry.json
-->

# Forge Debug — workflow

<purpose>
Find why an Unreal project misbehaves, and record *where* it misbehaves — because in Unreal the lane
a bug reproduces on is half the bug.
</purpose>

<core_principle>
Editor-open behaviour is not evidence about a packaged build. A fix accepted on the lane that is
easiest to test is a fix accepted on the wrong lane.
</core_principle>

<process>

<step name="collect_evidence_before_hypothesising" priority="first">
Read the artefacts before forming a theory, each by name:

| Evidence | Where |
|---|---|
| Crash dumps and callstacks | `Saved/Crashes/` |
| Editor and game logs, including the run that failed | `Saved/Logs/` — the current log and the `-backup-` rotation beside it |
| PIE output | The Output Log for the session that reproduced it |
| Cook and package failures | The build log for the target platform, not the editor log |

A log the user pasted is a quotation. Read the file.
</step>

<step name="name_the_reproduction_lane">
State which lane reproduces it, before anything is fixed:

| Lane | What a reproduction there proves |
|---|---|
| Editor open (`ue-live-native-mcp`, `ue-live-python`, `human-editor`) | It happens under PIE with editor-only subsystems live. It says nothing about a build |
| Editor closed (`ue-editor-closed-api`) | It happens in a commandlet with no rendering device and no editor tick. The cleanest signal, and the narrowest |
| Packaged build | It happens in what ships. The only lane whose result is about the product |

A bug that reproduces on one lane and not another is a finding, not a failed attempt — record which
lanes were tried and what each returned.
</step>

<step name="take_the_reproduction_lane">
Reproducing takes the lane it reproduces on, and the Unreal lanes are mutually exclusive through the
project super-lock:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-debug --lane <reproduction-lane> --apply
```

Use the lease name for the route: `ue-live-native-mcp`, `ue-live-python`, `ue-editor-closed-api` or
`human-editor`. A `blocked` answer means someone is working in the editor — a reproduction attempted
anyway is measuring their state, not the bug.

For a read-only pass over logs alone, name no `--lane`; `holds_no_lane` is recorded, and it is the
honest answer for a run that only reads `Saved/`.

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="run_gsd_debug_cycle">
Relay GSD's debugging cycle. It owns hypothesis tracking, the session state that survives a context
reset, and the checkpoint loop. Forge supplies the evidence set and the lane; GSD supplies the method.
</step>

<step name="verify_the_fix_on_the_lane_that_matters">
Re-verify on the narrowest lane the fix can be proven on, and on the lane the bug was reported from.

Reproduce editor-closed wherever the shape of the work allows it — a commandlet run is deterministic
and repeatable, and a PIE session is neither. Never promote a fix verified only in the editor to a
claim about a packaged build; say which lane the verification ran on.
</step>

<step name="release_and_record" priority="last">
Release the reproduction lane, including when the bug was not found:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```

An abandoned debugging session that keeps the editor lane blocks every other department.

Promote a confirmed root cause into `.forge/learnings/registry.json` only after repeated
evidence-backed success under a declared scope, and record the reproduction lane as part of that
scope. A learning that does not say which lane it was proven on will be applied to the lane it is
false for.

Keep failed attempts and contradictory evidence in the record. Use `forge-retrospective` when the
same failure recurs after a fix was accepted.
</step>

</process>
