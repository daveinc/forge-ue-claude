---
name: forge-capability-admin
description: Register, consent to, qualify, activate, invalidate, and route optional capabilities — MCPs, APIs, Unreal routes, Blender, local models, human lanes. Use when installing or updating an integration, or changing phase tool surfaces.
---

# Forge Capability Admin

## Workflow

1. Run `forge-doctor` and load the capability registry, consent ledger, qualification registry, phase activation policy, dependency catalog, and route policy. `capability-manager` owns this seat. Record the overlay state in `.forge/state/install-state.json`.
2. Register the capability contract from [lifecycle.md](references/lifecycle.md). Treat executable detection as availability evidence only, and start every optional provider `UNQUALIFIED`.
3. Classify permissions, external effects, secret boundary, executable surfaces, integrity, provenance, licence, locality, cost, context cost, lanes, fallbacks, and invalidation triggers.
4. Require explicit scoped consent before installing packages or models, enabling plugins, activating executable surfaces, using secrets or network, changing PATH, editing project descriptors, or allowing external writes.
5. Run known-good and seeded-bad evaluations per task class and complexity tier. Compare each optional provider with the resident-host baseline, including briefing, verification, retry, and contention cost.
6. Promote only the tested scope to `PARTIAL` or `QUALIFIED`. Keep failures and stale evidence visible.
7. Activate the smallest phase-specific capability set. Disable duplicate or shadow surfaces and keep one canonical provider per capability.
8. Revoke activation and mark evidence stale after a relevant version, schema, model, path, plugin, engine, hardware, permission, or acceptance change.
9. Amend the project's typed tool routes when a server is adopted, replaced, or retired:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py mcp add     --project <project-root> --id <provider> --command <exe> --arg <arg> --apply
   python <forge-plugin-root>/scripts/forge.py mcp disable --project <project-root> --id <provider> --apply
   python <forge-plugin-root>/scripts/forge.py mcp remove  --project <project-root> --id <provider> --apply
   ```

   Declare capabilities, lane, isolation mode and fallbacks in the entry for any provider outside the shipped catalog. Re-run `mcp-status` afterwards and requalify; a newly declared route starts `UNQUALIFIED`.
10. Choose each route's scope deliberately. `--scope project` reaches this game's session; `--scope user` or `both` also publishes to the machine-wide config so spawned agents can use the route:

    ```powershell
    python <forge-plugin-root>/scripts/forge.py mcp sync-user --project <project-root>          # plan
    python <forge-plugin-root>/scripts/forge.py mcp sync-user --project <project-root> --apply  # write
    ```

    Treat this as an external write: plan it by default, apply it only when asked, and record the consent. Prefer project scope unless delegated work needs the route. Never widen scope to silence a fallback.
11. Never equate free, local, installed, enabled, large-context, or one successful attempt with competence.
