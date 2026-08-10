$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$sourceRoot = if ($env:JUNA_N512_NO_HARM_SOURCE_ROOT) {
    $env:JUNA_N512_NO_HARM_SOURCE_ROOT
} else {
    $repo
}
$project = Join-Path $sourceRoot 'JunaCore\experiments\2026-08-08-red-awgn-snr-sweep'
$runner = Join-Path $repo 'JunaCore\bench\run_awgn_n512_crc_no_harm.jl'
$builder = Join-Path $repo 'JunaCore\bench\build_awgn_n512_crc_no_harm.py'
$validator = Join-Path $repo 'JunaCore\bench\validate_awgn_n512_crc_no_harm.py'
$captureSeconds = if ($env:JUNA_N512_NO_HARM_CAPTURE_SECONDS) {
    [int]$env:JUNA_N512_NO_HARM_CAPTURE_SECONDS
} else {
    32
}
$experimentId = "2026-08-10-red-awgn-first${captureSeconds}s-frames32-crc-gated-no-harm-n512-cp64-rate025-p5-5-dc14-kfill-pfft4"
$experiment = Join-Path $repo (Join-Path 'JunaCore\experiments' $experimentId)

$assignments = @(
    @{ Name = 'worker1'; Paths = '1,5,9' },
    @{ Name = 'worker2'; Paths = '2,6,10' },
    @{ Name = 'worker3'; Paths = '3,7,11' },
    @{ Name = 'worker4'; Paths = '4,8,12' }
)

$workers = foreach ($assignment in $assignments) {
    $stdout = Join-Path $experiment ($assignment.Name + '.stdout.log')
    $stderr = Join-Path $experiment ($assignment.Name + '.stderr.log')
    $arguments = @(
        "--project=$project",
        '--threads=1',
        $runner,
        'worker',
        $assignment.Paths,
        $assignment.Name
    )
    $process = Start-Process -FilePath 'julia' -ArgumentList $arguments `
        -WorkingDirectory $repo -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    [pscustomobject]@{
        Name = $assignment.Name
        Process = $process
        Stdout = $stdout
        Stderr = $stderr
        RunLog = Join-Path $experiment ('n512_crc_no_harm_' + $assignment.Name + '.log')
    }
}

Write-Output ("N512_NO_HARM_WORKERS_STARTED " +
    (($workers | ForEach-Object { $_.Name + '=' + $_.Process.Id }) -join ' '))

foreach ($worker in $workers) {
    Wait-Process -Id $worker.Process.Id
    $stderrLength = if (Test-Path $worker.Stderr) {
        (Get-Item -LiteralPath $worker.Stderr).Length
    } else {
        0
    }
    $complete = (Test-Path $worker.RunLog) -and
        [bool](Select-String -LiteralPath $worker.RunLog `
            -Pattern '^N512_CRC_NO_HARM_COMPUTE_COMPLETE ' -Quiet)
    if ($stderrLength -gt 0 -or -not $complete) {
        Write-Output ("N512_NO_HARM_WORKER_FAILED " + $worker.Name)
        if (Test-Path $worker.Stderr) {
            Get-Content -LiteralPath $worker.Stderr -Tail 100
        }
        exit 1
    }
    Write-Output ("N512_NO_HARM_WORKER_COMPLETE " + $worker.Name)
}

& python $builder
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& python $validator
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output 'N512_NO_HARM_BUILD_VALIDATE_COMPLETE'
