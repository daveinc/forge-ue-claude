<!-- forge:workflow
name: review
consumes: .forge/acceptance/registry.json, .forge/capabilities/qualifications.json, .forge/visual/registry.json, .gitattributes, the active phase plan
produces: .forge/reviews/registry.json
-->

# Forge Review — workflow

<purpose>
Front GSD's review workflows with Forge's acceptance grading, route qualification and cycle record.
</purpose>

<core_principle>
Never pass builder reasoning to a reviewer. Never auto-apply a fix in the pass that produced the
finding.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
A reviewer's isolation mode is read-only, so this workflow takes no lane and must say so:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-review --apply
```

Naming no `--lane` records `holds_no_lane` against this run. Read `quarantined` and
`interrupted_release` in the answer before grading: a change made in a lane a worker died in may be
half-written, and a review that does not know that grades an incomplete diff as a complete one.

**Never take a lane from this workflow.** A reviewer holding a write lease is not a reviewer.

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="resolve_scope">
Default to the active phase from Forge Next; an explicit phase argument overrides it.

Load `.forge/acceptance/registry.json` and grade against the registered suites.

Load `.forge/capabilities/qualifications.json` and note which routes carry evidence, under which
host.
</step>

<step name="choose_reviewer">
Default to the resident host. Use a qualified optional worker only when independence or economy
justifies it and its qualification covers the exact task class and complexity tier.

Hand the reviewer the requirements, the artifact or diff, acceptance criteria and evidence.
**Never pass builder reasoning.**
</step>

<step name="run_gsd_review">
Run one workflow per requested mode:

| Flag | Workflow | Against |
|---|---|---|
| none | `review.md` | The active phase plan |
| `--code` | `code-review.md` | Source changed during the phase |
| `--security` | `secure-phase.md` | The plan's threat model |
| `--audit` | `audit-uat.md` | Across phases |

Load each workflow from disk and give it the scope, acceptance criteria and artifacts only.

Require a structured result from each: findings with severity, the evidence behind each, and an
explicit verdict. Merge multiple modes into one verdict.
</step>

<step name="grade_findings">
Grade findings against the acceptance registry. A finding that breaks a registered suite is blocking,
whatever the reviewer scored it.

Apply Forge's own checks on the returned result, each against a named file:

| Check | Read from | Verdict |
|---|---|---|
| A change touching a `lockable` or `binary` path | `.gitattributes` against the diff's paths | Flag when the plan declared no project-exclusive lane |
| A change to a registered asset interface | `asset_interfaces` in `.forge/visual/registry.json` | Blocking. It invalidates every parallel visual task planned against the old one |
| Placeholder art where the plan permitted it | The phase's placeholder budget | Accept. Placeholder is not a defect |
| A step the doctrine requires and the work skipped | `forge.py procedure --task-class <task-class>` — its `steps[].produces` | Blocking. The skipped step is usually the one whose absence fails no build |

Reject any offload route whose qualification was recorded under a different host, and re-run the
review on the resident host.
</step>

<step name="record_and_return" priority="last">
Record the cycle in `.forge/reviews/registry.json` with the reviewer, mode, evidence and residual
risk.

Return `PASS`, `CHANGES_REQUIRED` or `ESCALATE`. Escalate on a stalled concern count or the
convergence cycle limit.
</step>

</process>

## Boundaries

- Never close a subjective art or game-feel gate. Report on it and leave it to the human.
- For plan convergence, use `forge-plan-convergence`.
