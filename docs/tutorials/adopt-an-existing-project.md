# Adopt an existing project

Forge adopts a project that already exists — code, content, design documents, or all three — without replacing what is there. Adoption adds orchestration state beside your work; it does not touch your GDD, source tree, `Content/`, `.uproject`, or VCS history.

You can point Forge at an existing pre-project directory, a directory containing exactly one `.uproject`, or the `.uproject` path itself.

## 1. Survey first — this writes nothing

```powershell
.\install.ps1 -Mode Survey -ProjectPath "D:\Unreal Projects\MyGame"
```

The survey reports what is verified, what is detected but unqualified, what is unavailable, and what is assumed.

## 2. Preview the overlay

```powershell
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame"
```

## 3. Apply it

```powershell
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

Existing files that differ are preserved: Forge writes a `.forge-proposed` sibling for you to review instead of overwriting your accepted local policy.

## 4. Open a fresh session and let Forge route you

```text
Use forge-bootstrap to adopt this project. Preserve existing work, delegate the applicable installation investigations, and stop at each persisted fresh-task handoff.
```

After bootstrap, `forge-next` routes on what it finds:

| What the project has | Where Forge routes |
|---|---|
| Design documents, no planning state | `forge-ingest-docs` |
| Unreal or other code, no planning state | `forge-onboard` |
| An existing `.planning` tree | The current phase verb |
| Nothing yet | `forge-init` |

## 5. Verify the adoption later

```powershell
.\install.ps1 -Mode Verify -ProjectPath "D:\Unreal Projects\MyGame"
```

## 6. Refresh capabilities as the project grows

Detection is not qualification, so refreshing the profile never grants a route production authority:

```powershell
.\install.ps1 -Mode Profile -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

## Next

- [Repository and project layout](../reference/repository-layout.md#what-project-adoption-adds) — every file adoption adds.
- [Troubleshoot](../how-to/troubleshoot.md) — if the project path is refused or the surfaces look wrong.
