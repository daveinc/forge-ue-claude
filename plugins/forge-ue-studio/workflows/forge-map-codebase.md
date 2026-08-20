<!-- forge:workflow
name: map-codebase
consumes: <project>.uproject, Source/*/*.Build.cs, Content/, .gitattributes, Plugins/
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

<step name="run_gsd_mappers">
Run GSD's codebase mappers. They own `.planning/codebase/` and the general-purpose analysis; Forge
writes none of it.
</step>

<step name="add_unreal_structure" priority="last">
Add what a language-generic mapper does not model, each read from a named file:

| Fact | Read from |
|---|---|
| Module boundaries and their dependencies | `Source/*/*.Build.cs` — `PublicDependencyModuleNames` and `PrivateDependencyModuleNames` |
| Enabled plugins and the engine this project expects | `<project>.uproject` — `Plugins` and `EngineAssociation` |
| The Blueprint and C++ split | `Content/**/*.uasset` against the `UCLASS`/`UFUNCTION` surface in `Source/`; a Blueprint deriving from a native class is a boundary, not a leaf |
| Which paths are binary and lockable | `.gitattributes` — the `lockable` and `binary` patterns. Everything they cover needs an LFS lock or a project-exclusive lease to write, and can never be merged |
| `Content/` organisation | The top-level folders and what each holds — a flat `Content/` and a feature-partitioned one schedule differently |

Report the binary-lockable set explicitly. It is the input `forge-plan-phase` needs to decide which
plans may run concurrently, and the one a generic map silently omits.
</step>

</process>
