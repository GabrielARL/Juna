#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "awgn022_sweep.jl"))
using .Awgn022Sweep
const A22 = Awgn022Sweep

const EXPECTED_SNAPSHOTS = [
    1, 96, 190, 285,
    385, 480, 574, 669,
    769, 864, 958, 1053,
    1153, 1248, 1342, 1437,
    1537, 1632, 1726, 1821,
    1921, 2016, 2110, 2205,
    2305, 2400, 2494, 2589,
    2689, 2784, 2878, 2973,
]

@testset verbose=true "AWGN-022 first-thirty-two-second five-receiver sweep" begin
    @testset "approved campaign contract" begin
        A22.require_contract(; verify_data=false)
        @test A22.DECISION == "AWGN-022"
        @test A22.FAMILY ==
            "2026-08-10-red-awgn-first32s-frames32-crc-no-harm"
        @test length(A22.CONFIGURATIONS) == 1
        @test length(A22.PATHS) == 12
        @test collect(A22.SNR_DB) == collect(0:2:30)
        @test A22.FRAMES == 32
        @test A22.CAPTURE_SECONDS == 32.0
        @test A22.SEED == 4
        @test A22.SNAPSHOT_INDICES == EXPECTED_SNAPSHOTS
        @test first(A22.SNAPSHOT_INDICES, 16) == [
            1, 96, 190, 285, 385, 480, 574, 669,
            769, 864, 958, 1053, 1153, 1248, 1342, 1437,
        ]
        @test last(A22.SNAPSHOT_INDICES, 16) ==
            first(A22.SNAPSHOT_INDICES, 16) .+ 1_536
        @test all(
            A22.SNAPSHOT_INDICES[(4 * block + 1):(4 * block + 4)] ==
                [1, 96, 190, 285] .+ 384block
            for block in 0:7)
        @test A22.GENERIC_THIRTYTWO_SNAPSHOT_INDICES == [
            1, 97, 193, 289, 384, 480, 576, 672,
            768, 864, 960, 1056, 1151, 1247, 1343, 1439,
            1535, 1631, 1727, 1823, 1918, 2014, 2110, 2206,
            2302, 2398, 2494, 2590, 2685, 2781, 2877, 2973,
        ]
        @test A22.GENERIC_APPENDED_SIXTEEN_SNAPSHOT_INDICES == [
            1537, 1633, 1728, 1824, 1920, 2016, 2111, 2207,
            2303, 2399, 2494, 2590, 2686, 2782, 2877, 2973,
        ]
        @test A22.GENERIC_THIRTYTWO_SNAPSHOT_INDICES != A22.SNAPSHOT_INDICES
        @test A22.GENERIC_APPENDED_SIXTEEN_SNAPSHOT_INDICES !=
            last(A22.SNAPSHOT_INDICES, 16)
        @test A22.expected_aggregate_rows() == 80
        @test A22.expected_frame_trace_rows() == 2_560
        @test A22.expected_protected_trace_rows() == 1_024
        A22.require_public_receiver_contract()
    end

    if "--capture-contract" in ARGS || "--probe" in ARGS
        capture = A22.load_first32s_capture(:red1, 1)
        geometry = A22.require_snapshot_contract(
            capture, only(A22.CONFIGURATIONS).config)
        @test size(capture.h) == (768, 3_073)
        @test length(capture.phase) == 614_600
        @test geometry.snapshot_indices == A22.SNAPSHOT_INDICES
        @test geometry.position_stop == 2_973
        @test geometry.frame_samples == 9_536
        @test geometry.payload_bits_per_frame == 1_616
        @test A22.B._snapshot_positions(
            capture, A22.FRAMES, geometry.frame_samples, A22.A.MODEM_FS) ==
            EXPECTED_SNAPSHOTS
        @test all(geometry.support_end_seconds .<= A22.CAPTURE_SECONDS)
        @test last(geometry.support_end_seconds) == 31.993854166666665
        @test geometry.payload_seeds == collect(4:35)
        @test geometry.noise_seeds == collect(4:35)
        @test geometry.replay_seeds == collect(4:35)
        @test geometry.optimizer_seeds == fill(4, 32)
    end

    if "--probe" in ARGS
        rows, frame_traces, protected_traces = A22.probe_path(snrs=[0])
        A22.validate_path_rows(
            rows, frame_traces, protected_traces; snrs=[0])
        @test length(rows) == 5
        @test length(frame_traces) == 160
        @test length(protected_traces) == 64
        @test all(row.payload_bits_per_frame == 1_616 for row in rows)
        @test all(row.payload_seed == row.noise_seed == row.replay_seed
                  for row in frame_traces)
        @test all(row.optimizer_seed == 4 for row in frame_traces)
        @test all(!row.decode_failure for row in frame_traces)
        @test all(!row.decode_failure for row in protected_traces)
    end
end
