---
name: forge-doctor
description: Survey the host, GSD, Unreal, VCS, MCP, DCC, model, build, and platform environment without changing it
---

<invocation>
- Invoked by naming `forge-doctor`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Build a machine-readable environment snapshot.

Delegation: native. Read-only throughout. Separates detection, verification, absence, and assumption, and never installs or activates anything.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-doctor.md
@<forge-plugin-root>/skills/forge-doctor/references/classification.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (read-only operation, detection-is-not-qualification, credential safety).
</process>
