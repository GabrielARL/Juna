#!/usr/bin/env julia

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const HARNESS = joinpath(
    REPO_ROOT, "JunaCore", "experiments", "2026-08-04-red-snr-sweep",
    "benchmark_port.jl")
include(HARNESS)

using .BenchmarkPort
using LinearAlgebra

const B = BenchmarkPort
const Juna = B.Juna
const Modulations = B.Modulations
const DATA_DIR = raw"C:\Users\Admin\Documents\GitHub\replaychan\data"
const MODEM_FS = 4_882.8125
const CAPTURE_FS = 9_765.625
const BLUE_FC = 13_000.0
const SYNC_SAMPLES = 1_042
const DFT_TAPS = parse(Int, get(ENV, "JUNA_BLUE_DFT_TAPS", "0"))
const DISABLE_CP_TRACKER =
    get(ENV, "JUNA_BLUE_DISABLE_CP_TRACKER", "0") == "1"
const SNAPSHOTS = [
    1, 74, 146, 219, 291, 364, 436, 509,
    581, 654, 726, 799, 871, 944, 1016, 1089,
    1161, 1234, 1306, 1379, 1451, 1524, 1596, 1669,
    1741, 1814, 1886, 1959, 2031, 2104, 2176, 2249,
]

@eval Juna begin
    _synclen(m::Modulation) = m.sync ? $SYNC_SAMPLES : 0
    _sync_overhead(m::Modulation, fs) = m.sync ? $(2 * SYNC_SAMPLES) : 0
end

@eval B begin
    function _snapshot_positions(capture::ReplayCapture, packets::Integer,
                                 waveform_length::Integer, modem_fs::Real)
        Int(packets) == 32 || throw(ArgumentError(
            "sparse-pilot diagnostic requires 32 frames"))
        copy($SNAPSHOTS)
    end
end

if DFT_TAPS > 0
    @eval Juna begin
        function _residual_pilot_equalize(m::Modulation, layout::_Layout,
                                          carriers)
            equalized = carriers isa Vector{ComplexF64} ?
                copy(carriers) : ComplexF64.(carriers)
            pilot_count = length(layout.pilot_idx)
            tap_count = min($DFT_TAPS, pilot_count)
            first_delay = -fld(tap_count, 2)
            delays = collect(first_delay:first_delay + tap_count - 1)
            design = Matrix{ComplexF64}(undef, pilot_count, tap_count)
            response = Vector{ComplexF64}(undef, pilot_count)
            N = Int(m.nc)
            for row in 1:pilot_count
                bin = layout.pilot_idx[row] - 1
                response[row] = equalized[layout.pilot_idx[row]] /
                    layout.pilot_syms[row]
                for column in 1:tap_count
                    design[row, column] = cispi(
                        -2 * bin * delays[column] / N)
                end
            end
            gram = design' * design
            scale = max(real(tr(gram)) / max(tap_count, 1), 1.0)
            gram += (1e-4 * scale) * I
            taps = gram \ (design' * response)
            for bin_index in layout.active
                bin = bin_index - 1
                channel = sum(
                    taps[column] * cispi(
                        -2 * bin * delays[column] / N)
                    for column in 1:tap_count)
                abs(channel) > eps(Float64) &&
                    (equalized[bin_index] /= channel)
            end
            equalized
        end
    end
end

if DISABLE_CP_TRACKER
    @eval Juna begin
        _track_block_carrier(m::Modulation, waveform) =
            ComplexF64.(waveform)
    end
end

function load_blue(channel::Int, lane::Int)
    full = B.ReplayLane.load_capture(
        joinpath(DATA_DIR, "blue_$(channel).mat"); receiver=lane)
    full.fs == CAPTURE_FS || error("Blue capture fs differs")
    full.fc == BLUE_FC || error("Blue capture fc differs")
    tap_snapshots = floor(Int, 47 * full.fs / full.step) + 1
    phase_samples = floor(Int, 47 * full.fs) + full.step
    B.ReplayLane.ReplayCapture(
        full.h[:, 1:tap_snapshots], full.phase[1:phase_samples],
        full.fs, full.fc, full.step, full.receiver,
        full.name * "_first47s")
end

const STANDARD_ONLY = (
    (id=:ofdm_fec, name="OFDM + FEC", profile=:standard,
     partial_fft_parts=4),
)

function diagnose(channel::Int, lane::Int, nfft::Int, spacing::Int)
    rows = NamedTuple[]
    B.benchmark_frame_capture(
        load_blue(channel, lane);
        channel_id="blue$(channel)", frames=32,
        frame_duration_s=1.0, frame_crc_bits=16,
        algorithms=STANDARD_ONLY, snr_db=30.0, seed=4,
        modem_fs=MODEM_FS, modem_profile=:passband_replay,
        sync_profile=:lfm, nfft=nfft, cp=64, code_rate=0.25,
        check_degree=14, ldpc_method=:auto, ldpc_seed=51_001,
        ldpc_no4cycle=true, outer_pilot_ratio=1 / spacing,
        inner_pilot_ratio=1 / spacing,
        frame_sink=row -> push!(rows, row),
    )
    errors = sum(row.bit_errors for row in rows)
    bits = sum(row.payload_bits for row in rows)
    println(
        "BLUE_SPARSE_RESULT channel=blue$(channel) lane=$(lane) nfft=$(nfft) spacing=$(spacing) window=$(round(nfft/spacing, digits=1)) " *
        "dft_taps=$(DFT_TAPS) cp_tracker=$(!DISABLE_CP_TRACKER) " *
        "errors=$(errors) bits=$(bits) " *
        "ber=$(errors / bits) successful=$(count(row -> row.success, rows))/32")
end

paths = isempty(ARGS) ? [(3, 1)] : [
    (parse(Int, split(arg, ':')[1]), parse(Int, split(arg, ':')[2]))
    for arg in ARGS]
# JUNA_BLUE_CONFIGS is a comma-separated list of nfft:spacing pairs; ARGS are
# channel:lane paths. Every pair runs against every path.
configs = [(parse(Int, split(t, ':')[1]), parse(Int, split(t, ':')[2]))
           for t in split(get(ENV, "JUNA_BLUE_CONFIGS", "512:20"), ',')]
for (nf, sp) in configs
    for p in paths
        diagnose(p[1], p[2], nf, sp)
    end
end
