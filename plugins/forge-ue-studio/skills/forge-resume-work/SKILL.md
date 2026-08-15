---
name: forge-resume-work
description: Resume interrupted game project work from persisted state after a context reset, a fresh session, or a handoff. Use when returning to a project that was paused mid-phase, when a session ended without finishing, or when the previous context is gone.
---

# Forge Resume Work

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user. GSD workflow: `resume-project.md`.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape, the delegation modes, and the rules not repeated here.

## PRE — Forge

1. Run `forge-next` first. Routing comes from persisted Forge and GSD state, never from what the previous session said.
2. If the runtime block reports stale surfaces, route to `forge-runtime` and stop.
3. Read `.forge/state/leases.json`. Reclaim or release every lane lease the interrupted session still holds before work restarts.

## CORE — GSD

1. Contain GSD's resume workflow. It owns phase state and decides where work restarts.

## POST — Forge

1. Compare the host recorded in the handoff with the assigned host in `.forge/runtime.json`. If they differ, treat provider qualification evidence as stale and re-probe through `forge-capability-admin` before taking any offload route.
2. Confirm the editor state the handoff recorded — open project, held locks, in-flight builds — before resuming production work.
3. Hand control to the action `forge-next` recommends, then stop.
