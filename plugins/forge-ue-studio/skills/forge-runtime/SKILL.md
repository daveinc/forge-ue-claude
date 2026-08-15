---
name: forge-runtime
description: Inspect, assign, or swap the resident AI runtime host for a Forge project without losing project state. Use when choosing which AI CLI runs a project, moving a project between Claude Code, Codex, or another Forge-capable host, adding support for a new host, re-rendering stale host surfaces, or answering whether a project is portable.
---

# Forge Runtime

A project records its resident host in `.forge/runtime.json`. Change it at any stage — before inception, mid-phase, or at a resume boundary — without losing planning state, packets, or evidence.

## The portability contract

Two kinds of files exist in a Forge project. Never confuse them.

| Kind | Location | Rule |
|---|---|---|
| **Canon** — portable, authoritative | `.forge/agents/*.json`, `.forge/directives.md`, `.forge/templates/`, `.forge/state/`, `.forge/capabilities/`, `.planning/` | Never host-specific. Edit these. |
| **Rendered** — disposable, host-specific | The project instruction file (`CLAUDE.md`, `AGENTS.md`, …) and the host agent directory (`.claude/agents/`, `.codex/agents/`, …) | Generated from canon. Never hand-edit. |

Reject any host name, skill prefix, or vendor path written into canon.

## Inspect

List known hosts, their prerequisites, and which CLIs are present:

```powershell
python <forge-plugin-root>/scripts/forge.py host list
```

Show the current assignment and whether rendered surfaces are current:

```powershell
python <forge-plugin-root>/scripts/forge.py host status --project <project-root>
```

`surfaces` reports `CURRENT`, `STALE`, or `MISSING` per file. Anything other than `CURRENT` means the project was edited or moved without re-rendering; fix it before doing production work.

## Assign or swap

1. Confirm the target host satisfies the prerequisite contract. `host list` reports `prerequisites.satisfied`; a host missing any required capability is refused.
2. Preview the change. Without `--apply` nothing is written:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py host set --host <id> --project <project-root>
   ```

3. Review the action list. Expect `create`/`regenerate` for the incoming host and `retire` for the outgoing host's generated files. Any `propose` action means a local edit exists that Forge will not overwrite — resolve it first.
4. Apply, then stop:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py host set --host <id> --project <project-root> --apply
   ```

5. Start a **fresh session in the new host** and run `forge-next`. Never continue a swap in the session that performed it; the new host has not loaded the new instruction file or agents.

## What a swap does and does not change

Preserved: `.planning` phase state, `.forge/state` packets and leases, canonical packet IDs, `.forge/agents` definitions, directives, and research.

Regenerated: the project instruction file and project-local agents, re-rendered from canon in the new host's format and skill spelling.

Re-pointed: GSD's `runtime` key in `.planning/config.json`, the only key Forge writes there. The sync is deferred when GSD has not created that file yet, and skipped for a host declaring no GSD runtime name; the swap result reports both, and neither is a failure.

Invalidated: provider qualification evidence and host context-cost measurements. Re-probe through `forge-capability-admin` before trusting an offload route after a swap; routing rejects an evaluation recorded under a different host.

## Adding a new host

Append a profile to `plugins/forge-ue-studio/hosts/registry.json` declaring its CLI, skill-invocation prefix, discovery roots, project surface (instruction filename, agent directory, agent format), plugin install commands, GSD install arguments, and the capabilities it `provides`. Never edit Forge code to add a host. Validate with `python scripts/validate_repo.py`.

Profile example and degradation rules: [host runtimes](../../../../docs/host-runtimes.md).

## Boundaries

- Never swap hosts to escape a failing gate. Investigate with `forge-retrospective` first.
- Never edit a rendered file to change behaviour. Edit `.forge/agents/*.json` or `.forge/templates/project-instructions.md`, then re-render.
- Never assume a mid-phase swap is free. Announce the stale-qualification consequence before applying it.
