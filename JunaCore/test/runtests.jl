#!/usr/bin/env julia
#
# JunaCore (JUNA-Lite migration) test runner.
#
# Usage:
#   julia --project=. -e 'using Pkg; Pkg.test()'          # all suites
#   julia --project=. test/runtests.jl                    # all suites
#   julia --project=. test/runtests.jl lite feedback      # only matching suites
#   julia --project=. test/runtests.jl list               # print the map, run nothing
#   julia --project=. test/runtests.jl roundtrip          # all + extended roundtrip
#   julia --project=. -e 'using Pkg; Pkg.test(test_args=["lite"])'
#
# A selector matches a suite key, file name, or title (case-insensitive
# substring). Every test file is also runnable on its own, e.g.
# `julia --project=. test/ofdm_layout.jl`.
#
# This SUITES registry is the authoritative machine-readable catalog of the
# package's test surface: the explorer exports it as suites.json
# (tools/explorer/export_suites.jl). Keep entries as flat literal NamedTuples.
# Provenance: adapted from sonique research/JunaCoreTests @ d49fff0; suites
# marked [byte-identical] must not drift from their source-repo files.

using Test

const SUITES = [
    (key = "smoke", file = "phase1_smoke.jl",
     title = "Migration smoke: clean-channel roundtrip",
     claim = "all three public facades recover a clean-channel payload bit-exactly and Lite declares :posterior_anchor_ls",
     provenance = "authored for this package (phase-1 migration gate)"),
    (key = "packaging", file = "source_layout.jl",
     title = "Migrated source layout and facade pruning",
     claim = "src/ carries exactly the Lite closure (common, frame_wide_ldpc, lite) and the wrapper exposes exactly the JunaLite, JunaStandard, and JunaPartialFFT facades while every foreign variant file and facade is absent",
     provenance = "adapted (inverted) from source_layout.jl"),
    (key = "config", file = "receiver_configuration.jl",
     title = "Receiver selection and init defaults",
     claim = "the migrated runtime modes select distinct modems and init() resets to the benchmark geometry",
     provenance = "adapted: scope narrowed to the three migrated facades"),
    (key = "interface", file = "public_modem_interface.jl",
     title = "Public modulate/demodulate boundary",
     claim = "every migrated receiver crosses the m-sequence, 3x3 fc/fs, waveform-length, metric-polarity, payload-rate, and error contracts; supported boundaries recover clean payloads",
     provenance = "adapted: scope narrowed to the three migrated facades"),
    (key = "contract", file = "interface_contract.jl",
     title = "Modem interface and refinement capability contract",
     claim = "the descriptor catalog exactly covers the three migrated public facades; every path satisfies Modulations, executes its declared objective (:none, :pilot_band_ls, :posterior_anchor_ls), and decodes a noiseless loopback payload-exactly",
     provenance = "adapted: scope narrowed to the three migrated facades"),
    (key = "sizing", file = "payload_block_sizing.jl",
     title = "Payload bits and block sizing",
     claim = "positive payload sizes exclude inner pilots (170 unknown of k=340), reject zero, and count 1280-sample blocks (N=1024 + CP 256)",
     provenance = "[byte-identical] source-repo suite"),
    (key = "layout", file = "ofdm_layout.jl",
     title = "OFDM tone layout and band partition",
     claim = "DC-nulled active tones split into comb pilots and data bands; bw times the fixed 24 kHz reference sets occupied width, fs sets the FFT occupancy fraction, and dc0 tunes the RF centre from 24 kHz without shifting baseband bins",
     provenance = "[byte-identical] source-repo suite"),
    (key = "lite", file = "juna_lite_refinement.jl",
     title = "JUNA-lite soft-anchor refinement",
     claim = "posterior metrics become confidence-weighted soft data anchors, JUNA-lite refits an invalid seed into a finite valid candidate, and valid seeds are preserved",
     provenance = "[byte-identical] source-repo suite"),
    (key = "pfft", file = "partial_fft_receiver.jl",
     title = "Baseline receivers: standard OFDM and partial FFT",
     claim = "the paper's OFDM+FEC and Partial FFT+FEC benchmark branches are public receiver modes pinned to their demodulate_methods columns, per-band combining survives the within-symbol channel one-tap cannot, lite never loses to its own seed, and both baselines roundtrip BPSK",
     provenance = "[byte-identical] source-repo suite"),
    (key = "feedback-modes", file = "feedback_mode_arms_contract.jl",
     title = "Decoder-feedback mechanism arms",
     claim = "the coupled receivers expose validated :real/:frozen/:genie/:graded feedback arms that share one code path, so frozen anchors no data decision, the oracle arms anchor transmitted symbols at unit weight and fail loudly without them, and graded corruption is seeded, bounded and on-constellation",
     provenance = "[byte-identical] source-repo suite"),
    (key = "adaptive-lite", file = "juna_adaptive_frontend_lite.jl",
     title = "Pilot-conditioned P=1/P=4 JUNA-Lite front end",
     claim = "disjoint outer-pilot folds collapse the Lite seed to full-FFT-equivalent P=1 unless the configured multi-part combiner has a material held-out prediction advantage",
     provenance = "[byte-identical] source-repo suite"),
]

_suite_matches(suite, sel) = begin
    s = lowercase(sel)
    occursin(s, lowercase(suite.key)) ||
        occursin(s, lowercase(suite.file)) ||
        occursin(s, lowercase(suite.title))
end

function _print_map()
    for suite in SUITES
        println(rpad(suite.key, 18), suite.file)
        println("    ", suite.title)
        println("    claim: ", suite.claim)
        println("    provenance: ", suite.provenance)
    end
end

function _run(selectors::Vector{String})
    wants_roundtrip = any(s -> lowercase(s) == "roundtrip", selectors)
    rest = [s for s in selectors if lowercase(s) != "roundtrip"]
    chosen = isempty(rest) ? SUITES :
        [s for s in SUITES if any(sel -> _suite_matches(s, sel), rest)]
    isempty(chosen) && error("no suite matches selectors $(repr(rest)); " *
                             "run with `list` to see the catalog")
    wants_roundtrip && (ENV["JUNA_INTERFACE_ROUNDTRIP"] = "1")
    @testset "JunaCore (JUNA-Lite migration)" begin
        for suite in chosen
            @testset "$(suite.title)" begin
                include(suite.file)
            end
        end
    end
end

# Run only when invoked as the program (Pkg.test or direct); when another
# script includes this file to read the SUITES registry (the explorer's
# export_suites.jl), loading must stay side-effect free.
if abspath(PROGRAM_FILE) == @__FILE__
    args = String.(ARGS)
    if length(args) == 1 && lowercase(args[1]) == "list"
        _print_map()
    else
        _run(args)
    end
end
