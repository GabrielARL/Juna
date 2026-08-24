param(
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$package = Join-Path $repo 'JunaCore'
$sourceRoot = 'C:\Users\Admin\Documents\GitHub\Juna-worktrees\awgn-results'
$dataDir = 'C:\Users\Admin\Documents\GitHub\replaychan\data'
$project = Join-Path $sourceRoot `
    'JunaCore\experiments\2026-08-08-red-awgn-snr-sweep'
$densityRunner = Join-Path $PSScriptRoot `
    'run_blue_native_awgn_pilot_percent.jl'
$baselineRunner = Join-Path $PSScriptRoot `
    'run_blue_native_awgn_matrix_crc_no_harm.jl'
$baseline1536Runner = Join-Path $PSScriptRoot `
    'run_blue_native_awgn_n1536_p6_8_crc_no_harm.jl'
$builder = Join-Path $PSScriptRoot `
    'build_blue_native_awgn_direct_cz_extension.py'
$validator = Join-Path $PSScriptRoot `
    'validate_blue_native_awgn_direct_cz_extension.py'
$cfoValidator = Join-Path $PSScriptRoot `
    'validate_blue1_refresh.py'
$renderer = Join-Path $PSScriptRoot 'build_blue_native_awgn_view.py'

foreach ($required in @(
        $project, $densityRunner, $baselineRunner, $baseline1536Runner,
        $builder, $validator, $cfoValidator, $renderer)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "required CFO-fix queue input is missing: $required"
    }
}

$expectedCaptures = @{
    'blue_1.mat' = '639830F78EA044B877284DC0058F1C25179BA2448C06F228C9F0A62D0B2162DE'
    'blue_2.mat' = 'A3B7452C6C999777B49E5B4DDB3EF113BA4F40FF2D1504847F6D4BE63E6A4BEE'
    'blue_3.mat' = 'E126E95880513453722B8E9530BD55347FDB1605B76210F99375D1226B4ACF9F'
    'blue_4.mat' = '24EAA514DA13AFF5B5F3F7F8C81EB0FD0DD664EE5EE009B450169C63999C766B'
}
foreach ($name in $expectedCaptures.Keys) {
    $path = Join-Path $dataDir $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "missing Blue replay capture: $path"
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash -ne
            $expectedCaptures[$name]) {
        throw "Blue replay capture hash differs: $name"
    }
}

$activeJulia = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(julia|julialauncher)(\.exe)?$'
})
if ($activeJulia.Count -gt 0) {
    throw "refusing to launch while $($activeJulia.Count) Julia processes are active"
}

$sourceCommit = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$markerTag = $sourceCommit.Substring(0, 12)
$env:JULIA_LOAD_PATH = "$package;@;@stdlib"
$env:JULIA_NUM_THREADS = '1'
$env:JUNA_BLUE_DATA_DIR = $dataDir
$env:PYTHONUTF8 = '1'

$configs = @()
foreach ($nfft in @(512, 1024, 1536, 2048)) {
    $configs += [pscustomobject]@{
        Mode = 'baseline'; N = $nfft; Percent = 0; Spacing = 0
        Budget = '1.0'
        Id = "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-" +
             "n${nfft}-cp64-r025-p6-8-dc14-kfill-pfft4"
        Runner = if ($nfft -eq 1536) { $baseline1536Runner } else { $baselineRunner }
    }
    foreach ($percent in @(10, 20, 30)) {
        $spacing = @{ 10 = 20; 20 = 10; 30 = 7 }[$percent]
        $configs += [pscustomobject]@{
            Mode = 'density'; N = $nfft; Percent = $percent
            Spacing = $spacing; Budget = '1.0'
            Id = "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-" +
                 "n${nfft}-d${percent}-p${spacing}"
            Runner = $densityRunner
        }
    }
}
foreach ($percent in @(10, 20, 30)) {
    $spacing = @{ 10 = 20; 20 = 10; 30 = 7 }[$percent]
    $configs += [pscustomobject]@{
        Mode = 'density'; N = 4096; Percent = $percent
        Spacing = $spacing; Budget = '1.28'
        Id = "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-" +
             "n4096-d${percent}-p${spacing}"
        Runner = $densityRunner
    }
}
$configs = @($configs | Where-Object { $_.N -eq 1024 })
if ($configs.Count -ne 4 -or
        @($configs.Id | Sort-Object -Unique).Count -ne 4) {
    throw 'Blue1 refresh target set is not exactly 4 unique configurations'
}

$assignments = @(
    [pscustomobject]@{ Name = 'blue1_worker1'; Paths = '1'; Count = 1 },
    [pscustomobject]@{ Name = 'blue1_worker2'; Paths = '2'; Count = 1 },
    [pscustomobject]@{ Name = 'blue1_worker3'; Paths = '3'; Count = 1 }
)

function Set-ConfigEnvironment($config) {
    $nfft = $config.N
    $env:JUNA_BLUE_NATIVE_NFFT = [string]$nfft
    $env:JUNA_BLUE_NATIVE_FRAME_BUDGET = $config.Budget
    $env:JUNA_BLUE_DIRECT_CZ_MODE = $config.Mode
    Set-Item -Path "Env:JUNA_N${nfft}_NO_HARM_SOURCE_ROOT" -Value $sourceRoot
    Set-Item -Path "Env:JUNA_N${nfft}_NO_HARM_CAPTURE_SECONDS" -Value '47'
    Set-Item -Path "Env:JUNA_N${nfft}_AWGN_RENDERER" -Value $renderer
    if ($config.Mode -eq 'density') {
        $env:JUNA_BLUE_NATIVE_REQUESTED_PERCENT = [string]$config.Percent
        $env:JUNA_BLUE_NATIVE_SPACING = [string]$config.Spacing
        Remove-Item Env:JUNA_BLUE_NATIVE_OUTER_SPACING -ErrorAction SilentlyContinue
        Remove-Item Env:JUNA_BLUE_NATIVE_INNER_SPACING -ErrorAction SilentlyContinue
    } else {
        $env:JUNA_BLUE_NATIVE_OUTER_SPACING = '6'
        $env:JUNA_BLUE_NATIVE_INNER_SPACING = '8'
    }
}

if ($PreflightOnly) {
    $index = 0
    foreach ($config in $configs) {
        Set-ConfigEnvironment $config
        $experiment = Join-Path $package `
            (Join-Path 'experiments' $config.Id)
        & python $validator $experiment
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $index++
        Write-Output (
            "BLUE1_REFRESH_PREFLIGHT_CONFIG index=$index/4 " +
            "id=$($config.Id)"
        )
    }
    Write-Output (
        'BLUE1_REFRESH_PREFLIGHT_COMPLETE configurations=4 ' +
        'refresh_paths=12 preserved_blue234_paths=36'
    )
    exit 0
}

Write-Output (
    "BLUE1_REFRESH_QUEUE_START pid=$PID commit=$sourceCommit " +
    'configurations=4 refresh_paths=12 preserved_blue234_paths=36'
)

$completed = 0
foreach ($config in $configs) {
    Set-ConfigEnvironment $config
    $nfft = $config.N
    $experiment = Join-Path $package (Join-Path 'experiments' $config.Id)
    if (-not (Test-Path -LiteralPath $experiment -PathType Container)) {
        throw "missing existing Blue experiment: $experiment"
    }
    $short = if ($config.Mode -eq 'density') {
        "n${nfft}_d$($config.Percent)_p$($config.Spacing)"
    } else { "n${nfft}_baseline_p6_8" }
    $markerStem = "blue1refresh_${markerTag}_${short}"
    $startedMarker = Join-Path $PSScriptRoot `
        ($markerStem + '.started.json')
    $completeMarker = Join-Path $PSScriptRoot `
        ($markerStem + '.complete.json')
    $preservedSnapshot = Join-Path $PSScriptRoot `
        ($markerStem + '.blue1.json')

    if (Test-Path -LiteralPath $completeMarker -PathType Leaf) {
        & python $cfoValidator check $experiment $sourceCommit
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $completed++
        Write-Output "BLUE1_REFRESH_CONFIG_ALREADY_COMPLETE index=$completed id=$($config.Id)"
        continue
    }

    if (-not (Test-Path -LiteralPath $startedMarker -PathType Leaf)) {
        & python $validator $experiment
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        [pscustomobject]@{
            experiment_id = $config.Id
            source_commit = $sourceCommit
            started_utc = [DateTimeOffset]::UtcNow.ToString('o')
        } | ConvertTo-Json | Set-Content -LiteralPath $startedMarker `
            -Encoding utf8
    }

    & python $cfoValidator snapshot $experiment $preservedSnapshot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $startedMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

    Write-Output (
        "BLUE1_REFRESH_CONTRACT_START index=$($completed + 1)/4 " +
        "mode=$($config.Mode) N=$nfft percent=$($config.Percent) " +
        "spacing=$($config.Spacing)"
    )
    & julia '--warn-overwrite=no' "--project=$project" '--threads=1' `
        $config.Runner contract
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output "BLUE1_REFRESH_CONTRACT_COMPLETE id=$($config.Id)"

    foreach ($channel in 1..1) {
        foreach ($lane in 1..3) {
            $stem = "blue${channel}_hydrophone${lane}"
            $contract = Join-Path $experiment `
                "results\runs\$stem\n${nfft}_crc_no_harm_path_contract.txt"
            if (Test-Path -LiteralPath $contract -PathType Leaf) {
                Remove-Item -LiteralPath $contract
            }
        }
    }

    $workers = foreach ($assignment in $assignments) {
        $stdout = Join-Path $experiment ($assignment.Name + '.stdout.log')
        $stderr = Join-Path $experiment ($assignment.Name + '.stderr.log')
        $runLog = Join-Path $experiment `
            ("n${nfft}_crc_no_harm_" + $assignment.Name + '.log')
        foreach ($old in @($stdout, $stderr, $runLog)) {
            if (Test-Path -LiteralPath $old -PathType Leaf) {
                Remove-Item -LiteralPath $old
            }
        }
        $arguments = @(
            '--warn-overwrite=no', "--project=$project", '--threads=1',
            $config.Runner, 'worker', $assignment.Paths, $assignment.Name
        )
        $process = Start-Process -FilePath 'julia' -ArgumentList $arguments `
            -WorkingDirectory $repo -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
        [pscustomobject]@{
            Assignment = $assignment
            Process = $process
            Stdout = $stdout
            Stderr = $stderr
            RunLog = $runLog
        }
    }
    Write-Output (
        "BLUE1_REFRESH_WORKERS_STARTED id=$($config.Id) " +
        (($workers | ForEach-Object {
            $_.Assignment.Name + '=' + $_.Process.Id
        }) -join ' ')
    )
    $workers.Process | ForEach-Object {
        Wait-Process -Id $_.Id -ErrorAction SilentlyContinue
    }

    $failed = @()
    foreach ($worker in $workers) {
        $stderrLength = if (Test-Path -LiteralPath $worker.Stderr) {
            (Get-Item -LiteralPath $worker.Stderr).Length
        } else { 0 }
        $pattern = "^N${nfft}_CRC_NO_HARM_COMPUTE_COMPLETE " +
            "paths=$($worker.Assignment.Count)(?: |$)"
        $done = (Test-Path -LiteralPath $worker.RunLog) -and [bool](
            Select-String -LiteralPath $worker.RunLog -Pattern $pattern -Quiet)
        if ($stderrLength -gt 0 -or -not $done) {
            $failed += $worker.Assignment.Name
            Write-Output (
                "BLUE1_REFRESH_WORKER_FAILED id=$($config.Id) " +
                "worker=$($worker.Assignment.Name) stderr_bytes=$stderrLength"
            )
            if (Test-Path -LiteralPath $worker.Stderr) {
                Get-Content -LiteralPath $worker.Stderr -Tail 100
            }
        } else {
            Write-Output (
                "BLUE1_REFRESH_WORKER_COMPLETE id=$($config.Id) " +
                "worker=$($worker.Assignment.Name) paths=$($worker.Assignment.Count)"
            )
        }
    }
    if ($failed.Count -gt 0) {
        throw "CFO-fix workers failed: $($failed -join ',')"
    }

    & python $builder $experiment
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & python $validator $experiment
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & python $cfoValidator finalize $experiment $preservedSnapshot `
        ([string]$startedMs) $sourceCommit
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    [pscustomobject]@{
        experiment_id = $config.Id
        source_commit = $sourceCommit
        completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
        refresh_paths = 3
    } | ConvertTo-Json | Set-Content -LiteralPath $completeMarker `
        -Encoding utf8
    $completed++
    Write-Output (
        "BLUE1_REFRESH_CONFIG_COMPLETE index=$completed/4 " +
        "id=$($config.Id) refresh_paths=3"
    )
}

Write-Output (
    'BLUE1_REFRESH_MATRIX_COMPLETE configurations=4 refresh_paths=12 ' +
    "preserved_blue234_paths=36 commit=$sourceCommit"
)
