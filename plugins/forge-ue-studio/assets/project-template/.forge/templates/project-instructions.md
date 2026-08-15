# Project workflow

<!-- FORGE:generated host={{host_id}} source:.forge/templates/project-instructions.md -->
<!-- Do not hand-edit. Edit the template, then run: forge.py host set --host <id> --apply -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `{{skill:gsd-quick}}` for small fixes, doc updates, and ad-hoc tasks
- `{{skill:gsd-debug}}` for investigation and bug fixing
- `{{skill:gsd-execute-phase}}` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

## Forge phase contract

- GSD is the only phase engine. Forge enriches GSD artifacts and routes bounded work; it does not replace the discuss → plan → execute → verify sequence.
- Use `{{skill:forge-next}}` as the normal Forge entry and resume command. It combines Forge readiness with GSD `smart-entry` and dispatches exactly one action.
- Read `.planning/STATE.md` and the active GSD phase artifacts before production work. GSD's `.planning` tree is authoritative.
- Treat `.forge/state/lifecycle.json` as deprecated compatibility history only. Never use or edit it as a phase router.
- Honor every GSD stop/handoff boundary. Start a fresh session and run `{{skill:forge-next}}`; do not auto-chain the next stage in the session that completed the prior stage.
- Keep Forge workflow steps (`FI-*`) distinct from canonical project packet IDs. Register packet IDs once in `.forge/state/packet-registry.json`.
- Never rename or replace a canonical packet ID. A new alias needs an explicit `alias → canonical` record; a genuinely new packet needs `derived_from` provenance.
- Route execution only for registered work orders. Use typed GSD/Forge agents when the active runtime exposes them and the user authorized delegation; record inline fallback as degraded execution.
- Persist state before every stop. Resume from files, not chat memory.

## Runtime contract

- The active runtime host for this project is **{{host_display_name}}** (`{{host_id}}`). It is the resident worker for orchestration, design, code, review, visual generation, and tool operation.
- The runtime is an assignment, not an assumption. `.forge/runtime.json` records it, and it can be swapped at any stage without losing project state.
- Every host-specific surface in this project is generated from the neutral canon in `.forge/`. Never hand-edit a generated file; edit the canon and re-render.
- Canonical (portable, never host-specific): `.forge/agents/*.json`, `.forge/directives.md`, `.forge/templates/`, `.forge/state/`, `.forge/capabilities/`, and the GSD `.planning` tree.
- Generated (host-specific, safe to discard and re-render): this file and `{{host_agent_dir}}/`.
- To change the resident runtime, run `forge.py host set --host <id> --project . --apply`, then start a fresh session in the new host and run `{{skill:forge-next}}`.
- Qualification evidence is recorded per host. A route qualified under one runtime does not transfer to another; re-probe after a swap.
