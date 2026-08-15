# Project workflow

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `$gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `$gsd-debug` for investigation and bug fixing
- `$gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

## Forge phase contract

- GSD is the only phase engine. Forge enriches GSD artifacts and routes bounded work; it does not replace the discuss → plan → execute → verify sequence.
- Use `$forge-next` as the normal Forge entry and resume command. It combines Forge readiness with GSD `smart-entry` and dispatches exactly one action.
- Read `.planning/STATE.md` and the active GSD phase artifacts before production work. GSD's `.planning` tree is authoritative.
- Treat `.forge/state/lifecycle.json` as deprecated compatibility history only. Never use or edit it as a phase router.
- Honor every GSD stop/handoff boundary. Start a fresh task and run `$forge-next`; do not auto-chain the next stage in the task that completed the prior stage.
- Keep Forge workflow steps (`FI-*`) distinct from canonical project packet IDs. Register packet IDs once in `.forge/state/packet-registry.json`.
- Never rename or replace a canonical packet ID. A new alias needs an explicit `alias → canonical` record; a genuinely new packet needs `derived_from` provenance.
- Route execution only for registered work orders. Use typed GSD/Forge agents when the active runtime exposes them and the user authorized delegation; record inline fallback as degraded execution.
- Persist state before every stop. Resume from files, not chat memory.
