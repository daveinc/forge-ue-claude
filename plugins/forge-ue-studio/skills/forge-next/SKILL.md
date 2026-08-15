---
name: forge-next
description: Detect persisted Forge adoption, bootstrap, project-document, Unreal/code, and authoritative GSD planning state, present the valid next actions, dispatch exactly one, and stop. Use as the normal entry or resume command for any Forge project, after a fresh-task boundary or interruption, when a project is partially built, or when Forge Init must avoid restarting existing work.
---

# Forge Next

Use GSD as the sole phase-state authority. Forge Next is a launcher, not another workflow engine and not a worker.

## Detect

1. Resolve the current project root. Do not infer state from the conversation.
2. Run the bundled read-only command:

   ```powershell
   python <forge-plugin-root>\scripts\forge.py next --project <project-root>
   ```

3. Parse the `forge.smart-entry/v1` result. It combines Forge readiness with GSD's `smart-entry --json` snapshot.
4. Treat `.planning` and the GSD snapshot as authoritative for phase status. Treat `.forge/state/lifecycle.json` as deprecated compatibility history only; never use it to override GSD or mutate it.
5. Read the `runtime` block. It names the assigned host and whether its rendered surfaces are current. Commands in `actions` are already spelled for that host — present them verbatim.
6. If the situation is `host-surfaces-stale`, the project's generated surfaces do not match the assigned runtime. Route to `forge-runtime` and stop; do not perform production work against stale instructions or agents.
7. If the detector fails, run `forge-doctor`; do not guess the active phase.

## Present and dispatch

1. Show the summary and ordered actions. Put the recommended action first.
2. Unless `--auto` was explicitly supplied, let the user select an action. If an interactive question tool is unavailable, print a numbered list and stop for a reply.
3. Display the chosen command before dispatch.
4. Dispatch exactly one existing Forge or GSD skill. Then stop. The chosen skill owns subsequent work and its own context boundary.
5. Never perform the routed work inside Forge Next and never chain a second command.

## Forge Init integration

When Forge Init invokes this detector at its entry gate:

- If the recommended command is `forge-init`, return control to Forge Init and continue inception without recursively invoking it.
- Otherwise dispatch the recommended action and stop Forge Init.
- Existing design documents route through `gsd-ingest-docs`; an existing Unreal/code project without planning routes through `gsd-onboard`; an existing `.planning` tree follows the exact GSD smart-entry action.
- A missing or incomplete Forge control plane routes through `forge-bootstrap` or `forge-bootstrap --resume` before any design or production work.

This makes re-running `forge-init` safe in a partially built project: it becomes a state scan and handoff, not a restart.
