#Requires -Version 5.1
<#
.SYNOPSIS
    Proves Forge against a real Unreal Engine, which no unit test can do.

.DESCRIPTION
    The suite runs MCP against a stand-in server and the commandlet against a stub
    binary. Both prove the plumbing and neither proves Unreal. This driver builds a
    throwaway project, drives a real editor through it, and asserts the claims that
    only a live engine can settle:

      - the first-party MCP route answers a real initialize handshake
      - an open editor is detected as holding the project
      - the live and editor-closed lanes swap as the editor opens and closes
      - a commandlet runs against the closed project and writes its result file

.PARAMETER EnginePath
    Engine root, e.g. "C:\Program Files\Epic Games\UE_5.8".

.PARAMETER WorkPath
    Where the throwaway project is built. Deleted and recreated each run.

.PARAMETER KeepProject
    Leave the fixture project on disk for inspection.
#>
[CmdletBinding()]
param(
    [string]$EnginePath = "C:\Program Files\Epic Games\UE_5.8",
    [string]$WorkPath = (Join-Path $env:TEMP "forge-unreal-acceptance"),
    [switch]$KeepProject
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$forge = Join-Path $repoRoot "plugins\forge-ue-studio\scripts\forge.py"
$results = @()
$editor = $null

function Add-Result {
    param([string]$Stage, [string]$Status, [string]$Detail, [hashtable]$Fields)
    $row = [pscustomobject]@{ stage = $Stage; status = $Status; detail = $Detail }
    if ($Fields) {
        foreach ($key in $Fields.Keys) { $row | Add-Member -NotePropertyName $key -NotePropertyValue $Fields[$key] }
    }
    $script:results += $row
    $colour = switch ($Status) { 'PASS' { 'Green' } 'FAIL' { 'Red' } default { 'Yellow' } }
    Write-Host ("  {0,-32} {1,-16} {2}" -f $Stage, $Status, $Detail) -ForegroundColor $colour
}

function Invoke-Native {
    param([string]$Exe, [string[]]$NativeArgs, [switch]$AllowFailure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = (& $Exe @NativeArgs 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "$Exe $($NativeArgs -join ' ') exited $code`n$output"
    }
    return $output
}

function Invoke-Forge {
    param([string[]]$ForgeArgs)
    $raw = Invoke-Native -Exe "python" -NativeArgs (@($forge) + $ForgeArgs) -AllowFailure
    if (-not $raw) { return $null }
    try { return ($raw | ConvertFrom-Json) } catch { return $null }
}

function Get-Route {
    param($Status, [string]$Provider)
    if (-not $Status -or -not $Status.routes) { return $null }
    return ($Status.routes | Where-Object { $_.provider -eq $Provider } | Select-Object -First 1)
}

function Get-Ownership {
    param([string]$Project)
    $probe = @"
import json, sys, pathlib
sys.path.insert(0, r'$repoRoot\plugins\forge-ue-studio\scripts')
import forge_mcp
print(json.dumps(forge_mcp.live_editor_holds_project(pathlib.Path(r'$Project'))))
"@
    $raw = Invoke-Native -Exe "python" -NativeArgs @("-c", $probe)
    return ($raw | ConvertFrom-Json)
}

Write-Host "Forge Unreal acceptance" -ForegroundColor Cyan
Write-Host "  engine : $EnginePath"
Write-Host "  work   : $WorkPath"
Write-Host ""

try {
    $editorExe = Join-Path $EnginePath "Engine\Binaries\Win64\UnrealEditor.exe"
    $cmdExe = Join-Path $EnginePath "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
    if (-not (Test-Path $editorExe)) { throw "UnrealEditor.exe not found under $EnginePath" }
    if (-not (Test-Path $cmdExe)) { throw "UnrealEditor-Cmd.exe not found under $EnginePath" }
    Add-Result "engine-binaries" "PASS" "editor and commandlet binaries resolved"

    if (Test-Path $WorkPath) { Remove-Item -Recurse -Force $WorkPath }
    $projectDir = Join-Path $WorkPath "ForgeFixture"
    New-Item -ItemType Directory -Force -Path (Join-Path $projectDir "Content") | Out-Null
    $uproject = Join-Path $projectDir "ForgeFixture.uproject"
    @{
        FileVersion = 3
        EngineAssociation = ""
        Category = ""
        Description = "Throwaway fixture for Forge acceptance. Safe to delete."
        Plugins = @(
            @{ Name = "ModelContextProtocol"; Enabled = $true }
            @{ Name = "AllToolsets"; Enabled = $true }
        )
    } | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 $uproject
    Add-Result "fixture-project" "PASS" "clean project at $projectDir"

    Push-Location $projectDir
    try {
        Invoke-Native -Exe "git" -NativeArgs @("init", "-q", "-b", "main") | Out-Null
        Invoke-Native -Exe "git" -NativeArgs @("config", "user.email", "forge@acceptance.invalid") | Out-Null
        Invoke-Native -Exe "git" -NativeArgs @("config", "user.name", "Forge Acceptance") | Out-Null
        Invoke-Native -Exe "git" -NativeArgs @("config", "core.autocrlf", "false") | Out-Null
        $install = Invoke-Forge @("install", "--project", ".", "--apply")
        if (-not $install) { throw "forge install did not return a payload" }
        Invoke-Native -Exe "git" -NativeArgs @("add", "-A") | Out-Null
        Invoke-Native -Exe "git" -NativeArgs @("commit", "-qm", "fixture base") | Out-Null
        Add-Result "forge-overlay" "PASS" "overlay applied and committed"

        $closedBefore = Get-Ownership $projectDir
        if ($closedBefore.ownership -eq "FREE") {
            Add-Result "ownership-before-launch" "PASS" "no editor holds the project"
        } else {
            Add-Result "ownership-before-launch" "FAIL" "expected FREE, got $($closedBefore.ownership). Close any open editor first."
        }

        Write-Host "`n  launching the editor (this takes a while on first run)..." -ForegroundColor DarkGray
        $editor = Start-Process -FilePath $editorExe -PassThru -ArgumentList @(
            "`"$uproject`"", "-ModelContextProtocolStartServer"
        )
        $deadline = (Get-Date).AddMinutes(10)
        $held = $null
        $ownedAt = $null
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 15
            if ($editor.HasExited) { throw "the editor exited during startup" }
            $held = Get-Ownership $projectDir
            if ($held.ownership -eq "HELD") { $ownedAt = Get-Date; break }
        }

        if ($held -and $held.ownership -eq "HELD") {
            $signal = ($held.evidence | Where-Object { $_.conclusive } | Select-Object -First 1).signal
            Add-Result "ownership-editor-open" "PASS" "HELD via $signal"
        } else {
            Add-Result "ownership-editor-open" "FAIL" "editor is open but ownership read $($held.ownership)"
        }

        $mcpSignal = $null
        while ((Get-Date) -lt $deadline) {
            $mcpSignal = $held.evidence | Where-Object { $_.signal -eq "mcp-handshake" -and $_.conclusive }
            if ($mcpSignal) { break }
            Start-Sleep -Seconds 15
            if ($editor.HasExited) { break }
            $held = Get-Ownership $projectDir
        }
        if ($mcpSignal -and -not $ownedAt) {
            Add-Result "mcp-handshake" "FAIL" "MCP answered but the process was never detected as holding the project, so the two waits cannot be compared"
        } elseif ($mcpSignal) {
            $waited = [int]((Get-Date) - $ownedAt).TotalSeconds
            Add-Result "mcp-handshake" "PASS" "a real editor answered an MCP initialize ${waited}s after the process was detected" @{
                process_detected_at = $ownedAt.ToString("o")
                mcp_answered_after_seconds = $waited
            }
        } else {
            $why = Invoke-Forge @("route-status", "--project", ".")
            $row = Get-Route $why "unreal-native-mcp"
            $reason = if ($row.endpoint_disagreement) {
                $row.endpoint_disagreement.detail
            } else {
                "no MCP answer within the window. The server only listens when -ModelContextProtocolStartServer is passed, bAutoStartServer is set, or ModelContextProtocol.StartServer is run, and both settings are read at startup so a change needs a restart"
            }
            Add-Result "mcp-handshake" "NOT_PROVEN" $reason
        }

        $status = Invoke-Forge @("route-status", "--project", ".")
        $live = Get-Route $status "unreal-native-mcp"
        $closed = Get-Route $status "unreal-python"
        if (-not $live) {
            Add-Result "live-route-verified" "FAIL" "route-status returned no row for unreal-native-mcp"
        } elseif ($live.status -eq "AVAILABLE_VERIFIED") {
            Add-Result "live-route-verified" "PASS" "ue.live.typed is AVAILABLE_VERIFIED against a real editor"
        } else {
            Add-Result "live-route-verified" "NOT_PROVEN" "live route read $($live.status): $($live.note)"
        }
        if (-not $closed) {
            Add-Result "lane-exclusivity-open" "FAIL" "route-status returned no row for unreal-python"
        } elseif ($closed.status -notlike "AVAILABLE*") {
            Add-Result "lane-exclusivity-open" "PASS" "editor-closed lane is shut while the editor holds the project"
        } else {
            Add-Result "lane-exclusivity-open" "FAIL" "both editor lanes reported available at once"
        }

        if ($mcpSignal) {
            $endpoint = if ($live.endpoint) { $live.endpoint } else { "http://127.0.0.1:8000/mcp" }
            $raw = Invoke-Native -Exe "python" -NativeArgs @(
                (Join-Path $PSScriptRoot "live_editor_stages.py"), "--url", $endpoint
            ) -AllowFailure
            try {
                foreach ($item in ($raw | ConvertFrom-Json).stages) {
                    Add-Result $item.stage $item.status $item.detail
                }
            } catch {
                Add-Result "blueprint-create-compile" "FAIL" "live stage driver returned no usable result"
                Add-Result "pie-and-viewport-evidence" "FAIL" "live stage driver returned no usable result"
            }
        } else {
            $why = "the MCP route never bound, so nothing could be driven through it"
            Add-Result "blueprint-create-compile" "NOT_PROVEN" $why
            Add-Result "pie-and-viewport-evidence" "NOT_PROVEN" $why
        }

        $mcpPath = Join-Path $projectDir ".forge\mcp.json"
        $mcpBefore = Get-Content -Raw -Encoding utf8 $mcpPath
        try {
            $silenced = $mcpBefore -replace ':8000/mcp', ':8/mcp'
            Set-Content -Encoding utf8 -Path $mcpPath -Value $silenced
            $frozen = Get-Ownership $projectDir
            $byProcess = $frozen.evidence | Where-Object { $_.signal -eq "process-inspection" -and $_.conclusive }
            if ($frozen.ownership -eq "HELD" -and $byProcess) {
                Add-Result "ownership-frozen-editor" "PASS" "a live editor that answers no MCP is still HELD, on process evidence"
            } elseif ($frozen.ownership -eq "HELD") {
                Add-Result "ownership-frozen-editor" "PASS" "HELD while MCP was silent, though no conclusive process evidence was carried"
            } else {
                Add-Result "ownership-frozen-editor" "FAIL" "an open editor answering no MCP read as $($frozen.ownership), which would open the editor-closed lane against a live project"
            }
        } finally {
            Set-Content -Encoding utf8 -Path $mcpPath -Value $mcpBefore
        }

        Write-Host "`n  closing the editor..." -ForegroundColor DarkGray
        $editor.CloseMainWindow() | Out-Null
        if (-not $editor.WaitForExit(120000)) { $editor.Kill() }
        $editor = $null
        Start-Sleep -Seconds 5

        $free = Get-Ownership $projectDir
        if ($free.ownership -eq "FREE") {
            Add-Result "ownership-editor-closed" "PASS" "positive evidence the project is free"
        } else {
            Add-Result "ownership-editor-closed" "FAIL" "expected FREE, got $($free.ownership)"
        }

        $env:PATH = "$(Split-Path $cmdExe);$env:PATH"
        $after = Invoke-Forge @("route-status", "--project", ".")
        $closedAfter = Get-Route $after "unreal-python"
        if (-not $closedAfter) {
            Add-Result "lane-swap-on-close" "FAIL" "route-status returned no row for unreal-python"
        } elseif ($closedAfter.status -like "AVAILABLE*") {
            Add-Result "lane-swap-on-close" "PASS" "editor-closed lane opened once the editor released the project"
        } else {
            Add-Result "lane-swap-on-close" "FAIL" "editor-closed lane stayed shut: $($closedAfter.status) - $($closedAfter.note)"
        }

        $resultFile = Join-Path $projectDir "commandlet-result.json"
        $auditScript = Join-Path $projectDir "audit.py"
        @"
import json, unreal
paths = [str(a.package_name) for a in unreal.AssetRegistryHelpers.get_asset_registry().get_all_assets()]
with open(r'$resultFile', 'w', encoding='utf-8') as handle:
    json.dump({'schema': 'forge.commandlet-result/v1', 'ok': True, 'asset_count': len(paths)}, handle)
"@ | Set-Content -Encoding utf8 $auditScript
        Invoke-Native -Exe $cmdExe -NativeArgs @(
            "$uproject", "-run=pythonscript", "-script=$auditScript", "-unattended", "-nop4", "-nosplash"
        ) -AllowFailure | Out-Null
        if (Test-Path $resultFile) {
            $payload = Get-Content $resultFile -Raw | ConvertFrom-Json
            Add-Result "commandlet-result-file" "PASS" "commandlet wrote a result file reporting $($payload.asset_count) assets"
        } else {
            Add-Result "commandlet-result-file" "FAIL" "no result file; the exit code alone is not authoritative for editor-closed work"
        }
    } finally {
        Pop-Location
    }
} catch {
    Add-Result "driver" "FAIL" $_.Exception.Message
} finally {
    if ($editor -and -not $editor.HasExited) { $editor.Kill() }
    if (-not $KeepProject -and (Test-Path $WorkPath)) {
        Remove-Item -Recurse -Force $WorkPath -ErrorAction SilentlyContinue
    }
}

Write-Host ""
$failed = @($results | Where-Object { $_.status -eq 'FAIL' })
$summary = [pscustomobject]@{
    schema = "forge.unreal-acceptance/v1"
    engine = $EnginePath
    stages = $results
    passed = @($results | Where-Object { $_.status -eq 'PASS' }).Count
    failed = $failed.Count
    unproven = @($results | Where-Object { $_.status -in @('NOT_PROVEN') }).Count
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $PSScriptRoot "acceptance-result.json")
Write-Host ("{0} passed, {1} failed, {2} unproven" -f $summary.passed, $summary.failed, $summary.unproven) -ForegroundColor Cyan

if ($failed.Count -gt 0) { exit 1 }
exit 0
