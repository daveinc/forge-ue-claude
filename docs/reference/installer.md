# Installer

`install.ps1` is the Windows entry point. Every mode is previewed by default; only `-Apply` writes.

## Modes

| Mode | Writes? | Purpose |
|---|---:|---|
| `Plugin` | Only with `-Apply` | Register the repository marketplace and install Forge in the selected host. |
| `Host` | Only with `-Apply` | List hosts, show the assignment, or assign/swap the resident runtime. |
| `GSD` | Only with `-Apply` | Preview or install a pinned GSD Core release for the selected host globally. |
| `Survey` | No | Inventory the project and available host capabilities. |
| `Install` | Only with `-Apply` | Preview or apply the project-local Forge overlay. |
| `Verify` | No | Check that the accepted overlay still matches Forge's template and rules. |
| `Profile` | Only with `-Apply` | Refresh detected capabilities without granting qualification. |
| `Next` | No | Combine Forge readiness with authoritative GSD smart-entry and return valid next actions. |
| `BootstrapCheck` | No | Run Forge's own bootstrap closure gate. Exits non-zero until every check passes. |
| `Mcp` | Only with `-Apply` | Add, remove, enable, disable, or publish this project's typed tool routes. |
| `McpStatus` | No | Report every typed tool route, its lane, and whether it is bound. |
| `GsdSync` | Only with `-Apply` | Write GSD's `runtime` key from the assigned host. |
| `Route` | No project mutation | Select a provider for a schema-valid route request using recorded qualification evidence. |
| `Lifecycle` | No | Read deprecated compatibility status only; transitions are rejected. |
| `Validate` | No | Check a Forge JSON contract against its required top-level fields. |

Only `GSD -Apply` downloads and runs an external package, and it always uses the displayed, pinned version. Project modes never download packages, model weights, plugins, or binaries; never change PATH or system settings; and never edit the `.uproject`.

## Common parameters

| Parameter | Applies to | Notes |
|---|---|---|
| `-RuntimeHost <id>` | All modes | Defaults to the registry's `default_host`. Named `-RuntimeHost` because `$Host` is a reserved PowerShell variable. |
| `-ProjectPath <path>` | Project modes | A directory, or a `.uproject` file. |
| `-Apply` | Writing modes | Omit it to preview. |
| `-GsdVersion X.Y.Z` | `GSD` | Use only for a deliberately different audited release. |
| `-HostAction list\|status\|set` | `Host` | `set` requires `-RuntimeHost`. |
| `-ContractKind`, `-InputPath` | `Validate` | The kind must be a shipped schema. |
| `-RequestPath` | `Route` | A `forge.route-request/v1` payload. |
| `-McpAction`, `-McpId`, `-McpCommand`, `-McpArg`, `-McpScope` | `Mcp` | `-McpScope project\|user\|both`. |
| `-OutputPath` | Read modes | Also write the JSON result to a file. |

## Examples

Inspect the state-aware next action. Read-only; it returns a `forge.smart-entry/v1` snapshot and ordered actions, of which `forge-next` presents and dispatches exactly one:

```powershell
.\install.ps1 -Mode Next -ProjectPath "D:\Unreal Projects\MyGame"
```

Validate a contract, or route a qualified packet:

```powershell
.\install.ps1 -Mode Validate -ContractKind attempt-result -InputPath ".\attempt.json"
.\install.ps1 -Mode Route -ProjectPath "D:\Unreal Projects\MyGame" -RequestPath ".\route-request.json"
```

Declare a typed tool route, then publish it so spawned agents can see it:

```powershell
.\install.ps1 -Mode Mcp -McpAction add -McpId unreal-native-mcp -McpCommand uvx -ProjectPath "<project>" -Apply
.\install.ps1 -Mode Mcp -McpAction sync-user -ProjectPath "<project>" -Apply
```

## Exit codes

`0` success, `1` operational failure, `2` the command ran and returned a verdict of not-ok, `3` usage error. See the [failure contract](../failure-contract.md).
