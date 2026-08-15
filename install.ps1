[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('Plugin', 'GSD', 'Survey', 'Install', 'Verify', 'Profile', 'Next', 'BootstrapCheck', 'Route', 'Lifecycle', 'Validate', 'Host')]
    [string]$Mode = 'Plugin',
    # The resident AI runtime. Defaults to the registry's default_host.
    # Named -RuntimeHost because $Host is a reserved PowerShell automatic variable.
    # Deliberately NOT a ValidateSet: hosts are declared in hosts/registry.json, and
    # binding-time validation here would reject a newly added profile before the
    # script could read it. Validation happens against the registry below.
    [ArgumentCompleter({
        param($commandName, $parameterName, $wordToComplete, $commandAst, $fakeBoundParameters)
        $registry = Join-Path (Split-Path -Parent $commandAst.CommandElements[0].Value) 'plugins\forge-ue-studio\hosts\registry.json'
        if (Test-Path -LiteralPath $registry) {
            (Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json).hosts |
                ForEach-Object { $_.id } |
                Where-Object { $_ -like "$wordToComplete*" }
        }
    })]
    [string]$RuntimeHost,
    [ValidateSet('list', 'status', 'set')]
    [string]$HostAction = 'status',
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$GsdVersion = '1.10.0',
    [string]$ProjectPath,
    [string]$RequestPath,
    [ValidateSet('attempt-result', 'bootstrap-report', 'capability-contract', 'host-profile', 'lane-lease', 'lifecycle-state', 'learning-record', 'packet-registry', 'provider-evaluation', 'research-record', 'review-cycle', 'route-request', 'runtime-state', 'smart-entry', 'work-packet')]
    [string]$ContractKind,
    [string]$InputPath,
    [ValidateSet('status')]
    [string]$LifecycleEvent = 'status',
    [int]$Phase,
    [switch]$Apply,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$forgeScript = Join-Path $repoRoot 'plugins\forge-ue-studio\scripts\forge.py'
$registryPath = Join-Path $repoRoot 'plugins\forge-ue-studio\hosts\registry.json'

if (-not (Test-Path -LiteralPath $registryPath)) {
    throw "Forge host registry was not found at $registryPath."
}
$registry = Get-Content -LiteralPath $registryPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $RuntimeHost) { $RuntimeHost = $registry.default_host }
$profileEntry = $registry.hosts | Where-Object { $_.id -eq $RuntimeHost } | Select-Object -First 1
if (-not $profileEntry) {
    throw "Unknown runtime host '$RuntimeHost'. Known hosts: $(($registry.hosts | ForEach-Object { $_.id }) -join ', ')."
}

function Expand-HostPath {
    param([string]$Value)
    if (-not $Value) { return $null }
    return $Value -replace '^~', [Environment]::GetFolderPath('UserProfile')
}

if ($Mode -eq 'Plugin') {
    $commands = @($profileEntry.plugin.install_commands | ForEach-Object { $_ -replace '<repo-root>', $repoRoot })
    $interactive = [bool]$profileEntry.plugin.install_is_interactive

    if (-not $Apply) {
        [pscustomobject]@{
            mode = 'dry-run'
            host = $RuntimeHost
            purpose = "Register the repository marketplace and install the Forge plugin for $($profileEntry.display_name)"
            marketplace_manifest = $profileEntry.plugin.marketplace_manifest
            commands = $commands
            interactive = $interactive
            note = $profileEntry.plugin.install_note
            changed = $false
        } | ConvertTo-Json -Depth 5
        exit 0
    }

    if ($interactive) {
        # Hosts flagged install_is_interactive install plugins from inside a session.
        # There is no non-interactive CLI to shell out to, so print the commands to run.
        [pscustomobject]@{
            mode = 'manual'
            host = $RuntimeHost
            purpose = "Install the Forge plugin for $($profileEntry.display_name)"
            run_these_in_a_session = $commands
            note = $profileEntry.plugin.install_note
            changed = $false
        } | ConvertTo-Json -Depth 5
        exit 0
    }

    $cliName = @($profileEntry.cli.executables)[0]
    if (-not (Get-Command $cliName -ErrorAction SilentlyContinue)) {
        throw "$($profileEntry.display_name) was not found. Forge will not install or modify it automatically."
    }
    if ($PSCmdlet.ShouldProcess("$($profileEntry.display_name) local plugin configuration", 'Register Forge marketplace and install Forge plugin')) {
        & $cliName plugin marketplace add $repoRoot
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $cliName plugin add 'forge-ue-studio@forge-ue-studio-local'
        exit $LASTEXITCODE
    }
    exit 0
}

if ($Mode -eq 'GSD') {
    $package = "@opengsd/gsd-core@$GsdVersion"
    $installArgs = @($profileEntry.gsd.install_args)
    $command = "npx `"$package`" $($installArgs -join ' ')"
    $userProfileRoot = [Environment]::GetFolderPath('UserProfile')
    $skillRoots = @($profileEntry.discovery.skill_roots | ForEach-Object { Expand-HostPath $_ })
    $agentRoot = Expand-HostPath $profileEntry.discovery.agent_root
    $agentGlob = $profileEntry.discovery.agent_glob
    $coreRoot = Expand-HostPath $profileEntry.gsd.runtime_root
    $runtimeScript = Join-Path $coreRoot 'bin\gsd-tools.cjs'

    $detectedSkills = @(
        foreach ($root in $skillRoots) {
            if ($root -and (Test-Path -LiteralPath $root)) {
                Get-ChildItem -LiteralPath $root -Directory -Filter 'gsd-*' -ErrorAction SilentlyContinue
            }
        }
    )
    $detectedAgents = if ($agentRoot -and (Test-Path -LiteralPath $agentRoot)) {
        @(Get-ChildItem -LiteralPath $agentRoot -File -Filter $agentGlob -ErrorAction SilentlyContinue)
    } else { @() }

    if (-not $Apply) {
        [pscustomobject]@{
            mode = 'dry-run'
            host = $RuntimeHost
            purpose = "Install the pinned upstream GSD phase engine for $($profileEntry.display_name)"
            package = $package
            command = $command
            scope = "global-$RuntimeHost"
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

    $required = @('node', 'npm', 'npx')
    if (@($profileEntry.cli.executables).Count -gt 0) { $required += @($profileEntry.cli.executables)[0] }
    foreach ($tool in $required) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "$tool was not found. Forge will not install or modify it automatically."
        }
    }

    if ($PSCmdlet.ShouldProcess("$($profileEntry.display_name) global GSD $GsdVersion", "Download and install $package")) {
        & npx $package @installArgs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $installedSkills = @(
            foreach ($root in $skillRoots) {
                if ($root -and (Test-Path -LiteralPath $root)) {
                    Get-ChildItem -LiteralPath $root -Directory -Filter 'gsd-*' -ErrorAction SilentlyContinue
                }
            }
        )
        $installedAgents = if ($agentRoot -and (Test-Path -LiteralPath $agentRoot)) {
            @(Get-ChildItem -LiteralPath $agentRoot -File -Filter $agentGlob -ErrorAction SilentlyContinue)
        } else { @() }
        if ($installedSkills.Count -eq 0 -or -not (Test-Path -LiteralPath $runtimeScript)) {
            throw "GSD installer completed but the $($profileEntry.display_name) GSD skills or runtime script were not detected."
        }
        [pscustomobject]@{
            mode = 'apply'
            host = $RuntimeHost
            package = $package
            scope = "global-$RuntimeHost"
            skills = $installedSkills.Count
            agents = $installedAgents.Count
            gsd_tools = [bool](Get-Command gsd-tools -ErrorAction SilentlyContinue)
            runtime_script = $runtimeScript
            skills_roots = $skillRoots
            restart_required = $true
        } | ConvertTo-Json -Depth 4
    }
    exit 0
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.10+ is required. Forge will not install it automatically.'
}

if ($Mode -eq 'Host') {
    $arguments = @($forgeScript, 'host', $HostAction)
    if ($HostAction -ne 'list') {
        if (-not $ProjectPath) { throw '-ProjectPath is required for Host status and set actions.' }
        $arguments += @('--project', $ProjectPath)
    }
    if ($HostAction -eq 'set') {
        $arguments += @('--host', $RuntimeHost)
        if ($Apply) {
            if ($PSCmdlet.ShouldProcess($ProjectPath, "Assign resident runtime '$RuntimeHost' and re-render host surfaces")) {
                $arguments += '--apply'
            }
        }
    } elseif ($HostAction -eq 'status' -and $PSBoundParameters.ContainsKey('RuntimeHost')) {
        $arguments += @('--host', $RuntimeHost)
    }
    if ($OutputPath) { $arguments += @('--output', $OutputPath) }
    & python @arguments
    exit $LASTEXITCODE
}

if ($Mode -ne 'Validate' -and -not $ProjectPath) {
    throw '-ProjectPath is required for Survey, Install, Verify, Profile, Next, BootstrapCheck, Route, and Lifecycle modes.'
}

# PascalCase mode names map to the CLI's kebab-case verbs.
$verbMap = @{ 'BootstrapCheck' = 'bootstrap-check' }
$verb = if ($verbMap.ContainsKey($Mode)) { $verbMap[$Mode] } else { $Mode.ToLowerInvariant() }
$arguments = @($forgeScript, $verb)
if ($Mode -eq 'Validate') {
    if (-not $ContractKind -or -not $InputPath) {
        throw '-ContractKind and -InputPath are required for Validate mode.'
    }
    $arguments += @('--kind', $ContractKind, '--input', $InputPath)
} else {
    $arguments += @('--project', $ProjectPath)
}
if ($Mode -in @('Survey', 'Install', 'Verify', 'Profile', 'Next', 'BootstrapCheck', 'Route') -and $PSBoundParameters.ContainsKey('RuntimeHost')) {
    $arguments += @('--host', $RuntimeHost)
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
