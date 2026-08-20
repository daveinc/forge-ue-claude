<!-- forge:workflow
name: ingest-docs
consumes: Docs/Design/, docs/design/ or Design/ as reported in signals.design_sources, .forge/visual/registry.json
produces: GDD decision ledger, registered asset interfaces, INGEST-CONFLICTS.md (GSD's)
-->

# Forge Ingest Docs — workflow

<purpose>
Turn design documents that already exist *into* planning state, and register the asset interfaces
hidden inside them before any of it is planned against.
</purpose>

<core_principle>
Never auto-resolve a design conflict. Two documents that both state a settled decision and disagree
is a question for the human who owns the design, not a merge.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Ingestion reads documents and writes planning state, never a game asset, so it holds no lane:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-ingest-docs --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="locate_sources">
Do not go looking by hand:

```powershell
python <forge-plugin-root>/scripts/forge.py next --project <project-root>
```

`signals.design_sources` in that payload holds every directory Forge found — `Docs/Design`,
`docs/design` or `Design`, listed only when it actually contains Markdown. An empty list means there
is nothing to ingest, and this workflow is the wrong verb: use `forge-init` to author the design
instead.

A source the user names that is not in that list is still ingestible. Say that it was outside the
detected set, so a later run of the detector does not read as having lost it.
</step>

<step name="run_gsd_ingestion">
Run GSD's document ingestion, including its classification and conflict detection. It owns the
classified documents, the precedence rules and `INGEST-CONFLICTS.md`.
</step>

<step name="rule_on_conflicts">
Read GSD's three conflict buckets and treat them differently:

| Bucket | Action |
|---|---|
| Auto-resolved | Accept. Precedence settled it |
| Competing variants | Present both. Do not pick one to keep the run moving |
| Unresolved blockers — LOCKED against LOCKED | **Stop.** A human rules on it |

Never auto-resolve a design conflict, and never record a decision as settled when the only reason it
looks settled is that one source was read last.
</step>

<step name="register_asset_interfaces">
Design documents describe assets, and an asset described in prose blocks nothing. Extract every one
that carries a contract — scale, pivot, collision, skeleton, sockets, material slots, animation
events, LODs, budgets — and register it in `asset_interfaces` in `.forge/visual/registry.json`.

This is what makes the ingested design schedulable: parallel visual and gameplay work synchronises
through registered interfaces, and an unregistered one is a collision waiting for the phase that
lands on it.
</step>

<step name="fold_into_the_ledger" priority="last">
Fold every accepted decision into the GDD decision ledger with its source document named, so
`forge-spec-phase` and `forge-discuss-phase` score ambiguity against a real prior rather than a blank
slate.

Record what was *not* settled just as explicitly. A decision the documents never made is a deferral,
and a deferral that goes unrecorded is re-invented by whichever session next needs it.
</step>

</process>
