# JunaCore (JUNA-Lite migration)

Standalone home of the **JUNA-Lite** underwater-acoustic OFDM/LDPC receiver and
the two paper baselines it is measured against.

Migrated from `sonique/research/JunaCore` @ `d49fff0127732af4fad3862628fd93a96e2e75e9`
(branch `juna-dev`). The algorithm files `src/juna/common.jl` and
`src/juna/lite.jl`, the modem interface, the LDPC wrapper, and the `tools/ldpc`
helper binaries are byte-identical to that commit; only the wrappers
(`src/JunaCore.jl`, `src/Juna.jl`) and `Project.toml` are pruned.

## Public facades

| Facade | Receiver |
|---|---|
| `JunaCore.JunaStandard.Modulation` | one-tap pilot-interpolated equalization + FEC |
| `JunaCore.JunaPartialFFT.Modulation` | pilot-trained per-band partial-FFT combining + FEC |
| `JunaCore.JunaLite.Modulation` | Partial-FFT seed → posterior-anchor ridge refit of the combiner W (`refinement_objective = :posterior_anchor_ls`) |

The other receiver variants of the source repository (Fully Coupled, Turbo MAP,
Profiled Gradient, frame-wide C,z, FrameRLS, …) are deliberately absent: their
implementation files are not migrated, so no facade may expose them.

## Usage

```julia
using JunaCore
const Modulations = JunaCore.Modulations

m = JunaCore.JunaLite.Modulation()
bits = rand(Bool, Modulations.bitspersymbol(m))
x = Modulations.modulate(m, bits, 24_000.0, 24_000.0)
metrics, cfo = Modulations.demodulate(m, length(bits), x, 24_000.0, 24_000.0)
decoded = metrics .> 0
```

`LDPC.build` shells out to Radford Neal's LDPC tools in `tools/ldpc`
(see `THIRD_PARTY_NOTICES.md`); codes are cached under `tempdir()`.

## Tests

```bash
julia --project=. test/phase1_smoke.jl   # clean-channel roundtrip, all facades
```

The behavioral suites (Lite refinement, feedback-mode arms, partial-FFT seed,
iteration sweeps) migrate in phase 2 and will be wired into `Pkg.test()` with a
keyed suite registry. Phase 3 adds the chain-centric explorer on port 8772.
