<!-- forge:workflow
name: plan-convergence
consumes: the phase plan, .forge/config.json (plan_review), .forge/capabilities/qualifications.json, .forge/visual/registry.json, plugins/forge-ue-studio/doctrine/procedures.json
produces: a revised plan, and a cycle record in .forge/reviews/registry.json
-->

# Forge Plan Convergence — workflow

<purpose>
Drive a plan to zero actionable findings through independent review cycles — or stop, and hand the
remaining concerns to the human who owns them.
</purpose>

<core_principle>
Never silently proceed past a stall, a malformed reviewer output or an unverifiable source. A plan
that converged because the reviewer stopped answering has not converged.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Review reads the plan and writes only its own cycle record:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-plan-convergence --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="require_a_reviewable_plan">
Refuse to open a cycle on a plan missing any of: scope, dependencies, work packets, write sets,
lanes, acceptance, verification, fallbacks, human gates, and the artifacts it declares it will
create.

A plan with no declared lane cannot be reviewed for lane conflicts, which is the class of finding
this workflow exists to catch. Return it to `forge-plan-phase`.
</step>

<step name="select_independent_reviewers">
Read `.forge/capabilities/qualifications.json`. Select reviewers only from routes qualified for this
task class and complexity tier, **under the currently assigned host** — qualification is host-scoped
and evidence recorded under a retired host is not evidence.

Keep at least one reviewer isolated from planner reasoning. Hand it the requirement, the plan and the
acceptance criteria, and nothing about how the plan was arrived at.
</step>

<step name="ground_every_citation">
`plan_review.source_grounding` in `.forge/config.json` is `true`, so every cited symbol, asset,
plugin, API, path, capability and acceptance command must be checked against source or a verified
registry:

| Cited | Grounded against |
|---|---|
| A C++ symbol or module | `Source/` |
| An asset path | `Content/`, and `.gitattributes` for whether it is binary |
| An enabled plugin or engine version | `<project>.uproject` |
| A capability or route | `forge.py route-status`, not the registry declaration alone |
| A task class's steps, acceptance or evidence | `forge.py procedure --task-class <task-class>` |
| An acceptance suite ID | `.forge/acceptance/registry.json` |
| An asset interface | `asset_interfaces` in `.forge/visual/registry.json` |

Exclude artifacts the plan itself says it will create. Everything else that cannot be grounded is an
unverifiable source, and this workflow stops on one rather than reviewing around it.
</step>

<step name="count_findings_honestly">
Record findings by severity. Return **two** numbers for the current cycle only: `HIGH` findings, and
actionable non-high findings.

Keep prior cycles as audit history in `.forge/reviews/registry.json` and never re-count a resolved
finding. A count that includes closed findings never reaches zero, and a count that quietly drops
open ones reaches zero without meaning it.
</step>

<step name="revise">
Revise the plan so every actionable finding becomes exactly one of: a task, an acceptance item, a
verified closure, an explicit deferral, or a reasoned rejection.

Nothing may leave a cycle in none of those five states. A finding acknowledged and not dispositioned
is a finding that returns next cycle as new.
</step>

<step name="stop_or_escalate" priority="last">
Repeat until both counts reach zero, `plan_review.max_cycles` is reached, or the counts stop
decreasing by `plan_review.stall_threshold`.

Stop and present the remaining concerns to the human owner on any of: a stall, a malformed reviewer
output, an unverifiable source, or cycle exhaustion. `plan_review.human_escalation` is `true`, and
this is the escalation it names.

Record the cycle — reviewer, mode, findings, evidence, residual risk — in
`.forge/reviews/registry.json` whether it converged or not. A plan that exhausted its cycles is the
record most worth keeping.
</step>

</process>
