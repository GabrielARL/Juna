# Red Direct-C,z rerun

Eleven additional Red additive white Gaussian noise (AWGN) configurations have
complete baseline results but no comparable CRC-gated Direct-C,z result. The
required run has not started, and its output is not retained evidence.

## Aim

We wish to compare eleven additional configurations with the eighteen
configurations used for Table III. We reuse the existing OFDM+LDPC,
Partial-FFT+LDPC, JUNA-Iterative, and JUNA-C,z results. We run only the
CRC-gated JUNA-Direct-C,z receiver with Standard OFDM+LDPC fallback.

The seven existing `direct6` results contain an ungated Direct-C,z arm. Their
frame traces do not contain the Direct candidate CRC result or decoded payload.
Hence the gated result cannot be reconstructed from those retained rows.

## Configurations

Each configuration uses CP 64, code rate 1/4, check degree 14, and four
Partial-FFT parts. We use the first 47 s of each Red capture and seed 4.
Each SNR value from 0 dB to 30 dB uses 32 frames in 2 dB steps.

The entries give N, outer spacing, inner spacing, payload bits per frame,
Partial-FFT bands, and waveform samples:

- `512, 50, 50, 2171, 2, 9280`.
- `1536, 3, 4, 1127, 16, 8896`.
- `1536, 5, 3, 1208, 16, 8896`.
- `1536, 6, 8, 1653, 16, 8896`.
- `512, 5, 7, 1557, 16, 9280`.
- `512, 8, 8, 1716, 16, 9280`.
- `512, 13, 14, 1922, 10, 9280`.
- `1024, 5, 5, 1616, 16, 9536`.
- `1536, 8, 8, 1737, 16, 8896`.
- `1536, 13, 14, 1956, 16, 8896`.
- `4096, 13, 14, 1737, 16, 8256`.

The first four configurations are outside the four Table III pilot-percentage
bands. They may be shown as supplemental BER results, but they do not enter
the present Table III configuration set.

The other seven configurations are inside those bands. Adding them to the
configuration search changes the complete set from eighteen to 25.
That change requires a new selection calculation and new result counts.

## Source gate

For comparison with the retained eighteen configurations, use a clean detached
worktree at commit `99bfd13be42e0cd49506e9eb0bc832d6268462f4`. Require the
following JUNA-Direct-C,z source SHA-256 value:

```text
6004c01aac1d98c685f204ac4b065e91af0d6307940dab9444a0b8014d8e7342
```

The retained Direct-18 runner also checks the helper, project, Red data, and
snapshot schedules. Keep those checks. If the transitive source differs,
the result is a different experiment; rerun the original eighteen Direct-C,z
configurations before combining the two sets.

## Runner preparation

Use the retained Direct-18 harness for a separate campaign with eleven
configurations. Do not overwrite the Direct-18 output. The source
harness contains five files:

- `direct18_sweep.jl`.
- `run_direct18.jl`.
- `direct18_contract.py`.
- `validate_direct18.py`.
- `build_direct18.py`.

On the machine that produced the retained results, the harness is under:

```text
/home/gabiel/Documents/GitHub/Juna-worktrees/crc-no-harm-gradients/JunaCore/experiments/2026-08-14-red-awgn-first47s-frame1s-frames32-direct-cz-table-iii-sweep/
```

Copy the harness into a new dated experiment directory. Replace its eighteen
configuration records with the table above, change its experiment identifier
and expected counts. Retain its source, data, geometry, seed, schedule,
staging, and checks that refuse to overwrite output.

The copied runner must retain four commands:

- `run_direct_extra.jl contract`.
- `run_direct_extra.jl geometry`.
- `run_direct_extra.jl preflight`.
- `run_direct_extra.jl path N OUTER INNER redX H`.

Use the pinned AWGN project, `OPENBLAS_NUM_THREADS=1`, and
`JULIA_NUM_THREADS=2`. Run two disjoint worker queues, with two Julia threads
per worker, on the host with four logical CPUs. Do not run four jobs with four
Julia threads each.

## Required run

Run all twelve Red capture and hydrophone paths for every configuration. Each
path contains sixteen SNR points and 32 frames. The complete workload
is therefore:

```text
11 configurations x 12 paths x 16 SNR values x 32 frames = 67,584 frames
```

The four supplemental configurations require 24,576 frames. Replacing the
seven ungated Direct-C,z arms requires 43,008 frames. Standard decoding still
runs inside JUNA-Direct-C,z because it supplies the CRC gate and fallback.

## Validation and retention

Run the gates in this order:

1. `python3 direct_extra_contract.py`.
2. `julia ... run_direct_extra.jl contract`.
3. `julia ... run_direct_extra.jl geometry`.
4. `julia ... run_direct_extra.jl preflight`.
5. `python3 validate_direct_extra.py preflight`.
6. Run the 132 path commands.
7. `python3 validate_direct_extra.py paths`.
8. `python3 build_direct_extra.py`.
9. `python3 validate_direct_extra.py full`.

For each configuration, require twelve path contracts, 192 aggregate rows,
6144 frame trace rows, and 6144 selection trace rows. Reconcile every aggregate
with its frame rows. Require each selection reason to be
`standard_crc_valid`, `crc_rescue`, or `standard_fallback`.

After validation, retain the aggregate, manifest, frame traces, selection
traces, contracts, runner, and source values through a reviewed evidence
change. A current five-receiver BER plot then uses 960 values per
configuration: twelve paths, sixteen SNR values, and five receivers. The old
`cwz_joint` rows remain outside that plot.

The `experiments/` directory remains scratch space. Numbers become evidence
only after promotion to `tools/`, `reports/`, and a registered test suite.
