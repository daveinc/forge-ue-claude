---
name: forge-capability-admin
description: Register, consent, qualify, activate, invalidate, and route optional Forge capabilities such as MCPs, APIs, Unreal routes, Blender, local models, cloud providers, skills, and human lanes. Use when installing or updating an integration, changing phase tool surfaces, investigating context cost, resolving duplicate providers, or deciding whether a detected capability may execute work.
---

# Forge Capability Admin

Manage optional capability surfaces without changing Forge's permanent directives.

## Workflow

1. Run `forge-doctor` and load the capability registry, consent ledger, qualification registry, phase activation policy, dependency catalog, and route policy. `capability-manager` owns this seat. Record the resulting overlay state in `.forge/state/install-state.json` so a later session resumes from the recorded decision instead of re-deriving it.
2. Register the capability contract from [lifecycle.md](references/lifecycle.md). Treat executable detection as availability evidence only; start optional providers `UNQUALIFIED`.
3. Classify permissions, external effects, secret boundary, executable surfaces, integrity, provenance, licence, locality, cost, context cost, lanes, fallbacks, and invalidation triggers.
4. Require explicit scoped consent before installing packages/models, enabling plugins, activating executable surfaces, using secrets/network, changing PATH, editing project descriptors, or allowing external writes.
5. Run known-good and seeded-bad evaluations for each task class and complexity tier. Compare optional providers with the resident-host baseline, including briefing, verification, retry, and contention cost.
6. Promote only the tested scope to `PARTIAL` or `QUALIFIED`. Keep failures and stale evidence visible.
7. Activate the smallest phase-specific capability set. Disable duplicate or shadow surfaces and keep one canonical provider per capability unless an experiment explicitly needs alternatives.
8. Revoke activation and mark evidence stale after relevant version, schema, model, path, plugin, engine, hardware, permission, or acceptance change.
9. Amend the project's typed tool routes when a server is adopted, replaced or retired. The project's declaration is the truth; the host's MCP surface is rendered from it:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py mcp add     --project <project-root> --id <provider> --command <exe> --arg <arg> --apply
   python <forge-plugin-root>/scripts/forge.py mcp disable --project <project-root> --id <provider> --apply
   python <forge-plugin-root>/scripts/forge.py mcp remove  --project <project-root> --id <provider> --apply
   ```

   A provider in the shipped catalog inherits its capabilities, lane, isolation mode and fallbacks; anything else declares them in its own entry so routing resolves. Rendering preserves servers this project did not declare. Re-run `mcp-status` afterwards and requalify: a newly declared route starts `UNQUALIFIED` like any other provider.
10. Choose a route's scope deliberately. `--scope project` is the default and reaches the session opened from this game. `--scope user` or `both` additionally publishes to the machine-wide config, which is what lets agents the session spawns use the route rather than falling back:

    ```powershell
    python <forge-plugin-root>/scripts/forge.py mcp sync-user --project <project-root>          # plan
    python <forge-plugin-root>/scripts/forge.py mcp sync-user --project <project-root> --apply  # write
    ```

    Treat this as an external write: plan it by default, apply it only when asked, and record the consent. Forge backs up first, edits only its own server entries, leaves an entry that no longer matches what it renders, and never rewrites a config it cannot parse. Prefer project scope unless delegated work needs the route; never widen scope to silence a fallback.

Never equate free, local, installed, enabled, large-context, or one successful attempt with competence.
