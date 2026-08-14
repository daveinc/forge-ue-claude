# Dependency and route policy

## GSD bootstrap

GSD is the required phase engine for the full Forge workflow. Forge exposes it as a separate, preview-first installation boundary:

```powershell
.\install.ps1 -Mode GSD
.\install.ps1 -Mode GSD -Apply
```

The preview displays the exact package, stable pinned version, scope, command, and current detection state without writing. Apply is the only Forge mode that downloads an external package for GSD; it requires explicit user approval and installs the Codex integration globally. Survey then inventories the GSD runtime, skills, and agents, but leaves `workflow.gsd` unqualified until a fresh-session compatibility check proves that GSD and Forge can coexist in the current environment.

## Selection rule

Codex is the resident default because Forge already runs inside it. First establish the Codex baseline for a task, then reject offload routes that lack required access, modality, safety, context, quality, or acceptance evidence. Rank the survivors using:

```text
quality + locality/free advantage + parallelism gain
- retry risk - elapsed time - money - queue pressure - lane contention - handoff cost
```

An installed local route normally wins qualified bounded work when it reduces total context, time or monetary cost. Complex, ambiguous, cross-system and final-synthesis work stays on Codex by default. “Free” is an optimization, not a waiver of verification.

## Context-efficient offload

Decompose long sources into stable, independently verifiable packets. Send local workers only the relevant excerpts/referrals, schema, objective, non-goals and acceptance criteria. Require structured results and evidence. Good candidates include extraction, indexing, asset/image breakdowns, variants, log triage, bounded code/test work, first-pass review and repetitive Blender operations. Evaluate coding, reviewing, visual reasoning and tool operation separately by complexity tier.

## Unreal routes

| Route | Best fit | Main constraint |
|---|---|---|
| Native Unreal MCP | Typed live inspection/mutation, PIE, viewport evidence | Editor open; project write lock |
| VibeUE/live Python | Live arbitrary `unreal.*` gaps and service wrappers | Optional; same editor/project lock |
| Unreal Python/commandlet | Batch imports, audits, LODs, deterministic or heavy/null-RHI-safe work | Editor closed; explicit result file is authority |

No route is a universal fallback. The closure matrix enables only steps a verified route can satisfy.

## Visual routes

Blender is normally the independent DCC lane for mesh, UV, baking, rigging, skinning, and animation. Unreal can author or finish work through Control Rig, Sequencer, retargeting, procedural content, materials, and in-engine tools. Benchmark representative asset classes and permit a split route, such as Blender mesh/UV followed by Unreal rig/animation.

Visual production begins after the compact GDD and primary visual anchors are approved. Gameplay continues with interface-compatible placeholders.

## Codex, Kimi K3 and model providers

Use Codex as resident worker and supervisor. For offload capacity, probe already-installed local runtimes/endpoints first, including but not limited to Kimi K3, followed by already-entitled services and approved remote APIs. Do not download weights or install a runtime implicitly. Store capability and benchmark evidence by task type and complexity, not a global “best model” label.

## Optional integration contract

Every optional integration declares:

```text
capability -> provider -> lane -> enabled steps -> fallback -> probe -> acceptance suite
```

Removing an adapter recasts its seats and blocks only the steps without a valid fallback.

## Lifecycle and activation

Every optional provider begins `UNQUALIFIED`, even when installed or enabled. Register executable surfaces, permissions, integrity, provenance, licence, health, cost, measured context cost, lanes, fallbacks and invalidation triggers. Require scoped consent before installation, activation, network/secrets, external writes, project-descriptor changes or privileged execution.

Qualify the exact provider/version + task class + complexity + environment fingerprint with known-good and seeded-bad controls. Activate only the current phase/packet surface and keep one canonical provider when capabilities overlap. A vision/audio/tool-capable model is not an image, video, mesh or animation generator unless those outputs pass their own suites.
