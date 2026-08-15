---
name: forge-doctor
description: Survey and verify a Forge, runtime-host, GSD, Unreal, VCS, MCP, DCC, model-provider, build, and platform environment without installing or changing it. Use before Forge installation, project adoption, route selection, runtime-host selection or swap, dependency troubleshooting, or after engine/tool/plugin changes.
---

# Forge Doctor

Build a machine-readable environment snapshot and clearly separate detection, verification, absence, and assumptions.

## Workflow

1. Run the bundled CLI survey from the repository root:

   ```powershell
   .\install.ps1 -Mode Survey -ProjectPath "<project>"
   ```

2. Read `runtime.detected_hosts` from the snapshot. It reports every known runtime host, whether its CLI is present, whether its GSD runtime is installed, and whether it satisfies the Forge prerequisite contract. The assigned host is marked `active`.
3. Inspect the resident host's image/tool capabilities, the project, `.uproject`, existing instructions/config, VCS, UE executables/plugins, native MCP, VibeUE, editor-closed Python, Blender/gateway, installed local runtimes/models, entitled services, approved remote providers, credential presence only, DDC/build tools, and platform visibility.
4. Probe every typed tool route declared in `dependencies/mcp-registry.json`:

   ```powershell
   python <forge-plugin-root>\scripts\forge.py mcp-status --project "<project>"
   ```

   Report `session_visible` and `subagent_visible` separately for every route. A route visible to the session but not to its spawned agents is project scope working as declared, not a fault; delegated work on that lane takes the declared fallback. Name the remedy without performing it — widening a route to user scope belongs to `forge-capability-admin`. Never report a route as available on the strength of the server being installed.
5. Treat executable or plugin detection as `AVAILABLE_UNVERIFIED` until a safe end-to-end probe passes.
6. Probe each accepted route independently with known-good and known-bad controls. Never expose or persist credential values.
7. Distinguish actual generation/operation surfaces from planning or prompt-only skills. A model advertising vision/audio/tools is an input/tool capability, not proof of image, video, mesh or animation generation.
8. Emit capability contracts plus optional proposals. Compare each worker against the resident-host baseline for the exact task/complexity class and state context savings, benefit, effective cost, permissions, hardware fit, test, fallback, and affected workflows.
9. Pass proposals through `forge-capability-admin`. Do not install packages, download models, enable UE plugins, change PATH, write credentials, or edit the `.uproject` without separate explicit approval.

Detection never selects a runtime. Report which hosts *could* hold the resident seat and let `forge-runtime` make the assignment.

Read [classification.md](references/classification.md) when translating survey facts into capability status.
