#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "awgn027_sweep.jl"))
using .Awgn027Sweep
const A27 = Awgn027Sweep

const EXPECTED_SNAPSHOTS = [
    1, 99, 197, 294, 392, 490, 588, 686,
    783, 881, 979, 1077, 1175, 1272, 1370, 1468,
    1566, 1664, 1761, 1859, 1957, 2055, 2153, 2250,
    2348, 2446, 2544, 2642, 2740, 2837, 2935, 3033,
    3131, 3229, 3326, 3424, 3522, 3620, 3718, 3815,
    3913, 4011, 4109, 4207, 4304, 4402, 4500,
]

@testset verbose=true "AWGN-027 N2048 rate-one-half pilots-ten complete-capture sweep" begin
    @testset "approved campaign contract" begin
        verify_data =
            "--capture-contract" in ARGS || "--probe" in ARGS
        A27.require_contract(; verify_data)
        @test A27.DECISION == "AWGN-027"
        @test A27.FAMILY ==
            "2026-08-10-red-awgn-full-capture-frames47-crc-no-harm"
        @test length(A27.CONFIGURATIONS) == 1
        @test only(A27.CONFIGURATIONS).id ==
            "2026-08-10-red-awgn-full-capture-frames47-crc-no-harm-n2048-cp64-rate05-p10-10-dc14-kfill-pfft4"
        config = only(A27.CONFIGURATIONS).config
        @test config == (
            nfft=2048, cp=64, code_rate=0.5,
            outer_spacing=10, inner_spacing=10,
            check_degree=14, horizon=0,
        )
        @test length(A27.PATHS) == 12
        @test collect(A27.SNR_DB) == collect(0:2:30)
        @test A27.FRAMES == 47
        @test A27.CAPTURE_SECONDS == 47.78125
        @test A27.SEED == 4
        @test A27.SNAPSHOT_INDICES == EXPECTED_SNAPSHOTS
        @test issorted(A27.SNAPSHOT_INDICES)
        @test allunique(A27.SNAPSHOT_INDICES)
        @test first(A27.SNAPSHOT_INDICES) == 1
        @test last(A27.SNAPSHOT_INDICES) == 4_500
        @test A27.EXPECTED_PAYLOAD_BITS_PER_FRAME == 3_296
        @test A27.EXPECTED_PAYLOAD_BITS_PER_POINT == 154_912
        @test A27.expected_aggregate_rows() == 80
        @test A27.expected_frame_trace_rows() == 3_760
        @test A27.expected_protected_trace_rows() == 1_504
        @test length(A27.PATHS) * A27.expected_aggregate_rows() == 960
        @test length(A27.PATHS) * A27.expected_frame_trace_rows() == 45_120
        @test length(A27.PATHS) * A27.expected_protected_trace_rows() ==
            18_048
        A27.require_public_receiver_contract()

        source = read(joinpath(@__DIR__, "awgn027_sweep.jl"), String)
        @test length(findall("function _snapshot_positions", source)) == 1
        @test !occursin("_compare_reference_rows", source)
        @test !occursin("REFERENCE_RESULTS", source)
        contract = read(joinpath(@__DIR__, "source_contract.json"), String)
        @test occursin("\"schedule_source\": \"AWGN-023B\"", contract)
        @test occursin("\"outcome_equality_required\": false", contract)
        @test occursin(
            "\"snapshot_schedule_equality_required\": false", contract)
        @test occursin("\"frame_samples\": 8320", contract)
        @test occursin("\"capture_position_stop\": 4500", contract)
        @test occursin(
            "\"final_replay_support_end_seconds\": 47.7734375", contract)
        @test occursin("\"payload_bits_per_frame\": 3296", contract)
        @test occursin("\"payload_bits_per_point\": 154912", contract)

        runner = read(joinpath(@__DIR__, "run_awgn027.jl"), String)
        @test occursin("suffix = partial ? \".partial\" : \"\"", runner)
        @test occursin("write_path_contract(\n            staged.contract", runner)
        moves = [
            findfirst("mv(staged.$name", runner)
            for name in ("aggregate", "frame_trace", "protected_trace", "contract")
        ]
        @test all(!isnothing, moves)
        @test issorted(first.(moves))
        @test count("mv(staged.", runner) == 4
        @test occursin("awgn027_path_contract.txt\" * suffix", runner)
    end

    if "--capture-contract" in ARGS || "--probe" in ARGS
        capture = A27.load_full_capture(:red1, 1)
        geometry = A27.require_snapshot_contract(
            capture, only(A27.CONFIGURATIONS).config)
        @test size(capture.h) == (768, 4_588)
        @test length(capture.phase) == 917_600
        @test geometry.snapshot_indices == EXPECTED_SNAPSHOTS
        @test geometry.position_stop == 4_500
        @test geometry.frame_samples == 8_320
        @test geometry.payload_bits_per_frame == 3_296
        @test A27.B._snapshot_positions(
            capture, A27.FRAMES, geometry.frame_samples, A27.A.MODEM_FS) ==
            EXPECTED_SNAPSHOTS
        @test all(geometry.support_end_seconds .<= A27.CAPTURE_SECONDS)
        @test last(geometry.support_end_seconds) == 47.7734375
        @test geometry.payload_seeds == collect(4:50)
        @test geometry.noise_seeds == collect(4:50)
        @test geometry.replay_seeds == collect(4:50)
        @test geometry.optimizer_seeds == fill(4, 47)
    end

    if "--probe" in ARGS
        rows, frame_traces, protected_traces = A27.probe_path(snrs=[0])
        A27.validate_path_rows(
            rows, frame_traces, protected_traces; snrs=[0])
        @test length(rows) == 5
        @test length(frame_traces) == 235
        @test length(protected_traces) == 94
        @test all(row.payload_bits_per_frame == 3_296 for row in rows)
        @test all(row.payload_bits == 154_912 for row in rows)
        @test all(row.payload_seed == row.noise_seed == row.replay_seed
                  for row in frame_traces)
        @test all(row.optimizer_seed == 4 for row in frame_traces)
        @test all(!row.decode_failure for row in frame_traces)
        @test all(!row.decode_failure for row in protected_traces)
    end
end
