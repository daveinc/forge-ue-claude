<!-- forge:workflow
name: doctor
consumes: .forge/capabilities/, .forge/config.json, .uproject, host CLIs
produces: capability contracts and optional proposals (read-only; nothing is installed)
-->

# Forge Doctor — workflow

<purpose>
Classify the environment read-only: what is present, what is proven, and what is merely installed.
</purpose>

<core_principle>
Never install, download, enable, change PATH, write credentials or edit the `.uproject`. Detection is
not qualification.
</core_principle>

<process>

<step name="survey" priority="first">
From the repository root:

```powershell
.\install.ps1 -Mode Survey -ProjectPath "<project>"
```
</step>

<step name="report_hosts">
Read `runtime.detected_hosts`. Report every known host, its CLI presence, its GSD runtime, and
whether it satisfies the prerequisite contract. The assigned host is marked `active`.
</step>

<step name="inspect_environment">
Inspect the resident host's image and tool capabilities, the project, `.uproject`, existing
instructions and config, VCS, UE executables and plugins, native MCP, VibeUE, editor-closed Python,
Blender and its gateway, installed local runtimes and models, entitled services, approved remote
providers, credential presence only, DDC and build tools, and platform visibility.
</step>

<step name="verify_overlay">
Check the overlay against what shipped, before trusting anything read out of it:

```powershell
python <forge-plugin-root>\scripts\forge.py verify --project "<project>"
```

It reports every canon file missing or drifted from the template. Drift is not automatically wrong —
a project may have amended canon deliberately — but an unexplained difference makes every capability
answer below it suspect. Report what drifted and why; re-apply through `forge-bootstrap`, never by
hand.

Read `state_version` in the same payload:

| `state_version` | Meaning | Action |
|---|---|---|
| `CURRENT` | The normal answer | Continue |
| `MIGRATABLE` | `.forge` predates this Forge | Carry out the listed migrations before trusting the state |
| `NEWER` | `.forge` was written by a newer Forge | **Do not operate on it.** The verdict is already `ok: false` — upgrade Forge |

> **Why:** CHANGELOG.md 0.6.0 § *`.forge` state has a version that means something* — 0.5.0 § *Every verb is reachable from a workflow, and a guard keeps it that way*
</step>

<step name="probe_routes">
Probe every declared typed tool route:

```powershell
python <forge-plugin-root>\scripts\forge.py route-status --project "<project>"
```

When Unreal's first-party route does not answer, read `endpoint_disagreement` and `engine_settings`
on that row before concluding the editor is closed. A project that moved `ServerPortNumber` presents
exactly as a project with no editor running: a silent endpoint. Never diagnose this from silence
alone.

Both `bAutoStartServer` and `ServerPortNumber` are read at editor startup, so changing either needs a
restart before it can be true.

Report `session_visible` and `subagent_visible` separately. A route visible to the session but not to
its spawned agents is project scope working as declared — report it so, and name the declared
fallback. Name the remedy without performing it; widening a route to user scope belongs to
`forge-capability-admin`.

Never report a route as available because the server is installed.

> **Why:** CHANGELOG.md 0.6.0 § *A moved MCP port no longer reads as a closed editor* — 0.4.0 § *All three Unreal routes exist, and the verb that reports them says so*
</step>

<step name="classify_detection">
Report executable or plugin detection as `AVAILABLE_UNVERIFIED` until a safe end-to-end probe passes.

Probe each accepted route with known-good and known-bad controls. Never expose or persist credential
values.

Distinguish generation and operation surfaces from planning or prompt-only skills. Never treat
advertised vision, audio or tool support as proof of image, video, mesh or animation generation.
</step>

<step name="emit_proposals">
Emit capability contracts and optional proposals. Compare each worker against the resident-host
baseline for the exact task and complexity class, stating context savings, benefit, effective cost,
permissions, hardware fit, test, fallback and affected workflows.
</step>

<step name="hand_off" priority="last">
Pass proposals to `forge-capability-admin`.

Report which hosts could hold the resident seat and leave the assignment to `forge-runtime`.
</step>

</process>
