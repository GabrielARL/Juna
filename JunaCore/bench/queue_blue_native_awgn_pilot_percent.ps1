$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$sourceRoot = 'C:\Users\Admin\Documents\GitHub\Juna-worktrees\awgn-results'
$dataDir = 'C:\Users\Admin\Documents\GitHub\replaychan\data'
$project = Join-Path $sourceRoot `
    'JunaCore\experiments\2026-08-08-red-awgn-snr-sweep'
$runner = Join-Path $PSScriptRoot 'run_blue_native_awgn_pilot_percent.jl'
$builder = Join-Path $PSScriptRoot `
    'build_blue_native_awgn_direct_cz_extension.py'
$validator = Join-Path $PSScriptRoot `
    'validate_blue_native_awgn_direct_cz_extension.py'
$renderer = Join-Path $PSScriptRoot 'build_blue_native_awgn_view.py'
$spacingByPercent = @{ 10 = 20; 20 = 10; 30 = 7 }
$nfftValues = @(1024, 1536, 4096)
if (-not [string]::IsNullOrWhiteSpace(
        $env:JUNA_BLUE_NATIVE_NFFT_SEQUENCE)) {
    $nfftValues = @($env:JUNA_BLUE_NATIVE_NFFT_SEQUENCE.Split(',') |
        ForEach-Object { [int]$_.Trim() })
}
$allowedNfft = @(512, 1024, 1152, 1200, 1280, 1344, 1408, 1536, 2048, 4096)
$percentValues = @(10, 20, 30)
if (-not [string]::IsNullOrWhiteSpace(
        $env:JUNA_BLUE_NATIVE_PERCENT_SEQUENCE)) {
    $percentValues = @($env:JUNA_BLUE_NATIVE_PERCENT_SEQUENCE.Split(',') |
        ForEach-Object { [int]$_.Trim() })
}
if ($percentValues.Count -eq 0 -or
        @($percentValues | Where-Object { $_ -notin @(10, 20, 30) }).Count -gt 0) {
    throw 'invalid native-Blue percent sequence'
}
if ($nfftValues.Count -eq 0 -or
        @($nfftValues | Where-Object { $_ -notin $allowedNfft }).Count -gt 0 -or
        @($nfftValues | Sort-Object -Unique).Count -ne $nfftValues.Count) {
    throw 'invalid or duplicate native-Blue NFFT sequence'
}

$expected = @{
    'blue_1.mat' = '639830F78EA044B877284DC0058F1C25179BA2448C06F228C9F0A62D0B2162DE'
    'blue_2.mat' = 'A3B7452C6C999777B49E5B4DDB3EF113BA4F40FF2D1504847F6D4BE63E6A4BEE'
    'blue_3.mat' = 'E126E95880513453722B8E9530BD55347FDB1605B76210F99375D1226B4ACF9F'
    'blue_4.mat' = '24EAA514DA13AFF5B5F3F7F8C81EB0FD0DD664EE5EE009B450169C63999C766B'
}
foreach ($name in $expected.Keys) {
    $path = Join-Path $dataDir $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "missing Blue replay capture: $path"
    }
    if ((Get-Item -LiteralPath $path).Length -le 1000000) {
        throw "Blue replay capture is truncated: $path"
    }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($hash -ne $expected[$name]) {
        throw "Blue replay capture hash differs: $name $hash"
    }
}

$activeJulia = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(julia|julialauncher)(\.exe)?$'
})
if ($activeJulia.Count -gt 0) {
    throw "refusing to launch while $($activeJulia.Count) Julia processes are active"
}

$package = Join-Path $repo 'JunaCore'
# CL-280: load JunaCore from the repository, not from the pinned worktree,
# so configurations created here are produced by the same source as the
# nineteen-config campaign. Without this Julia resolves JunaCore from
# $project and silently runs pre-acquisition-fix code.
$env:JULIA_LOAD_PATH = "$package;@;@stdlib"
$env:JUNA_BLUE_DATA_DIR = $dataDir
$assignments = @(
    @{ Name = 'worker1'; Paths = '1,5,9' },
    @{ Name = 'worker2'; Paths = '2,6,10' },
    @{ Name = 'worker3'; Paths = '3,7,11' },
    @{ Name = 'worker4'; Paths = '4,8,12' }
)

foreach ($nfft in $nfftValues) {
    foreach ($requestedPercent in $percentValues) {
        $spacing = [int]$spacingByPercent[$requestedPercent]
        $frameBudget = if ($nfft -eq 4096) { '1.28' } else { '1.0' }
        $env:JUNA_BLUE_NATIVE_NFFT = [string]$nfft
        $env:JUNA_BLUE_NATIVE_REQUESTED_PERCENT = [string]$requestedPercent
        $env:JUNA_BLUE_NATIVE_SPACING = [string]$spacing
        $env:JUNA_BLUE_NATIVE_FRAME_BUDGET = $frameBudget
        Set-Item -Path "Env:JUNA_N${nfft}_NO_HARM_SOURCE_ROOT" `
            -Value $sourceRoot
        Set-Item -Path "Env:JUNA_N${nfft}_NO_HARM_CAPTURE_SECONDS" -Value '47'
        Set-Item -Path "Env:JUNA_N${nfft}_AWGN_RENDERER" -Value $renderer
        $experimentId = "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-n${nfft}-" +
            "d${requestedPercent}-p${spacing}"
        $experiment = Join-Path $repo `
            (Join-Path 'JunaCore\experiments' $experimentId)

        $savedPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & python $validator $experiment 2>$null
        $validationExit = $LASTEXITCODE
        $ErrorActionPreference = $savedPreference
        if ($validationExit -eq 0) {
            Write-Output (
                "BLUE_NATIVE_AWGN_PILOT_ALREADY_VALID N=${nfft} " +
                "requested=${requestedPercent}% P=${spacing}/${spacing}"
            )
            continue
        }

        Write-Output (
            "BLUE_NATIVE_AWGN_PILOT_CONTRACT_START N=${nfft} " +
            "requested=${requestedPercent}% P=${spacing}/${spacing}"
        )
        & julia '--warn-overwrite=no' "--project=$project" '--threads=1' `
            $runner contract
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Output (
            "BLUE_NATIVE_AWGN_PILOT_CONTRACT_COMPLETE N=${nfft} " +
            "requested=${requestedPercent}% P=${spacing}/${spacing}"
        )

        New-Item -ItemType Directory -Force -Path $experiment | Out-Null
        $workers = foreach ($assignment in $assignments) {
            $stdout = Join-Path $experiment ($assignment.Name + '.stdout.log')
            $stderr = Join-Path $experiment ($assignment.Name + '.stderr.log')
            $arguments = @(
                '--warn-overwrite=no', "--project=$project", '--threads=1',
                $runner, 'worker', $assignment.Paths, $assignment.Name
            )
            $process = Start-Process -FilePath 'julia' -ArgumentList $arguments `
                -WorkingDirectory $repo -RedirectStandardOutput $stdout `
                -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
            [pscustomobject]@{
                Name = $assignment.Name
                Process = $process
                Stderr = $stderr
                RunLog = Join-Path $experiment `
                    ("n${nfft}_crc_no_harm_" + $assignment.Name + '.log')
            }
        }
        Write-Output (
            "BLUE_NATIVE_AWGN_PILOT_WORKERS_STARTED N=${nfft} " +
            "requested=${requestedPercent}% " +
            (($workers | ForEach-Object {
                $_.Name + '=' + $_.Process.Id
            }) -join ' ')
        )
        $workers.Process | ForEach-Object {
            Wait-Process -Id $_.Id -ErrorAction SilentlyContinue
        }

        $failed = @()
        foreach ($worker in $workers) {
            $stderrLength = if (Test-Path $worker.Stderr) {
                (Get-Item -LiteralPath $worker.Stderr).Length
            } else { 0 }
            $complete = (Test-Path $worker.RunLog) -and [bool](
                Select-String -LiteralPath $worker.RunLog `
                    -Pattern "^N${nfft}_CRC_NO_HARM_COMPUTE_COMPLETE " -Quiet)
            if ($stderrLength -gt 0 -or -not $complete) {
                Write-Output (
                    "BLUE_NATIVE_AWGN_PILOT_WORKER_FAILED N=${nfft} " +
                    "requested=${requestedPercent}% $($worker.Name)"
                )
                if (Test-Path $worker.Stderr) {
                    Get-Content -LiteralPath $worker.Stderr -Tail 100
                }
                $failed += $worker.Name
            } else {
                Write-Output (
                    "BLUE_NATIVE_AWGN_PILOT_WORKER_COMPLETE N=${nfft} " +
                    "requested=${requestedPercent}% $($worker.Name)"
                )
            }
        }
        if ($failed.Count -gt 0) {
            Write-Output (
                "BLUE_NATIVE_AWGN_PILOT_FAILED N=${nfft} " +
                "requested=${requestedPercent}% workers=$($failed -join ',')"
            )
            exit 1
        }

        & python $builder $experiment
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & python $validator $experiment
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Output (
            "BLUE_NATIVE_AWGN_PILOT_CONFIG_COMPLETE N=${nfft} " +
            "requested=${requestedPercent}% P=${spacing}/${spacing} paths=12"
        )
    }
}

$configurationCount = $nfftValues.Count * $spacingByPercent.Count
$pathCount = $configurationCount * 12
Write-Output (
    "BLUE_NATIVE_AWGN_DIRECT_CZ_MATRIX_COMPLETE " +
    "configurations=${configurationCount} paths=${pathCount}"
)
