# Repository and project layout

## What ships in this repository

```text
.claude-plugin/marketplace.json        repo-local Claude Code marketplace
.agents/plugins/marketplace.json       repo-local Codex marketplace
plugins/forge-ue-studio/               installable plugin
  .claude-plugin/plugin.json           Claude Code manifest
  .codex-plugin/plugin.json            Codex manifest
  hosts/registry.json                  runtime host profiles and prerequisite contract
  verbs/registry.json                  GSD command -> Forge verb map, with delegation modes
  references/delegation-contract.md    the PRE / CORE / POST shape every delegating verb follows
  skills/                              one launcher per verb: invocation, flags, what to load
  workflows/                           one procedure per verb, loaded by its launcher
  dependencies/catalog.json            capability and route declarations
  dependencies/route-registry.json     typed routes: mcp servers and process commands alike
  dependencies/route-policy.json       resident default and offload scoring
  schemas/                             contracts for state and work packets
  assets/project-template/             reversible, host-neutral project overlay
    .forge/agents/*.json               canonical studio-role definitions
    .forge/templates/                  instruction template rendered per host
    .forge/mcp.json                    the routes a project declares
  scripts/forge.py                     the CLI: arguments, result contract, exit codes
  scripts/forge_core.py                failure contract, paths, shared primitives
  scripts/forge_executor.py            leases, worktrees and LFS locks, transactionally
  scripts/forge_mcp.py                 typed tool routes and the probes that verify them
  scripts/forge_hosts.py               host registry and rendered host surfaces
  scripts/forge_gsd.py                 the pinned phase engine and the verbs Forge fronts
  scripts/forge_survey.py              read-only capability detection
  scripts/forge_lifecycle.py           where the project stands and what comes next
  scripts/forge_install.py             the reversible project overlay
  scripts/forge_routing.py             which provider earns a work order
  scripts/forge_runtime.py             assigning and reporting the resident seat
install.ps1                            Windows entry point
scripts/validate_repo.py               repository validation
tests/                                 standard-library tests
docs/                                  documentation (see docs/README.md)
```

## What project adoption adds

Forge applies a reversible project-local overlay:

```text
.forge/
  acceptance/       acceptance-suite registry
  capabilities/     detected, consented, and qualified routes
  context/          phase-scoped activation policy
  jobs/             one folder per canonical work order, written by dispatch:
                    brief.md, packet.json, context/ and result.json
  learnings/        evidence-backed reusable recipes
  research/         approved sources and capability research
  reviews/          plan and result review state
  state/            work orders, install state, and lane leases
                    bootstrap evidence and canonical packet registry
  visual/           visual-production registry
  agents/           canonical, host-neutral studio-role definitions
  templates/        instruction template rendered per host
  config.json       project Forge policy
  directives.md     persistent operating rules
  mcp.json          the typed tool routes this project declares
  runtime.json      the assigned resident host and swap history
```

Plus the surfaces rendered for the assigned host, generated from the canon above and safe to discard and rebuild:

```text
CLAUDE.md | AGENTS.md                GSD/Forge phase and identity enforcement
.claude/agents/ | .codex/agents/     Forge studio-role agents in the host's format
.mcp.json                            typed tool routes in the host's format
```

Forge does not replace your GDD, source tree, `Content/` directory, `.uproject`, or VCS history. It adds persistent orchestration state beside them.

`.planning/` belongs to GSD. Forge writes exactly one key in it — `runtime`, so GSD spells its own commands for the assigned host.

## Canon versus rendered

| Kind | Rule |
|---|---|
| **Canon** — `.forge/agents/*.json`, `.forge/directives.md`, `.forge/templates/`, `.forge/state/`, `.forge/capabilities/`, `.planning/` | Portable and authoritative. Never host-specific. Edit these. |
| **Rendered** — the project instruction file, the host agent directory, the host MCP surface | Generated from canon. Disposable. Never hand-edit. |

Full detail: [host runtimes](../host-runtimes.md).
