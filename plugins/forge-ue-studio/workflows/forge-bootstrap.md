<!-- forge:workflow
name: bootstrap
consumes: .forge/config.json, .forge/directives.md, .forge/state/install-state.json, .forge/state/install-jobs.json, .forge/state/packet-registry.json
produces: .forge/capabilities/detected.json, .forge/state/install-jobs.json, .forge/state/bootstrap-report.json
never-reads: .forge/state/lifecycle.json (deprecated history)
-->

# Forge Bootstrap — workflow

<purpose>
Stand up the Forge control plane in a project, using read-only investigation and bounded jobs.
</purpose>

<core_principle>
Never install packages, models, plugins or MCPs here, and never change the machine. Detection is not
qualification.
</core_principle>

<process>

<step name="resolve_project_root" priority="first">
Accept an empty or pre-project directory, or one containing exactly one `.uproject`.
</step>

<step name="apply_overlay">
**Skip if:** both `.forge/config.json` and `.forge/directives.md` are present.

```powershell
scripts/forge.py install --project <root> --apply
```

**STOP after first overlay installation.** Tell the user to open a fresh task and run `forge-next`.
Never continue in the current task.
</step>

<step name="resume_from_ledger">
**Skip if:** this is not a `--resume` invocation.

Read the host's project instruction file, `.forge/directives.md`,
`.forge/state/install-state.json`, `.forge/state/install-jobs.json`, and the canonical packet
registry.

The job ledger is the resume point:

| Job status | Action |
|---|---|
| `COMPLETE`, `NOT_APPLICABLE`, `FAILED` | Carry forward with its evidence |
| `PLANNED`, or `DISPATCHED` by an interrupted session | Re-dispatch |

Never re-probe a job the ledger already answers.

> **Why:** CHANGELOG.md 0.4.0 § *The bootstrap job ledger is wired to the resume it exists for*
</step>

<step name="detect_capabilities">
Detect before compiling anything, writing `.forge/capabilities/detected.json`:

```powershell
python <forge-plugin-root>/scripts/forge.py survey --project <project-root>
python <forge-plugin-root>/scripts/forge.py profile --project <project-root> --apply
```

Run `profile` without `--apply` first to read what it would record.

`profile` records what is present; only `forge-capability-admin` records what is proven to work.

> **Why:** CHANGELOG.md 0.4.0 § *Re-profiling the same machine no longer proposes a change to it* — 0.3.1 § *The profile verb worked again, and every verb got exercised*
</step>

<step name="compile_jobs">
Compile only applicable jobs from
[installation-waves.md](../skills/forge-bootstrap/references/installation-waves.md).

Record each job in `.forge/state/install-jobs.json` against `forge.install-jobs/v1` before dispatch:
canonical `FI-*` work order, wave, objective, inputs, read/write scope, agent type, expected result,
acceptance, `PLANNED` status.

Update status and evidence in place as each job dispatches and returns, so the ledger is always what
`resume_from_ledger` resumes from.
</step>

<step name="dispatch_jobs">
Dispatch agents whenever the host exposes authorized subagents: independent read-only Wave 1 jobs
concurrently, local work stopped while they run, then Wave 2 analysis on their structured results.

Use exact project-local agent types when visible, otherwise an exactly suitable installed typed
agent. Never substitute an unnamed local model.

Mark every affected job `DEGRADED_INLINE` and report the lost independence when dispatch is
forbidden.
</step>

<step name="keep_human_decisions_human">
Never delegate package installation, consent, credentials, PATH or system changes, project
descriptor mutation, or external writes. Surface each as a separate human approval.

Adapt around absent optional capabilities instead of blocking unrelated production.
</step>

<step name="persist_observations">
Persist observations, evidence, failures, proposed capability contracts and unresolved human actions.

Never qualify a provider because an investigator found it.
</step>

<step name="verify_independently">
Dispatch a fresh read-only verifier against the deterministic profile, job results and acceptance
criteria. Never give it investigator reasoning beyond the returned artifacts.
</step>

<step name="write_report">
Write `.forge/state/bootstrap-report.json` against `forge.bootstrap-report/v1` with `verdict`, every
canonical `FI-*` job including evidence-backed `NOT_APPLICABLE` entries, `delegation`, `verified`,
`assumed`, `unavailable`, `blocking`, `human_actions`, `evidence` and `next_action`.

Set `next_action` to `forge-next`. Never maintain a competing Forge phase pointer.

Check both ledgers against their contracts before the gate reads them:

```powershell
python <forge-plugin-root>/scripts/forge.py validate --kind bootstrap-report --input <project-root>/.forge/state/bootstrap-report.json
python <forge-plugin-root>/scripts/forge.py validate --kind install-jobs --input <project-root>/.forge/state/install-jobs.json
```

The gate says a required field is absent; `validate` says which and why.

> **Why:** CHANGELOG.md 0.5.0 § *Every verb is reachable from a workflow, and a guard keeps it that way*
</step>

<step name="run_gate">
Treat every failure as work remaining:

```powershell
python <forge-plugin-root>/scripts/forge.py bootstrap-check --project <project-root>
```

| Check | Fails when |
|---|---|
| `capability-profile` | `.forge/capabilities/detected.json` is missing |
| `bootstrap-report` | The report is missing or unparseable |
| `report-schema` | A required `forge.bootstrap-report/v1` field is absent |
| `report-verdict` | The verdict is not `PASS` or `DEGRADED_ACCEPTED` |
| `report-blocking` | Blocking items remain unresolved |
| `packet-coverage` | The canonical packet registry is unreadable, so coverage cannot be judged |
| `installation-jobs` | A canonical `FI-*` packet is unaccounted for |
| `phase-contract` | The rendered instruction file is missing or lacks `## Forge phase contract` |

On `phase-contract`, stop for an explicit merge decision on any `.forge-proposed` sibling, or
re-render:

```powershell
python <forge-plugin-root>/scripts/forge.py host set --host <id> --project . --apply
```
</step>

<step name="stop" priority="last">
**STOP.** Require a fresh session and present `forge-next`.
</step>

</process>

Use `forge-doctor` for read-only environment classification, `forge-research` for new sources, and
`forge-capability-admin` for consent and qualification.
