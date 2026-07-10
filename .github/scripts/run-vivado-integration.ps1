[CmdletBinding()]
param(
    [string]$ArtifactsRoot = (Join-Path $PWD ".tmp\vivado-integration")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-LoggedNativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$LogPath,

        [switch]$AllowFailure
    )

    Push-Location -LiteralPath $WorkingDirectory
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $commandOutput = @(& $Executable @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }

    $commandOutput |
        ForEach-Object { "$_" } |
        Out-File -LiteralPath $LogPath -Encoding utf8

    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "Command failed with exit code ${exitCode}: $Executable $($Arguments -join ' ')"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $commandOutput
        LogPath = $LogPath
    }
}

function Assert-FreshFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [datetime]$StartedAt
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required Vivado artifact is missing: $Path"
    }

    $artifact = Get-Item -LiteralPath $Path
    if ($artifact.LastWriteTimeUtc -lt $StartedAt.AddSeconds(-5).ToUniversalTime()) {
        throw "Vivado artifact is stale: $Path"
    }
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$vivadoCommand = Get-Command vivado -ErrorAction Stop
$uvCommand = Get-Command uv -ErrorAction Stop
$vivadoExecutable = if ($vivadoCommand.Source) {
    $vivadoCommand.Source
}
else {
    $vivadoCommand.Path
}
$uvExecutable = if ($uvCommand.Source) {
    $uvCommand.Source
}
else {
    $uvCommand.Path
}

$vivadoRoot = Split-Path (Split-Path $vivadoExecutable -Parent) -Parent
$tclStore = Join-Path $vivadoRoot "data\XilinxTclStore"
$tclLibraryPaths = @(
    (Join-Path $tclStore "support"),
    (Join-Path $tclStore "support\appinit"),
    (Join-Path $tclStore "tclapp"),
    (Join-Path $tclStore "tclapp\xilinx"),
    (Join-Path $tclStore "tclapp\xilinx\xsim")
) | Where-Object { Test-Path -LiteralPath $_ -PathType Container }
if ($tclLibraryPaths.Count -gt 0) {
    $encodedTclPaths = @(
        $tclLibraryPaths |
            ForEach-Object { "{" + ($_.Replace("\", "/")) + "}" }
    )
    if ($env:TCLLIBPATH) {
        $encodedTclPaths += $env:TCLLIBPATH
    }
    $env:TCLLIBPATH = $encodedTclPaths -join " "
}

$runId = if ($env:GITHUB_RUN_ID) {
    "$($env:GITHUB_RUN_ID)-$($env:GITHUB_RUN_ATTEMPT)"
}
else {
    "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), ([guid]::NewGuid().ToString("N"))
}
$runDirectory = Join-Path $ArtifactsRoot $runId
New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null

$versionResult = Invoke-LoggedNativeCommand `
    -Executable $vivadoExecutable `
    -Arguments @("-version") `
    -WorkingDirectory $repositoryRoot `
    -LogPath (Join-Path $runDirectory "vivado-version.log") `
    -AllowFailure

$versionBanner = $versionResult.Output -join "`n"
if ($versionBanner -notmatch "(?i)vivado\s+v?\d{4}\.\d+") {
    throw "Vivado version command did not return a valid version banner"
}

$preflightResult = Invoke-LoggedNativeCommand `
    -Executable $vivadoExecutable `
    -Arguments @(
        "-mode", "batch",
        "-nojournal",
        "-nolog",
        "-notrace",
        "-source", (Join-Path $PSScriptRoot "vivado-preflight.tcl")
    ) `
    -WorkingDirectory $repositoryRoot `
    -LogPath (Join-Path $runDirectory "vivado-preflight.log")

if (($preflightResult.Output -join "`n") -notmatch "VIVADO_PREFLIGHT_PASS") {
    throw "Vivado startup or license preflight did not report PASS"
}

$simulationStartedAt = Get-Date
$agentPath = Join-Path $repositoryRoot ".trae\agent\agent.py"
$simulationResult = Invoke-LoggedNativeCommand `
    -Executable $uvExecutable `
    -Arguments @(
        "run", "--frozen", "python", "-B", $agentPath,
        "--sim-rtl", "sync-fifo",
        "--no-wave-gui",
        "--output-dir", $runDirectory
    ) `
    -WorkingDirectory $repositoryRoot `
    -LogPath (Join-Path $runDirectory "sync-fifo-agent.log")

$projectDirectory = Join-Path $runDirectory "sync-fifo"
$rtlPath = Join-Path $projectDirectory "rtl\sync_fifo.v"
$testbenchPath = Join-Path $projectDirectory "tb\tb_sync_fifo.v"
$vcdPath = Join-Path $projectDirectory "sim\sync_fifo_trace.vcd"
$projectPath = Join-Path $projectDirectory "vivado_project\sync_fifo_project.xpr"
$manifestPath = Join-Path $projectDirectory "artifacts.json"
$simulationReportPath = Join-Path $projectDirectory "reports\sim_report.md"

foreach ($requiredPath in @(
    $rtlPath,
    $testbenchPath,
    $vcdPath,
    $projectPath,
    $manifestPath,
    $simulationReportPath
)) {
    Assert-FreshFile -Path $requiredPath -StartedAt $simulationStartedAt
}

$waveDatabases = @(
    Get-ChildItem `
        -LiteralPath (Join-Path $projectDirectory "sim") `
        -Filter "*.wdb" `
        -File
)
if ($waveDatabases.Count -eq 0) {
    throw "Simulation did not generate a WDB file"
}
foreach ($waveDatabase in $waveDatabases) {
    Assert-FreshFile -Path $waveDatabase.FullName -StartedAt $simulationStartedAt
}

$evidenceFiles = @(
    Get-ChildItem -LiteralPath $projectDirectory -Recurse -File |
        Where-Object { $_.Extension -in @(".log", ".jou", ".md", ".txt") }
)
$scoreboardMatches = @()
if ($evidenceFiles.Count -gt 0) {
    $scoreboardMatches = @(
        Select-String `
            -Path $evidenceFiles.FullName `
            -Pattern "SYNC_FIFO_SCOREBOARD_PASS" `
            -SimpleMatch `
            -ErrorAction SilentlyContinue
    )
}
if ($scoreboardMatches.Count -eq 0) {
    throw "Real simulator output did not contain SYNC_FIFO_SCOREBOARD_PASS"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 |
    ConvertFrom-Json
$runs = @($manifest.runs)
if ($runs.Count -eq 0) {
    throw "Runtime manifest contains no runs"
}
$latestRun = $runs[-1]
if ($latestRun.status -ne "PASS") {
    throw "Latest runtime manifest status is not PASS"
}
if (-not $latestRun.run_id) {
    throw "Latest runtime manifest run_id is missing"
}
if ($latestRun.flow -ne "sim-rtl") {
    throw "Latest runtime manifest flow is not sim-rtl"
}

$negativeDirectory = Join-Path $runDirectory "negative-syntax"
Copy-Item -LiteralPath $projectDirectory -Destination $negativeDirectory -Recurse
$negativeRtlPath = Join-Path $negativeDirectory "rtl\sync_fifo.v"
Add-Content `
    -LiteralPath $negativeRtlPath `
    -Value "`nTHIS_TOKEN_IS_INTENTIONALLY_INVALID_VERILOG"

$negativeResult = Invoke-LoggedNativeCommand `
    -Executable $vivadoExecutable `
    -Arguments @(
        "-mode", "batch",
        "-source", "run_vivado_sync_fifo.tcl"
    ) `
    -WorkingDirectory (Join-Path $negativeDirectory "sim") `
    -LogPath (Join-Path $runDirectory "negative-syntax.log") `
    -AllowFailure

if ($negativeResult.ExitCode -eq 0) {
    throw "Vivado accepted invalid RTL syntax"
}

$summary = [ordered]@{
    status = "PASS"
    run_id = $latestRun.run_id
    vivado_version = $versionBanner
    preflight_exit_code = $preflightResult.ExitCode
    simulation_exit_code = $simulationResult.ExitCode
    negative_syntax_exit_code = $negativeResult.ExitCode
    project = $projectPath
    vcd = $vcdPath
    wdb = @($waveDatabases.FullName)
    manifest = $manifestPath
}
$summary |
    ConvertTo-Json -Depth 5 |
    Out-File -LiteralPath (Join-Path $runDirectory "integration-summary.json") -Encoding utf8

Write-Host "Vivado integration PASS"
Write-Host "Run ID: $($latestRun.run_id)"
Write-Host "Artifacts: $runDirectory"
