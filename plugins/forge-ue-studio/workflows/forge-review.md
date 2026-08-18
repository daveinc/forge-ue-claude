<!-- forge:workflow
name: review
consumes: .forge/acceptance/registry.json, .forge/capabilities/qualifications.json, the active phase plan
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

<step name="resolve_scope" priority="first">
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

Apply Forge's own checks on the returned result:

- Flag a change touching Unreal content that declared no project-exclusive lane.
- Flag a change to a registered asset interface, which invalidates parallel visual work.
- Accept placeholder art; reject an undeclared interface change.

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
