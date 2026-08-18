<!-- forge:workflow
name: next
consumes: .planning/ (GSD snapshot), project root
produces: nothing — read-only detection and one dispatch
never-reads: .forge/state/lifecycle.json (never used to override GSD, never mutated)
-->

# Forge Next — workflow

<purpose>
Detect project state read-only, then dispatch exactly one skill.
</purpose>

<core_principle>
Never infer state from the conversation. Never perform the routed work here.
</core_principle>

<process>

<step name="detect" priority="first">
1. Resolve the current project root. Never infer state from the conversation.
2. Run the read-only detector:

   ```powershell
   python <forge-plugin-root>\scripts\forge.py next --project <project-root>
   ```

3. Parse the `forge.smart-entry/v1` result.
4. Treat `.planning` and the GSD snapshot as authoritative for phase status. Never use `.forge/state/lifecycle.json` to override GSD, and never mutate it.
5. Present commands from `actions` verbatim; they are already spelled for the assigned host.
6. On situation `host-surfaces-stale`, route to `forge-runtime` and stop.
7. Surface every `warnings` entry verbatim, then continue. Put a partially executed phase from `execution_coverage` to the user as a question, never as an error.
8. List `suppressed_actions` below the Forge actions as available in GSD, each with its reason and its `run_directly` spelling. Never present one as a routed action.
9. On detector failure, run `forge-doctor`. Never guess the active phase.

> **Why:** CHANGELOG.md 0.4.0 § *`forge-next` stops offering choices that are not choices*
</step>

<step name="present_and_dispatch">
1. Show the summary and ordered actions, recommended first.
2. Let the user select unless `--auto` was supplied. Print a numbered list and stop for a reply when no interactive question tool exists.
3. Display the chosen command before dispatch.
4. Dispatch exactly one skill, then stop.
5. Never perform the routed work here, and never chain a second command.
6. Run a GSD command directly when the user asks for one, after naming what the Forge route would have added.
</step>

<step name="forge_init_integration" priority="last">
1. Return control to Forge Init when the recommended command is `forge-init`. Never invoke Forge Init recursively.
2. Otherwise dispatch the recommended action and stop Forge Init.
3. Route an incomplete Forge control plane through `forge-bootstrap` or `forge-bootstrap --resume` before any design or production work.
</step>

</process>
