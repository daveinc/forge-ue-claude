# Forge UE Studio

**Design it. Build it. Ship it.**

A host-agnostic plugin for planning and orchestrating an Unreal Engine game — from the first design interview through production and release.

## What is Forge UE Studio

Forge runs your game project as a studio. One assigned AI runtime holds the resident seat — director, designer, coder, reviewer, tool operator — and bounded jobs go to Unreal, Blender, local models, MCP servers, APIs, or human reviewers only after those routes are proven fit for the exact work. A detected tool is never assumed to be a working one.

The runtime is an **assignment, not an assumption**. A project records its host in `.forge/runtime.json` and can swap it — Claude Code, Codex CLI, or any runtime meeting the prerequisite contract — at any stage, including mid-phase, without losing planning state, packets, or evidence.

Forge uses [GSD](https://github.com/open-gsd/gsd-core) as its only phase engine, invoked in place and never forked. Forge adds game-development departments, capability discovery, immutable work packets, review gates, visual production, and Unreal lane control on top of GSD's discuss → plan → execute → verify boundaries.

## How it works

1. **Adopt** — a reversible overlay installs into your project directory. It works before a `.uproject` exists.
2. **Discuss** — Forge interviews you one question at a time and builds a compact GDD decision ledger.
3. **Plan** — phases become plans that declare asset interfaces, lanes, and mutation risk, then face bounded convergence review.
4. **Execute** — approved plans run under the Unreal write-lock and lane leases, with work packets routed to qualified lanes.
5. **Verify and ship** — UAT plus in-engine evidence, then cook, package, and PR.

Every step stops at a boundary and resumes from files. A new session starts with `forge-next`, never with what the last conversation remembered.

## Quickstart

Clone this repository, open PowerShell in its root, and install the plugin for your host:

```powershell
.\install.ps1 -Mode Host -HostAction list      # which runtimes can hold the seat?
.\install.ps1 -Mode Plugin                     # preview
.\install.ps1 -Mode Plugin -RuntimeHost codex -Apply
```

Claude Code installs plugins from inside a session, so Forge prints the two commands to run there instead of applying them.

Install the pinned phase engine, previewing first:

```powershell
.\install.ps1 -Mode GSD
.\install.ps1 -Mode GSD -Apply
```

Adopt a project directory — an empty one is fine:

```powershell
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

A new project declares Unreal's first-party MCP route at `http://127.0.0.1:8000/mcp`. To bind it, enable the **Unreal MCP** (`ModelContextProtocol`) and **AllToolsets** plugins in your `.uproject`, keep the editor open, and check the route:

```powershell
.\install.ps1 -Mode McpStatus -ProjectPath "D:\Unreal Projects\MyGame"
```

`AVAILABLE_VERIFIED` means the endpoint answered an MCP handshake. Anything else means Unreal work degrades to the editor-closed or human route.

Then open a **fresh session in that directory** and say:

```text
Use forge-next to inspect this directory and take me to the correct next action.
```

Full steps: [Install Forge](docs/how-to/install-forge.md) · [Your first game](docs/tutorials/your-first-game.md) · [Adopt an existing project](docs/tutorials/adopt-an-existing-project.md)

## Documentation

Full index: **[docs/README.md](docs/README.md)**

**Tutorials**
- [Your first game](docs/tutorials/your-first-game.md) — empty folder to first phase.
- [Adopt an existing project](docs/tutorials/adopt-an-existing-project.md) — bring Forge to existing code, content, or docs.

**How-to guides**
- [Install Forge](docs/how-to/install-forge.md) · [Swap the resident runtime](docs/how-to/swap-runtime-host.md) · [Troubleshoot](docs/how-to/troubleshoot.md)

**Reference**
- [Skills](docs/reference/skills.md) — every `forge-` verb and when to use it.
- [Installer](docs/reference/installer.md) — every `install.ps1` mode and flag.
- [Repository and project layout](docs/reference/repository-layout.md) · [Failure contract](docs/failure-contract.md) · [Host runtimes](docs/host-runtimes.md)

**Explanation**
- [How Forge works](docs/explanation/how-forge-works.md) — the studio model and the capability ladder.
- [Dependency and route policy](docs/dependency-policy.md) · [GSD independence map](docs/gsd-independence-map.md) · [The counterplan](docs/COUNTERPLAN.md)

## Forge verbs, GSD verbs

Both are installed and both are yours. GSD is a complete toolset in its own right — run any `gsd-` command whenever you want it.

What Forge adds is the game side: when it **routes** an action it emits its own verb, because the Forge verb carries the work the bare GSD command has no reason to do — lane leases and the Unreal write-lock, the acceptance registry, canonical packet IDs, asset-interface checks, in-engine evidence. Take the Forge route for game production and you get those gates; call GSD directly and you get GSD, which is often exactly right for a quick fix, a spike, or anything outside production.

Commands Forge does not route are listed with their reason and a spelling you can run, not hidden. Spell a skill the way your host expects: `/forge-next` in Claude Code, `$forge-next` in Codex.

The Forge verbs you will use daily:

| Skill | Use it when |
|---|---|
| `forge-next` | Entering or resuming any project. The front door. |
| `forge-init` | Starting a new game from nothing. |
| `forge-discuss-phase` → `forge-plan-phase` → `forge-route-work` | Running a phase. |
| `forge-verify-work` | Validating finished work with in-engine evidence. |
| `forge-resume-work` | Returning to work that was interrupted or paused. |
| `forge-doctor` | Asking what is actually available, changing nothing. |

All 31: [skills reference](docs/reference/skills.md).

## Status

```powershell
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

Verified by the included tests: manifest/skill/schema structure, host registry and prerequisite contract, host-surface rendering and byte-identical swap round-trip, cross-host qualification staleness, verb translation and suppression of out-of-scope actions, GSD runtime-key sync across swaps, the bootstrap closure gate, resident/offload policy, typed tool routing and user-scope consent, result-contract validation, and idempotent overlay reapplication.

Also verified against real Git: a lane lease refuses a second holder of the same lane or exclusive group, two racing processes produce one holder and one refusal, failed isolation leaves no lease behind, worktrees are created from the named revision and discarded on a failed outcome, and an expired lease is recovered rather than inherited.

Verified against real `git lfs`: the tests run a Git LFS locking server, so `exec acquire` takes an actual lock, a path another writer already holds is refused by git rather than by Forge, a partly-locked set is unlocked again on rollback, and a lock that cannot be released is reported instead of swallowed.

Verified against a real MCP endpoint: the tests run a server that answers `initialize` over both JSON and SSE framing. A route earns `AVAILABLE_VERIFIED` only from an answer, an endpoint that errors or that is listening without speaking MCP earns `UNAVAILABLE_OPTIONAL`, and a live server the host's configuration does not declare is reported as undeclared rather than as available.

Assumed until probed on a target workstation: Unreal/VibeUE/Blender/local-model capabilities and their performance rankings. The MCP verification path is tested against a stand-in server, so what a workstation adds is proof that Epic's own plugin answers it.

Not covered by CI: nothing here launches Unreal. The tests run on `windows-latest` with no engine, so the Claude → MCP → editor → Blueprint → PIE path is proven on a workstation with the editor open, never by a green build.

## License

MIT. See [LICENSE](LICENSE).
