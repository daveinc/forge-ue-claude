<!-- forge:workflow
name: handoff
consumes: .forge/state/leases.json, .forge/state/work-orders.json, .forge/jobs/<work-order>/, .forge/runtime.json, editor state
produces: handoff context naming every held lease, its job folder, and the producing host
-->

# Forge Handoff — workflow

<purpose>
Pause deliberately: leave behind what a return session cannot re-derive — which lanes this session
holds, which job folder the work was being done from, and which host produced it.
</purpose>

<core_principle>
A session that ends holding a lease it never named hands the next one a lane that looks busy and is
not. Say what is held, then decide its fate here rather than letting the process exit decide it.
</core_principle>

<process>

<step name="read_what_is_held" priority="first">
Do not describe the lane state from memory. Read it:

```powershell
python <forge-plugin-root>/scripts/forge.py exec status --project <project-root>
```

This names every live lease, its lane, its work order and its expiry, plus anything already
quarantined. **Do not run `exec supervise` here** — supervision sweeps leases whose owner exited, and
this session has not exited. The point of a handoff is to record the lane state, not to recover it.
</step>

<step name="decide_each_lease">
Every lease read above gets a decision, written into the handoff:

| Return expected | Action |
|---|---|
| Within the two-hour TTL | Keep it and say so. `forge.py exec renew` in the returning session extends it |
| Later, or unknown | Release it through `forge-route-work`'s `release_lease` with a real outcome, so the order reaches `ACCEPTED` or `REJECTED` rather than resting at `DISPATCHED` forever |

An order left at `DISPATCHED` in `.forge/state/work-orders.json` is indistinguishable from work still
running, which is exactly the ambiguity a handoff exists to remove.

A held LFS lock or a live git worktree is a write-lock: name the target, not just the lease.

> **Why:** CHANGELOG.md 0.7.0 § *An order that finished says so*
</step>

<step name="name_the_restore_point">
Name `.forge/jobs/<work-order>/` for every order the session was working. That folder holds
`brief.md`, `packet.json` and `context/` as they were rendered at dispatch, and it is a stronger
restore than the handoff prose — the prose says what was intended, the folder says what was actually
handed to the worker.

Record the interrupted step by name, and which of the brief's steps had produced their `produces`.

> **Why:** [build doctrine](../../../docs/explanation/build-doctrine.md) § *The job tree*
</step>

<step name="record_the_producing_host">
Read the assigned host from `.forge/runtime.json` and record it in the handoff.

Capability qualification is host-scoped, so a return in a different host invalidates every offload
route this session was relying on. A handoff that does not name its host cannot warn about that.
</step>

<step name="record_editor_state">
Record whether an Unreal editor is open on this project, and on which lane the work sat —
editor-open, editor-closed, or packaged. A resume that guesses wrong reproduces nothing.
</step>

<step name="run_gsd_pause">
Run GSD's pause workflow for the phase-context half. It owns the narrative handoff artifact; Forge
owns everything above, which GSD has no way to know.
</step>

<step name="point_at_the_return" priority="last">
Point the user at `forge-resume-work`, and say that it resumes from `.forge/state/` and the job
folder rather than from this document. This document is the human summary; the state files are the
authority.
</step>

</process>
