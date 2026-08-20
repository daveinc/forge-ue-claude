<!-- forge:workflow
name: capability-admin
seat: capability-manager
consumes: .forge/capabilities/registry.json, .forge/capabilities/consent-ledger.json, .forge/capabilities/qualifications.json, .forge/context/activation-policy.json, dependency catalog, route policy
produces: .forge/capabilities/qualifications.json, .forge/capabilities/consent-ledger.json, .forge/state/install-state.json, .forge/mcp.json
-->

# Forge Capability Admin — workflow

<purpose>
Qualify, activate, scope and revoke capability routes, and own the consent record for each.
</purpose>

<core_principle>
Never equate free, local, installed, enabled, large-context or one successful attempt with
competence.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Qualifying a capability writes `.forge` control-plane state, never a game asset — with one exception
that matters:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-capability-admin --apply
```

Naming no `--lane` records `holds_no_lane` against this run.

**The exception is `evaluate`.** A probe that drives the live editor occupies the editor exactly as
production work does, so that step declares its Unreal lane and reads the refusal as binding.
Probing a lane another department is working in measures their state, not the route.

> **Why:** CHANGELOG.md 0.7.0 § *Lane supervision is reachable from any workflow, not only from the one that dispatches*
</step>

<step name="load_state">
Run `forge-doctor`, then load `.forge/capabilities/registry.json`,
`.forge/capabilities/consent-ledger.json`, `.forge/capabilities/qualifications.json`, the phase
activation policy at `.forge/context/activation-policy.json`, the dependency catalog and the route
policy.

Record the overlay state in `.forge/state/install-state.json`.
</step>

<step name="register_contract">
Register the capability contract from
[lifecycle.md](../skills/forge-capability-admin/references/lifecycle.md).

Treat executable detection as availability evidence only. Start every optional provider
`UNQUALIFIED`.

Classify permissions, external effects, secret boundary, executable surfaces, integrity, provenance,
licence, locality, cost, context cost, lanes, fallbacks and invalidation triggers.
</step>

<step name="require_consent">
Require explicit scoped consent before installing packages or models, enabling plugins, activating
executable surfaces, using secrets or network, changing PATH, editing project descriptors, or
allowing external writes.
</step>

<step name="evaluate">
**Take the lane first when the probe drives Unreal.** A live-editor probe is exclusive with every
other Unreal route through the project super-lock:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-capability-admin --lane ue-live-native-mcp --apply
```

Use `ue-live-python` or `ue-editor-closed-api` for those routes instead. A `blocked` answer is
binding — wait, do not probe alongside a live writer.

Run known-good **and seeded-bad** evaluations per task class and complexity tier. A route that accepts
a deliberately bad input without complaint has not been shown to work; it has been shown to answer.

Compare each optional provider with the resident-host baseline, including briefing, verification,
retry and contention cost. A provider that is faster per attempt and needs two attempts and a
verification pass is not cheaper.

Promote only the tested scope to `PARTIAL` or `QUALIFIED` — the exact task class and complexity tier
that was probed, and nothing adjacent. Keep failures and stale evidence visible.

Record the host the evidence was gathered under. Qualification is host-scoped, and routing rejects an
evaluation recorded under a different one.

Release the lane when the probe ends, including when it failed:

```powershell
python <forge-plugin-root>/scripts/forge.py exec release --project <project-root> --work-order <id> --outcome passed|failed --apply
```
</step>

<step name="activate">
Activate the smallest phase-specific capability set. Disable duplicate or shadow surfaces and keep
one canonical provider per capability.
</step>

<step name="revoke_on_change">
Revoke activation and mark evidence stale after a relevant version, schema, model, path, plugin,
engine, hardware, permission or acceptance change.
</step>

<step name="amend_routes">
**Skip if:** no server is being adopted, replaced or retired.

```powershell
python <forge-plugin-root>/scripts/forge.py mcp add     --project <project-root> --id <provider> --command <exe> --arg <arg> --apply
python <forge-plugin-root>/scripts/forge.py mcp disable --project <project-root> --id <provider> --apply
python <forge-plugin-root>/scripts/forge.py mcp enable  --project <project-root> --id <provider> --apply
python <forge-plugin-root>/scripts/forge.py mcp remove  --project <project-root> --id <provider> --apply
```

| Verb | Effect |
|---|---|
| `disable` | Keeps the declaration, stops the route being probed or dispatched to |
| `enable` | Re-adopts a disabled route — not a second `add` |
| `remove` | Deletes the declaration, losing its scope and fallbacks with it |

Declare capabilities, lane, isolation mode and fallbacks in the entry for any provider outside the
shipped catalog.

Re-run `route-status` afterwards and requalify. A newly declared route starts `UNQUALIFIED`, and so
does one re-enabled after a version, path or schema change.

> **Why:** CHANGELOG.md 0.5.0 § *Every verb is reachable from a workflow, and a guard keeps it that way*
</step>

<step name="choose_scope">
Choose each route's scope deliberately:

| Scope | Reach |
|---|---|
| `project` | This game's session |
| `user` or `both` | Also the machine-wide config, so spawned agents can use the route |

```powershell
python <forge-plugin-root>/scripts/forge.py mcp sync-user --project <project-root>
python <forge-plugin-root>/scripts/forge.py mcp sync-user --project <project-root> --apply
```

Treat this as an external write: plan it by default, apply it only when asked, and record the
consent. Prefer project scope unless delegated work needs the route.

**Never widen scope to silence a fallback.**
</step>

</process>
