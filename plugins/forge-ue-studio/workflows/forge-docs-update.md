<!-- forge:workflow
name: docs-update
consumes: the implemented codebase, project docs, the GDD decision ledger, .forge/visual/registry.json, .forge/acceptance/registry.json
produces: regenerated docs, plus reconciliation of the ledger and the asset-interface registry against them
-->

# Forge Docs Update — workflow

<purpose>
Regenerate documentation *from* code that has already landed, then close the gap GSD's verifier
cannot: a doc verified against `Source/` can still contradict the asset interfaces and acceptance
suites the game is actually built against.
</purpose>

<core_principle>
The codebase is the input and the docs are the output. Never edit code to match a doc. This is the
opposite direction to `forge-ingest-docs`, which turns documents into planning state.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Documentation writes no production asset and takes no lane:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-docs-update --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="run_gsd_writers">
Run GSD's doc writers and its verifier. They own the documents and the claim-against-codebase check.
</step>

<step name="reconcile_asset_interfaces">
GSD's verifier checks a doc against source. It has no model of an Unreal asset interface, so check
those here.

For every asset interface a regenerated doc describes, compare it against its entry in
`asset_interfaces` in `.forge/visual/registry.json`: scale, pivot, collision, skeleton, sockets,
material slots, animation events, LODs, budgets.

- Doc and registry agree → nothing to do.
- The doc describes something the registry does not carry → the interface was changed without being
  registered. Register it, and say that parallel visual work planned against the old one is now
  invalid.
- The registry carries something no doc describes → a documentation gap, not a registry error. Never
  delete a registry entry to make a doc consistent.
</step>

<step name="reconcile_acceptance">
Compare what the docs now claim the game does against the suites in
`.forge/acceptance/registry.json`. A doc claiming behaviour no registered suite grades is a claim
with no gate behind it — report it; do not invent a suite to cover it here.
</step>

<step name="fold_into_the_ledger" priority="last">
Fold anything the regeneration revealed as a settled decision into the GDD decision ledger, so the
next `forge-discuss-phase` scores ambiguity against it rather than against a blank slate.

Surface, rather than resolve, any place where an implemented behaviour contradicts a decision the
ledger records as settled. That is a design conflict and belongs to a human.
</step>

</process>
