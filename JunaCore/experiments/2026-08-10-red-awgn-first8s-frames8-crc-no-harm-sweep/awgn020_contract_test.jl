#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "awgn020_sweep.jl"))
using .Awgn020Sweep
const A20 = Awgn020Sweep

@testset verbose=true "AWGN-020 first-eight-second five-receiver sweep" begin
    @testset "approved campaign contract" begin
        A20.require_contract(; verify_data=false)
        @test A20.DECISION == "AWGN-020"
        @test A20.FAMILY ==
            "2026-08-10-red-awgn-first8s-frames8-crc-no-harm"
        @test length(A20.CONFIGURATIONS) == 1
        @test length(A20.PATHS) == 12
        @test collect(A20.SNR_DB) == collect(0:2:30)
        @test A20.FRAMES == 8
        @test A20.CAPTURE_SECONDS == 8.0
        @test A20.SEED == 4
        @test A20.SNAPSHOT_INDICES == [1, 96, 190, 285, 385, 480, 574, 669]
        @test A20.GENERIC_EIGHT_SNAPSHOT_INDICES != A20.SNAPSHOT_INDICES
        @test first(A20.SNAPSHOT_INDICES, 4) == [1, 96, 190, 285]
        @test A20.expected_aggregate_rows() == 80
        @test A20.expected_frame_trace_rows() == 640
        @test A20.expected_protected_trace_rows() == 256
        A20.require_public_receiver_contract()
    end

    if "--capture-contract" in ARGS || "--probe" in ARGS
        capture = A20.load_first8s_capture(:red1, 1)
        geometry = A20.require_snapshot_contract(
            capture, only(A20.CONFIGURATIONS).config)
        @test size(capture.h) == (768, 769)
        @test length(capture.phase) == 153_800
        @test geometry.snapshot_indices == A20.SNAPSHOT_INDICES
        @test geometry.position_stop == 669
        @test geometry.frame_samples == 9_536
        @test geometry.payload_bits_per_frame == 1_616
        @test all(geometry.support_end_seconds .<= A20.CAPTURE_SECONDS)
        @test geometry.payload_seeds == collect(4:11)
        @test geometry.noise_seeds == collect(4:11)
        @test geometry.replay_seeds == collect(4:11)
        @test geometry.optimizer_seeds == fill(4, 8)
    end

    if "--probe" in ARGS
        rows, frame_traces, protected_traces = A20.probe_path(snrs=[0])
        A20.validate_path_rows(
            rows, frame_traces, protected_traces; snrs=[0])
        @test length(rows) == 5
        @test length(frame_traces) == 40
        @test length(protected_traces) == 16
        @test all(row.payload_bits_per_frame == 1_616 for row in rows)
        @test all(row.payload_seed == row.noise_seed == row.replay_seed
                  for row in frame_traces)
        @test all(row.optimizer_seed == 4 for row in frame_traces)
        @test all(!row.decode_failure for row in frame_traces)
        @test all(!row.decode_failure for row in protected_traces)
    end
end
