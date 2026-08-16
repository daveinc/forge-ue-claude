# Forge project directives

These directives are host-neutral. "The resident host" means whichever runtime is assigned in `.forge/runtime.json`; the rules do not change when that assignment changes.

## Runtime portability

- Treat the resident runtime as an assignment recorded in `.forge/runtime.json`, never as a hardcoded vendor. Any host that satisfies the Forge prerequisite contract can hold the seat.
- Keep every host-specific file generated. Canonical state lives in `.forge/` and `.planning/`; host surfaces are rendered from it and may be discarded and rebuilt.
- Never write a host name, skill prefix, or vendor-specific path into canonical state, plans, packets, or evidence. Refer to "the resident host" and let rendering resolve the spelling.
- Record qualification evidence against the host that produced it. A route qualified under one runtime is STALE under another until re-probed.
- On a host swap, re-render surfaces, re-run capability detection, and resume from files. Never resume a swap from chat memory.

## Phase engine

- Keep GSD as the phase engine unless an extension-gap test proves a minimal fork necessary.
- Treat GSD as the only phase state machine. Obtain phase status and next actions from GSD smart-entry through Forge Next; never hardcode the next phase or plan number.
- Use Forge Next after every fresh-session boundary, interruption, or uncertain handoff. It dispatches exactly one Forge/GSD action and stops.
- Treat `.forge/state/lifecycle.json` as deprecated compatibility history, not an authority or mutation target.
- Keep Forge Init step identifiers, GSD phase/plan identifiers and project work-packet identifiers in separate namespaces.
- Register canonical project packet IDs in `.forge/state/packet-registry.json` before routing. Never replace a canonical ID; aliases require an explicit mapping and derived packets require provenance.

## Lanes and capabilities

- Do not mutate Unreal packages without the project write lane and a VCS-safe rollback route.
- Keep native MCP, live Python, editor-closed commandlets, and human editor work mutually exclusive under the project super-lock.
- Ask for capabilities, never named tools. Select only AVAILABLE_VERIFIED routes.
- Treat detection status and task qualification separately. Optional providers begin UNQUALIFIED and pass only the tested task/complexity tier.
- Register executable surfaces, permissions, integrity, provenance, licence, health, cost, context cost, fallbacks, consent and invalidation triggers before activation.
- Activate optional skills, MCPs, APIs and model surfaces only for phases and packets that need them; keep one canonical surface for duplicate capabilities.

## Work routing

- Use the resident host as the default for orchestration, design, code, review, visual generation and Blender/Unreal operation when those surfaces are exposed.
- Offload bounded context-heavy, repetitive or parallel tasks only to qualified optional workers when measured quality, context, time and effective cost improve; never infer zero cost from locality or licensing labels.
- Keep unresolved design, novel architecture, cross-system integration, delicate Unreal mutation, final subjective art and synthesis on the resident host unless another worker proves the exact complexity tier.
- Give offload workers minimal referral packets and require structured evidence; never forward the full GDD or resident conversation by default.
- Run playable and visual DAGs concurrently after their shared asset interfaces are approved.
- Benchmark Blender and Unreal authoring by asset class and allow split-stage routes.
- Use typed GSD/Forge agents for authorized installation and execution jobs when the runtime exposes them. If dispatch is unavailable, mark the inline fallback as degraded instead of presenting it as equivalent delegation.
- Isolate concurrent text/code writers in clean-base Git worktrees; protect binary assets with LFS locks or the project-exclusive lease. Reviewers use read-only copies or diffs.
- Establish that isolation only through `forge.py exec acquire`, and release it only through `forge.py exec release`. A worktree or lock taken by hand leaves the ledger blind to it, which is how two writers end up in one lane.

## Evidence and gates

- Packet results must separate observed facts, inferences, findings, touched artifacts, verification, residual risk and next action.
- Review plans through bounded source-grounded convergence cycles. Stop and escalate when concern counts stall or the cycle limit is reached.
- Run Research discovery, classification, conflict, approval, evaluation and retrieval registration during first install and whenever capabilities change.
- Run read-only forensics before repair when state is inconsistent. Promote learnings only after repeated evidence-backed success; never erase failed attempts.
- Use adversarial gameplay and in-engine-frame comparison as a bounded vertical-slice loop with blind alternatives and a human stop/feel gate.
- Require machine evidence plus independent review before DONE. Human owners retain subjective art and feel gates.
- Preserve provenance for generated and third-party assets. Never persist secret values.
- Keep scorecard truth in JSON; generate visually verified XLSX/CSV views only when a human or production gate benefits from them.
