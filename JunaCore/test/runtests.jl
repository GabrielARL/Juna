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
# Historical source: adapted from sonique research/JunaCoreTests @ d49fff0.
# These tests are now maintained by Juna and do not have to match those copies.

using Test

const SUITES = [
    (key = "smoke", file = "phase1_smoke.jl",
     tier = "universal", receivers = "all",
     title = "Migration smoke: clean-channel roundtrip",
     claim = "all three public facades recover a clean-channel payload bit-exactly and Lite declares :posterior_anchor_ls",
     origin = "authored for this package (phase-1 migration gate)",
     reader_title = "Clean transmission and recovery",
     reader_summary = "The Standard, partial fast Fourier transform (Partial-FFT), and JUNA-Lite receivers recover every bit from their own clean transmissions, and JUNA-Lite reports that it uses decoder results for a second equalization pass.",
     method = "It uses alternating ones and zeros so that reversed signs or bit order cause a failure.",
     reader_origin = "Written for this package."),
    (key = "source-files", file = "source_file_check.jl",
     tier = "structural", receivers = "structural",
     title = "Source file check",
     claim = "five selected Juna algorithm files and three LDPC helper programs match the values stored in this repository, so an unreviewed edit is visible",
     origin = "written for Juna; the first stored values were recorded during migration",
     reader_title = "Source file check",
     reader_summary = "Five algorithm files and three helper programs are compared with values stored by Juna. If one changes without review, this test fails.",
     method = "For each selected file, the test calculates a SHA-256 value from its contents and compares it with the stored value.",
     reader_origin = "Written for this package."),
    (key = "packaging", file = "source_layout.jl",
     tier = "structural", receivers = "structural",
     title = "Migrated source layout and facade pruning",
     claim = "src/ carries exactly the Lite closure (common, frame_wide_ldpc, lite) and the wrapper exposes exactly the JunaLite, JunaStandard, and JunaPartialFFT facades while every foreign variant file and facade is absent",
     origin = "adapted (inverted) from source_layout.jl",
     reader_title = "Files and receivers included in this package",
     reader_summary = "The required source files remain present; the Standard, Partial-FFT, and JUNA-Lite receivers remain available, and the listed excluded receiver files and names remain absent.",
     method = "The test checks file presence, loading order, and available module names while confirming that removed receiver files and names remain absent.",
     reader_origin = "Adapted from the source layout test for this smaller package."),
    (key = "config", file = "receiver_configuration.jl",
     tier = "universal", receivers = "all",
     title = "Receiver selection and init defaults",
     claim = "the migrated runtime modes select distinct modems and init() resets to the benchmark geometry",
     origin = "adapted: scope narrowed to the three migrated facades",
     reader_title = "Receiver choices and default settings",
     reader_summary = "The test checks receiver choices and valid settings, while initialization retains the selected receiver and synchronization settings and restores the paper frame dimensions.",
     method = "It constructs each receiver, checks accepted and rejected settings, changes the defaults, and checks the values after initialization.",
     reader_origin = "Adapted from the source test for the three receivers in this package."),
    (key = "interface", file = "public_modem_interface.jl",
     tier = "universal", receivers = "all",
     title = "Public modulate/demodulate boundary",
     claim = "every migrated receiver crosses the m-sequence, 3x3 fc/fs, waveform-length, metric-polarity, payload-rate, and error contracts; supported boundaries recover clean payloads",
     origin = "adapted: scope narrowed to the three migrated facades",
     reader_title = "Sending and receiving data",
     reader_summary = "Every receiver choice sends and recovers data through the same functions at several carrier frequencies and sample rates, reports the expected signal length and payload rate, and rejects invalid inputs.",
     method = "The test uses fixed bit patterns, exact and padded blocks, nine combinations of carrier frequency and sample rate, a short signal, and an invalid receiver setting.",
     reader_origin = "Adapted from the source test for the three receivers in this package."),
    (key = "contract", file = "interface_contract.jl",
     tier = "universal", receivers = "all",
     title = "Modem interface and refinement capability contract",
     claim = "the descriptor catalog exactly covers the three migrated public facades; every path satisfies Modulations, executes its declared objective (:none, :pilot_band_ls, :posterior_anchor_ls), and decodes a noiseless loopback payload-exactly",
     origin = "adapted: scope narrowed to the three migrated facades",
     reader_title = "Checks shared by all receivers",
     reader_summary = "The receiver list contains Standard, Partial FFT, and Lite; each receiver provides the required operations, reports its stated refinement method, and recovers a clean payload bit for bit.",
     method = "The test runs the Partial FFT fit, checks that the JUNA-Lite function for a second equalization pass is present, and confirms that the three low-density parity-check helper programs are available. It can repeat recovery over several blocks when requested.",
     reader_origin = "Adapted from the source test for the three receivers in this package."),
    (key = "sizing", file = "payload_block_sizing.jl",
     tier = "universal", receivers = "all",
     title = "Payload bits and block sizing",
     claim = "positive payload sizes exclude inner pilots (170 unknown of k=340), reject zero, and count 1280-sample blocks (N=1024 + CP 256)",
     origin = "copied during migration and now maintained by Juna",
     reader_title = "Payload and signal length",
     reader_summary = "Under the paper settings, one 1,280-sample block carries 170 payload bits; larger payloads use whole additional blocks, zero bits are rejected, and synchronization adds 4,096 samples.",
     method = "The expected values are fixed numbers from the paper rather than values recalculated from the receiver settings.",
     reader_origin = "Copied during migration and now maintained by Juna."),
    (key = "layout", file = "ofdm_layout.jl",
     tier = "mechanism", receivers = "stage:acquisition",
     title = "OFDM tone layout and band partition",
     claim = "DC-nulled active tones split into comb pilots and data bands; bw times the fixed 24 kHz reference sets occupied width, fs sets the FFT occupancy fraction, and dc0 tunes the RF centre from 24 kHz without shifting baseband bins",
     origin = "copied during migration and now maintained by Juna",
     reader_title = "Pilot, data, and frequency bands",
     reader_summary = "The test checks which frequency tones carry pilots and data, how the tones divide into receiver bands, how many coded bits fit, and how bandwidth and centre frequency affect the occupied frequencies.",
     method = "It checks the exact tone counts, pilot pattern, divisions into 16 bands and four bands, data capacity, and changes caused by bandwidth and centre frequency.",
     reader_origin = "Copied during migration and now maintained by Juna."),
    (key = "lite", file = "juna_lite_refinement.jl",
     tier = "receiver-specific", receivers = "receiver:lite",
     title = "JUNA-lite soft-anchor refinement",
     claim = "posterior metrics become confidence-weighted soft data anchors, JUNA-lite refits an invalid seed into a finite valid candidate, and valid seeds are preserved",
     origin = "copied during migration and now maintained by Juna",
     reader_title = "JUNA-Lite second equalization pass",
     reader_summary = "JUNA-Lite turns decoder results into weighted data values for a second equalization pass, improves an invalid first result, and retains an already valid result.",
     method = "The test checks the conversion and selection of decoder results before exercising both invalid and valid starting results.",
     reader_origin = "Copied during migration and now maintained by Juna."),
    (key = "pfft", file = "partial_fft_receiver.jl",
     tier = "mechanism", receivers = "all",
     title = "Baseline receivers: standard OFDM and partial FFT",
     claim = "the paper's OFDM+FEC and Partial FFT+FEC benchmark branches are public receiver modes pinned to their demodulate_methods columns, per-band combining survives the within-symbol channel one-tap cannot, lite never loses to its own seed, and both baselines roundtrip BPSK",
     origin = "copied during migration and now maintained by Juna",
     reader_title = "Standard and partial fast Fourier transform receivers",
     reader_summary = "The two receiver choices use distinct processing paths and recover a clean payload; the partial transform also handles the selected channel that changes within one symbol and defeats the Standard receiver.",
     method = "The test compares each public result with its direct receiver result, exercises the selected changing channel, and checks six fixed noisy packets. Across those packets, JUNA-Lite must have no more aggregate bit errors than its Partial FFT starting result.",
     reader_origin = "Copied during migration and now maintained by Juna."),
    (key = "feedback-modes", file = "feedback_mode_arms_contract.jl",
     tier = "mechanism", receivers = "stage:anchors",
     title = "Decoder-feedback mechanism arms",
     claim = "the coupled receivers expose validated :real/:frozen/:genie/:graded feedback arms that share one code path, so frozen anchors no data decision, the oracle arms anchor transmitted symbols at unit weight and fail loudly without them, and graded corruption is seeded, bounded and on-constellation",
     origin = "copied during migration and now maintained by Juna",
     reader_title = "Decoder feedback settings",
     reader_summary = "The four settings use normal decoder output, pilots only, transmitted symbols, or transmitted symbols changed at a set rate; they share one processing path and differ where expected.",
     method = "The test checks accepted settings, required transmitted symbols, repeatable symbol changes, handling for each block, and the resulting refinement output.",
     reader_origin = "Copied during migration and now maintained by Juna."),
    (key = "adaptive-lite", file = "juna_adaptive_frontend_lite.jl",
     tier = "mechanism", receivers = "stage:seed",
     title = "Pilot-conditioned P=1/P=4 JUNA-Lite front end",
     claim = "disjoint outer-pilot folds collapse the Lite seed to full-FFT-equivalent P=1 unless the configured multi-part combiner has a material held-out prediction advantage",
     origin = "copied during migration and now maintained by Juna",
     reader_title = "Lite input using one or four parts",
     reader_summary = "For each block, the receiver uses four partial fast Fourier transforms only when pilots left out of the fit show the required error reduction; otherwise it uses one transform.",
     method = "One test case selects one part, another selects four parts, and a case with two blocks makes the choice independently for each block.",
     reader_origin = "Copied during migration and now maintained by Juna."),
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
        println("    origin: ", suite.origin)
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
