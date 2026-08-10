#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "awgn023b_sweep.jl"))
using .Awgn023bSweep
const A23B = Awgn023bSweep

const EXPECTED_AWGN022_SNAPSHOTS = [
    1, 96, 190, 285,
    385, 480, 574, 669,
    769, 864, 958, 1053,
    1153, 1248, 1342, 1437,
    1537, 1632, 1726, 1821,
    1921, 2016, 2110, 2205,
    2305, 2400, 2494, 2589,
    2689, 2784, 2878, 2973,
]
const EXPECTED_SNAPSHOTS = [
    EXPECTED_AWGN022_SNAPSHOTS...,
    3073, 3168, 3262, 3357,
    3457, 3552, 3646, 3741,
    3841, 3936, 4030, 4125,
    4225, 4320, 4414,
]

@testset verbose=true "AWGN-023B complete-capture five-receiver sweep" begin
    @testset "approved campaign contract" begin
        A23B.require_contract(; verify_data=false)
        @test A23B.DECISION == "AWGN-023B"
        @test A23B.FAMILY ==
            "2026-08-10-red-awgn-full-capture-frames47-crc-no-harm"
        @test length(A23B.CONFIGURATIONS) == 1
        @test length(A23B.PATHS) == 12
        @test collect(A23B.SNR_DB) == collect(0:2:30)
        @test A23B.FRAMES == 47
        @test A23B.CAPTURE_SECONDS == 47.78125
        @test A23B.SEED == 4
        @test A23B.SNAPSHOT_INDICES == EXPECTED_SNAPSHOTS
        @test first(A23B.SNAPSHOT_INDICES, 32) ==
            EXPECTED_AWGN022_SNAPSHOTS
        @test all(
            A23B.SNAPSHOT_INDICES[(4 * block + 1):(4 * block + 4)] ==
                [1, 96, 190, 285] .+ 384block
            for block in 0:10)
        @test last(A23B.SNAPSHOT_INDICES, 3) ==
            first([1, 96, 190, 285] .+ 384 * 11, 3)
        @test A23B.expected_aggregate_rows() == 80
        @test A23B.expected_frame_trace_rows() == 3_760
        @test A23B.expected_protected_trace_rows() == 1_504
        @test A23B.EXPECTED_PAYLOAD_BITS_PER_POINT == 75_952
        @test length(A23B.PATHS) * A23B.expected_aggregate_rows() == 960
        @test length(A23B.PATHS) * A23B.expected_frame_trace_rows() == 45_120
        @test length(A23B.PATHS) * A23B.expected_protected_trace_rows() ==
            18_048
        A23B.require_public_receiver_contract()
    end

    if "--capture-contract" in ARGS || "--probe" in ARGS
        capture = A23B.load_full_capture(:red1, 1)
        geometry = A23B.require_snapshot_contract(
            capture, only(A23B.CONFIGURATIONS).config)
        @test size(capture.h) == (768, 4_588)
        @test length(capture.phase) == 917_600
        @test geometry.snapshot_indices == A23B.SNAPSHOT_INDICES
        @test geometry.position_stop == 4_488
        @test geometry.frame_samples == 9_536
        @test geometry.payload_bits_per_frame == 1_616
        @test A23B.B._snapshot_positions(
            capture, A23B.FRAMES, geometry.frame_samples, A23B.A.MODEM_FS) ==
            EXPECTED_SNAPSHOTS
        @test all(geometry.support_end_seconds .<= A23B.CAPTURE_SECONDS)
        @test last(geometry.support_end_seconds) == 47.004270833333336
        @test geometry.payload_seeds == collect(4:50)
        @test geometry.noise_seeds == collect(4:50)
        @test geometry.replay_seeds == collect(4:50)
        @test geometry.optimizer_seeds == fill(4, 47)
    end

    if "--probe" in ARGS
        rows, frame_traces, protected_traces = A23B.probe_path(snrs=[0])
        A23B.validate_path_rows(
            rows, frame_traces, protected_traces; snrs=[0])
        @test length(rows) == 5
        @test length(frame_traces) == 235
        @test length(protected_traces) == 94
        @test all(row.payload_bits_per_frame == 1_616 for row in rows)
        @test all(row.payload_bits == 75_952 for row in rows)
        @test all(row.payload_seed == row.noise_seed == row.replay_seed
                  for row in frame_traces)
        @test all(row.optimizer_seed == 4 for row in frame_traces)
        @test all(!row.decode_failure for row in frame_traces)
        @test all(!row.decode_failure for row in protected_traces)
    end
end
