# GSD independence map

What GSD does today, what Forge would have to own to reach the same end-to-end result on a game project, and what it would cost to retire the `gsd-` command surface.

Measured against the installed GSD **1.9.1** (Forge pins 1.8.0 — see [Open questions](#open-questions)).

## The dependency is not where it looks

| Surface | Size | Forge's coupling |
|---|---:|---|
| `gsd-*` skills | 71 | Prompt-level. Forge dispatches skill *names* as strings. |
| Runtime workflows | 96 | None directly — invoked by the skills. |
| GSD agents | 34 | None directly. |
| Artifact templates | 35 | None — Forge reads the rendered `.planning` files. |
| `gsd-tools` runtime verbs | ~75 namespaces | **One.** `smart-entry --json`. |

Forge's entire *code* dependency on GSD is `gsd_smart_entry()` in `forge.py` — one subprocess call to one verb, plus path discovery for the runtime script. Everything else is Forge printing a `gsd-…` string and stopping.

That has a sharp consequence: **renaming the command surface is cheap; replacing the engine is not.** The 71 skills are prompts, but behind them sit 96 workflows and a runtime that owns `.planning` state, phase-ID arithmetic (including decimal insertion), roadmap mutation, frontmatter parsing, planning-directory locking, verification gating, workstream scoping, and worktree isolation.

## Three readings of "release the GSD dependency"

### A. Surface unification — rename only

Every user-facing command becomes `forge-*`. GSD stays installed as the execution engine; Forge skills wrap it. No `gsd-` command ever reaches the user.

- **Buys:** one vocabulary, game-dev framing, Forge-specific gates layered on. `forge-review` exists and behaves the way Forge needs.
- **Costs:** still `npx @opengsd/gsd-core` at install time; still tracks upstream releases; a GSD breaking change still breaks Forge.
- **Effort:** low. Mostly SKILL.md authoring plus dispatch-string changes.

### B. Vendor and absorb — recommended

Fork GSD's runtime into `plugins/forge-ue-studio/engine/`, ship it with the plugin, rename the surface, and adapt the parts that need game-dev semantics.

- **Buys:** no external package install, no upstream version race, full freedom to change gate semantics. Genuinely no GSD dependency.
- **Costs:** you now own ~96 workflows and a large runtime, including its bug tail. Upstream fixes become manual merges. License and attribution must be checked.
- **Effort:** moderate-to-high, but front-loaded and mechanical rather than inventive.

### C. Reimplement the engine

Write Forge's own `.planning` state machine from scratch.

- **Costs:** re-creates the exact failure class the RunnerRoyale incident was about — a second, less-tested phase engine competing for authority. GSD's edge cases (decimal phase insertion, milestone-scoped roadmap mutation, `previous_status` frontmatter false-positives, vacuous-pass prevention) are all scar tissue you would have to re-earn.
- **Effort:** very high.
- **Recommendation:** don't, unless GSD's model turns out to be fundamentally wrong for games — which the analysis below does not support.

## Command mapping

Legend — **Have**: Forge covers it. **Wrap**: thin Forge skill over GSD behaviour. **Adapt**: real game-dev change needed. **Drop**: not needed for Forge's scope.

### Tier 1 — Phase lifecycle spine (mandatory)

The discuss → plan → execute → verify sequence. Forge must not fork this; it must own or wrap it intact.

| GSD | Forge target | Action | Notes |
|---|---|---|---|
| `gsd-next` | `forge-next` | **Have** | Already the front door; wraps `smart-entry`. |
| `gsd-new-project` | `forge-init` | **Have** | Forge does game inception, then delegates project memory. |
| `gsd-discuss-phase` | `forge-discuss-phase` | **Adapt** | Needs GDD decision-ledger framing, art/gameplay interface questions. |
| `gsd-plan-phase` | `forge-plan-phase` | **Adapt** | Must emit asset-interface and lane declarations alongside tasks. |
| `gsd-execute-phase` | `forge-execute-phase` | **Adapt** | Must respect the Unreal project write-lock and lane leases. |
| `gsd-verify-work` | `forge-verify-work` | **Adapt** | Needs in-engine evidence (PIE, frame captures), not just tests. |
| `gsd-progress` | `forge-progress` | **Wrap** | |
| `gsd-phase` | `forge-phase` | **Wrap** | Phase CRUD; decimal insertion is fiddly — do not rewrite. |
| `gsd-new-milestone`, `gsd-complete-milestone`, `gsd-audit-milestone`, `gsd-milestone-summary` | `forge-milestone` | **Wrap** | Fold four commands into one verb-based skill. |

### Tier 2 — Quality gates (where Forge diverges most)

| GSD | Forge target | Action | Notes |
|---|---|---|---|
| `gsd-review` | **`forge-review`** | **Adapt** | Explicitly requested. Cross-AI peer review, but graded against Forge's acceptance registry and capability qualification, not generic code criteria. |
| `gsd-plan-review-convergence` | `forge-plan-convergence` | **Have** | Already exists. |
| `gsd-code-review` | `forge-review --code` | **Adapt** | Merge into `forge-review` as a mode. |
| `gsd-secure-phase` | `forge-review --security` | **Adapt** | Same. |
| `gsd-validate-phase` | `forge-quality-gate` | **Have** | Nyquist validation overlaps Forge's acceptance suites. |
| `gsd-add-tests` | `forge-quality-gate --tests` | **Adapt** | Game tests need PIE/automation harness awareness. |
| `gsd-audit-uat`, `gsd-audit-fix` | `forge-review --audit` | **Adapt** | |
| `gsd-ui-phase`, `gsd-ui-review` | `forge-visual-production` | **Have** | Forge's version is stronger for games (boards, direction, asset interfaces). |
| `gsd-eval-review`, `gsd-ai-integration-phase` | — | **Drop** | LLM-app evaluation. Not a game-production concern unless you ship AI features. |

### Tier 3 — Onboarding and context

| GSD | Forge target | Action |
|---|---|---|
| `gsd-onboard` | `forge-onboard` | **Wrap** |
| `gsd-ingest-docs` | `forge-ingest-docs` | **Wrap** |
| `gsd-map-codebase` | `forge-map-codebase` | **Adapt** — must map Content/, Blueprints, and C++ modules, not just source. |
| `gsd-docs-update` | `forge-docs-update` | **Wrap** |
| `gsd-extract-learnings` | `forge-retrospective` | **Have** |
| `gsd-graphify`, `gsd-mempalace-*` | — | **Drop** — optional knowledge tooling, not lifecycle. |

### Tier 4 — Session, recovery, debugging

| GSD | Forge target | Action | Notes |
|---|---|---|---|
| `gsd-pause-work`, `gsd-resume-work` | `forge-handoff` | **Adapt** | Must persist lane leases and editor state, not just context. |
| `gsd-forensics` | `forge-retrospective` | **Have** | |
| `gsd-debug` | `forge-debug` | **Adapt** | Needs Unreal crash logs, PIE traces, and editor-closed reproduction. |
| `gsd-health` | `forge-doctor` | **Have** | Merge planning-health checks into Doctor. |
| `gsd-undo` | `forge-undo` | **Wrap** | Git-backed revert; interacts with the binary-asset lock. |
| `gsd-thread` | — | **Drop** | |

### Tier 5 — Ideation

| GSD | Forge target | Action |
|---|---|---|
| `gsd-spec-phase` | `forge-spec-phase` | **Wrap** |
| `gsd-mvp-phase` | `forge-mvp-phase` | **Adapt** — vertical slice means playable loop, not a web feature. |
| `gsd-explore`, `gsd-sketch`, `gsd-spike` | `forge-explore` | **Adapt** — sketch should produce greybox/blockout, not HTML mockups. |
| `gsd-capture`, `gsd-review-backlog` | `forge-capture` | **Wrap** |

### Tier 6 — Delivery

| GSD | Forge target | Action | Notes |
|---|---|---|---|
| `gsd-ship` | `forge-ship` | **Adapt** | Game ship means cook/package/build, not just a PR. |
| `gsd-pr-branch` | `forge-ship --pr` | **Wrap** | |
| `gsd-inbox` | — | **Drop** | |

### Tier 7 — Meta and housekeeping (mostly drop)

`gsd-config`, `gsd-settings`, `gsd-help`, `gsd-update`, `gsd-surface`, `gsd-stats`, `gsd-manager`, `gsd-workspace`, `gsd-workstreams`, `gsd-profile-user`, `gsd-ns-*` (6), `gsd-autonomous`, `gsd-fast`, `gsd-quick`, `gsd-cleanup`, `gsd-import`, `gsd-ultraplan-phase`.

Keep only: `forge-config` (fold in `gsd-config`/`gsd-settings`), `forge-help`, and `forge-fast` for trivial tasks. Workstreams and worktrees stay as **runtime capability**, not user commands — Forge already declares worktree isolation in its directives.

## Runtime verbs Forge must own under option B

Vendoring means owning these namespaces. Grouped by whether Forge can leave them untouched:

- **Take as-is (~40):** `frontmatter`, `find-phase`, `phase-plan-index`, `template`, `scaffold`, `generate-slug`, `current-timestamp`, `git`, `commit`, `worktree`, `workstream`, `config-*`, `validate`, `verify-path-exists`, `verify-summary`, `requirements`, `task`, `state`, `progress`, `history-digest`, and similar leaf utilities.
- **Adapt (~10):** `smart-entry` (add Forge adoption/capability routing — Forge already layers this externally), `phase`, `roadmap`, `milestone`, `verification`, `verify`, `check`, `init`, `docs-init`, `intel`.
- **Drop (~25):** `graphify`, `eval`, `capability` (Forge has its own, richer), `mempalace`-adjacent, `profile-*`, `user-story`, `from-gsd2`, `package-legitimacy`, `prompt-budget`, `resolve-model`, and other GSD-general tooling.

## What Forge has that GSD does not

These are Forge's reason to exist and need no GSD equivalent: capability discovery/consent/qualification, host-runtime assignment and swapping (`forge-runtime`), Unreal lane control and the project write-lock, visual production DAGs, the gameplay gauntlet, bounded work-packet routing with evidence, and the bootstrap gate.

## Recommended sequence

1. **Land `forge-review` first.** It is the explicitly requested one, it is self-contained, and it proves the wrap-and-adapt pattern before committing to the rest.
2. **Wrap Tier 1** so no `gsd-` string is ever shown to a user. Forge Next already re-spells commands per host; extend it to re-spell GSD actions as their Forge equivalents.
3. **Adapt the four game-critical skills:** `forge-execute-phase` (write-lock), `forge-verify-work` (in-engine evidence), `forge-debug` (Unreal traces), `forge-ship` (cook/package).
4. **Then decide on vendoring.** Steps 1–3 deliver the full `forge-*` vocabulary while GSD is still underneath. Vendoring becomes a mechanical follow-up rather than a prerequisite.

## Open questions

- **Version pin.** Forge pins `@opengsd/gsd-core@1.8.0`; the workstation runs 1.9.1. Resolve before vendoring — you would be forking a version you have not been testing against.
- **Licence.** GSD's terms must permit vendoring and redistribution inside the Forge plugin. Unverified.
- **Gate authority.** If Forge wraps GSD's verification gate, GSD stays the authority and the RunnerRoyale invariant holds. If Forge replaces it, Forge must become the *sole* authority — never both. That invariant is what the incident was about.
