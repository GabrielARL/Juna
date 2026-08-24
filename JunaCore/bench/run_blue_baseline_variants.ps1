# Create and gate 6/8 baseline variants (cyclic prefix, budget, seed) that the
# density creation queue cannot make. One JSON config list via
# JUNA_BLUE_BASELINE_CONFIGS: [{"n":1024,"cp":352,"seed":4,"budget":1.0,"label":"C5"}].
# Each config is independent; a failure records and the batch continues.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$package = Join-Path $repo 'JunaCore'
$sourceRoot = 'C:\Users\Admin\Documents\GitHub\Juna-worktrees\awgn-results'
$dataDir = 'C:\Users\Admin\Documents\GitHub\replaychan\data'
$project = Join-Path $sourceRoot 'JunaCore\experiments\2026-08-08-red-awgn-snr-sweep'
$matrixRunner = Join-Path $PSScriptRoot 'run_blue_native_awgn_matrix_crc_no_harm.jl'
$n1536Runner = Join-Path $PSScriptRoot 'run_blue_native_awgn_n1536_p6_8_crc_no_harm.jl'
$builder = Join-Path $PSScriptRoot 'build_blue_native_awgn_direct_cz_extension.py'
$validator = Join-Path $PSScriptRoot 'validate_blue_native_awgn_direct_cz_extension.py'
$renderer = Join-Path $PSScriptRoot 'build_blue_native_awgn_view.py'
$gate = Join-Path $PSScriptRoot 'gate_blue_12paths.py'
$seeder = Join-Path $PSScriptRoot 'seed_blue_manifest.py'
$env:JULIA_LOAD_PATH = "$package;@;@stdlib"
$env:JUNA_BLUE_DATA_DIR = $dataDir
$commit = (& git -C $repo rev-parse HEAD).Trim()
$configs = $env:JUNA_BLUE_BASELINE_CONFIGS | ConvertFrom-Json
$assignments = @(
    @{ Name = 'worker1'; Paths = '1,5,9' }, @{ Name = 'worker2'; Paths = '2,6,10' },
    @{ Name = 'worker3'; Paths = '3,7,11' }, @{ Name = 'worker4'; Paths = '4,8,12' }
)
foreach ($c in $configs) {
    $nfft = [int]$c.n; $cp = [int]$c.cp; $seed = [int]$c.seed; $budget = [double]$c.budget
    $runner = if ($nfft -eq 1536) { $n1536Runner } else { $matrixRunner }
    $sfx = ''
    if ($seed -ne 4) { $sfx += "-s$seed" }
    if ($budget -ne 1.0) { $sfx += '-b' + ([string]$budget).Replace('.', 'p') }
    $id = "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-n${nfft}-cp${cp}-r025-p6-8-dc14-kfill-pfft4${sfx}"
    $experiment = Join-Path $repo (Join-Path 'JunaCore\experiments' $id)
    Write-Output "BASELINE_START label=$($c.label) id=$id"
    $env:JUNA_BLUE_NATIVE_NFFT = [string]$nfft
    $env:JUNA_BLUE_DIRECT_CZ_MODE = 'baseline'
    $env:JUNA_BLUE_NATIVE_OUTER_SPACING = '6'
    $env:JUNA_BLUE_NATIVE_INNER_SPACING = '8'
    $env:JUNA_BLUE_NATIVE_CP = [string]$cp
    $env:JUNA_BLUE_NATIVE_SEED = [string]$seed
    $env:JUNA_BLUE_NATIVE_FRAME_BUDGET = [string]$budget
    Set-Item -Path "Env:JUNA_N${nfft}_NO_HARM_SOURCE_ROOT" -Value $sourceRoot
    Set-Item -Path "Env:JUNA_N${nfft}_NO_HARM_CAPTURE_SECONDS" -Value '47'
    Set-Item -Path "Env:JUNA_N${nfft}_AWGN_RENDERER" -Value $renderer
    try {
        & julia '--warn-overwrite=no' "--project=$project" '--threads=1' $runner contract
        if ($LASTEXITCODE -ne 0) { Write-Output "BASELINE_SKIP label=$($c.label) reason=contract_exit_$LASTEXITCODE"; continue }
        New-Item -ItemType Directory -Force -Path $experiment | Out-Null
        $workers = foreach ($a in $assignments) {
            $so = Join-Path $experiment ($a.Name + '.stdout.log'); $se = Join-Path $experiment ($a.Name + '.stderr.log')
            $pr = Start-Process -FilePath 'julia' -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput $so -RedirectStandardError $se `
                -ArgumentList @('--warn-overwrite=no', "--project=$project", '--threads=1', $runner, 'worker', $a.Paths, $a.Name)
            [pscustomobject]@{ Name = $a.Name; Process = $pr; Stderr = $se; RunLog = Join-Path $experiment ("n${nfft}_crc_no_harm_" + $a.Name + '.log') }
        }
        $workers.Process | ForEach-Object { Wait-Process -Id $_.Id -ErrorAction SilentlyContinue }
        $failed = @()
        foreach ($w in $workers) {
            $len = if (Test-Path $w.Stderr) { (Get-Item -LiteralPath $w.Stderr).Length } else { 0 }
            $ok = (Test-Path $w.RunLog) -and [bool](Select-String -LiteralPath $w.RunLog -Pattern "^N${nfft}_CRC_NO_HARM_COMPUTE_COMPLETE " -Quiet)
            if ($len -gt 0 -or -not $ok) { $failed += $w.Name; if (Test-Path $w.Stderr) { Get-Content -LiteralPath $w.Stderr -Tail 40 } }
        }
        if ($failed.Count -gt 0) { Write-Output "BASELINE_SKIP label=$($c.label) reason=workers_failed:$($failed -join ',')"; continue }
        & python $seeder "$repo\JunaCore\experiments\2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-n1024-cp64-r025-p6-8-dc14-kfill-pfft4" $experiment $nfft ([int]$c.payload) ([int]$c.samples) $cp $seed
        if ($LASTEXITCODE -ne 0) { Write-Output "BASELINE_SKIP label=$($c.label) reason=seed_exit_$LASTEXITCODE"; continue }
        & python $builder $experiment
        if ($LASTEXITCODE -ne 0) { Write-Output "BASELINE_SKIP label=$($c.label) reason=build_exit_$LASTEXITCODE"; continue }
        & python $validator $experiment
        if ($LASTEXITCODE -ne 0) { Write-Output "BASELINE_SKIP label=$($c.label) reason=validate_exit_$LASTEXITCODE"; continue }
        & python $gate $experiment $commit
        Write-Output "BASELINE_DONE label=$($c.label) id=$id"
    } catch {
        Write-Output "BASELINE_SKIP label=$($c.label) reason=exception:$($_.Exception.Message)"
    }
}
Write-Output 'BASELINE_BATCH_COMPLETE'
