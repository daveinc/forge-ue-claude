# Skills

Invoke a Forge workflow by naming its skill in your prompt. You can also give Forge an outcome in ordinary language; the explicit skill name is useful when you want predictable entry into a particular workflow.

Spell a skill the way your host expects: `/forge-next` in Claude Code, `$forge-next` in Codex. Forge Next returns commands already spelled for the assigned host.

**Forge verbs do not replace GSD verbs.** GSD is installed alongside Forge and stays directly usable. A Forge verb exists where the game side needs work the bare GSD command does not do — lane leases, the acceptance registry, canonical packet IDs, in-engine evidence — so Forge routes to its own verb and you get those gates. For anything outside game production, calling GSD directly is correct and supported; the [commands Forge does not route](#commands-forge-does-not-route) are listed below with their reasons.

## Lifecycle

| Skill | Use it when |
|---|---|
| `forge-next` | Entering or resuming any Forge project. The normal front door: detects adoption, bootstrap, existing docs/code, and the authoritative next action. |
| `forge-init` | Starting greenfield game inception; on an existing/partial project it first defers to Forge Next. |
| `forge-spec-phase` | A phase goal is vague or contested and needs ambiguity scoring before discussion. |
| `forge-mvp-phase` | Reducing a phase to the thinnest playable loop, and splitting it if it is too big. |
| `forge-discuss-phase` | Settling gameplay and art decisions for a phase before a plan exists. Modes: `--assumptions` (codebase-first, best on an existing project), `--power` (batch all questions), `--list-assumptions`. |
| `forge-plan-phase` | Turning a discussed phase into plans that declare asset interfaces, lanes, and mutation risk. `--dependencies` detects file overlap between phases and feeds the lane leases. |
| `forge-execute-phase` | Running approved plans under the Unreal write-lock and lane leases. |
| `forge-verify-work` | Validating completed work through UAT plus in-engine evidence. |
| `forge-progress` | Checking phase state, execution coverage, and the next action. |
| `forge-phase` | Adding, inserting, removing, or editing phases in the roadmap. |
| `forge-milestone` | Starting, completing, auditing, or summarising a milestone. `--plan-gaps` turns an audit's findings into fix phases. |
| `forge-ship` | Cooking, packaging, verifying, and opening a PR for a verified milestone. |

## Quality and review

| Skill | Use it when |
|---|---|
| `forge-review` | Reviewing a plan, code, security mitigations, or outstanding UAT — graded against your acceptance registry. Modes: default, `--code`, `--security`, `--audit`. |
| `forge-plan-convergence` | Challenging a non-trivial phase plan through bounded convergence cycles before execution. |
| `forge-quality-gate` | Defining acceptance tests or independently reviewing a work result. |
| `forge-gameplay-gauntlet` | Improving a playable loop through bounded variants, harsh critique, blind comparison, and a human feel gate. |

## Production

| Skill | Use it when |
|---|---|
| `forge-visual-production` | Concept boards, character/world direction, asset breakdowns, meshes, rigs, animation, materials, or Unreal art integration. |
| `forge-route-work` | Compiling and dispatching bounded work packets across available studio lanes. |
| `forge-capability-admin` | Registering, consenting to, testing, activating, or invalidating an optional tool or model route. |
| `forge-research` | Teaching Forge about a new MCP, API, CLI, model, documentation set, or project corpus. |

## Setup, context, and recovery

| Skill | Use it when |
|---|---|
| `forge-bootstrap` | Installing or resuming the project-local Forge control plane and delegated installation checks. |
| `forge-doctor` | Surveying runtime hosts, Unreal, VCS, MCP, DCC, local-model, build, and platform availability without changing anything. |
| `forge-runtime` | Inspecting, assigning, or swapping the resident AI runtime host without losing project state. |
| `forge-onboard` | Adopting an existing Unreal project that has no planning state. |
| `forge-ingest-docs` | A project has design documents but no project memory. |
| `forge-map-codebase` | Analysing an unfamiliar or inherited Unreal codebase. |
| `forge-docs-update` | Refreshing documentation after implementation lands. |
| `forge-debug` | Crashes, PIE failures, broken gameplay, or asset problems. |
| `forge-handoff` | Pausing before a context reset. |
| `forge-resume-work` | Returning to work that was interrupted, paused, or left mid-phase. |
| `forge-retrospective` | Investigating a failed workflow or promoting a repeatedly successful recipe. |
| `forge-undo` | Rolling back a phase or plan when execution went wrong. |

## The normal sequence

```text
forge-next
    -> dispatch exactly one of: forge-bootstrap / forge-ingest-docs /
       forge-onboard / forge-init / the current phase verb
    -> routed workflow reaches its persisted STOP boundary
fresh session -> forge-next
    -> the current discuss / plan / execute / verify / recovery action,
       already spelled as a forge- verb for the assigned host
```

A full phase then runs:

```text
forge-spec-phase   (optional, when the goal is contested)
forge-discuss-phase  ->  forge-plan-phase  ->  forge-plan-convergence
                     ->  forge-execute-phase  ->  forge-review
                     ->  forge-verify-work  ->  forge-progress
```

`forge-visual-production` runs alongside playable development once the shared art/gameplay interfaces exist. `forge-gameplay-gauntlet` begins after there is a playable loop or a stable in-engine presentation target.

## Commands Forge does not route

These are working GSD commands. Forge does not front them, because they are not game production — so no Forge verb would add anything, and routing them through one would only put a wrapper in your way. Run them directly. `forge-next` lists any that GSD recommends under `suppressed_actions`, with the spelling for your host.

| GSD command | Why Forge does not route it |
|---|---|
| `gsd-quick`, `gsd-fast` | Trivial-task shortcuts; Forge routes production work through packets. |
| `gsd-capture`, `gsd-review-backlog` | Idea capture and backlog triage. A Forge verb is planned. |
| `gsd-explore`, `gsd-sketch`, `gsd-spike` | Exploration. `forge-explore` is planned; `--sketch` will be greybox rather than HTML mockups. |
| `gsd-workspace`, `gsd-workstreams` | GSD-general isolation. Forge uses lanes and worktrees instead. |
| `gsd-graphify`, `gsd-mempalace-capture`, `gsd-mempalace-recall` | Optional knowledge and memory tooling, outside the lifecycle. |
| `gsd-config`, `gsd-settings`, `gsd-surface`, `gsd-update` | Forge configures and installs itself. |
| `gsd-stats`, `gsd-profile-user`, `gsd-help`, `gsd-manager`, `gsd-inbox` | Not production concerns; Forge Next is the entry point and Forge documents its own surface. |
| `gsd-autonomous` | Forge requires human gates at phase boundaries. |
| `gsd-thread`, `gsd-import`, `gsd-cleanup` | Superseded by `forge-handoff`, `forge-ingest-docs`, and milestone archival. |
| `gsd-eval-review`, `gsd-ai-integration-phase`, `gsd-ultraplan-phase` | LLM-application work and cloud planning, not game production. |

`plugins/forge-ue-studio/verbs/registry.json` is the authority; every GSD command is either fronted there or dropped with its reason, and a command in neither state is a registry gap that `forge-next` reports as `UNMAPPED`.

## Example prompts

Survey an existing project without changing it:

```text
Use forge-doctor to inspect D:\Unreal Projects\MyGame. Report what is verified, detected but unqualified, unavailable, and assumed. Do not install or change anything.
```

Prepare the next production phase:

```text
Use forge-plan-convergence on the next vertical-slice phase. Verify every referenced code path and Unreal asset, then stop for my approval before execution.
```

Run parallel production:

```text
Use forge-route-work to compile the approved phase into bounded gameplay, visual, research, and QA packets. Keep the resident host in the seat and use optional workers only where exact qualification evidence exists.
```

Develop the visual side while placeholder gameplay continues:

```text
Use forge-visual-production to create the character and world direction, then plan asset production across the resident host, Blender, and Unreal according to the routes that are actually available and qualified.
```

Improve a playable slice:

```text
Use forge-gameplay-gauntlet to compare the current combat loop against our approved reference and feel rubric. Keep the loop bounded and stop at the human feel gate.
```
