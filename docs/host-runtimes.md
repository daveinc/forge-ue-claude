# Host runtimes

Forge treats the AI runtime as an **assignment**, not an assumption. A project records which runtime holds the resident seat, and that assignment can change at any stage without losing project state.

This document defines the contract a runtime must meet, what a swap actually does, and how to add a host.

## Why the runtime is an assignment

The original Forge release hardcoded one vendor. Every path, command spelling, agent format, and instruction filename assumed it. That made a project non-portable: moving it to another runtime meant rewriting state, and any evidence recorded along the way silently described a runtime that was no longer in use.

Forge now separates two things that were previously fused:

- **The resident seat** — the role of orchestrator, designer, coder, reviewer, and tool operator. Always exactly one host holds it.
- **The host filling it** — a specific runtime, recorded in `.forge/runtime.json`.

Policy, packets, plans, directives, and evidence refer to the *seat*. Only rendering resolves the *host*.

## The prerequisite contract

A runtime can hold the resident seat when it provides every required capability:

| Capability | Why Forge needs it |
|---|---|
| `filesystem-read-write` | Canon and phase state live in files, not chat. |
| `shell-execution` | `forge.py`, GSD, builds, and probes are shelled out. |
| `skill-loading` | Forge ships progressive workflows as `SKILL.md`. |
| `project-instruction-file` | Phase and identity enforcement must load automatically per session. |
| `fresh-session-boundary` | GSD stop/handoff boundaries require starting clean and resuming from files. |
| `gsd-engine` | GSD is the only phase engine; Forge never replaces it. |

Optional capabilities degrade behaviour instead of blocking it:

| Capability | Degradation when absent |
|---|---|
| `project-local-agents` | Delegation is recorded as degraded inline execution rather than typed dispatch. |
| `interactive-question-tool` | Forge prints a numbered list and stops for a reply. |
| `image-generation` | Visual concepts route to an external qualified provider or a human. |
| `mcp-client` | Native MCP routes are unavailable; Unreal work falls back to Python/commandlet or human editor lanes. |

`forge.py host list` reports `prerequisites.satisfied` per host. `host set` refuses a host that cannot meet the required set.

## Canon versus rendered surfaces

| Kind | Location | Rule |
|---|---|---|
| **Canon** | `.forge/agents/*.json`, `.forge/directives.md`, `.forge/templates/`, `.forge/state/`, `.forge/capabilities/`, `.planning/` | Portable and authoritative. Never host-specific. |
| **Rendered** | The project instruction file and the host agent directory | Generated from canon. Disposable. Never hand-edited. |

Canon uses tokens that rendering resolves:

| Token | Resolves to |
|---|---|
| `{{resident}}` | The host's display name |
| `{{skill:forge-next}}` | The host's skill spelling, e.g. `/forge-next` or `$forge-next` |
| `{{host_id}}` / `{{host_display_name}}` | The host identifier and label |
| `{{host_agent_dir}}` / `{{host_instruction_file}}` | The host's project surface paths |

`python scripts/validate_repo.py` fails if canon hardcodes a host spelling, and the test suite asserts that no `{{token}}` survives rendering for any registered host.

## Built-in hosts

| Host | Skill spelling | Instruction file | Agent directory | Agent format |
|---|---|---|---|---|
| `claude` — Claude Code | `/forge-next` | `CLAUDE.md` | `.claude/agents/` | Markdown + frontmatter |
| `codex` — OpenAI Codex CLI | `$forge-next` | `AGENTS.md` | `.codex/agents/` | TOML |
| `generic` — any Forge-capable agent | `forge-next` | `AGENTS.md` | `.agents/agents/` | Markdown + frontmatter |

## Assigning and swapping

```powershell
# What can hold the seat?
.\install.ps1 -Mode Host -HostAction list

# What holds it now, and are surfaces current?
.\install.ps1 -Mode Host -HostAction status -ProjectPath "D:\Unreal Projects\MyGame"

# Preview a swap. Writes nothing.
.\install.ps1 -Mode Host -HostAction set -RuntimeHost codex -ProjectPath "D:\Unreal Projects\MyGame"

# Apply it.
.\install.ps1 -Mode Host -HostAction set -RuntimeHost codex -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

The parameter is `-RuntimeHost` rather than `-Host` because `$Host` is a reserved PowerShell automatic variable.

A swap:

- **Preserves** `.planning` phase state, `.forge/state` packets and leases, canonical packet IDs, agent definitions, directives, and research.
- **Regenerates** the project instruction file and project-local agents in the new host's format and spelling.
- **Retires** the previous host's generated files, and removes the directory when it empties.
- **Invalidates** provider qualification evidence and host context-cost measurements.

Round-tripping is byte-identical: swapping away and back reproduces the original surfaces exactly, which is what makes the assignment reversible rather than destructive.

## Qualification does not cross hosts

A route qualified under one runtime is **STALE** under another. Context windows, tool scopes, image generation, and MCP surfaces all differ, so evidence gathered under one host does not predict behaviour under the next.

Routing enforces this. An evaluation carrying `"host": "<other>"` is rejected as ineligible with an explicit re-probe reason, and the work stays on the resident seat. Record the host on every evaluation; evidence without a host field is treated as belonging to whichever host is active.

## Adding a host

Append a profile to `plugins/forge-ue-studio/hosts/registry.json`. No Forge code changes are required.

```json
{
  "id": "myhost",
  "display_name": "My Agent CLI",
  "vendor": "Example",
  "resident_capability": "worker.myhost.resident",
  "cli": { "executables": ["myhost"], "version_args": ["--version"] },
  "skill_invocation": { "prefix": ":", "example": ":forge-next", "style": "bare-name" },
  "home": { "dir": ".myhost" },
  "discovery": {
    "skill_roots": ["~/.myhost/skills"],
    "agent_root": "~/.myhost/agents",
    "agent_glob": "gsd-*.md"
  },
  "project_surface": {
    "instruction_file": "MYHOST.md",
    "agent_dir": ".myhost/agents",
    "agent_format": "markdown-frontmatter",
    "agent_extension": ".md"
  },
  "plugin": {
    "manifest_dir": ".myhost-plugin",
    "marketplace_manifest": ".myhost-plugin/marketplace.json",
    "marketplace_name": "forge-ue-studio-local",
    "install_commands": ["myhost plugin add ..."],
    "install_is_interactive": true
  },
  "gsd": { "install_args": ["--global"], "runtime_root": "~/.myhost/gsd-core" },
  "provides": ["filesystem-read-write", "shell-execution", "skill-loading",
               "project-instruction-file", "fresh-session-boundary", "gsd-engine"]
}
```

Validation rejects duplicate skill prefixes, unsupported agent formats, a `manifest_dir` with no `plugin.json`, and any host that cannot satisfy the required contract. Only `markdown-frontmatter` and `toml` agent formats are implemented; a host needing another format requires a new renderer in `render_agent`.

## Boundaries

- Never swap hosts to escape a failing gate. Investigate with `forge-retrospective` first.
- Never continue work in the session that performed a swap. Start fresh in the new host and run `forge-next`.
- Never edit a rendered file to change behaviour. Edit canon and re-render.
- Detection never grants the resident seat. `forge-doctor` reports which hosts *could* hold it; `forge-runtime` makes the assignment.
