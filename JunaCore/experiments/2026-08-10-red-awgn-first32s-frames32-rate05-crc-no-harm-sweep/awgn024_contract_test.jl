#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "awgn024_sweep.jl"))
using .Awgn024Sweep
const A24 = Awgn024Sweep

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

@testset verbose=true "AWGN-024 rate-one-half first-thirty-two-second sweep" begin
    @testset "approved campaign contract" begin
        verify_data =
            "--capture-contract" in ARGS || "--probe" in ARGS
        A24.require_contract(; verify_data)
        @test A24.DECISION == "AWGN-024"
        @test A24.FAMILY ==
            "2026-08-10-red-awgn-first32s-frames32-rate05-crc-no-harm"
        @test length(A24.CONFIGURATIONS) == 1
        config = only(A24.CONFIGURATIONS).config
        @test config == (
            nfft=1024, cp=64, code_rate=0.5,
            outer_spacing=5, inner_spacing=5,
            check_degree=14, horizon=0,
        )
        @test length(A24.PATHS) == 12
        @test collect(A24.SNR_DB) == collect(0:2:30)
        @test A24.FRAMES == 32
        @test A24.CAPTURE_SECONDS == 32.0
        @test A24.SEED == 4
        @test A24.SNAPSHOT_INDICES == EXPECTED_SNAPSHOTS
        @test A24.AWGN022_SNAPSHOT_INDICES == EXPECTED_SNAPSHOTS
        @test A24.EXPECTED_PAYLOAD_BITS_PER_FRAME == 3_248
        @test A24.EXPECTED_PAYLOAD_BITS_PER_POINT == 103_936
        @test A24.expected_aggregate_rows() == 80
        @test A24.expected_frame_trace_rows() == 2_560
        @test A24.expected_protected_trace_rows() == 1_024
        A24.require_public_receiver_contract()

        source = read(joinpath(@__DIR__, "awgn024_sweep.jl"), String)
        @test length(findall("function _snapshot_positions", source)) == 1
        @test !occursin("_compare_reference_rows", source)
        @test !occursin("AWGN022_REFERENCE_RESULTS", source)
        contract = read(joinpath(@__DIR__, "source_contract.json"), String)
        @test occursin("\"schedule_source\": \"AWGN-022\"", contract)
        @test occursin("\"outcome_equality_required\": false", contract)

        runner = read(joinpath(@__DIR__, "run_awgn024.jl"), String)
        @test occursin("suffix = partial ? \".partial\" : \"\"", runner)
        @test occursin("write_path_contract(\n            staged.contract", runner)
        moves = [
            findfirst("mv(staged.$name", runner)
            for name in ("aggregate", "frame_trace", "protected_trace", "contract")
        ]
        @test all(!isnothing, moves)
        @test issorted(first.(moves))
        @test count("mv(staged.", runner) == 4
        @test occursin("awgn024_path_contract.txt\" * suffix", runner)
    end

    if "--capture-contract" in ARGS || "--probe" in ARGS
        capture = A24.load_first32s_capture(:red1, 1)
        geometry = A24.require_snapshot_contract(
            capture, only(A24.CONFIGURATIONS).config)
        @test size(capture.h) == (768, 3_073)
        @test length(capture.phase) == 614_600
        @test geometry.snapshot_indices == EXPECTED_SNAPSHOTS
        @test geometry.position_stop == 2_973
        @test geometry.frame_samples == 9_536
        @test geometry.payload_bits_per_frame == 3_248
        @test A24.B._snapshot_positions(
            capture, A24.FRAMES, geometry.frame_samples, A24.A.MODEM_FS) ==
            EXPECTED_SNAPSHOTS
        @test all(geometry.support_end_seconds .<= A24.CAPTURE_SECONDS)
        @test last(geometry.support_end_seconds) == 31.993854166666665
        @test geometry.payload_seeds == collect(4:35)
        @test geometry.noise_seeds == collect(4:35)
        @test geometry.replay_seeds == collect(4:35)
        @test geometry.optimizer_seeds == fill(4, 32)
    end

    if "--probe" in ARGS
        rows, frame_traces, protected_traces = A24.probe_path(snrs=[0])
        A24.validate_path_rows(
            rows, frame_traces, protected_traces; snrs=[0])
        @test length(rows) == 5
        @test length(frame_traces) == 160
        @test length(protected_traces) == 64
        @test all(row.payload_bits_per_frame == 3_248 for row in rows)
        @test all(row.payload_seed == row.noise_seed == row.replay_seed
                  for row in frame_traces)
        @test all(row.optimizer_seed == 4 for row in frame_traces)
        @test all(!row.decode_failure for row in frame_traces)
        @test all(!row.decode_failure for row in protected_traces)
    end
end
