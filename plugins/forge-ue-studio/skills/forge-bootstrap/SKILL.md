---
name: forge-bootstrap
description: Install or resume the project-local Forge overlay in a pre-project or Unreal project folder, inventory GSD and production capabilities, delegate bounded installation investigations, verify the result, and stop at a fresh-task handoff to Forge Next. Use for first-time project setup, Forge complete installation, or repairing a partial project adoption.
---

# Forge Bootstrap

Create the durable project control plane before design or Unreal project-shell work. Installation is a stateful workflow, not a survey performed from chat memory.

## Required behavior

1. Resolve the intended project root. It may be an existing empty/pre-project directory or contain exactly one `.uproject`.
2. If `.forge/config.json` or `.forge/directives.md` is absent, apply the bundled project overlay with `scripts/forge.py install --project <root> --apply`. This is a reversible project-file installation and must not install packages, models, plugins, MCPs, or change the machine.
3. **STOP after first overlay installation.** Tell the user to open a fresh task in the project and run `forge-next`. Do not continue in the current task: the newly rendered project instruction file, project agents, state and skill surface must be loaded by a fresh host context.
4. On `--resume`, read the project instruction file named by the active host profile (`CLAUDE.md`, `AGENTS.md`, or whatever `project_surface.instruction_file` declares), `.forge/directives.md`, install state, and the canonical packet registry. Treat any `.forge/state/lifecycle.json` as deprecated compatibility history.
5. Run deterministic Survey and Profile first; write `.forge/capabilities/detected.json`. Detection never grants qualification.
6. Compile only applicable installation jobs from [installation-waves.md](references/installation-waves.md). Record each job's canonical `FI-*` work order, objective, inputs, read/write scope, agent type, expected result and acceptance in `.forge/state/install-jobs.json` before dispatch.
7. Agent dispatch is required when the current runtime host exposes authorized subagents. Dispatch independent read-only Wave 1 jobs concurrently, stop local work while they run, collect their structured results, then dispatch Wave 2 analysis. Use exact project-local agent types when visible; otherwise use an exactly suitable installed typed agent. Do not substitute an unnamed local model. If the runtime or user policy forbids dispatch, mark every affected job `DEGRADED_INLINE` and explain the lost independence in the report.
8. Never delegate package installation, consent, credentials, PATH/system changes, project descriptor mutation, or external writes. Surface each as a separate human approval/action. Optional capabilities may be absent; adapt the workflow instead of blocking unrelated production.
9. Persist observations, evidence, failures, proposed capability contracts and unresolved human actions. A provider is not qualified merely because an investigator found it.
10. Dispatch a fresh read-only verifier against the deterministic profile, job results and acceptance criteria. The verifier must not receive investigator reasoning beyond the returned artifacts.
11. Write `.forge/state/bootstrap-report.json` against `forge.bootstrap-report/v1` with `verdict`, every canonical `FI-*` job (including evidence-backed `NOT_APPLICABLE` entries), `delegation`, `verified`, `assumed`, `unavailable`, `blocking`, `human_actions`, `evidence`, and `next_action`. If overlay installation preserved an existing project instruction file and wrote a `.forge-proposed` sibling, stop for an explicit merge decision; bootstrap cannot pass until the active instruction file contains the Forge phase contract.
12. Verify that the detected profile and a closable bootstrap report exist. Set the report's `next_action` to `forge-next`; do not maintain a competing Forge phase pointer.
13. **STOP.** Require a fresh project task and present `forge-next`. Forge Next will inspect existing docs, Unreal/code, and GSD state before deciding whether inception, ingestion, onboarding, or phase recovery is correct.

Use `forge-doctor` for read-only environment classification, `forge-research` for newly discovered sources, and `forge-capability-admin` for consent/qualification after bootstrap.
