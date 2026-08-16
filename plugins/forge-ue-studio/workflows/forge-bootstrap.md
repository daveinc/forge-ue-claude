# Forge Bootstrap — workflow

## Required behavior

1. Resolve the intended project root. Accept an empty or pre-project directory, or one containing exactly one `.uproject`.
2. Apply the overlay with `scripts/forge.py install --project <root> --apply` when `.forge/config.json` or `.forge/directives.md` is absent. Never install packages, models, plugins, or MCPs here, and never change the machine.
3. **STOP after first overlay installation.** Tell the user to open a fresh task and run `forge-next`. Never continue in the current task.
4. On `--resume`, read the host's project instruction file, `.forge/directives.md`, install state, and the canonical packet registry. Treat `.forge/state/lifecycle.json` as deprecated history.
5. Run Survey and Profile first and write `.forge/capabilities/detected.json`. Never treat detection as qualification.
6. Compile only applicable jobs from [installation-waves.md](../skills/forge-bootstrap/references/installation-waves.md). Record each job's canonical `FI-*` work order, objective, inputs, read/write scope, agent type, expected result and acceptance in `.forge/state/install-jobs.json` before dispatch.
7. Dispatch agents whenever the host exposes authorized subagents: independent read-only Wave 1 jobs concurrently, local work stopped while they run, then Wave 2 analysis on their structured results. Use exact project-local agent types when visible, otherwise an exactly suitable installed typed agent. Never substitute an unnamed local model. Mark every affected job `DEGRADED_INLINE` and report the lost independence when dispatch is forbidden.
8. Never delegate package installation, consent, credentials, PATH or system changes, project descriptor mutation, or external writes. Surface each as a separate human approval. Adapt around absent optional capabilities instead of blocking unrelated production.
9. Persist observations, evidence, failures, proposed capability contracts, and unresolved human actions. Never qualify a provider because an investigator found it.
10. Dispatch a fresh read-only verifier against the deterministic profile, job results, and acceptance criteria. Never give the verifier investigator reasoning beyond the returned artifacts.
11. Write `.forge/state/bootstrap-report.json` against `forge.bootstrap-report/v1` with `verdict`, every canonical `FI-*` job including evidence-backed `NOT_APPLICABLE` entries, `delegation`, `verified`, `assumed`, `unavailable`, `blocking`, `human_actions`, `evidence`, and `next_action`. Set `next_action` to `forge-next`. Never maintain a competing Forge phase pointer.
12. Run the gate and treat every failure as work remaining:

    ```powershell
    python <forge-plugin-root>/scripts/forge.py bootstrap-check --project <project-root>
    ```

    | Check | Fails when |
    |---|---|
    | `capability-profile` | `.forge/capabilities/detected.json` is missing. |
    | `bootstrap-report` | The report is missing or unparseable. |
    | `report-schema` | A required `forge.bootstrap-report/v1` field is absent. |
    | `report-verdict` | The verdict is not `PASS` or `DEGRADED_ACCEPTED`. |
    | `report-blocking` | Blocking items remain unresolved. |
    | `installation-jobs` | A canonical `FI-*` packet is unaccounted for. |
    | `phase-contract` | The rendered instruction file is missing or lacks `## Forge phase contract`. |

    On `phase-contract`, stop for an explicit merge decision on any `.forge-proposed` sibling, or re-render with `forge.py host set --host <id> --project . --apply`.
13. **STOP.** Require a fresh session and present `forge-next`.

Use `forge-doctor` for read-only environment classification, `forge-research` for new sources, and `forge-capability-admin` for consent and qualification.
