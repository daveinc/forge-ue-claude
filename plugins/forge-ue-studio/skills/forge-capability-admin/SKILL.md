---
name: forge-capability-admin
description: Register, consent, qualify, activate, invalidate, and route optional Forge capabilities such as MCPs, APIs, Unreal routes, Blender, local models, cloud providers, skills, and human lanes. Use when installing or updating an integration, changing phase tool surfaces, investigating context cost, resolving duplicate providers, or deciding whether a detected capability may execute work.
---

# Forge Capability Admin

Manage optional capability surfaces without changing Forge's permanent directives.

## Workflow

1. Run `$forge-doctor` and load the capability registry, consent ledger, qualification registry, phase activation policy, dependency catalog, and route policy.
2. Register the capability contract from [lifecycle.md](references/lifecycle.md). Treat executable detection as availability evidence only; start optional providers `UNQUALIFIED`.
3. Classify permissions, external effects, secret boundary, executable surfaces, integrity, provenance, licence, locality, cost, context cost, lanes, fallbacks, and invalidation triggers.
4. Require explicit scoped consent before installing packages/models, enabling plugins, activating executable surfaces, using secrets/network, changing PATH, editing project descriptors, or allowing external writes.
5. Run known-good and seeded-bad evaluations for each task class and complexity tier. Compare optional providers with the resident Codex baseline, including briefing, verification, retry, and contention cost.
6. Promote only the tested scope to `PARTIAL` or `QUALIFIED`. Keep failures and stale evidence visible.
7. Activate the smallest phase-specific capability set. Disable duplicate or shadow surfaces and keep one canonical provider per capability unless an experiment explicitly needs alternatives.
8. Revoke activation and mark evidence stale after relevant version, schema, model, path, plugin, engine, hardware, permission, or acceptance change.

Never equate free, local, installed, enabled, large-context, or one successful attempt with competence.
