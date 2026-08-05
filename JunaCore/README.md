# JunaCore (JUNA-Lite migration)

Standalone home of the **JUNA-Lite** underwater-acoustic OFDM/LDPC receiver and
the two paper baselines it is measured against.

Migrated from `sonique/research/JunaCore` @ `d49fff0127732af4fad3862628fd93a96e2e75e9`
(branch `juna-dev`). This records where the migration began. Juna is a separate
entity and does not have to remain byte-identical to that source or produce the
same receiver results. This package removed the rpchan synchronization and
compatibility profiles and the FrameRLS preset, keeping only the linear
frequency-modulated synchronization path. The wrappers (`src/JunaCore.jl`,
`src/Juna.jl`) and `Project.toml` are pruned.

`test/source_file_check.jl` stores values for selected Juna files so a reviewed
change is visible. `tools/parity_check.jl` repeats fixed Juna transmit and
receive cases and compares them with results stored in this repository. Neither
check requires a corresponding Sonique change.

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
julia --project=. -e 'using Pkg; Pkg.test()'   # all suites
julia --project=. test/runtests.jl list        # print the suite map
julia --project=. test/runtests.jl lite        # selector-matched suites
julia --project=. test/phase1_smoke.jl         # any file runs standalone
```

The keyed `SUITES` registry in `test/runtests.jl` is the authoritative
catalog; the explorer consumes it via `tools/explorer/suites.json`
(regenerate with `julia tools/explorer/export_suites.jl`). The replay-
campaign sweeps (Red/Yellow iteration evidence) deliberately stay in the
source repository — they depend on its benchmark harness and Zenodo
captures.

## Explorer

```bash
python3 tools/explorer/server.py   # http://127.0.0.1:8772/
```

Unified workbench: Home | Tests | Map | Chain | Source | Coverage | Health |
Progress, all served by one shell with a command palette (Ctrl-K) and an
uncommitted-state banner. Source has two integrated modes:
`/source` is the evidence inspector, and `/source/graph` is the advanced
context graph entered from receiver, stage, suite, file, and symbol links
throughout the workbench. The original self-contained analyzer is retained at
`/source-advanced` (with `/source-legacy` as a compatibility alias) and carries
an Explorer bridge bar. The Health tab runs a fixed allowlist of verification
commands and records results (with commit and dirty-state) separately from
browser test runs.

JSON API layer (`/api/repository`, `/api/suites`, `/api/chain`,
`/api/receivers`, `/api/symbols`, `/api/symbol/<name>`, `/api/graph`,
`/api/coverage`, `/api/runs`, `/api/health`, `/api/palette`): every response
carries the provenance
envelope `{commit, working_tree_dirty, generated_at, schema_version, data}`.
Any future frontend builds against these APIs, not against page HTML.

Data contracts: `python3 tools/explorer/explorer_contract.py` (C1–C10) and
`python3 tools/explorer/server_contract.py` (S1–S17, including headless-browser
canvas-pixel checks). The source
repository's explorer remains the home of the full nine-receiver family on
port 8771.
