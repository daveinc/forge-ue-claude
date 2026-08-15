---
name: forge-init
description: Start a greenfield Unreal game through a design interview, compact GDD, visual direction, and parallel playable/visual DAGs. Use for a new game idea, or when a directory's state must be detected before inception.
---

# Forge Init

## Entry gate

1. Run `scripts/forge.py next --project <root>` before interpreting or changing project state.
2. Dispatch the recommended action and **STOP** when it is not `forge-init`.
3. Continue only on `greenfield-ready`. Never invoke Forge Init recursively.
4. Read the host's project instruction file, `.forge/state/packet-registry.json`, `.forge/directives.md`, and current `.planning` artifacts. Treat `.forge/state/lifecycle.json` as deprecated history.
5. Run `gsd-new-project` without `--auto`. Preserve its questions, agent dispatch, approvals, commits, state files, and stop points.

## Workflow

1. Run `forge-doctor`. Record verified and assumed facts separately.
2. Declare the typed tool routes this game will use:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py mcp add --project <project-root> --id <provider> --command <exe> --arg <arg> --apply
   ```

   Run `mcp-status` to confirm each route before depending on it. Declare capabilities, lane and fallbacks in the entry for any provider outside the shipped catalog. Amend the set later through `forge-capability-admin`.
3. Ask one highest-value question at a time. Resolve mandate, audience, platforms, camera, core loop, progression, tone, scope, content boundaries, references, performance envelope, business constraints, and decision owners. Offer concrete options without forcing the framing.
4. Record every unknown as an explicit hypothesis, deferral, or spike. Never silently choose one, and never let changeable art block the playable contract.
5. Run a divergent design pass before locking the compact GDD. Generate materially different core-loop, progression, narrative and production options, test them against the mandate, and keep rejected tradeoffs in the decision ledger.
6. Produce the compact GDD, decision ledger, and acceptance spine. Link large lore, research and references as sources rather than worker payload.
7. Develop the first visual pillars, negative references, character/world sheets and storyboard candidates on the resident host. Offload bounded alternatives to qualified workers; preserve prompt, model/source, licence and date.
8. Obtain human approval for the primary visual direction. Create replacement-safe asset interfaces for scale, skeleton, sockets, collision, material slots, animation events, and budgets.
9. Compile concurrent playable, visual, narrative, audio, research and QA workstreams. Synchronize them only through requirements, accepted decisions and asset interfaces. Register each canonical packet ID once in `.forge/state/packet-registry.json`; require an explicit alias record for an alias and `derived_from` provenance for a new packet.
10. Run `forge-plan-convergence` on the inception artifacts. Never dispatch a walking-skeleton packet from Forge Init.
11. Re-run `scripts/forge.py next --project <root>` once inception artifacts are persisted. Take the next action from GSD smart-entry; never hardcode a phase number or command.
12. **STOP.** Require a fresh task and present `forge-next`. Never run phase discussion, planning, routing, implementation or verification here.

Read [project-inception.md](references/project-inception.md) when conducting the interview or compiling the two DAGs.
Read [gsd-lifecycle.md](references/gsd-lifecycle.md) before completing inception or describing the next step.

## Gates

- Never auto-approve the mandate, primary visual direction, subjective art, game feel, or release.
- Never start full production while a decision that changes architecture or content scope is implicit.
- Never present a project packet as a Forge workflow step. Use `FI-*` for Forge bootstrap and inception controls, GSD's identifiers for lifecycle, and registered IDs such as `P0`/`V0` for production packets.
