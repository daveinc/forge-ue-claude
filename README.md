# Forge UE Studio

Forge UE Studio is a Codex plugin for planning and orchestrating an Unreal Engine game from its first design interview through production and release. Forge keeps Codex as the resident studio director and worker, then routes bounded jobs to Unreal, Blender, local models, MCP servers, APIs, and human reviewers only after those routes are available and qualified for the exact work.

Forge uses GSD as its only phase engine. Forge adds game-development departments, capability discovery, immutable work packets, review gates, persistent project state, visual production, and Unreal-specific lane control without replacing GSD's discuss → plan → execute → verify boundaries.

The current release provides the installation and orchestration spine. Its only external-package installation path is an explicit, preview-first GSD mode pinned to a stable version. It does not install Unreal Engine, Blender, MCP servers, model runtimes, model weights, or platform SDKs. It also does not claim that a detected tool can perform production work until its route passes Forge's probes and acceptance checks.

The full architecture and staged build proposal are in [the Forge counterplan](docs/COUNTERPLAN.md).

## Requirements

| Requirement | Needed for | Notes |
|---|---|---|
| Windows PowerShell | Included installer | Run commands from the Forge repository root. |
| Codex CLI with plugin support | Installing and using Forge | Confirm with `codex plugin --help`. |
| Node.js, npm, and npx | Installing GSD through Forge | Required only for `-Mode GSD`; Forge pins the requested package version. |
| Python 3.10 or newer | Surveying or adopting Unreal projects | Forge has no third-party Python package dependencies. |
| Git | Safe production work | Strongly recommended before Forge performs durable project writes. |
| Unreal Engine project | Unreal execution | Not required for the initial game-design interview. |
| GSD | Full phase workflow | Install separately with the approved, pinned GSD mode below. |

Unreal MCP, VibeUE, Unreal Python, Blender, local model runtimes, image/audio/video tools, and build services are optional capability routes. Install only the routes your project needs.

## Quick install

Download or clone this repository, open PowerShell in its root, and preview the installation:

```powershell
.\install.ps1 -Mode Plugin
```

The preview prints the Codex commands without changing configuration. Apply the installation when the paths look correct:

```powershell
.\install.ps1 -Mode Plugin -Apply
```

Confirm that Forge is installed and enabled:

```powershell
codex plugin list
```

Look for `forge-ue-studio@forge-ue-studio-local` with status `installed, enabled`.

Preview the separate GSD installation. This makes no changes and shows the exact pinned package and command:

```powershell
.\install.ps1 -Mode GSD
```

After reviewing that output, explicitly approve and apply it:

```powershell
.\install.ps1 -Mode GSD -Apply
```

Forge currently defaults to stable `@opengsd/gsd-core@1.8.0` and installs its Codex integration globally. Use `-GsdVersion X.Y.Z` only when you intentionally want a different audited release. GSD installation is independent of Forge plugin installation, so either can be repaired or updated without silently changing the other.

Start a **new Codex task** after installation. Codex loads newly installed plugin skills and tools into new tasks, as described by the [official OpenAI plugin documentation](https://learn.chatgpt.com/docs/plugins).

## First use: start a new game

You do not need an Unreal project yet. Create the intended project directory, then install the project control plane before the first design interview:

```powershell
New-Item -ItemType Directory -Path "D:\Unreal Projects\MyGame"
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame"
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

The pre-project overlay installs `.forge`, project `AGENTS.md`, and project-local agents before a `.uproject` exists. Open a **fresh Codex task in that directory** and enter:

```text
Use $forge-next to inspect this directory and take me to the correct next Forge or GSD action.
```

`$forge-next` is the normal front door. It routes an incomplete installation to `$forge-bootstrap --resume`; after bootstrap it scans for existing design documents, Unreal/code, and GSD `.planning` state. It routes a true greenfield project to `$forge-init`, existing docs to `$gsd-ingest-docs`, existing code to `$gsd-onboard`, or an active project to the exact action returned by GSD smart-entry. Each routed workflow keeps its own stop boundary.

Forge should:

1. Ask one high-value design question at a time.
2. Build a compact GDD decision ledger instead of forwarding the entire conversation to every worker.
3. Establish the story, gameplay pillars, visual anchors, constraints, and unresolved decisions.
4. Produce parallel playable and visual production DAGs once their shared interfaces are approved.
5. Survey the environment before recommending integrations.
6. Keep optional providers unqualified until their exact task class and complexity tier pass evaluation.

When the project-shell phase creates the `.uproject`, rerun Survey/Profile to expose Unreal-specific routes. The original Forge/GSD state remains in the same project root.

## Core behavior

- Interview the user until a compact GDD and unresolved decision list are explicit.
- Produce storyboard/beat boards, character direction, and world direction before launching full production.
- Start playable and visual DAGs in parallel once their shared asset interfaces are approved.
- Use Codex as the resident default for orchestration, design, coding, review, visual generation and Blender/Unreal operation when the required tools are exposed.
- Offload bounded, context-heavy, repetitive or parallel work to qualified optional models only when measured quality, context, time, and cost evidence beats the resident route.
- Benchmark Blender and Unreal authoring by asset class. Split stages when Blender frees the editor lane or Unreal's Control Rig, Sequencer, retargeting, procedural tools, or in-engine workflow wins.
- Keep native Unreal MCP, optional VibeUE live Python, and editor-closed Unreal Python/commandlets as separate routes behind one capability contract.
- Register optional surfaces with trust, consent, integrity, permissions, qualification, context cost and invalidation state; activate only the smallest phase-specific set.
- Converge non-trivial plans through independent source-grounded review with bounded cycles and human escalation on stalls.
- Preserve attempt results, read-only forensics and evidence-backed learning promotion instead of relying on chat memory.
- Isolate concurrent code/text writers in clean-base Git worktrees; use LFS locks or a project-exclusive lease for Unreal binary assets.
- Keep production metrics canonical in JSON and generate visually verified XLSX/CSV scorecards only for human-facing gates or portfolio review.
- Run adversarial playable/in-engine-frame comparisons as bounded Gauntlet rounds after a playable loop exists.
- Continue mechanics with tagged placeholders whenever final art is unavailable.

## How to use Forge

Invoke a Forge workflow by naming its skill in your prompt. You can give Forge an outcome in ordinary language; the explicit skill name is useful when you want predictable entry into a particular workflow.

| Skill | Use it when |
|---|---|
| `$forge-next` | Entering or resuming any Forge project; detecting adoption, bootstrap, existing docs/code, and the authoritative GSD next action. |
| `$forge-bootstrap` | Installing/resuming the project-local Forge control plane and delegated installation checks. |
| `$forge-init` | Starting greenfield game inception; on an existing/partial project it first defers to Forge Next. |
| `$forge-doctor` | Surveying Codex, Unreal, VCS, MCP, DCC, local-model, build, and platform availability without changing anything. |
| `$forge-capability-admin` | Registering, consenting to, testing, activating, or invalidating an optional tool or model route. |
| `$forge-research` | Teaching Forge about a new MCP, API, CLI, model, documentation set, or project corpus. |
| `$forge-plan-convergence` | Challenging a non-trivial phase plan before execution. |
| `$forge-route-work` | Compiling and dispatching bounded work packets across available studio lanes. |
| `$forge-quality-gate` | Defining acceptance tests or independently reviewing a work result. |
| `$forge-visual-production` | Producing concept boards, character/world direction, asset breakdowns, meshes, rigs, animation, materials, or Unreal art integration. |
| `$forge-gameplay-gauntlet` | Improving a playable loop through bounded variants, harsh critique, blind comparison, and a human feel gate. |
| `$forge-retrospective` | Investigating a failed/interrupted workflow or promoting a repeatedly successful recipe. |

### Example prompts

Survey an existing project without changing it:

```text
Use $forge-doctor to inspect D:\Unreal Projects\MyGame. Report what is verified, detected but unqualified, unavailable, and assumed. Do not install or change anything.
```

Prepare the next production phase:

```text
Use $forge-plan-convergence on the next vertical-slice phase. Verify every referenced code path and Unreal asset, then stop for my approval before execution.
```

Run parallel production:

```text
Use $forge-route-work to compile the approved phase into bounded gameplay, visual, research, and QA packets. Keep Codex resident and use optional workers only where exact qualification evidence exists.
```

Develop the visual side while placeholder gameplay continues:

```text
Use $forge-visual-production to create the character and world direction, then plan asset production across Codex, Blender, and Unreal according to the routes that are actually available and qualified.
```

Improve a playable slice:

```text
Use $forge-gameplay-gauntlet to compare the current combat loop against our approved reference and feel rubric. Keep the loop bounded and stop at the human feel gate.
```

### Normal production sequence

```text
$forge-next
    -> dispatch exactly one of: bootstrap / ingest / onboard / init / GSD action
    -> routed workflow reaches its persisted STOP boundary
fresh task -> $forge-next
    -> GSD smart-entry supplies the current discuss / plan / execute / verify / recovery action
```

GSD's `.planning` artifacts are the sole phase authority. Forge Next reads them through GSD smart-entry and adds only Forge adoption/capability routing, so a new task resumes from files rather than inherited chat. The old `.forge/state/lifecycle.json` is compatibility history and must not drive work. `$forge-visual-production` runs alongside playable development once the shared art/gameplay interfaces exist. `$forge-gameplay-gauntlet` begins after there is a playable loop or stable in-engine presentation target.

## Repository layout

```text
.agents/plugins/marketplace.json       repo-local Codex marketplace
plugins/forge-ue-studio/               installable Codex plugin
  skills/                              progressive studio workflows
  dependencies/                        capability and route declarations
  schemas/                             contracts for state and work packets
  assets/project-template/             reversible project overlay
  scripts/forge.py                     survey/next/install/verify CLI
install.ps1                            Windows entry point
scripts/validate_repo.py               repository validation
tests/                                 standard-library tests
```

## Manual plugin installation

The PowerShell installer registers this repository as the local marketplace named `forge-ue-studio-local`, then installs the Forge plugin from it. If you need to run those operations manually:

```powershell
codex plugin marketplace add "C:\path\to\forge-ue-studio"
codex plugin add forge-ue-studio@forge-ue-studio-local
codex plugin list
```

After pulling a Forge update, rerun `.\install.ps1 -Mode Plugin -Apply` and start a new Codex task so the updated skill snapshot is loaded.

## Adopt a project directory

Supply an existing pre-project directory, a directory containing exactly one `.uproject`, or the `.uproject` path itself. This removes the former bootstrap deadlock: Forge state and agents can exist before the UE project-shell packet.

Start with the read-only survey from PowerShell, or open a new Codex task in the project and ask:

```text
Use $forge-bootstrap to adopt this project. Preserve existing work, delegate the applicable installation investigations, and stop at each persisted fresh-task handoff.
```

The survey is read-only:

```powershell
.\install.ps1 -Mode Survey -ProjectPath "D:\Unreal Projects\MyGame"
```

Preview the overlay without writing:

```powershell
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame"
```

Apply the overlay explicitly:

```powershell
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

Verify later:

```powershell
.\install.ps1 -Mode Verify -ProjectPath "D:\Unreal Projects\MyGame"
```

Refresh the detected capability profile without overwriting the accepted registry:

```powershell
.\install.ps1 -Mode Profile -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

Validate a Forge contract or route a qualified packet:

```powershell
.\install.ps1 -Mode Validate -ContractKind attempt-result -InputPath ".\attempt.json"
.\install.ps1 -Mode Route -ProjectPath "D:\Unreal Projects\MyGame" -RequestPath ".\route-request.json"
```

Only `GSD -Apply` downloads and runs an external package, and it always uses the displayed, pinned version. Project modes never download packages, model weights, plugins, or binaries; never change PATH or system settings; and never edit the `.uproject`. They write a detected capability profile whose optional providers remain `UNQUALIFIED`. Existing differing files are preserved and a `.forge-proposed` sibling is written for review.

### What project adoption adds

Forge applies a reversible project-local overlay:

```text
.forge/
  acceptance/       acceptance-suite registry
  capabilities/     detected, consented, and qualified routes
  context/          phase-scoped activation policy
  learnings/        evidence-backed reusable recipes
  research/         approved sources and capability research
  reviews/          plan and result review state
  state/            work orders, install state, and lane leases
                    bootstrap evidence and canonical packet registry
  visual/           visual-production registry
  config.json       project Forge policy
  directives.md     persistent operating rules
.codex/agents/       Forge studio-role agent templates
AGENTS.md             GSD/Forge phase and identity enforcement
```

Forge does not replace your GDD, source tree, Content directory, `.uproject`, or VCS history. It adds persistent orchestration state beside them.

### Installer command reference

| Mode | Writes? | Purpose |
|---|---:|---|
| `Plugin` | Only with `-Apply` | Register the repository marketplace and install Forge in Codex. |
| `GSD` | Only with `-Apply` | Preview or install a pinned GSD Core release for Codex globally. |
| `Survey` | No | Inventory the project and available host capabilities. |
| `Install` | Only with `-Apply` | Preview or apply the project-local Forge overlay. |
| `Verify` | No | Check that the accepted overlay still matches Forge's template and rules. |
| `Profile` | Only with `-Apply` | Refresh detected capabilities without granting qualification. |
| `Next` | No | Combine Forge readiness with authoritative GSD smart-entry and return valid next actions. |
| `Route` | No project mutation | Select a provider for a schema-valid route request using recorded qualification evidence. |
| `Lifecycle` | No | Read deprecated compatibility status only; transitions are rejected. |
| `Validate` | No | Check a Forge JSON contract against its required top-level fields. |

For `Install` and `Profile`, omitting `-Apply` is always the preview path.

Inspect the state-aware next action:

```powershell
.\install.ps1 -Mode Next -ProjectPath "D:\Unreal Projects\MyGame"
```

The command is read-only. It returns a `forge.smart-entry/v1` snapshot and ordered actions; `$forge-next` presents and dispatches exactly one of them.

## Capability and tool behavior

Forge distinguishes four ideas that are easy to confuse:

1. **Installed:** software or a plugin exists.
2. **Detected:** Forge can see a declaration, executable, model, or endpoint.
3. **Qualified:** a specific provider/version passed known-good and seeded-bad tests for an exact task class, complexity tier, and environment.
4. **Activated:** the smallest required surface is enabled for the current phase or work packet.

Detection never grants production authority. If an optional route is missing or unqualified, Forge keeps Codex as the default worker or blocks only the step that has no safe fallback.

The principal Unreal routes are:

| Route | Editor state | Typical use |
|---|---|---|
| Native Unreal MCP | Open | Typed inspection and mutation, PIE, viewport evidence. |
| VibeUE/live Python | Open | Live `unreal.*` operations that fill verified MCP gaps. |
| Unreal Python/commandlet | Closed | Batch imports, audits, LODs, deterministic processing, and heavy/null-RHI-safe jobs. |
| Human editor | Open | Subjective or unsupported work requiring direct operator control. |

These routes share the Unreal project write lock and must not mutate the same project concurrently. Blender can operate as an independent DCC lane where asset contracts and file ownership allow it.

## Troubleshooting

### Forge does not appear in a task

1. Run `codex plugin list`.
2. Confirm `forge-ue-studio@forge-ue-studio-local` is `installed, enabled`.
3. Rerun `.\install.ps1 -Mode Plugin -Apply` from the current Forge repository.
4. Start a new Codex task; existing tasks do not automatically acquire a newly installed skill snapshot.

### `codex` is not found

Forge will not install or modify Codex automatically. Install or repair the Codex CLI through the supported Codex setup, confirm `codex plugin --help`, then rerun the preview.

### GSD is missing or not visible to Forge

1. Run `.\install.ps1 -Mode GSD` and review the pinned package and current detection state.
2. Run `.\install.ps1 -Mode GSD -Apply` only after approving the external install.
3. Rerun the Forge survey and confirm `workflow.gsd` is detected. GSD 1.8.0 places shared Codex skills under `~/.agents/skills`, agents under `~/.codex/agents`, and its runtime under `~/.codex/gsd-core`; Forge checks both that current layout and the older `~/.codex/skills` layout.
4. Start a new Codex task so newly installed GSD skills and agents are loaded.

### Project adoption says the project path is invalid

Pass an existing directory or a full `.uproject` path. Pre-project directories are supported. If a directory contains multiple top-level `.uproject` files, pass the intended file explicitly; Forge refuses to guess.

### Forge tries to continue after a stop point

Stop the current task. Open a fresh project task and run `$forge-next`. It reads GSD smart-entry state and routes paused, blocked, failed-verification, planning, execution, and verification situations without trusting prior chat or the deprecated Forge lifecycle mirror.

### A detected model, MCP, Blender, or Unreal route is not used

This is expected until the exact route is consented, probed, and qualified. Ask:

```text
Use $forge-capability-admin to explain the missing qualification evidence for this route. Do not install or activate anything without my approval.
```

### Forge proposes `.forge-proposed` files

The target already contains a different file. Forge preserves it and writes the proposed version beside it for review instead of overwriting accepted local policy.

## Dependency policy

Core: Codex, this plugin, Python 3.10+, and upstream GSD. Forge provides a separately approved, stable-version-pinned GSD installer because GSD is required for the full phase workflow. Unreal is required only for Unreal execution. A working VCS route is required before durable production writes.

Everything else is capability-based: native Unreal MCP, Unreal Python/Editor Scripting plugins, VibeUE, Blender and its gateway, local model runtimes and provider-neutral adapters, image/audio/video providers, BuildGraph/Horde, DDC, and platform SDKs. Codex remains the fallback when an offload provider is absent. See [dependency policy](docs/dependency-policy.md).

## Status and verification

Run the repository's no-download checks:

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

Verified by the included tests: manifest/skill/schema structure, resident-Codex/offload policy, dependency references, survey behavior, dry-run safety, capability profiling, exact-scope route qualification, result-contract validation, applied overlay creation, and idempotent reapplication. Assumed until probed on a target workstation: actual Unreal/MCP/VibeUE/Blender/local-model capabilities and their performance rankings.
