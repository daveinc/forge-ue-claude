# Changelog

## Unreleased

### Resume as a first-class verb

- Add `forge-resume-work`, fronting `gsd-resume-work`. Resuming was previously reachable only as `forge-handoff --resume`, which hid a daily command behind a flag on a verb named for pausing. `forge-handoff` now pauses only, and smart-entry's `gsd-resume-work` emission translates to `/forge-resume-work`.
- Resuming reclaims lane leases before work restarts and re-probes qualification when the handoff was produced under a different host.

### Correctness

- Fix `mcp-status` routes overwriting the declared scope with the probe's. Both are reported: `scope` is what the project declared (`project`/`user`/`both`), `found_in_scope` is where the probe found the server. Consumers reading `scope` were reading the probe result.
- Fix `mcp amend` writing an unroutable declaration to disk and only then failing to resolve it, which left `.forge/mcp.json` in a state the next command refused. The amendment now resolves before anything is written.

### Skills follow GSD's architecture

- Split every skill into a launcher and a workflow, the way GSD does. `skills/<verb>/SKILL.md` carries `<invocation>`, `<objective>`, `<flags>`, `<execution_context>`, `<context>` and `<process>`; the steps live in `workflows/<verb>.md` and load by path. Descriptions are one line under 110 characters, saying what the verb does — the "Use when …" trailer moved into `<objective>`.
- `<execution_context>` lists every file a verb loads, which closed a silent gap: `forge-discuss-phase` fronts four GSD workflows and named one, `forge-milestone` fronts five and named one, `forge-review` fronts five and named four.
- Declare flags where the agent reads them, with GSD's rule that a flag is active only when its literal token appears in `{{FORGE_ARGS}}`. `forge-discuss-phase --assumptions/--power/--list-assumptions` and `forge-plan-phase --dependencies` were documented publicly and absent from the skill.
- Every line of a workflow is now a step. Justification clauses, restated rationale, and one reference to a past incident are gone or have become instructions.

### Forge runs GSD's workflows instead of containing them

- Replace the `contain` delegation mode with `run`. It spawned a subagent whose only job was reading a workflow file whose path the registry already declares, which then spawned GSD's real agents — three layers where GSD itself uses two. Forge now loads the workflow from disk and runs it end to end in the current session, with its own PRE before and POST after. GSD's typed agents still spawn as its workflow directs.
- Delete `forge-execute-phase`. Its PRE restated `forge-route-work` steps 7–9 and its POST restated step 15, and its own PRE ended by routing through `forge-route-work` anyway. `gsd-execute-phase` now fronts `forge-route-work`, which gained clean-base verification and a step that runs GSD's executor under the leases it already holds.
- `forge-resume-work` now treats an `ACTIVE` lease past its `expires_at` as stale. The schema has always required that field and nothing read it, so a lease held by a dead session was indistinguishable from a live one.
- Distinguish `forge-docs-update` from `forge-ingest-docs` in both objectives. They read as duplicates because both touch the GDD ledger; they run in opposite directions — ingest takes documents into planning state, docs-update takes implemented code out to documentation.

### Promises closed

- Declare `forge-quality-gate --tests` and `forge-ship --pr` in their skills. Both appeared in the verb registry and the independence map, and in neither `<flags>` block, so an agent executing the skill could not act on them.
- Take the real `git lfs lock` on a declared binary write scope where LFS is configured, so a second writer is refused by git rather than by convention. Where it is not configured, the recorded lease stays the only protection and the attempt result now says so.
- Stop advertising `forge-explore` and `forge-capture`. Five GSD commands were dropped with the reason "Planned: …" against verbs that do not exist. Greybox and blockout belong to `forge-visual-production`; Socratic ideation, spikes, idea capture and backlog triage are not production surface, and each drop reason now says to run the GSD command directly.

### Forge fronts GSD; it does not replace it

- Correct a claim that was never true of the product: the docs said "GSD is never addressed directly — you will not type a `gsd-` verb". Both surfaces are installed and GSD stays directly usable. The instruction file Forge renders has always pointed at `gsd-quick` and `gsd-debug` for small fixes, so the code and the documentation disagreed.
- Reframe the rule to what it actually is: a Forge verb exists where the game side needs work the bare GSD command does not do — lane leases, the acceptance registry, canonical packet IDs, in-engine evidence — so a **routed** action is a Forge verb. That is a statement about what Forge emits, not a restriction on the user.
- Stop treating a `drop` as something the user cannot run. `forge-next` now reports each suppressed action with `run_directly`, the command spelled for the assigned host, and `forge-next` presents them as available in GSD. Added a reference table of the 29 commands Forge does not route, with reasons.

### Documentation

- Rebuild `README.md` as a landing page — what Forge is, how it works, a quickstart, and an index — instead of a 500-line manual. Everything it used to carry now lives in `docs/`, organised as tutorials, how-to guides, reference, and explanation, with `docs/README.md` as the index.
- Add [Your first game](docs/tutorials/your-first-game.md), [Adopt an existing project](docs/tutorials/adopt-an-existing-project.md), [Install Forge](docs/how-to/install-forge.md), [Swap the resident runtime](docs/how-to/swap-runtime-host.md), [Troubleshoot](docs/how-to/troubleshoot.md), [Skills](docs/reference/skills.md), [Installer](docs/reference/installer.md), [Repository and project layout](docs/reference/repository-layout.md), and [How Forge works](docs/explanation/how-forge-works.md).

### Comments and skill prose

- Remove every comment from `forge.py`, `validate_repo.py`, `test_forge.py`, and `install.ps1` (−350 lines). Rules moved to the skill step, doc, or registry that owns them; explanations became named values, extracted functions, or failure messages; history stayed in git.
- Record the rule in `CONTRIBUTING.md` and enforce it in `validate_repo.py`, which now fails on any comment in those four files apart from shebangs and tool pragmas.
- Cut the same class of prose from 18 `SKILL.md` files: justification clauses, restated rationale, and one reference to a past incident. A skill states what to do and what is refused, not why the rule was written.

### Host-agnostic runtime

- Make the resident AI runtime a **swappable assignment** rather than a hardcoded vendor. A project records its host in `.forge/runtime.json` and can change it at any stage — including mid-phase and at a resume boundary — without losing planning state, packets, or evidence.
- Add `plugins/forge-ue-studio/hosts/registry.json`: host profiles plus a required/optional prerequisite contract. Built-in hosts are `claude` (Claude Code, default), `codex` (OpenAI Codex CLI), and `generic`. A new host is added by appending a profile; no Forge code changes are required.
- Split the project overlay into **canon** (host-neutral, authoritative) and **rendered surfaces** (host-specific, disposable). Canonical studio-role agents now live in `.forge/agents/*.json` and the project instruction file is generated from `.forge/templates/project-instructions.md`.
- Render host surfaces per assignment: `CLAUDE.md` + `.claude/agents/*.md` for Claude Code, `AGENTS.md` + `.codex/agents/*.toml` for Codex. Swapping away and back is byte-identical.
- Add `forge-runtime`, a skill for inspecting, assigning, and swapping the resident host, and `forge.py host list|status|set` behind `install.ps1 -Mode Host`.
- Spell skill invocations per host (`/forge-next` in Claude Code, `$forge-next` in Codex). Forge Next returns commands already spelled for the assigned host.
- Detect every known host in the survey, not just the active one, so a swap can be planned from evidence. Detection never grants the resident seat.
- Add the `host-surfaces-stale` smart-entry situation so Forge Next refuses to proceed against stale instructions or agents.
- Treat provider qualification evidence as **host-scoped**. An evaluation recorded under a different host is rejected as ineligible with an explicit re-probe reason.
- Replace the literal `codex` resident provider with the neutral `resident` role across route policy, project config, capability registry, and dependency catalog.
- Add `host-profile` and `runtime-state` schemas, and extend repository validation to reject duplicate skill prefixes, unsupported agent formats, hosts that cannot meet the contract, host-specific files shipped in the project template, and canon that hardcodes a host spelling.
- Add the Claude Code plugin manifest and repo-local marketplace alongside the existing Codex ones.
- Add [docs/host-runtimes.md](docs/host-runtimes.md) covering the prerequisite contract, canon/rendered split, swap semantics, and how to add a host.

### Neutrality audit follow-ups

- Fix `install.ps1` rejecting newly registered hosts: `-RuntimeHost` had a hardcoded `ValidateSet` that failed parameter binding before the registry was read, contradicting the documented "append a profile, no code changes" path. Validation is now registry-driven, with an argument completer for tab-completion.
- Remove vendor names from four canon files that the old guard could not see: the template capability registry provider id and activation list, the activation policy `always_on` entry, the acceptance-suite purpose, and a duplicated host list in the dependency catalog.
- Replace the narrow neutrality check — four skill prefixes inside `.forge/agents/*.json` — with a guard over all of `assets/project-template/`, `dependencies/*.json`, and `schemas/*.json`, banning vendor names, host home directories, host instruction filenames, host agent directories, and host skill invocations. Banned tokens derive from the registry, so the guard extends itself as hosts are added.
- Stop skill prose instructing agents to read `AGENTS.md`, which does not exist under the default host. Bootstrap and Init now refer to the instruction file named by the active host profile.
- Re-word ~20 prose assertions in SKILL.md, `references/*.md`, and `docs/installation-agent-jobs.md` that still named a vendor as the resident worker.
- Make bare skill names the canonical internal form in `forge.py`, and change the missing-profile prefix fallback from `$` to none, so a forgotten profile degrades neutrally instead of emitting another host's spelling.
- Fix a deprecation error message that hardcoded `$forge-next`, and correct stale `pyproject.toml` metadata (`0.1.0`, "Codex-native") to match the manifests.

### Forge owns the verb surface; GSD becomes an invoked sublayer

- Add `verbs/registry.json`: every GSD command maps to the Forge verb that fronts it, with a declared delegation mode (`contain` / `relay` / `native`), the GSD workflow it calls, and the game-dev adaptation applied. Validation refuses a verb with no matching skill, an unknown mode, or a duplicate GSD mapping.
- Translate GSD commands into Forge vocabulary at the one boundary where they surface. `normalize_gsd_command()` maps `gsd-*` to its Forge verb, then spells it for the active host. An unmapped GSD verb emits an explicit `[UNMAPPED: …]` marker rather than leaking silently.
- Add 17 skills: `forge-review` (verb-based — plan, `--code`, `--security`, `--audit` — graded against Forge's acceptance registry rather than generic criteria) plus `forge-discuss-phase`, `forge-plan-phase`, `forge-execute-phase`, `forge-verify-work`, `forge-progress`, `forge-phase`, `forge-milestone`, `forge-onboard`, `forge-ingest-docs`, `forge-map-codebase`, `forge-docs-update`, `forge-spec-phase`, `forge-debug`, `forge-handoff`, `forge-ship`, `forge-undo`.
- Add `references/delegation-contract.md` defining the shared PRE (Forge) / CORE (stock GSD) / POST (Forge) shape. GSD is invoked in place — never edited, never copied — so upstream fixes arrive without a merge.
- Tell GSD which host it is running under. GSD resolves its command spelling from `.planning/config.json`'s `runtime` key and defaults to `claude`, so a Codex-hosted project previously got the wrong spelling. `sync_gsd_runtime()` writes that one key at overlay install and on every host swap, and `GSD_RUNTIME` is exported on every `gsd_run` call. Repairable with `forge.py gsd-sync`.
- Move the GSD pin from 1.8.0 to **1.9.1**, the version actually installed and tested against. 1.10.0 exists but is unvalidated.

### Bootstrap gate and dead-code removal

- Make Forge's bootstrap closure checks **reachable**. They previously lived in `require_artifacts()`, which only the unreachable lifecycle-transition block called, so nothing ran them. They are now `bootstrap_verdict()`, wired into `bootstrap_is_complete()` (and therefore Forge Next) and exposed as `forge.py bootstrap-check` / `install.ps1 -Mode BootstrapCheck`, which exits non-zero until every check passes.
- The gate verifies the capability profile exists, the report parses and carries every required `forge.bootstrap-report/v1` field, the verdict is closable, no blocking items remain, every canonical `FI-*` packet is accounted for, and the rendered instruction file actually contains `## Forge phase contract`. These are Forge's own domain — GSD owns phase state and has no equivalent — so nothing downstream catches them.
- Surface partial phase execution in Forge Next as advisory `warnings` plus per-phase `execution_coverage`. GSD computes the same set but keeps it non-blocking, so an interrupted phase can reach 100% silently. Forge reports it without raising a competing gate; the routed action is unchanged.
- Delete `require_artifacts()` and the unreachable lifecycle-transition block, plus the now-unused `LIFECYCLE_EVENTS` constant. `lifecycle_state()` keeps only its read-only status path and still rejects transitions. Its `phase` and `apply` parameters are removed — they were inert.
- Retain GSD's verification gate as the authority for phase completion. Its `readVerificationStatus` / UAT predicate is stricter than Forge's old UAT regex (it requires positive passing evidence and refuses a vacuous pass), so no Forge equivalent was reintroduced.

### Earlier in this cycle

- Add `forge-next`, a state-aware front door that combines Forge adoption/bootstrap readiness with GSD `smart-entry`, dispatches one action, and stops.
- Make GSD `.planning` the sole phase authority; deprecate Forge lifecycle transitions and retain the old lifecycle file as compatibility history only.
- Make Forge Init invoke the detector first, so re-running it in a partial project routes to bootstrap, document ingestion, onboarding, or the exact active GSD action instead of restarting inception.
- Allow the Forge project overlay to install before a `.uproject` exists, eliminating the new-game bootstrap deadlock.
- Add `forge-bootstrap` with explicit delegated installation waves, independent verification, persisted reports, and visible degraded-inline fallback.
- Add project `AGENTS.md`, compatibility state, canonical packet registry, and route rejection for unknown/relabelled work orders.
- Stop Forge Init after inception and use Forge Next/GSD smart-entry for the next command instead of hardcoding phase 1 or dispatching the first implementation packet in the same task.
- Add a separate preview-first, stable-version-pinned GSD Core installer plus runtime/skill/agent detection and fresh-session qualification guidance.
- Rewrite the README as an end-user installation, first-use, skill, project-adoption, capability, and troubleshooting guide.
- Make the resident host the default across art, code, review and tool-operation seats.
- Remove the named model-provider routes and replace provider-specific cost assumptions with evidence-backed, provider-neutral local and remote worker registration.
- Add bounded-context offload rules for long extraction, code/review, image-to-3D breakdown and DCC work.
- Adopt typed capability trust/consent/integrity, phase-scoped activation, exact task/complexity qualification and deterministic route decisions.
- Add plan convergence, quality gate, retrospective/forensics, gameplay gauntlet and capability-administration skills.
- Add attempt, evaluation, review, learning, lease, route and research schemas plus persistent project registries.
- Extend installation with a non-destructive detected capability profile and contract validation/profile/route commands.
- Enforce clean-base Git worktree isolation for concurrent text/code workers, binary ownership for Unreal assets, and canonical-JSON production scorecards with optional XLSX/CSV views.

## 0.1.0 - 2026-08-14

- Add the Codex plugin, repo-local marketplace, five studio skills, environment doctor, project overlay installer, capability catalog, routing policy, schemas, tests, and CI.
- Define cost-aware local routing after quality and safety qualification.
- Treat Blender and Unreal as alternate or split asset, rigging, and animation routes.
