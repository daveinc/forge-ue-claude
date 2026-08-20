<!-- forge:workflow
name: research
consumes: candidate sources, .forge/research/index.json, .forge/capabilities/registry.json, plugins/forge-ue-studio/doctrine/procedures.json
produces: a capability or research contract, .forge/research/index.json
-->

# Forge Research — workflow

<purpose>
Absorb an external source — an API, a plugin, a tool, a body of documentation — into a contract Forge
can route against, without importing any of it into approved project state.
</purpose>

<core_principle>
Request capabilities in recipes, never product names. Never grant `AVAILABLE_VERIFIED` on a detection
probe alone: detection says a thing is installed, not that it works for the task class asked of it.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Research reads sources and writes only its own index:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-research --apply
```

Naming no `--lane` records `holds_no_lane` against this run. Probing an Unreal route is the one
exception: a probe that drives the live editor takes `--lane ue-live-native-mcp` like any other
writer, because it occupies the same editor.
</step>

<step name="discover_without_importing">
Discover candidate sources and keep them out of approved project state. A source read is not a source
adopted.

For each, identify: exact source, version, licence, trust boundary, update signal, and the task
classes it is intended to serve. Name those from the closed catalogue where they exist —
`forge.py procedure --task-class <task-class>` says which do — so a source is scoped to work Forge
already knows the shape of.
</step>

<step name="prefer_the_authoritative_local_answer">
Present the discovered set for approval before reading it in depth. Prefer, in order:

authoritative local schemas · help output · reflection · headers · generated API references ·
configured tool manifests

Browse only when current external documentation is genuinely required. A local schema is versioned
with the thing it describes; a web page is not, and an absorbed contract built on the wrong version
is worse than none.
</step>

<step name="classify_in_bounded_packets">
Classify independent sources in bounded parallel packets, never as one large read. Extract:

decisions · requirements · constraints · conflicts · atomic operations · inputs and outputs ·
mutation behaviour · lanes · error surfaces · rollback evidence

**Mutation behaviour and lane are the two that matter for routing.** An operation that mutates inside
the editor tick belongs on a different lane from one that does not, and a contract that omits which
is which cannot be routed safely.
</step>

<step name="stage_conflicts_without_merging">
Stage contradictions rather than reconciling them. Never merge competing acceptance variants — two
sources that disagree about what "done" means produce one contract that is wrong in both directions.

Block the destination contract until the human owner resolves a material contradiction.
</step>

<step name="write_the_contract">
Create the capability or research contract described in
[absorption-contract.md](../skills/forge-research/references/absorption-contract.md), and register it
in `.forge/research/index.json` with its source, version, licence and date.
</step>

<step name="probe_before_believing">
Implement known-good **and** seeded-bad probes. A route that accepts a deliberately bad input without
complaint has not been shown to work; it has been shown to answer.

Compare an optional worker against the resident-host baseline on the exact task class and complexity
tier, including briefing cost, verification cost, retry cost and contention.

Never grant `AVAILABLE_VERIFIED` on a detection probe alone.
</step>

<step name="link_to_fallbacks">
Link every workflow step the new capability enables to its fallback and its acceptance suite in
`.forge/acceptance/registry.json`.

A capability with no declared fallback becomes a single point of failure the first time the route is
unbound, and nothing will say so until a dispatch refuses.

Request capabilities in recipes — *drive a headless Unreal commandlet* — never product names.
</step>

<step name="compile_retrieval" priority="last">
Generate small domain cards, relationship graphs where they help, and retrieval keys. Compile minimal
offload packets so a worker never receives a whole manual, the complete GDD, or the resident
conversation.

Record the invalidation triggers, and re-probe after any version, schema, model, plugin, engine,
hardware or path change.

Route installation, consent and activation through `forge-capability-admin`. **This workflow never
installs anything** — it decides what would be worth installing and what evidence would justify it.
</step>

</process>
