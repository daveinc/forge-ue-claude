# Install Forge

Forge installs in two independent steps: the plugin, and the GSD phase engine. Either can be repaired or updated without changing the other.

## Requirements

| Requirement | Needed for | Notes |
|---|---|---|
| Windows PowerShell | Included installer | Run commands from the Forge repository root. |
| A supported runtime host | Installing and using Forge | Claude Code, Codex CLI, or any host meeting the [prerequisite contract](../host-runtimes.md). |
| Node.js, npm, and npx | Installing GSD through Forge | Required only for `-Mode GSD`; Forge pins the requested package version. |
| Python 3.10 or newer | Surveying or adopting Unreal projects | Forge has no third-party Python package dependencies. |
| Git | Safe production work | Strongly recommended before Forge performs durable project writes. |
| Unreal Engine project | Unreal execution | Not required for the initial game-design interview. |

Unreal MCP, VibeUE, Unreal Python, Blender, local model runtimes, image/audio/video tools, and build services are optional capability routes. Install only the routes your project needs.

## 1. Choose a runtime host

List the runtimes Forge can use, whether their CLIs are present, and whether they satisfy the prerequisite contract:

```powershell
.\install.ps1 -Mode Host -HostAction list
```

Built-in hosts are `claude` (Claude Code, the default), `codex` (OpenAI Codex CLI), and `generic` (any other Forge-capable agent). Every command accepts `-RuntimeHost <id>`; omit it to use the default. The parameter is `-RuntimeHost` rather than `-Host` because `$Host` is a reserved PowerShell variable.

## 2. Install the plugin

Download or clone this repository, open PowerShell in its root, and preview:

```powershell
.\install.ps1 -Mode Plugin
```

The preview prints the install commands for the selected host without changing configuration.

**Claude Code** installs plugins from inside a session, so Forge prints the commands rather than shelling out. Run them in a Claude Code session:

```text
/plugin marketplace add "D:\path\to\forge-ue-studio"
/plugin install forge-ue-studio@forge-ue-studio-local
```

**Codex CLI** installs non-interactively, so the installer applies it directly:

```powershell
.\install.ps1 -Mode Plugin -RuntimeHost codex -Apply
codex plugin list
```

Look for `forge-ue-studio@forge-ue-studio-local` with status `installed, enabled`.

## 3. Install GSD

Preview the pinned package and the exact command for the selected host:

```powershell
.\install.ps1 -Mode GSD
```

Approve and apply it:

```powershell
.\install.ps1 -Mode GSD -Apply
```

Forge defaults to stable `@opengsd/gsd-core@1.10.0` — the version it is tested against — and installs the integration for the selected host globally. Use `-GsdVersion X.Y.Z` only when you intentionally want a different audited release.

## 4. Start a new session

Hosts load newly installed plugin skills and tools into new sessions, not running ones.

## Installing the plugin by hand

The installer registers this repository as the local marketplace `forge-ue-studio-local`, then installs Forge from it. To run those steps yourself:

```powershell
codex plugin marketplace add "C:\path\to\forge-ue-studio"
codex plugin add forge-ue-studio@forge-ue-studio-local
codex plugin list
```

## Updating

After pulling a Forge update, rerun `.\install.ps1 -Mode Plugin -RuntimeHost <id> -Apply` and start a new session so the updated skill snapshot is loaded.

## Next

- [Your first game](../tutorials/your-first-game.md)
- [Adopt an existing project](../tutorials/adopt-an-existing-project.md)
- [Troubleshoot](troubleshoot.md)
