<!-- forge:workflow
name: quality-gate
consumes: .forge/jobs/<work-order>/ (brief.md, packet.json, result.json), .forge/acceptance/registry.json, .forge/config.json (human_gates), plugins/forge-ue-studio/doctrine/procedures.json, the route contract
produces: a forge.attempt-result/v1 with findings ordered by severity
-->

# Forge Quality Gate — workflow

<purpose>
Grade work that has come back — against the evidence it was required to produce, not against the
account it gave of itself — and return a typed attempt result.
</purpose>

<core_principle>
Never let a review finding grant permission to apply its own fix. Never replace a human decision on
primary art direction, likeness, appeal, game feel or release.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Grading is read-only. A grader that holds a write lease is a builder:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-quality-gate --apply
```

Naming no `--lane` records `holds_no_lane` against this run. Read `quarantined` and
`abandoned_workspaces`: an artifact produced in a lane whose owner died may be half-written, and that
changes what the evidence proves.
</step>

<step name="read_the_job_folder">
Read `.forge/jobs/<work-order>/`, which holds what was actually asked and what actually came back:

| File | What it settles |
|---|---|
| `brief.md` | The objective, ordered steps, acceptance, verification and evidence as rendered at dispatch — not as remembered |
| `packet.json` | The declared write scope, isolation, leases and capabilities. A change outside `write_scope` is a finding regardless of quality |
| `context/` | Exactly what the worker was handed. "The brief was thin" is checkable here rather than a suspicion |
| `result.json` | The worker's own `forge.attempt-result/v1` |

A `result.json` marked `result_source: release-observation` means the worker filed nothing and the
release recorded what it observed. Grade that as evidence absent, not as evidence weak.

Read builder reasoning **only** when investigating a failure, and only after the independent pass has
returned.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The job tree*
</step>

<step name="grade_against_doctrine_not_improvisation">
Read what this shape of work owed:

```powershell
python <forge-plugin-root>/scripts/forge.py procedure --task-class <task-class>
```

Compare the returned work against `steps[].produces`, `acceptance`, `verification` and `evidence`.
A step that produced nothing is a finding even when the build is green — the step whose absence fails
no build is exactly the one improvisation drops.

Where `procedure` is `null`, or the packet recorded `procedure.procedured: false`, say the work was
graded against improvised criteria. That is a weaker verdict, and it should read as one.
</step>

<step name="select_test_layers">
Select the smallest sufficient set from: schema/static, unit, contract, integration,
editor/commandlet, PIE/runtime, asset structural, performance, cook/package, platform, visual, human
subjective.

Smallest sufficient, not most. A layer that cannot fail for this change adds runtime and no signal.
</step>

<step name="audit_what_passing_hides">
Audit the classes of defect a green result does not exclude: missing regression coverage, boundary
compatibility, bad-input behaviour, idempotency, rollback, stale asset references, and whether a
seeded-bad input is actually rejected.

For Unreal work specifically: a commandlet's exit code is not the authority — the result file is. A
pass that exited zero having failed to load assets is the common shape here.
</step>

<step name="run_fresh_verification">
Run verification commands fresh, or inspect fresh tool-produced evidence. Never grade on evidence
captured before the change.

Separate, and keep separate: observed facts, inferences drawn from them, uncertainties, and residual
risk. A gate that merges the four returns a confident verdict about something it did not observe.
</step>

<step name="run_gsd_gap_fillers">
**Skip if:** neither gap-filling nor test generation was asked for.

Run GSD's `validate-phase.md` to fill validation gaps for a completed phase, and `add-tests.md` to
generate tests from its UAT criteria. Require a structured result from each and grade it through the
steps above — a generated test suite is returned work like any other.
</step>

<step name="return_the_contract" priority="last">
Return the attempt-result contract from
[result-contract.md](../skills/forge-quality-gate/references/result-contract.md), findings ordered by
severity, and check it before returning it:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind attempt-result --input <result-path>
```

A result that omits its verification or evidence is not a result.

Accept only when every required criterion has current evidence **and** every required human gate in
`human_gates` in `.forge/config.json` is signed. Never sign one here.

On `FAIL`, `PARTIAL`, `BLOCKED` or `INDETERMINATE`: preserve the attempt, leave `result.json` in the
job folder, and route the next action through `forge-route-work` or `forge-retrospective`. Never
apply the fix for a finding raised in the same pass.
</step>

</process>
