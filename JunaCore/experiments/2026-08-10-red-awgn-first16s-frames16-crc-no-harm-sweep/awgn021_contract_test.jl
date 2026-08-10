#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "awgn021_sweep.jl"))
using .Awgn021Sweep
const A21 = Awgn021Sweep

const EXPECTED_SNAPSHOTS = [
    1, 96, 190, 285,
    385, 480, 574, 669,
    769, 864, 958, 1053,
    1153, 1248, 1342, 1437,
]

@testset verbose=true "AWGN-021 first-sixteen-second five-receiver sweep" begin
    @testset "approved campaign contract" begin
        A21.require_contract(; verify_data=false)
        @test A21.DECISION == "AWGN-021"
        @test A21.FAMILY ==
            "2026-08-10-red-awgn-first16s-frames16-crc-no-harm"
        @test length(A21.CONFIGURATIONS) == 1
        @test length(A21.PATHS) == 12
        @test collect(A21.SNR_DB) == collect(0:2:30)
        @test A21.FRAMES == 16
        @test A21.CAPTURE_SECONDS == 16.0
        @test A21.SEED == 4
        @test A21.SNAPSHOT_INDICES == EXPECTED_SNAPSHOTS
        @test first(A21.SNAPSHOT_INDICES, 8) ==
            [1, 96, 190, 285, 385, 480, 574, 669]
        @test last(A21.SNAPSHOT_INDICES, 8) ==
            first(A21.SNAPSHOT_INDICES, 8) .+ 768
        @test all(
            A21.SNAPSHOT_INDICES[(4block + 1):(4block + 4)] ==
                [1, 96, 190, 285] .+ 384block
            for block in 0:3)
        @test A21.GENERIC_SIXTEEN_SNAPSHOT_INDICES != A21.SNAPSHOT_INDICES
        @test A21.expected_aggregate_rows() == 80
        @test A21.expected_frame_trace_rows() == 1_280
        @test A21.expected_protected_trace_rows() == 512
        A21.require_public_receiver_contract()
    end

    if "--capture-contract" in ARGS || "--probe" in ARGS
        capture = A21.load_first16s_capture(:red1, 1)
        geometry = A21.require_snapshot_contract(
            capture, only(A21.CONFIGURATIONS).config)
        @test size(capture.h) == (768, 1_537)
        @test length(capture.phase) == 307_400
        @test geometry.snapshot_indices == A21.SNAPSHOT_INDICES
        @test geometry.position_stop == 1_437
        @test geometry.frame_samples == 9_536
        @test geometry.payload_bits_per_frame == 1_616
        @test A21.B._snapshot_positions(
            capture, A21.FRAMES, geometry.frame_samples, A21.A.MODEM_FS) ==
            EXPECTED_SNAPSHOTS
        @test all(geometry.support_end_seconds .<= A21.CAPTURE_SECONDS)
        @test geometry.payload_seeds == collect(4:19)
        @test geometry.noise_seeds == collect(4:19)
        @test geometry.replay_seeds == collect(4:19)
        @test geometry.optimizer_seeds == fill(4, 16)
    end

    if "--probe" in ARGS
        rows, frame_traces, protected_traces = A21.probe_path(snrs=[0])
        A21.validate_path_rows(
            rows, frame_traces, protected_traces; snrs=[0])
        @test length(rows) == 5
        @test length(frame_traces) == 80
        @test length(protected_traces) == 32
        @test all(row.payload_bits_per_frame == 1_616 for row in rows)
        @test all(row.payload_seed == row.noise_seed == row.replay_seed
                  for row in frame_traces)
        @test all(row.optimizer_seed == 4 for row in frame_traces)
        @test all(!row.decode_failure for row in frame_traces)
        @test all(!row.decode_failure for row in protected_traces)
    end
end
