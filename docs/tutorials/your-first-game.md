# Your first game

This takes you from an empty folder to a design interview and a first phase. You do not need an Unreal project yet — the project shell is something Forge plans with you, not a prerequisite.

Before you start, install Forge and GSD: [Install Forge](../how-to/install-forge.md).

## 1. Create the project directory

```powershell
New-Item -ItemType Directory -Path "D:\Unreal Projects\MyGame"
```

## 2. Preview the project overlay

Nothing is written without `-Apply`, so look first:

```powershell
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame"
```

## 3. Apply it

```powershell
.\install.ps1 -Mode Install -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

This installs `.forge` canon plus the project instruction file and project-local agents rendered for your assigned host. See [what adoption adds](../reference/repository-layout.md#what-project-adoption-adds).

## 4. Open a fresh session in the project directory

Hosts load a project's instruction file and agents when a session starts, so the session that installed the overlay cannot use it.

## 5. Ask Forge where you are

```text
Use forge-next to inspect this directory and take me to the correct next action.
```

`forge-next` is the front door for every session. It routes an incomplete installation to `forge-bootstrap --resume`; after bootstrap it scans for existing design documents, Unreal/code, and `.planning` state, then routes a greenfield project to `forge-init`, existing docs to `forge-ingest-docs`, existing code to `forge-onboard`, or an active project to its current phase verb. Each routed workflow keeps its own stop boundary.

## 6. Answer the design interview

Forge asks one high-value question at a time and builds a compact GDD decision ledger rather than forwarding the whole conversation to every worker. Expect it to establish the story, gameplay pillars, visual anchors, constraints, and the decisions still open, then produce parallel playable and visual production DAGs once their shared interfaces are approved.

## 7. Stop when Forge stops

A workflow that reaches a stop boundary means it. Start a fresh session and run `forge-next` again; it resumes from files, not from the previous conversation.

## When the `.uproject` appears

The project-shell phase creates it. Re-run Survey and Profile afterwards to expose Unreal-specific routes:

```powershell
.\install.ps1 -Mode Profile -ProjectPath "D:\Unreal Projects\MyGame" -Apply
```

Forge and GSD state stay in the same project root.

## Next

- [Skills reference](../reference/skills.md) — the full verb list and the normal production sequence.
- [How Forge works](../explanation/how-forge-works.md) — why detected tools are not used until they are qualified.
