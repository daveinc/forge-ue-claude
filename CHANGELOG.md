# Changelog

## Unreleased

### All three Unreal routes exist, and the verb that reports them says so

- Declare VibeUE's live-Python route, the third of the three `COUNTERPLAN.md` separates. It shares `lane.ue-editor` with the first-party typed route because it runs inside the same editor process, and takes the `ue-live-python` lease the super-lock already declared. Declaring the route does not install it: it stays uncommitted until a project declares the server and the probe finds it, which is what "not a Forge prerequisite" means.
- `forge.py route-status` replaces `mcp-status`, which reported only the routes reachable by connecting to a server and would have hidden the two routes that are not. Its `routes` list now carries every kind with its lane, lease and reason, and the payload is `forge.route-status/v1`. The `mcp-status` spelling still works, so nothing that already calls it breaks.

### The editor-closed Unreal API is a route, not a fallback string

- `COUNTERPLAN.md` specifies three deliberately separate Unreal routes and calls the editor-closed API "a primary production surface, not just documentation" and "first-class rather than exceptional" — the first choice for batch import, retargeting, asset audits, LOD generation, null-RHI-safe work and anything unsafe inside the editor tick. The lease layer implemented that: `ue-editor-closed-api` has always been a peer inside `unreal-project-super-lock`. The route layer did not. `mcp-registry.json` held only `kind: mcp` rows, so `unreal-python` sat in the catalog as `routing: declared` with the note "No typed tool route declared yet", and `ue.python.commandlet` and `ue.batch` were capabilities no route could serve, no contract could describe, and `forge-route-work` step 7 could therefore never bind.
- The registry is now `dependencies/route-registry.json` and admits any kind of route: `mcp` names a server the host connects to, `process` names a command it runs. Nothing else varies by kind, so both are probed, scored, leased and reported the same way. `mcp-provider` becomes `route-provider`, with the required reach field chosen by kind.
- `unreal-python` is a routed peer on its own lane, `lane.ue-editor-closed`. The `lane.ue-editor` description no longer claims editor-closed commandlets contend for the live lane; they contend for the project, which is what the super-lock already expressed.
- Add the `ue-commandlet-ready` probe. Readiness is the inverse of `mcp-http-handshake`: the engine command must resolve *and* the editor's MCP endpoint must be silent, because a commandlet must not run against a project the live editor holds. The two Unreal routes now swap availability as the editor opens and closes, and a test asserts they are never both available for one project.
- Route rows name the `lease` they take, and the validator refuses a lease no exclusive group declares. The registry said `lane.ue-editor` while the ledger that enforces exclusion said `ue-live-native-mcp`; two vocabularies that happened to agree now agree by rule.
- `route-policy.json` gains `unreal_routing`, which says which work shape belongs to which lane and records that the result file, never the exit code alone, is authoritative for editor-closed work. `forge-route-work` gains a step that picks the route by the shape of the work rather than by what happens to be running.

### The bootstrap job ledger is wired to the resume it exists for

- `.forge/state/install-jobs.json` was mandated before dispatch by step 6 and read by nothing. Step 4 enumerated what `--resume` reads and did not name it, so the ledger written to survive bootstrap's two stop points was not read by the resume those stops require. Step 4 now reads it and carries forward every job already `COMPLETE`, `NOT_APPLICABLE` or `FAILED`, re-dispatching only what is still `PLANNED` or was left `DISPATCHED`.
- The ledger ships in the project template and has a contract, `forge.install-jobs/v1`, with a `status` vocabulary the resume can act on. It was the only bootstrap state file with neither.
- Name the phase activation policy by path in `forge-capability-admin` and `forge-route-work`. Both told the agent to load "the phase activation policy" while naming fourteen other state files by exact path, leaving the agent to guess that it meant `.forge/context/activation-policy.json`.

### Re-profiling the same machine no longer proposes a change to it

- `forge.py profile --apply` wrote a `.forge-proposed` sibling on every run against an installed project, because the stored profile records the literal `--project` argument and that literal was compared. `install` resolves the path before profiling and an agent typically passes `.`, so the two never matched. The gate treats a proposal as a human merge decision, so the noise arrived exactly where bootstrap tells the agent to run Profile.
- `stable_profile` now drops the invocation record alongside the timestamp it already dropped. `requested` stays in the file as provenance; it can no longer cause a proposal.

### `forge-next` stops offering choices that are not choices

- Two situations offered a recommended Forge verb and, as the alternative, a GSD verb the registry fronts with that same Forge verb. On a greenfield project `forge-init` and `project-discovery` both rendered as `/forge-init`, and on unreadable GSD state `doctor` and `planning-health` both rendered as `/forge-doctor`. Distinct ids hid it: the collapse happens at translation, after the ids are assigned.
- Greenfield now offers `forge-doctor` as its alternative, which is a different action. The unfronted GSD path is not lost: `gsd_snapshot` already lists `/gsd:new-project` untranslated, which is where a user who wants stock GSD should find it.
- A test renders every action block's commands through the same translation the payload uses and fails when two ids land on one verb.

### One module per concern, cut where the code already separated

- Split `forge.py` into ten modules. It had grown to 2,558 lines carrying the failure contract, host registry, MCP routes, GSD front, capability survey, lifecycle, installer, routing and the CLI, so every one of those concerns was read and edited through the same file.
- The cut follows the call graph rather than a guess. Three names had to move first: `capability` was used only by the MCP layer and the survey that defined it, and the overlay's path helpers were used by both the host renderer and the installer, so both belong to `forge_core`. `host_set`, `host_status` and `host_list` are called only by the CLI and sat between the host registry and the GSD sync that depends on it, so they became `forge_runtime`. With those moved the layering is acyclic, and a test asserts it stays that way.
- `forge.py` keeps every public name, so `forge.<verb>` resolves exactly as before and the split changes no behaviour. A test walks each module with `symtable` and fails on any name a module references but never defines or imports, which is the check that would otherwise wait for a rare path to raise `NameError`.
- `forge_executor.py` imports nothing from the rest, and a test holds it there. The transactional core does not depend on the layers above it.

### Isolation is enforced by the runtime, not by workflow compliance

- Add `scripts/forge_executor.py` and the `forge.py exec acquire|release|status` verbs. Leases, Git worktrees and `git lfs lock` were described in `forge-route-work` and `directives.md` and implemented nowhere: the words "lease", "worktree" and "lfs" did not appear in `forge.py`, and `.forge/state/leases.json` shipped an `exclusive_groups` map nothing read or wrote. A guarantee that depends on an agent following prose is not a guarantee.
- `exec acquire` resolves the base revision, refuses a lane already held or held in the same exclusive group, creates the worktree, takes each LFS lock, and rolls back every completed step when a later one fails. A lock it cannot take never becomes a lease it appears to hold.
- The ledger is written atomically under a cross-process mutex, so two workers racing one lane produce a holder and a refusal rather than two writers. A test races two real processes and asserts exactly one wins with `lease_conflict`.
- `exec acquire` expires leases past `expires_at` before checking conflicts, so a crashed session blocks its lane until expiry rather than forever.
- `forge-route-work` steps 8, 9 and 15 call the executor instead of instructing the agent to take isolation by hand. Step 8 declares isolation, step 9 establishes it, and nothing else may.
- Test the LFS path against real `git lfs` by running a Git LFS locking server in the suite. A path another writer holds is refused by git, a partly-locked set is unlocked again on rollback, and `release` reports the paths it could not unlock instead of freeing the lane silently and leaving them held.
- Report incomplete rollback. An undo step that fails now attaches `rollback_incomplete` to the failure, because a lock left behind that Forge is no longer tracking is worse than the error that caused it.

### Unreal's first-party MCP is the shipped route

- Point `unreal-native-mcp` at Unreal Engine's own Unreal MCP plugin (`ModelContextProtocol` plus `AllToolsets`, Experimental since 5.8), which advertises itself as `unreal-mcp` — the server id the registry already named. The editor hosts it; Forge never starts it.
- Support http transports. The renderer emitted `command`/`args`/`env` only, so an editor-hosted endpoint could not be expressed at all. `mcp add` now takes `--url`, and refuses a declaration naming both a command and a url.
- A new project's `.forge/mcp.json` declares that route instead of shipping `servers: []`, so the layer that decides whether Unreal work is possible is no longer left for the user to choose.
- Add the `mcp-http-handshake` probe kind: it sends a real MCP `initialize` to the declared endpoint. Passing earns `AVAILABLE_VERIFIED`, which a configuration file alone never did. Failing marks the route `UNAVAILABLE_OPTIONAL`, so work degrades to `ue.editor-closed-or-human` instead of dispatching into a closed editor.
- Test that path against a server that answers `initialize`, over JSON and over the SSE framing the first-party plugin uses. A port that is listening without speaking MCP does not earn a route, and a live server the host's configuration does not declare is reported as undeclared rather than as available.

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
