# Forge UE Studio

Forge UE Studio is a Codex plugin for planning and orchestrating an Unreal Engine game from its first design interview through production and release. Forge keeps Codex as the resident studio director and worker, then routes bounded jobs to Unreal, Blender, local models, MCP servers, APIs, and human reviewers only after those routes are available and qualified for the exact work.

Forge is GSD-compatible: GSD remains the phase engine while Forge adds game-development departments, capability discovery, work packets, review gates, persistent project state, visual production, and Unreal-specific lane control.

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

Unreal MCP, VibeUE, Unreal Python, Blender, Kimi K3, Ollama, LM Studio, image/audio/video tools, and build services are optional capability routes. Install only the routes your project needs.

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

You do not need an Unreal project yet. Open a new, projectless Codex task and enter:

```text
Use $forge-init to start a brand-new Unreal Engine game. Interview me one question at a time. Do not install dependencies or create project files until the game mandate and initial production plan are approved.
```

Forge should:

1. Ask one high-value design question at a time.
2. Build a compact GDD decision ledger instead of forwarding the entire conversation to every worker.
3. Establish the story, gameplay pillars, visual anchors, constraints, and unresolved decisions.
4. Produce parallel playable and visual production DAGs once their shared interfaces are approved.
5. Survey the environment before recommending integrations.
6. Keep optional providers unqualified until their exact task class and complexity tier pass evaluation.

When the design is ready and an Unreal project exists, adopt that project using the commands in [Adopt an Unreal project](#adopt-an-unreal-project).

## Core behavior

- Interview the user until a compact GDD and unresolved decision list are explicit.
- Produce storyboard/beat boards, character direction, and world direction before launching full production.
- Start playable and visual DAGs in parallel once their shared asset interfaces are approved.
- Use Codex as the resident default for orchestration, design, coding, review, visual generation and Blender/Unreal operation when the required tools are exposed.
- Offload bounded, context-heavy, repetitive or parallel work to qualified local models, including Kimi K3 as one recommended option, when doing so saves resident context or time without lowering quality.
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
| `$forge-init` | Starting a new game or adopting an existing Unreal project. |
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
$forge-init
    -> $forge-doctor
    -> $forge-capability-admin / $forge-research as needed
    -> $forge-plan-convergence
    -> $forge-route-work
    -> $forge-quality-gate
    -> $forge-retrospective
```

`$forge-visual-production` runs alongside playable development once the shared art/gameplay interfaces exist. `$forge-gameplay-gauntlet` begins after there is a playable loop or stable in-engine presentation target.

## Repository layout

```text
.agents/plugins/marketplace.json       repo-local Codex marketplace
plugins/forge-ue-studio/               installable Codex plugin
  skills/                              progressive studio workflows
  dependencies/                        capability and route declarations
  schemas/                             contracts for state and work packets
  assets/project-template/             reversible project overlay
  scripts/forge.py                     survey/install/verify CLI
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

## Adopt an Unreal project

Supply either the project directory containing exactly one `.uproject` file or the `.uproject` path itself.

Start with the read-only survey from PowerShell, or open a new Codex task in the project and ask:

```text
Use $forge-init to adopt this existing Unreal project. Survey it first, preserve existing work, identify unresolved design and technical decisions, and show me the proposed Forge overlay before applying it.
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
  visual/           visual-production registry
  config.json       project Forge policy
  directives.md     persistent operating rules
.codex/agents/       Forge studio-role agent templates
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
| `Route` | No project mutation | Select a provider for a schema-valid route request using recorded qualification evidence. |
| `Validate` | No | Check a Forge JSON contract against its required top-level fields. |

For `Install` and `Profile`, omitting `-Apply` is always the preview path.

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

### Project adoption says no `.uproject` was found

Pass a directory containing exactly one top-level `.uproject`, or pass the full `.uproject` path. Forge refuses to guess between multiple project files.

### A detected model, MCP, Blender, or Unreal route is not used

This is expected until the exact route is consented, probed, and qualified. Ask:

```text
Use $forge-capability-admin to explain the missing qualification evidence for this route. Do not install or activate anything without my approval.
```

### Forge proposes `.forge-proposed` files

The target already contains a different file. Forge preserves it and writes the proposed version beside it for review instead of overwriting accepted local policy.

## Dependency policy

Core: Codex, this plugin, Python 3.10+, and upstream GSD. Forge provides a separately approved, stable-version-pinned GSD installer because GSD is required for the full phase workflow. Unreal is required only for Unreal execution. A working VCS route is required before durable production writes.

Everything else is capability-based: native Unreal MCP, Unreal Python/Editor Scripting plugins, VibeUE, Blender and its gateway, local model runtimes and adapters such as Kimi K3, image/audio/video providers, BuildGraph/Horde, DDC, and platform SDKs. Codex remains the fallback when an offload provider is absent. See [dependency policy](docs/dependency-policy.md).

## Status and verification

Run the repository's no-download checks:

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

Verified by the included tests: manifest/skill/schema structure, resident-Codex/offload policy, dependency references, survey behavior, dry-run safety, capability profiling, exact-scope route qualification, result-contract validation, applied overlay creation, and idempotent reapplication. Assumed until probed on a target workstation: actual Unreal/MCP/VibeUE/Blender/local-model capabilities and their performance rankings.
