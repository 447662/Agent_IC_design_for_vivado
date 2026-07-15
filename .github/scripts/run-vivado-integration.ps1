[CmdletBinding()]
param(
    [string]$ArtifactsRoot = (Join-Path $PWD ".tmp\vivado-integration"),
    [string]$VivadoPath = $env:VIVADO_EXECUTABLE
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

function Assert-CanonicalVerdict {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectDirectory,

        [Parameter(Mandatory = $true)]
        [object]$LatestRun,

        [Parameter(Mandatory = $true)]
        [datetime]$StartedAt
    )

    $verdictPath = Join-Path $ProjectDirectory "reports\verification_verdict.json"
    Assert-FreshFile -Path $verdictPath -StartedAt $StartedAt
    $verdict = Get-Content -LiteralPath $verdictPath -Raw -Encoding utf8 |
        ConvertFrom-Json
    if ($verdict.status -ne "PASS" -or $verdict.passed -ne $true) {
        throw "Canonical verification verdict is not PASS: $verdictPath"
    }
    if ($LatestRun.PSObject.Properties.Name -notcontains "verification_verdict") {
        throw "Runtime manifest does not embed the canonical verification verdict"
    }
    if ($LatestRun.status -ne $verdict.status) {
        throw "Runtime manifest status disagrees with canonical verification verdict"
    }
    $embeddedVerdict = $LatestRun.verification_verdict
    $embeddedJson = $embeddedVerdict | ConvertTo-Json -Depth 20 -Compress
    $verdictJson = $verdict | ConvertTo-Json -Depth 20 -Compress
    if ($embeddedJson -ne $verdictJson) {
        throw "Runtime manifest embeds a different canonical verification verdict"
    }

    return $verdict
}

function Assert-RuntimeManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedFlow,

        [Parameter(Mandatory = $true)]
        [string[]]$ManifestCurrentArtifactPaths
    )

    Assert-FreshFile -Path $ManifestPath -StartedAt $script:GateStartedAt
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding utf8 |
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
    if ($latestRun.flow -ne $ExpectedFlow) {
        throw "Latest runtime manifest flow is not $ExpectedFlow"
    }

    $artifactByPath = @{}
    foreach ($artifact in @($latestRun.artifacts)) {
        if ($artifact.path) {
            $artifactByPath[$artifact.path] = $artifact
        }
    }
    foreach ($relativePath in $ManifestCurrentArtifactPaths) {
        $manifestPath = $relativePath.Replace("\", "/")
        if (-not $artifactByPath.ContainsKey($manifestPath)) {
            throw "Runtime manifest does not list required artifact: $manifestPath"
        }
        $artifact = $artifactByPath[$manifestPath]
        if ($artifact.status -ne "CURRENT") {
            throw "Runtime manifest artifact is not CURRENT: $manifestPath"
        }
        if (-not $artifact.produced_by_run_id) {
            throw "Runtime manifest artifact has no produced_by_run_id: $manifestPath"
        }
    }

    return $latestRun
}

function Resolve-VivadoExecutable {
    param(
        [string]$RequestedPath
    )

    $candidatePath = $RequestedPath
    if ([string]::IsNullOrWhiteSpace($candidatePath)) {
        $vivadoCommand = Get-Command vivado -ErrorAction Stop
        $candidatePath = if ($vivadoCommand.Source) {
            $vivadoCommand.Source
        }
        else {
            $vivadoCommand.Path
        }
    }

    $resolvedPath = (Resolve-Path -LiteralPath $candidatePath -ErrorAction Stop).Path
    $pathParts = @($resolvedPath -split '[\\/]')
    $isUnwrappedExecutable = (
        (Split-Path -Leaf $resolvedPath) -ieq "vivado.exe" -and
        $pathParts -icontains "unwrapped"
    )
    if (-not $isUnwrappedExecutable) {
        return $resolvedPath
    }

    $currentDirectory = Split-Path -Parent $resolvedPath
    while ($currentDirectory) {
        $wrapperCandidate = Join-Path $currentDirectory "vivado.bat"
        if (Test-Path -LiteralPath $wrapperCandidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $wrapperCandidate).Path
        }
        $parentDirectory = Split-Path -Parent $currentDirectory
        if ($parentDirectory -eq $currentDirectory) {
            break
        }
        $currentDirectory = $parentDirectory
    }

    return $resolvedPath
}

function Get-VivadoRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$VivadoExecutable
    )

    $executableDirectory = Split-Path -Parent $VivadoExecutable
    if ((Split-Path -Leaf $executableDirectory) -ieq "bin") {
        return Split-Path -Parent $executableDirectory
    }

    return Split-Path (Split-Path $executableDirectory -Parent) -Parent
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$uvCommand = Get-Command uv -ErrorAction Stop
$vivadoExecutable = Resolve-VivadoExecutable -RequestedPath $VivadoPath
$env:DIGITAL_IC_AGENT_VIVADO = $vivadoExecutable
$uvExecutable = if ($uvCommand.Source) {
    $uvCommand.Source
}
else {
    $uvCommand.Path
}
if ([string]::IsNullOrWhiteSpace($env:UV_CACHE_DIR)) {
    $env:UV_CACHE_DIR = Join-Path $repositoryRoot ".tmp\uv-cache"
}

$vivadoRoot = Get-VivadoRoot -VivadoExecutable $vivadoExecutable
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

$agentPath = Join-Path $repositoryRoot ".trae\agent\agent.py"
$targetGates = @(
    [pscustomobject]@{
        Target = "sync-fifo"
        Rtl = "rtl\sync_fifo.v"
        SimulationScript = "run_vivado_sync_fifo.tcl"
        Flows = @(
            [pscustomobject]@{
                Name = "sim-rtl"
                CliFlag = "--sim-rtl"
                LogName = "sync-fifo-sim-rtl-agent.log"
                RequiredArtifacts = @(
                    "rtl\sync_fifo.v",
                    "tb\tb_sync_fifo.v",
                    "sim\sync_fifo_trace.vcd",
                    "vivado_project\sync_fifo_project.xpr",
                    "reports\sim_report.md",
                    "sim\sync_fifo_smoke.wdb"
                )
                ManifestCurrentArtifacts = @(
                    "rtl\sync_fifo.v",
                    "tb\tb_sync_fifo.v",
                    "sim\sync_fifo_trace.vcd",
                    "vivado_project\sync_fifo_project.xpr",
                    "reports\sim_report.md",
                    "sim\sync_fifo_smoke.wdb"
                )
                Markers = @("SYNC_FIFO_SCOREBOARD_PASS")
            }
        )
    },
    [pscustomobject]@{
        Target = "async-fifo"
        Rtl = "rtl\async_fifo.v"
        SimulationScript = "run_vivado_async_fifo.tcl"
        Flows = @(
            [pscustomobject]@{
                Name = "sim-rtl"
                CliFlag = "--sim-rtl"
                LogName = "async-fifo-sim-rtl-agent.log"
                RequiredArtifacts = @(
                    "rtl\async_fifo.v",
                    "tb\tb_async_fifo.v",
                    "sim\async_fifo_trace.vcd",
                    "vivado_project\async_fifo_project.xpr",
                    "reports\sim_report.md",
                    "sim\async_fifo_smoke.wdb"
                )
                ManifestCurrentArtifacts = @(
                    "rtl\async_fifo.v",
                    "tb\tb_async_fifo.v",
                    "sim\async_fifo_trace.vcd",
                    "vivado_project\async_fifo_project.xpr",
                    "reports\sim_report.md",
                    "sim\async_fifo_smoke.wdb"
                )
                Markers = @("ASYNC_FIFO_SCOREBOARD_PASS")
            },
            [pscustomobject]@{
                Name = "uvm-smoke"
                CliFlag = "--uvm-smoke"
                LogName = "async-fifo-uvm-smoke-agent.log"
                RequiredArtifacts = @(
                    "rtl\async_fifo.v",
                    "sim\async_fifo_uvm_smoke.wdb",
                    "reports\uvm_smoke_report.md"
                )
                ManifestCurrentArtifacts = @(
                    "sim\async_fifo_uvm_smoke.wdb",
                    "reports\uvm_smoke_report.md"
                )
                Markers = @(
                    "ASYNC_FIFO_UVM_SCOREBOARD_PASS",
                    "ASYNC_FIFO_UVM_TEST_DONE"
                )
            },
            [pscustomobject]@{
                Name = "uvm-coverage"
                CliFlag = "--uvm-coverage"
                LogName = "async-fifo-uvm-coverage-agent.log"
                RequiredArtifacts = @(
                    "rtl\async_fifo.v",
                    "sim\async_fifo_uvm_coverage.wdb",
                    "reports\uvm_coverage_summary.md"
                )
                ManifestCurrentArtifacts = @(
                    "sim\async_fifo_uvm_coverage.wdb",
                    "reports\uvm_coverage_summary.md"
                )
                Markers = @(
                    "ASYNC_FIFO_UVM_SCOREBOARD_PASS",
                    "ASYNC_FIFO_UVM_TEST_DONE"
                )
            }
        )
    },
    [pscustomobject]@{
        Target = "round-robin-arbiter"
        Rtl = "rtl\round_robin_arbiter.v"
        SimulationScript = "run_vivado_round_robin_arbiter.tcl"
        Flows = @(
            [pscustomobject]@{
                Name = "sim-rtl"
                CliFlag = "--sim-rtl"
                LogName = "round-robin-arbiter-sim-rtl-agent.log"
                RequiredArtifacts = @(
                    "rtl\round_robin_arbiter.v",
                    "tb\tb_round_robin_arbiter.v",
                    "sim\round_robin_arbiter_trace.vcd",
                    "vivado_project\round_robin_arbiter_project.xpr",
                    "reports\sim_report.md",
                    "sim\round_robin_arbiter_smoke.wdb"
                )
                ManifestCurrentArtifacts = @(
                    "rtl\round_robin_arbiter.v",
                    "tb\tb_round_robin_arbiter.v",
                    "sim\round_robin_arbiter_trace.vcd",
                    "vivado_project\round_robin_arbiter_project.xpr",
                    "reports\sim_report.md",
                    "sim\round_robin_arbiter_smoke.wdb"
                )
                Markers = @("ROUND_ROBIN_ARBITER_SCOREBOARD_PASS")
            }
        )
    }
)

$gateSummaries = @()
foreach ($targetGate in $targetGates) {
    $projectDirectory = Join-Path $runDirectory $targetGate.Target
    foreach ($flowGate in $targetGate.Flows) {
        $script:GateStartedAt = Get-Date
        $flowResult = Invoke-LoggedNativeCommand `
            -Executable $uvExecutable `
            -Arguments @(
                "run", "--frozen", "python", "-B", $agentPath,
                $flowGate.CliFlag, $targetGate.Target,
                "--no-wave-gui",
                "--output-dir", $runDirectory
            ) `
            -WorkingDirectory $repositoryRoot `
            -LogPath (Join-Path $runDirectory $flowGate.LogName)

        foreach ($relativePath in $flowGate.RequiredArtifacts) {
            Assert-FreshFile `
                -Path (Join-Path $projectDirectory $relativePath) `
                -StartedAt $script:GateStartedAt
        }
        $requiredWaveDatabases = @(
            $flowGate.RequiredArtifacts |
                Where-Object { $_ -like "*.wdb" }
        )
        if ($requiredWaveDatabases.Count -eq 0) {
            throw "Flow does not declare a required WDB artifact: $($targetGate.Target) $($flowGate.Name)"
        }
        foreach ($requiredWaveDatabase in $requiredWaveDatabases) {
            Assert-FreshFile `
                -Path (Join-Path $projectDirectory $requiredWaveDatabase) `
                -StartedAt $script:GateStartedAt
        }

        $latestRun = Assert-RuntimeManifest `
            -ManifestPath (Join-Path $projectDirectory "artifacts.json") `
            -ExpectedFlow $flowGate.Name `
            -ManifestCurrentArtifactPaths $flowGate.ManifestCurrentArtifacts
        $canonicalVerdict = Assert-CanonicalVerdict `
            -ProjectDirectory $projectDirectory `
            -LatestRun $latestRun `
            -StartedAt $script:GateStartedAt

        $gateSummaries += [ordered]@{
            target = $targetGate.Target
            flow = $flowGate.Name
            run_id = $latestRun.run_id
            exit_code = $flowResult.ExitCode
            required_artifacts = $flowGate.RequiredArtifacts
            manifest_current_artifacts = $flowGate.ManifestCurrentArtifacts
            canonical_verdict = $canonicalVerdict
        }
    }
}

$negativeSummaries = @()
foreach ($negativeGate in $targetGates) {
    $sourceProjectDirectory = Join-Path $runDirectory $negativeGate.Target
    $negativeDirectory = Join-Path $runDirectory ("negative-syntax-" + $negativeGate.Target)
    Copy-Item -LiteralPath $sourceProjectDirectory -Destination $negativeDirectory -Recurse
    $negativeRtlPath = Join-Path $negativeDirectory $negativeGate.Rtl
    Add-Content `
        -LiteralPath $negativeRtlPath `
        -Value "`nTHIS_TOKEN_IS_INTENTIONALLY_INVALID_VERILOG"

    $negativeResult = Invoke-LoggedNativeCommand `
        -Executable $vivadoExecutable `
        -Arguments @(
            "-mode", "batch",
            "-source", $negativeGate.SimulationScript
        ) `
        -WorkingDirectory (Join-Path $negativeDirectory "sim") `
        -LogPath (Join-Path $runDirectory ("negative-syntax-" + $negativeGate.Target + ".log")) `
        -AllowFailure

    if ($negativeResult.ExitCode -eq 0) {
        throw "Vivado accepted invalid RTL syntax for $($negativeGate.Target)"
    }

    $negativeSummaries += [ordered]@{
        target = $negativeGate.Target
        script = $negativeGate.SimulationScript
        exit_code = $negativeResult.ExitCode
    }
}

$summary = [ordered]@{
    status = "PASS"
    vivado_version = $versionBanner
    preflight_exit_code = $preflightResult.ExitCode
    matrix = $gateSummaries
    negative_syntax = $negativeSummaries
}
$summary |
    ConvertTo-Json -Depth 5 |
    Out-File -LiteralPath (Join-Path $runDirectory "integration-summary.json") -Encoding utf8

Write-Host "Vivado integration PASS"
Write-Host "Targets: $($targetGates.Target -join ', ')"
Write-Host "Artifacts: $runDirectory"
