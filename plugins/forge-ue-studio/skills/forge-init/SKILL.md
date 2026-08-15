---
name: forge-init
description: Start or adopt an Unreal game project through a structured design interview, compact GDD, visual direction, capability-aware planning, and parallel playable/visual work DAGs. Use when a user presents a new game idea, wants Forge added to an existing project, or asks to begin full game production.
---

# Forge Init

Turn an idea into approved, schedulable studio work, then hand control to GSD's persisted phase loop. Forge Init is project inception; it is not an execution phase.

## Entry gate

1. Read the project `AGENTS.md`, `.forge/state/lifecycle.json`, `.forge/state/packet-registry.json`, `.forge/directives.md`, and `.planning/STATE.md` if present.
2. If the Forge overlay or completed bootstrap is absent, route to `$forge-bootstrap` and stop.
3. The lifecycle must name `$forge-init` as `next_command`. Apply `init-start`; do not edit lifecycle JSON by hand.
4. If `.planning/PROJECT.md` is absent, run `$gsd-new-project` without `--auto` as the canonical project/requirements/roadmap initialization workflow. Preserve all of its questions, agent dispatch, approvals, commits and state files. Forge artifacts link to GSD decisions; they do not create a competing phase engine. Even when the user later chooses autonomous execution, Forge's persisted fresh-task boundaries remain mandatory.

## Workflow

1. Run `$forge-doctor` before committing to tool-specific routes. Preserve verified and assumed facts separately.
2. Map unresolved gaps, then ask one highest-value question at a time. Resolve mandate, audience, platforms, camera, core loop, progression, tone, scope, content boundaries, references, performance envelope, business constraints, and decision owners. Offer concrete options without forcing the framing.
3. Record unknowns as explicit hypotheses, deferrals or spikes. Do not silently choose them or make changeable art block the playable contract.
4. Run a divergent design pass before locking the compact GDD. Generate materially different core-loop, progression, narrative and production options, test them against the mandate, and preserve rejected tradeoffs in the decision ledger.
5. Produce the compact GDD, decision ledger and acceptance spine. Keep large lore, research, and references as linked sources rather than worker payload.
6. Have Codex develop the first visual pillars, negative references, character/world sheets and storyboard/beat-board candidates, using exposed image generation for art/photo concepts when available. Send bounded alternatives or breakdowns to qualified local workers when useful; preserve prompts, model/source, licence and date.
7. Obtain human approval for the primary visual direction. Create replacement-safe asset interfaces for scale, skeleton, sockets, collision, material slots, animation events, and budgets.
8. Compile concurrent playable, visual, narrative, audio, research and QA workstreams. Synchronize them only through explicit requirements, accepted decisions and asset interfaces. Register each canonical packet ID once in `.forge/state/packet-registry.json`; later plans must reuse it. An alias requires an explicit alias record, and a genuinely new packet requires `derived_from` provenance.
9. Run `$forge-plan-convergence` on the inception/roadmap artifacts. Do **not** dispatch a walking-skeleton packet from Forge Init.
10. Apply lifecycle event `init-complete`. This must verify `.planning/PROJECT.md`, `.planning/ROADMAP.md`, and `.planning/STATE.md` and persist `$gsd-discuss-phase 1` as the next command.
11. **STOP.** Require a fresh project task and present only the persisted next command. Do not invoke phase discussion, planning, routing, implementation or verification in the Forge Init task.

Read [project-inception.md](references/project-inception.md) when conducting the interview or compiling the two DAGs.
Read [gsd-lifecycle.md](references/gsd-lifecycle.md) before completing inception or describing the next step.

## Gates

Never auto-approve the mandate, primary visual direction, subjective art, game feel, or release. Do not start full production while a decision that changes architecture or content scope is still implicit.

Never present a project packet as a Forge workflow step. Use `FI-*` only for Forge bootstrap/inception controls, GSD's own phase/plan identifiers for lifecycle, and registered project IDs such as `P0`/`V0` for production packets.
