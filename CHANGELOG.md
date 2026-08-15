# Changelog

## Unreleased

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
