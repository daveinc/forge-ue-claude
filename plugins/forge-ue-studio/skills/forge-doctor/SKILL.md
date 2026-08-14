---
name: forge-doctor
description: Survey and verify a Forge, Codex, GSD, Unreal, VCS, MCP, DCC, model-provider, build, and platform environment without installing or changing it. Use before Forge installation, project adoption, route selection, dependency troubleshooting, or after engine/tool/plugin changes.
---

# Forge Doctor

Build a machine-readable environment snapshot and clearly separate detection, verification, absence, and assumptions.

## Workflow

1. Run the bundled CLI survey from the repository root:

   ```powershell
   .\install.ps1 -Mode Survey -ProjectPath "<project>"
   ```

2. Inspect Codex's resident image/tool capabilities, the project, `.uproject`, existing instructions/config, VCS, UE executables/plugins, native MCP, VibeUE, editor-closed Python, Blender/gateway, every local runtime/model including any Kimi route, provider credentials by presence only, DDC/build tools, and platform visibility.
3. Treat executable or plugin detection as `AVAILABLE_UNVERIFIED` until a safe end-to-end probe passes.
4. Probe each accepted route independently with known-good and known-bad controls. Never expose or persist credential values.
5. Distinguish actual generation/operation surfaces from planning or prompt-only skills. A model advertising vision/audio/tools is an input/tool capability, not proof of image, video, mesh or animation generation.
6. Emit capability contracts plus optional proposals. Compare each worker against the Codex baseline for the exact task/complexity class and state context savings, benefit, effective cost, permissions, hardware fit, test, fallback, and affected workflows.
7. Pass proposals through `$forge-capability-admin`. Do not install packages, download models, enable UE plugins, change PATH, write credentials, or edit the `.uproject` without separate explicit approval.

Read [classification.md](references/classification.md) when translating survey facts into capability status.
