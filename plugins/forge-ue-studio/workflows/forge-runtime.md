<!-- forge:workflow
name: runtime
consumes: plugins/forge-ue-studio/hosts/registry.json, .forge/agents/*.json, .forge/templates/
produces: the host's project instruction file and agent directory, .planning/config.json (runtime key only)
-->

# Forge Runtime — workflow

<purpose>
Assign or swap the resident host, and keep every rendered surface regenerated from canon.
</purpose>

<core_principle>
Edit canon, never a rendered file. Reject any host name, skill prefix or vendor path written into
canon.
</core_principle>

## The portability contract

| Kind | Location | Rule |
|---|---|---|
| **Canon** | `.forge/agents/*.json`, `.forge/directives.md`, `.forge/templates/`, `.forge/state/`, `.forge/capabilities/`, `.planning/` | Edit these. Never host-specific. |
| **Rendered** | The host's project instruction file and agent directory | Regenerate from canon. Never hand-edit. |

<process>

<step name="inspect" priority="first">
1. List hosts, prerequisites, and detected CLIs:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py host list
   ```

2. Show the assignment and surface freshness:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py host status --project <project-root>
   ```

3. Re-render before production work whenever `surfaces` reports anything other than `CURRENT`.
4. Check GSD's `runtime` key against the assigned host, and repair it if it drifted:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py gsd-sync --project <project-root>
   ```

   `install` and `host set --apply` both write this key already, so a mismatch here means `.planning/config.json` was edited outside Forge. Add `--apply` to repoint it. This is the only key Forge writes there, so nothing else in that file is Forge's to correct.
</step>

<step name="assign_or_swap">
**Skip if:** no host change is requested.

1. Confirm the target host satisfies the prerequisite contract through `prerequisites.satisfied`.
2. Preview the change; without `--apply` nothing is written:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py host set --host <id> --project <project-root>
   ```

3. Resolve every `propose` action before applying. Expect `create`/`regenerate` for the incoming host and `retire` for the outgoing one.
4. Apply, then stop:

   ```powershell
   python <forge-plugin-root>/scripts/forge.py host set --host <id> --project <project-root> --apply
   ```

5. Start a fresh session in the new host and run `forge-next`. Never continue a swap in the session that performed it.
6. Re-probe every offload route through `forge-capability-admin` before trusting it; routing rejects an evaluation recorded under a different host.

> **Why:** CHANGELOG.md 0.2.0 § *Host-agnostic runtime*
</step>

## What a swap changes

| | |
|---|---|
| Preserved | `.planning` state, `.forge/state` packets and leases, canonical packet IDs, agent definitions, directives, research. |
| Regenerated | The project instruction file and project-local agents, from canon. |
| Retired | The previous host's generated files. |
| Re-pointed | GSD's `runtime` key in `.planning/config.json`, the only key Forge writes there. |
| Invalidated | Provider qualification evidence and host context-cost measurements. |

<step name="add_host">
**Skip if:** the target host already has a profile.

1. Append a profile to `plugins/forge-ue-studio/hosts/registry.json` declaring its CLI, skill-invocation prefix, discovery roots, project surface, plugin install commands, GSD install arguments, and the capabilities it `provides`.
2. Never edit Forge code to add a host.
3. Validate with `python scripts/validate_repo.py`.
</step>

</process>

## Boundaries

- Never swap hosts to escape a failing gate. Investigate with `forge-retrospective` first.
- Never edit a rendered file to change behaviour. Edit canon, then re-render.
- Never apply a mid-phase swap without announcing the stale-qualification consequence first.
