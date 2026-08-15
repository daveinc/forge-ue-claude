[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Plugin', 'GSD', 'Survey', 'Install', 'Verify', 'Profile', 'Route', 'Lifecycle', 'Validate')]
    [string]$Mode = 'Plugin',
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$GsdVersion = '1.8.0',
    [string]$ProjectPath,
    [string]$RequestPath,
    [ValidateSet('attempt-result', 'bootstrap-report', 'capability-contract', 'lane-lease', 'lifecycle-state', 'learning-record', 'packet-registry', 'provider-evaluation', 'research-record', 'review-cycle', 'route-request', 'work-packet')]
    [string]$ContractKind,
    [string]$InputPath,
    [ValidateSet('status', 'bootstrap-start', 'bootstrap-complete', 'init-start', 'init-complete', 'discuss-start', 'discuss-complete', 'plan-start', 'plan-complete', 'execute-start', 'execute-complete', 'verify-start', 'verify-complete', 'next-phase', 'project-complete')]
    [string]$LifecycleEvent = 'status',
    [int]$Phase,
    [switch]$Apply,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$forgeScript = Join-Path $repoRoot 'plugins\forge-ue-studio\scripts\forge.py'

if ($Mode -eq 'Plugin') {
    $commands = @(
        "codex plugin marketplace add `"$repoRoot`"",
        'codex plugin add forge-ue-studio@forge-ue-studio-local'
    )
    if (-not $Apply) {
        [pscustomobject]@{
            mode = 'dry-run'
            purpose = 'Register the repository marketplace and install the Forge Codex plugin'
            commands = $commands
            changed = $false
        } | ConvertTo-Json -Depth 4
        exit 0
    }
    if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        throw 'Codex CLI was not found. Forge will not install or modify it automatically.'
    }
    if ($PSCmdlet.ShouldProcess('Codex local plugin configuration', 'Register Forge marketplace and install Forge plugin')) {
        & codex plugin marketplace add $repoRoot
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & codex plugin add 'forge-ue-studio@forge-ue-studio-local'
        exit $LASTEXITCODE
    }
    exit 0
}

if ($Mode -eq 'GSD') {
    $package = "@opengsd/gsd-core@$GsdVersion"
    $command = "npx `"$package`" --codex --global"
    $userProfileRoot = [Environment]::GetFolderPath('UserProfile')
    $sharedSkillRoot = Join-Path $userProfileRoot '.agents\skills'
    $legacySkillRoot = Join-Path $userProfileRoot '.codex\skills'
    $agentRoot = Join-Path $userProfileRoot '.codex\agents'
    $coreRoot = Join-Path $userProfileRoot '.codex\gsd-core'
    $runtimeScript = Join-Path $coreRoot 'bin\gsd-tools.cjs'
    $detectedSkills = @(
        foreach ($root in @($sharedSkillRoot, $legacySkillRoot)) {
            if (Test-Path -LiteralPath $root) {
                Get-ChildItem -LiteralPath $root -Directory -Filter 'gsd-*' -ErrorAction SilentlyContinue
            }
        }
    )
    $detectedAgents = if (Test-Path -LiteralPath $agentRoot) { @(Get-ChildItem -LiteralPath $agentRoot -File -Filter 'gsd-*.toml' -ErrorAction SilentlyContinue) } else { @() }

    if (-not $Apply) {
        [pscustomobject]@{
            mode = 'dry-run'
            purpose = 'Install the pinned upstream GSD phase engine for Codex'
            package = $package
            command = $command
            scope = 'global-codex'
            existing = [pscustomobject]@{
                gsd_tools = [bool](Get-Command gsd-tools -ErrorAction SilentlyContinue)
                skills = $detectedSkills.Count
                agents = $detectedAgents.Count
                core = Test-Path -LiteralPath $coreRoot
                runtime_script = Test-Path -LiteralPath $runtimeScript
            }
            changed = $false
        } | ConvertTo-Json -Depth 5
        exit 0
    }

    foreach ($required in @('node', 'npm', 'npx', 'codex')) {
        if (-not (Get-Command $required -ErrorAction SilentlyContinue)) {
            throw "$required was not found. Forge will not install or modify it automatically."
        }
    }

    if ($PSCmdlet.ShouldProcess("Codex global GSD $GsdVersion", "Download and install $package")) {
        & npx $package --codex --global
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $installedSkills = @(
            foreach ($root in @($sharedSkillRoot, $legacySkillRoot)) {
                if (Test-Path -LiteralPath $root) {
                    Get-ChildItem -LiteralPath $root -Directory -Filter 'gsd-*' -ErrorAction SilentlyContinue
                }
            }
        )
        $installedAgents = @(Get-ChildItem -LiteralPath $agentRoot -File -Filter 'gsd-*.toml' -ErrorAction SilentlyContinue)
        if ($installedSkills.Count -eq 0 -or $installedAgents.Count -eq 0 -or -not (Test-Path -LiteralPath $runtimeScript)) {
            throw 'GSD installer completed but the Codex GSD skills, agents, or runtime script were not detected.'
        }
        [pscustomobject]@{
            mode = 'apply'
            package = $package
            scope = 'global-codex'
            skills = $installedSkills.Count
            agents = $installedAgents.Count
            gsd_tools = [bool](Get-Command gsd-tools -ErrorAction SilentlyContinue)
            runtime_script = $runtimeScript
            skills_roots = @($sharedSkillRoot, $legacySkillRoot)
            restart_required = $true
        } | ConvertTo-Json -Depth 4
    }
    exit 0
}

if ($Mode -ne 'Validate' -and -not $ProjectPath) {
    throw '-ProjectPath is required for Survey, Install, Verify, Profile, Route, and Lifecycle modes.'
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.10+ is required. Forge will not install it automatically.'
}

$arguments = @($forgeScript, $Mode.ToLowerInvariant())
if ($Mode -eq 'Validate') {
    if (-not $ContractKind -or -not $InputPath) {
        throw '-ContractKind and -InputPath are required for Validate mode.'
    }
    $arguments += @('--kind', $ContractKind, '--input', $InputPath)
} else {
    $arguments += @('--project', $ProjectPath)
}
if ($Mode -eq 'Route') {
    if (-not $RequestPath) { throw '-RequestPath is required for Route mode.' }
    $arguments += @('--request', $RequestPath)
}
if ($Mode -eq 'Lifecycle') {
    $arguments += @('--event', $LifecycleEvent)
    if ($Phase -gt 0) { $arguments += @('--phase', [string]$Phase) }
    if ($Apply) { $arguments += '--apply' }
}
if ($OutputPath) {
    $arguments += @('--output', $OutputPath)
}
if ($Mode -in @('Install', 'Profile') -and $Apply) {
    $operation = if ($Mode -eq 'Profile') { 'Write a non-destructive detected capability profile' } else { 'Apply the reversible Forge project overlay' }
    if ($PSCmdlet.ShouldProcess($ProjectPath, $operation)) {
        $arguments += '--apply'
    } else {
        $arguments += '--dry-run'
    }
} elseif ($Mode -in @('Install', 'Profile')) {
    $arguments += '--dry-run'
}

& python @arguments
exit $LASTEXITCODE
