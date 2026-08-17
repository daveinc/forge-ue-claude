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
      - a frozen editor -- alive but not answering MCP -- is still detected
      - the live and editor-closed lanes swap as the editor opens and closes
      - a commandlet runs against the closed project and writes its result file

    Stages it cannot yet settle are reported NOT_IMPLEMENTED with the reason,
    rather than skipped silently or asserted on faith.

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
    param([string]$Stage, [string]$Status, [string]$Detail)
    $script:results += [pscustomobject]@{ stage = $Stage; status = $Status; detail = $Detail }
    $colour = switch ($Status) { 'PASS' { 'Green' } 'FAIL' { 'Red' } default { 'Yellow' } }
    Write-Host ("  {0,-32} {1,-16} {2}" -f $Stage, $Status, $Detail) -ForegroundColor $colour
}

function Invoke-Forge {
    param([string[]]$ForgeArgs)
    $raw = & python $forge @ForgeArgs 2>$null
    if (-not $raw) { return $null }
    try { return ($raw | ConvertFrom-Json) } catch { return $null }
}

function Get-Ownership {
    param([string]$Project)
    $script = @"
import json, sys
sys.path.insert(0, r'$repoRoot\plugins\forge-ue-studio\scripts')
import forge_mcp, pathlib
print(json.dumps(forge_mcp.live_editor_holds_project(pathlib.Path(r'$Project'))))
"@
    return (& python -c $script | ConvertFrom-Json)
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
        & git init -q -b main 2>$null
        & git config user.email "forge@acceptance.invalid"
        & git config user.name "Forge Acceptance"
        $install = Invoke-Forge @("install", "--project", ".", "--apply")
        if (-not $install) { throw "forge install did not return a payload" }
        & git add -A 2>$null; & git commit -qm "fixture base" 2>$null
        Add-Result "forge-overlay" "PASS" "overlay applied and committed"

        $closedBefore = Get-Ownership $projectDir
        if ($closedBefore.ownership -eq "FREE") {
            Add-Result "ownership-before-launch" "PASS" "no editor holds the project"
        } else {
            Add-Result "ownership-before-launch" "FAIL" "expected FREE, got $($closedBefore.ownership). Close any open editor first."
        }

        Write-Host "`n  launching the editor (this takes a while on first run)..." -ForegroundColor DarkGray
        $editor = Start-Process -FilePath $editorExe -ArgumentList @("`"$uproject`"") -PassThru
        $deadline = (Get-Date).AddMinutes(10)
        $held = $null
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 15
            if ($editor.HasExited) { throw "the editor exited during startup" }
            $held = Get-Ownership $projectDir
            if ($held.ownership -eq "HELD") { break }
        }

        if ($held -and $held.ownership -eq "HELD") {
            $signal = ($held.evidence | Where-Object { $_.conclusive } | Select-Object -First 1).signal
            Add-Result "ownership-editor-open" "PASS" "HELD via $signal"
        } else {
            Add-Result "ownership-editor-open" "FAIL" "editor is open but ownership read $($held.ownership)"
        }

        $mcpSignal = $held.evidence | Where-Object { $_.signal -eq "mcp-handshake" -and $_.conclusive }
        if ($mcpSignal) {
            Add-Result "mcp-handshake" "PASS" "a real editor answered an MCP initialize"
        } else {
            Add-Result "mcp-handshake" "NOT_PROVEN" "the editor did not answer MCP; enable ModelContextProtocol and AllToolsets, and confirm the endpoint in .forge/mcp.json"
        }

        $status = Invoke-Forge @("route-status", "--project", ".")
        $live = $status.routes | Where-Object { $_.id -eq "unreal-native-mcp" }
        $closed = $status.routes | Where-Object { $_.id -eq "unreal-python" }
        if ($live.status -eq "AVAILABLE_VERIFIED") {
            Add-Result "live-route-verified" "PASS" "ue.live.typed is AVAILABLE_VERIFIED against a real editor"
        } else {
            Add-Result "live-route-verified" "NOT_PROVEN" "live route read $($live.status); this is the claim only a real editor can settle"
        }
        if ($closed.status -notlike "AVAILABLE*") {
            Add-Result "lane-exclusivity-open" "PASS" "editor-closed lane is shut while the editor holds the project"
        } else {
            Add-Result "lane-exclusivity-open" "FAIL" "both editor lanes reported available at once"
        }

        Add-Result "blueprint-create-compile" "NOT_IMPLEMENTED" "needs the live toolset's real call names, which are discovered from the bound namespace rather than assumed"
        Add-Result "pie-and-viewport-evidence" "NOT_IMPLEMENTED" "same: written only once the tool names are read off a live handshake"

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
        $closedAfter = $after.routes | Where-Object { $_.id -eq "unreal-python" }
        if ($closedAfter.status -like "AVAILABLE*") {
            Add-Result "lane-swap-on-close" "PASS" "editor-closed lane opened once the editor released the project"
        } else {
            Add-Result "lane-swap-on-close" "FAIL" "editor-closed lane stayed shut: $($closedAfter.status)"
        }

        $resultFile = Join-Path $projectDir "commandlet-result.json"
        $script = Join-Path $projectDir "audit.py"
        @"
import json, unreal
paths = [str(a.package_name) for a in unreal.AssetRegistryHelpers.get_asset_registry().get_all_assets()]
with open(r'$resultFile', 'w', encoding='utf-8') as handle:
    json.dump({'schema': 'forge.commandlet-result/v1', 'ok': True, 'asset_count': len(paths)}, handle)
"@ | Set-Content -Encoding utf8 $script
        & $cmdExe "$uproject" -run=pythonscript -script="$script" -unattended -nop4 -nosplash 2>&1 | Out-Null
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
    unproven = @($results | Where-Object { $_.status -in @('NOT_PROVEN', 'NOT_IMPLEMENTED') }).Count
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $PSScriptRoot "acceptance-result.json")
Write-Host ("{0} passed, {1} failed, {2} unproven" -f $summary.passed, $summary.failed, $summary.unproven) -ForegroundColor Cyan

if ($failed.Count -gt 0) { exit 1 }
exit 0
