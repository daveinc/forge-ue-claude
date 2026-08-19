# Forge UE Studio

**Design it. Build it. Ship it.**

A host-agnostic plugin for planning and orchestrating an Unreal Engine game — from the first design interview through production and release.

## What is Forge UE Studio

Forge runs your game project as a studio. One assigned AI runtime holds the resident seat — director, designer, coder, reviewer, tool operator — and bounded jobs go to Unreal, Blender, local models, MCP servers, APIs, or human reviewers only after those routes are proven fit for the exact work. A detected tool is never assumed to be a working one.

The runtime is an **assignment, not an assumption**. A project records its host in `.forge/runtime.json` and can swap it — Claude Code, Codex CLI, or any runtime meeting the prerequisite contract — at any stage, including mid-phase, without losing planning state, packets, or evidence.

Forge uses [GSD](https://github.com/open-gsd/gsd-core) as its only phase engine, invoked in place and never forked. The two split planning between them: **GSD owns planning artifacts** — `.planning/`, phases, plans, summaries, and the schedule, which Forge reads and never writes — while **Forge owns build doctrine**, the domain procedure for making a game in Unreal: what needs building, in what order, with which capabilities and tools, and what evidence closes a step. *"Add a red magic spell"* means nothing to a phase engine; Forge is what turns it into an ability, Niagara systems, a cast animation, a socket, hit handling and an input binding, then hands each down as a written job. See [build doctrine](docs/explanation/build-doctrine.md).

On top of GSD's discuss → plan → execute → verify boundaries, Forge adds game-development departments, capability discovery, immutable work packets, review gates, visual production, and Unreal lane control.

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

A new project declares Unreal's first-party MCP route at `http://127.0.0.1:8000/mcp`. To bind it, enable the **Unreal MCP** (`ModelContextProtocol`) and **AllToolsets** plugins in your `.uproject`, and keep the editor open.

Two things beyond enabling the plugins decide whether that route ever binds, and both are read at **editor startup** — changing either takes effect only after a restart:

| Setting | Default | Why the route stays silent without it |
|---|---|---|
| `bAutoStartServer` | `False` | Enabling the plugin does not make the server listen. Launch with `-ModelContextProtocolStartServer`, set this to `True`, or run `ModelContextProtocol.StartServer` in the editor console. |
| `ServerPortNumber` | `8000` | If your project moved it, Forge is probing the wrong endpoint and an open editor reads exactly like a closed one. |

Both live in `Config/DefaultEditorPerProjectUserSettings.ini` (or `Saved/Config/<Platform>/…`, which wins) under `[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]`. Forge reads them: when the handshake fails it compares the configured port and path against the endpoint it probed and **names the mismatch first**, because a moved port is the one cause that looks identical to every other. Then check the route:

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
- [Build doctrine](docs/explanation/build-doctrine.md) — what Forge owns, what GSD owns, and what crosses between them.
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

Also verified against real Git: a lane lease refuses a second holder of the same lane or exclusive group, two racing processes produce one holder and one refusal, failed isolation leaves no lease behind, worktrees are created from the named revision and discarded on a failed outcome, and an expired lease is recovered only when its owning process is actually gone.

Verified against real processes: a lease past its expiry whose owner is still running keeps its lane and is reported as overdue rather than freed, a recycled pid does not read as the original owner, and an Unreal editor holding a project is detected from the process table even when its MCP endpoint is silent.

Verified against real `git lfs`: the tests run a Git LFS locking server, so `exec acquire` takes an actual lock, a path another writer already holds is refused by git rather than by Forge, a partly-locked set is unlocked again on rollback, and a lock that cannot be released is reported instead of swallowed.

Verified against a real MCP endpoint: the tests run a server that answers `initialize` over both JSON and SSE framing. A route earns `AVAILABLE_VERIFIED` only from an answer, an endpoint that errors or that is listening without speaking MCP earns `UNAVAILABLE_OPTIONAL`, and a live server the host's configuration does not declare is reported as undeclared rather than as available.

Assumed until probed on a target workstation: Unreal/VibeUE/Blender/local-model capabilities and their performance rankings. The MCP verification path is tested against a stand-in server, so what a workstation adds is proof that Epic's own plugin answers it.

Not covered by the default CI: nothing on `windows-latest` launches Unreal, because there is no engine there. [`tests/unreal/run_unreal_acceptance.ps1`](tests/unreal/run_unreal_acceptance.ps1) closes that gap where an engine exists. It builds a throwaway project and drives a real editor end to end:

```
clean fixture -> install Forge -> launch editor -> MCP initialize handshake ->
create Blueprint -> compile it -> run PIE -> read actor state -> capture the viewport ->
close the editor -> run a commandlet -> verify its result file
```

Every stage asserts something only a live engine can settle, and the run is green against UE 5.8: **13 passed, 0 failed, 0 unproven.** Run it on a workstation, or nightly through [`unreal-nightly.yml`](.github/workflows/unreal-nightly.yml) once a self-hosted runner labelled `unreal` exists and the repository variable `UNREAL_RUNNER` is set — until then that workflow skips cleanly rather than queuing forever.

The Blueprint and PIE stages go through [`mcp_client.py`](tests/unreal/mcp_client.py), a small streamable-HTTP MCP client that lives with the tests rather than in the plugin, because Forge itself only ever performs `initialize` — a probe needs to know whether a route answers, not to drive it. Every tool name and argument shape in those stages was read off a live handshake, never inferred: `tools/list` returns only `list_toolsets`, `describe_toolset` and `call_tool`, and everything else is reached through `call_tool`. Two behaviours worth knowing before writing against this server: it answers on a keep-alive `text/event-stream` with no content length, which `urllib` reads as an empty body, and it applies **no schema defaults**, so a parameter marked optional must still be supplied.

## License

MIT. See [LICENSE](LICENSE).
