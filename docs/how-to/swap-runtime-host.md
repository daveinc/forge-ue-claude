# Swap the resident runtime

A project's runtime host is an assignment recorded in `.forge/runtime.json`, and it can change at any stage — including mid-phase and at a resume boundary.

## 1. See the current assignment

```powershell
.\install.ps1 -Mode Host -HostAction status -ProjectPath "D:\Unreal Projects\MyGame"
```

`surfaces` reports `CURRENT`, `STALE`, or `MISSING` per file. Anything other than `CURRENT` means the project was edited or moved without re-rendering.

## 2. Preview the swap

This writes nothing:

```powershell
.\install.ps1 -Mode Host -HostAction set -RuntimeHost codex -ProjectPath "D:\Unreal Projects\MyGame"
```

Review the action list. Expect `create`/`regenerate` for the incoming host and `retire` for the outgoing one. A `propose` action means a local edit exists that Forge will not overwrite — resolve it first.

## 3. Apply it

```powershell
.\install.ps1 -Mode Host -HostAction set -RuntimeHost codex -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

## 4. Start a fresh session in the new host and run `forge-next`

Never continue a swap in the session that performed it: that session has not loaded the new instruction file or agents.

## What changes

| | |
|---|---|
| **Preserved** | `.planning` phase state, `.forge/state` packets and leases, canonical packet IDs, agent definitions, directives, research. |
| **Regenerated** | The project instruction file and project-local agents, in the new host's format and skill spelling. |
| **Retired** | The previous host's generated files; the directory is removed when it empties. |
| **Re-pointed** | GSD's `runtime` key in `.planning/config.json`, the only key Forge writes there. |
| **Invalidated** | Provider qualification evidence and host context-cost measurements. |

Swapping away and back reproduces the original surfaces byte for byte.

Qualification does not cross hosts. A route qualified under one runtime is stale under another, and routing rejects an evaluation recorded under a different host with an explicit re-probe reason. Re-probe through `forge-capability-admin` before trusting an offload route after a swap.

## Never

- Never swap hosts to escape a failing gate. Investigate with `forge-retrospective` first.
- Never edit a rendered file to change behaviour. Edit canon and re-render.

## Related

- [Host runtimes](../host-runtimes.md) — the full contract, degradation rules, and how to add a host.
