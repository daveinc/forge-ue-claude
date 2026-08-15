---
name: forge-doctor
description: Survey a Forge, host, GSD, Unreal, VCS, MCP, DCC, model, build, and platform environment without changing it. Use before installation, adoption, route selection, a host swap, or dependency troubleshooting.
---

# Forge Doctor

## Workflow

1. Run the survey from the repository root:

   ```powershell
   .\install.ps1 -Mode Survey -ProjectPath "<project>"
   ```

2. Read `runtime.detected_hosts`. Report every known host, its CLI presence, its GSD runtime, and whether it satisfies the prerequisite contract. The assigned host is marked `active`.
3. Inspect the resident host's image and tool capabilities, the project, `.uproject`, existing instructions and config, VCS, UE executables and plugins, native MCP, VibeUE, editor-closed Python, Blender and its gateway, installed local runtimes and models, entitled services, approved remote providers, credential presence only, DDC and build tools, and platform visibility.
4. Probe every declared typed tool route:

   ```powershell
   python <forge-plugin-root>\scripts\forge.py mcp-status --project "<project>"
   ```

   Report `session_visible` and `subagent_visible` separately. Report a route visible to the session but not to its spawned agents as project scope working as declared, with the declared fallback named. Name the remedy without performing it; widening a route to user scope belongs to `forge-capability-admin`. Never report a route as available because the server is installed.
5. Report executable or plugin detection as `AVAILABLE_UNVERIFIED` until a safe end-to-end probe passes.
6. Probe each accepted route with known-good and known-bad controls. Never expose or persist credential values.
7. Distinguish generation and operation surfaces from planning or prompt-only skills. Never treat advertised vision, audio, or tool support as proof of image, video, mesh, or animation generation.
8. Emit capability contracts and optional proposals. Compare each worker against the resident-host baseline for the exact task and complexity class, stating context savings, benefit, effective cost, permissions, hardware fit, test, fallback, and affected workflows.
9. Pass proposals to `forge-capability-admin`. Never install packages, download models, enable UE plugins, change PATH, write credentials, or edit the `.uproject` without separate explicit approval.
10. Report which hosts could hold the resident seat and leave the assignment to `forge-runtime`.

Read [classification.md](references/classification.md) when translating survey facts into capability status.
