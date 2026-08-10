#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "awgn023c_sweep.jl"))
using .Awgn023cSweep
const A23 = Awgn023cSweep

const EXPECTED_PASS = [
    1, 96, 190, 285, 385, 480, 574, 669,
    769, 864, 958, 1053, 1153, 1248, 1342, 1437,
    1537, 1632, 1726, 1821, 1921, 2016, 2110, 2205,
    2305, 2400, 2494, 2589, 2689, 2784, 2878, 2973,
]
const EXPECTED_REPEATED = repeat(EXPECTED_PASS, 4)

@testset verbose=true "AWGN-023C repeated first-thirty-two-second sweep" begin
    @testset "approved campaign contract" begin
        source = read(joinpath(@__DIR__, "awgn023c_sweep.jl"), String)
        @test length(findall("function _snapshot_positions", source)) == 1
        A23.require_contract(; verify_data=false)
        @test A23.DECISION == "AWGN-023C"
        @test A23.FAMILY ==
            "2026-08-10-red-awgn-repeated-first32s-frames128-crc-no-harm"
        @test length(A23.CONFIGURATIONS) == 1
        @test length(A23.PATHS) == 12
        @test collect(A23.SNR_DB) == collect(0:2:30)
        @test A23.FRAMES == 128
        @test A23.CAPTURE_SECONDS == 32.0
        @test A23.SEED == 4
        @test A23.BASE_SNAPSHOT_INDICES == EXPECTED_PASS
        @test A23.SNAPSHOT_INDICES == EXPECTED_REPEATED
        @test length(A23.SNAPSHOT_INDICES) == 128
        @test all(
            A23.SNAPSHOT_INDICES[(32pass + 1):(32pass + 32)] == EXPECTED_PASS
            for pass in 0:3)
        @test !allunique(A23.SNAPSHOT_INDICES)
        @test allunique(A23.GENERIC_128_SNAPSHOT_INDICES)
        @test A23.GENERIC_128_SNAPSHOT_INDICES != A23.SNAPSHOT_INDICES
        @test A23.expected_aggregate_rows() == 80
        @test A23.expected_frame_trace_rows() == 10_240
        @test A23.expected_protected_trace_rows() == 4_096
        @test A23.EXPECTED_PAYLOAD_BITS_PER_FRAME == 1_616
        @test A23.EXPECTED_PAYLOAD_BITS_PER_POINT == 206_848
        @test parentmodule(A23.F) === A23
        @test parentmodule(A23.B) === A23.F.A
        A23.require_public_receiver_contract()

        # Exercise the harness-local method without loading a measured MAT
        # file. The dimensions are the pinned first-32-second geometry, so the
        # test proves that the padded planning length yields stop=2973 and that
        # frame 128 repeats frame 32's final supported replay window.
        synthetic = A23.B.ReplayLane.ReplayCapture(
            zeros(ComplexF64, 768, 3_073), zeros(Float64, 614_600),
            19_200.0, 25_000.0, 200, 1, "awgn023c-contract")
        _, padded_stop = A23.B._capture_position_limit(
            synthetic, 9_536 + 22, A23.A.MODEM_FS)
        @test padded_stop == 2_973
        @test A23.B._snapshot_positions(
            synthetic, 128, 9_536, A23.A.MODEM_FS) == EXPECTED_REPEATED
        @test A23.B._snapshot_positions(
            synthetic, 32, 9_536, A23.A.MODEM_FS) == EXPECTED_PASS
        @test A23._default_snapshot_positions(
            synthetic, 128, 9_536, A23.A.MODEM_FS) ==
            A23.GENERIC_128_SNAPSHOT_INDICES
        @test all(1 .<= EXPECTED_REPEATED .<= padded_stop)
        @test A23.replay_support_end_seconds(
            synthetic, EXPECTED_REPEATED[128], 9_536) ==
            A23.replay_support_end_seconds(
                synthetic, EXPECTED_REPEATED[32], 9_536) ==
            31.993854166666665
        synthetic = nothing
        GC.gc()
    end

    if "--capture-contract" in ARGS || "--probe" in ARGS
        capture = A23.load_first32s_capture(:red1, 1)
        geometry = A23.require_snapshot_contract(
            capture, only(A23.CONFIGURATIONS).config)
        @test size(capture.h) == (768, 3_073)
        @test length(capture.phase) == 614_600
        @test geometry.snapshot_indices == EXPECTED_REPEATED
        @test geometry.position_stop == 2_973
        @test geometry.frame_samples == 9_536
        @test geometry.payload_bits_per_frame == 1_616
        @test A23.B._snapshot_positions(
            capture, 128, geometry.frame_samples, A23.A.MODEM_FS) ==
            EXPECTED_REPEATED
        @test A23._default_snapshot_positions(
            capture, 128, geometry.frame_samples, A23.A.MODEM_FS) ==
            A23.GENERIC_128_SNAPSHOT_INDICES
        @test A23.B._snapshot_positions(
            capture, 32, geometry.frame_samples, A23.A.MODEM_FS) ==
            EXPECTED_PASS
        @test all(geometry.support_end_seconds .<= A23.CAPTURE_SECONDS)
        @test maximum(geometry.support_end_seconds) == 31.993854166666665
        @test geometry.support_end_seconds[128] ==
            geometry.support_end_seconds[32] == 31.993854166666665
        @test geometry.payload_seeds == collect(4:131)
        @test geometry.noise_seeds == collect(4:131)
        @test geometry.replay_seeds == collect(4:131)
        @test geometry.optimizer_seeds == fill(4, 128)
    end

    if "--probe" in ARGS
        rows, frame_traces, protected_traces = A23.probe_path(snrs=[0])
        A23.validate_path_rows(
            rows, frame_traces, protected_traces; snrs=[0])
        @test length(rows) == 5
        @test length(frame_traces) == 640
        @test length(protected_traces) == 256
        @test all(row.payload_bits_per_frame == 1_616 for row in rows)
        @test all(row.payload_bits == 206_848 for row in rows)
        @test all(row.payload_seed == row.noise_seed == row.replay_seed
                  for row in frame_traces)
        @test all(row.optimizer_seed == 4 for row in frame_traces)
        @test all(!row.decode_failure for row in frame_traces)
        @test all(!row.decode_failure for row in protected_traces)
    end
end
