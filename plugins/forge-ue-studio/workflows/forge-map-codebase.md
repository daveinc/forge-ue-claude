<!-- forge:workflow
name: map-codebase
consumes: forge.py survey (modules, engine_association, content), Source/*/*.Build.cs, .gitattributes, <project>.uproject
produces: .planning/codebase/ (GSD's) extended with the Unreal structure GSD's mappers cannot see
-->

# Forge Map Codebase — workflow

<purpose>
Extend GSD's language-generic codebase map with the four Unreal facts that decide how work on this
project can be scheduled: module boundaries, the Blueprint/C++ split, `Content/` organisation, and
which files are binary and therefore lockable rather than mergeable.
</purpose>

<core_principle>
Read-only. A map that guesses at `Content/` from directory names, rather than from `.gitattributes`
and the `.uproject`, produces a plan that collides on a binary asset.
</core_principle>

<process>

<step name="declare_no_lane" priority="first">
Mapping reads and never writes, so it holds no lane:

```powershell
python <forge-plugin-root>/scripts/forge.py exec supervise --project <project-root> --holder forge-map-codebase --apply
```

Naming no `--lane` records `holds_no_lane` against this run.
</step>

<step name="read_what_forge_already_counts">
Do not walk the tree by hand for what a verb already answers:

```powershell
python <forge-plugin-root>/scripts/forge.py survey --project <project-root>
```

| In the payload | What it settles |
|---|---|
| `modules[]` | The C++ module boundaries the `.uproject` descriptor declares, with each module's `type` and `loading_phase`. Authoritative — a `Source/` walk guesses at this |
| `engine_association` | The engine this project expects. A source-build GUID rather than a version is an unknown, not a shortfall |
| `content.top_level[]` and `content.totals` | Per-folder `.uasset` and `.umap` counts. A flat `Content/` and a feature-partitioned one schedule differently |
| `content.import_sources` | The FBX, PNG and similar sources sitting beside the assets |
| `content.signals` | The default map, the default game mode, the build targets, and whether this project has been built |
| `content.implies[]` | Task classes a directory walk settles outright, each with its evidence |
| `content.undetermined[]` | Task classes that need an asset opened. Each carries `settled_by: "asset-audit"` |
| `content.not_opened` | What this report deliberately does not claim. Quote it — a map that omits its own ceiling reads as complete |

`content.truncated` means the walk hit its scan limit and every count below it is a floor rather than
a total. Say so rather than reporting a floor as a figure.
</step>

<step name="run_gsd_mappers">
Run GSD's codebase mappers. They own `.planning/codebase/` and the general-purpose analysis; Forge
writes none of it.
</step>

<step name="add_what_the_survey_does_not_reach" priority="last">
Three Unreal facts the survey does not answer, each read from a named file:

| Fact | Read from |
|---|---|
| Module *dependencies* | `Source/*/*.Build.cs` — `PublicDependencyModuleNames` and `PrivateDependencyModuleNames`. The survey names the modules; only these name what they depend on |
| Enabled plugins | `Plugins` in `<project>.uproject` |
| Which paths are binary and lockable | `.gitattributes` — the `lockable` and `binary` patterns |

Report the binary-lockable set explicitly. It is the input `forge-plan-phase` needs to decide which
plans may run concurrently, and the one a generic map silently omits: everything those patterns cover
needs an LFS lock or a project-exclusive lease to write, and can never be merged.

For the Blueprint and C++ split, pair `content.top_level[]` against the `UCLASS`/`UFUNCTION` surface
in `Source/`. A Blueprint deriving from a native class is a boundary between two lanes, not a leaf —
and no directory walk can see it, which is why `content.undetermined[]` exists.
</step>

</process>
