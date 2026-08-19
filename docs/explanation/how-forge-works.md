# How Forge works

Forge is a studio, not a code generator. One assigned AI runtime holds the resident seat — director, designer, coder, reviewer, tool operator — and bounded jobs leave that seat only for routes proven fit for the exact work.

## The studio model

- Interview the user until a compact GDD and an explicit list of unresolved decisions exist.
- Produce storyboard/beat boards, character direction, and world direction before launching full production.
- Start playable and visual DAGs in parallel once their shared asset interfaces are approved.
- Use the resident host for orchestration, design, coding, review, visual generation, and Blender/Unreal operation wherever the required tools are exposed.
- Offload bounded, context-heavy, repetitive, or parallel work to a qualified optional model only when measured quality, context, time, and cost evidence beats the resident route.
- Converge non-trivial plans through independent source-grounded review with bounded cycles, escalating to a human on a stall.
- Preserve attempt results, read-only forensics, and evidence-backed learning promotion instead of relying on chat memory.
- Continue mechanics with tagged placeholders whenever final art is unavailable.

## Installed, detected, qualified, activated

Four ideas that are easy to confuse, and the distinction Forge is built on:

1. **Installed** — software or a plugin exists.
2. **Detected** — Forge can see a declaration, executable, model, or endpoint.
3. **Qualified** — a specific provider/version passed known-good and seeded-bad tests for an exact task class, complexity tier, and environment.
4. **Activated** — the smallest required surface is enabled for the current phase or work packet.

Detection never grants production authority. When an optional route is missing or unqualified, Forge keeps the resident host as the default worker, or blocks only the step that has no safe fallback. Qualification is also host-scoped: evidence gathered under one runtime does not predict behaviour under another.

## The Unreal routes

| Route | Editor state | Typical use |
|---|---|---|
| Native Unreal MCP | Open | Typed inspection and mutation, PIE, viewport evidence. |
| VibeUE/live Python | Open | Live `unreal.*` operations that fill verified MCP gaps. |
| Unreal Python/commandlet | Closed | Batch imports, audits, LODs, deterministic processing, heavy or null-RHI-safe jobs. |
| Human editor | Open | Subjective or unsupported work requiring direct operator control. |

These routes share the Unreal project write lock and must not mutate the same project concurrently. Blender operates as an independent DCC lane where asset contracts and file ownership allow it, and Blender-versus-Unreal authoring is benchmarked by asset class rather than assumed.

Concurrent code and text writers are isolated in clean-base Git worktrees; Unreal binary assets use LFS locks or a project-exclusive lease.

## Forge and GSD

They are two tools, both installed, that do different jobs. GSD is the phase engine and a complete workflow toolset on its own. Forge is the game-development layer on top of it, and it is invoked in place — never edited, never copied — so upstream GSD fixes arrive without a merge.

Forge takes charge where game work needs something GSD has no reason to do. Each delegating verb has the same shape: Forge applies its own preconditions (build doctrine for the task class, capability qualification, the Unreal write-lock, canonical packet IDs, game-dev framing), hands the mechanical work to the stock GSD workflow, then applies its own gates (acceptance registry, in-engine evidence, asset-interface checks).

Planning splits between them. GSD owns the **planning artifacts** — `.planning/`, phase IDs, plans, summaries, the schedule — and writes every one of them; Forge reads that state and never writes it. Forge owns **build doctrine**: what a game of this kind needs built, in what order, with which capabilities and tools, and what evidence closes a step. GSD schedules the phase; Forge says what a phase of this kind consists of. See [build doctrine](build-doctrine.md).

That is why a routed action is a Forge verb rather than the GSD command underneath it: the Forge verb is the GSD workflow *plus* the game-specific work around it, and dispatching the bare command in its place silently drops the second half. It is a statement about what Forge emits, not a restriction on you.

**GSD stays directly usable.** Both surfaces are installed, and running `gsd-quick`, `gsd-spike`, or any other GSD command yourself is supported and often correct — the project instruction file Forge renders points at GSD's own verbs for small fixes and debugging. `verbs/registry.json` records, for every GSD command, either the Forge verb that fronts it or an explicit reason Forge does not route it. A command Forge does not route is not unavailable: `forge-next` reports it with its reason and the spelling that runs it.

See [the delegation contract](../../plugins/forge-ue-studio/references/delegation-contract.md), [build doctrine](build-doctrine.md), and [the independence map](../gsd-independence-map.md).

## What Forge is not

It does not install Unreal Engine, Blender, MCP servers, model runtimes, model weights, or platform SDKs. Its only external-package installation path is an explicit, preview-first GSD mode pinned to a stable version. And it does not claim a detected tool can perform production work until that route passes its probes and acceptance checks.
