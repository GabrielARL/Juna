#!/usr/bin/env julia

using Dates
using SHA

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const SOURCE_ROOT = get(ENV, "JUNA_N512_NO_HARM_SOURCE_ROOT", REPO_ROOT)
const SHARED_HARNESS = joinpath(
    SOURCE_ROOT, "JunaCore", "experiments",
    "2026-08-08-red-awgn-snr-sweep")
const DATA_DIR = get(
    ENV, "JUNA_RED_DATA_DIR",
    joinpath(SOURCE_ROOT, "JunaCore", "experiments",
             "2026-08-01-red-lite-search", "data"))
const CAPTURE_SECONDS = parse(
    Float64, get(ENV, "JUNA_N512_NO_HARM_CAPTURE_SECONDS", "32"))
CAPTURE_SECONDS > 0 && isinteger(CAPTURE_SECONDS) || error(
    "JUNA_N512_NO_HARM_CAPTURE_SECONDS must be a positive whole number")
const CAPTURE_LABEL = string(Int(CAPTURE_SECONDS))
const EXPERIMENT_ID =
    "2026-08-10-red-awgn-first$(CAPTURE_LABEL)s-frames32-crc-gated-no-harm-" *
    "n512-cp64-rate025-p5-5-dc14-kfill-pfft4"
const OUTPUT_EXPERIMENTS = get(
    ENV, "JUNA_N512_NO_HARM_OUTPUT_EXPERIMENTS",
    normpath(joinpath(@__DIR__, "..", "experiments")))
const EXPERIMENT_DIR = joinpath(OUTPUT_EXPERIMENTS, EXPERIMENT_ID)
const RESULT_BASENAME =
    "red_snr_sweep_awgn_first$(CAPTURE_LABEL)s_frames32_configuration.csv"
const FRAME_TRACE_SUFFIX = "_frame_trace.csv"
const SELECTION_TRACE_SUFFIX = "_selection_trace.csv"
const PATHS = [(Symbol("red$channel"), lane)
               for channel in 1:4 for lane in 1:3]
const CONFIG = (
    nfft=512, cp=64, code_rate=0.25,
    outer_spacing=5, inner_spacing=5,
    check_degree=14, horizon=0,
)

ENV["SWEEP_FRAMES"] = "32"
ENV["SWEEP_PARTIAL_FFT_PARTS"] = "4"
ENV["SWEEP_ARMS"] = ""
const AWGN_SWEEP_SOURCE = joinpath(SHARED_HARNESS, "awgn_sweep.jl")
isfile(AWGN_SWEEP_SOURCE) || error(
    "missing AWGN sweep dependency at $AWGN_SWEEP_SOURCE; set " *
    "JUNA_N512_NO_HARM_SOURCE_ROOT to a compatible checkout")
include(AWGN_SWEEP_SOURCE)
using .AwgnSweep
const A = AwgnSweep
const B = A.B
const Juna = B.Juna
const Modulations = B.Modulations

const ALGORITHMS = (
    (id=:ofdm_fec, name="OFDM + FEC", profile=:ofdm_fec,
     partial_fft_parts=4),
    (id=:pfft, name="Partial-FFT + FEC", profile=:pfft,
     partial_fft_parts=4),
    (id=:lite, name="JUNA-Lite", profile=:lite,
     partial_fft_parts=4),
    (id=:profiled_cz, name="JUNA (C,z) CRC no-harm", profile=:profiled_cz,
     cz_crc_gate=true, cz_gate_selection_only=false,
     cz_gradient_only=false, partial_fft_parts=4),
    (id=:cwz_joint, name="Juna joint (C,W,z) CRC no-harm",
     profile=:profiled_cz,
     cz_em_enabled=true, cz_independent_w=false, cz_bp_feedback=0.5,
     cz_vp_gradient=true, cz_conditioned_joint=true,
     cz_crc_gate=true, cz_gate_selection_only=false,
     cz_gradient_only=false, partial_fft_parts=4),
)
const IDS = Tuple(String(item.id) for item in ALGORITHMS)
const PROTECTED = Set((:profiled_cz, :cwz_joint))
const MARKER_LOCK = ReentrantLock()
const RUN_LOG_NAME = length(ARGS) >= 3 && ARGS[1] == "worker" ?
    "n512_crc_no_harm_$(ARGS[3]).log" : "n512_crc_no_harm_sweep.log"
const SNAPSHOT_INDICES_32 = [
    1, 96, 190, 285, 385, 480, 574, 669,
    769, 864, 958, 1053, 1153, 1248, 1342, 1437,
    1537, 1632, 1726, 1821, 1921, 2016, 2110, 2205,
    2305, 2400, 2494, 2589, 2689, 2784, 2878, 2973,
]
const AGGREGATE_HEADER = (
    "channel", "lane", "snr_db", "algorithm_id", "seed", "frames",
    "objective", "noise_model", "nfft", "cp", "code_rate",
    "outer_spacing", "inner_spacing", "check_degree", "horizon",
    "partial_fft_parts", "partial_fft_bands", "payload_bits_per_frame",
    "successful_frames", "psr", "payload_bits", "bit_errors", "ber",
    "decode_failures", "decode_seconds", "effective_rate_bps",
    "capture_start_seconds", "capture_stop_seconds",
    "capture_tap_snapshots", "capture_phase_samples",
)
const FRAME_TRACE_HEADER = (
    "workload_id", "snr_db", "frame", "algorithm_id", "noise_model",
    "capture_start_seconds", "capture_stop_seconds", "snapshot_index",
    "snapshot_seconds", "replay_support_end_seconds",
    "frame_duration_seconds", "frame_samples", "payload_bits",
    "payload_seed", "noise_seed", "replay_seed", "optimizer_seed",
    "bit_errors", "success", "decode_failure", "partial_fft_parts",
    "partial_fft_bands",
)
const PROTECTED_TRACE_HEADER = (
    "workload_id", "snr_db", "frame", "algorithm_id", "noise_model",
    "capture_start_seconds", "capture_stop_seconds", "snapshot_index",
    "snapshot_seconds", "replay_support_end_seconds",
    "frame_duration_seconds", "bit_errors", "success", "decode_failure",
    "selected_source", "selection_reason", "standard_crc_valid",
    "rescue_executed", "rescue_is_gradient", "rescue_crc_valid",
    "gradient_checkpoints", "selected_iteration", "optimized_variables",
    "partial_fft_parts", "partial_fft_bands",
)

@eval B begin
    const _N512_CRC_NO_HARM_POSITIONS_32 = $SNAPSHOT_INDICES_32
    const _N512_CRC_NO_HARM_CAPTURE_SECONDS = $CAPTURE_SECONDS
    function _snapshot_positions(capture::ReplayCapture, packets::Integer,
                                 waveform_length::Integer, modem_fs::Real)
        count = Int(packets)
        count == 1 && return [1]
        count == 32 || throw(ArgumentError(
            "N512 no-harm runner supports one probe frame or 32 result frames"))
        _channel_samples, stop = _capture_position_limit(
            capture, Int(waveform_length) + 22, Float64(modem_fs))
        if _N512_CRC_NO_HARM_CAPTURE_SECONDS == 32.0
            last(_N512_CRC_NO_HARM_POSITIONS_32) <= stop || throw(ArgumentError(
                "first32 schedule needs position 2973, capture supports $stop"))
            return copy(_N512_CRC_NO_HARM_POSITIONS_32)
        end
        positions = round.(Int, range(1, stop; length=count))
        allunique(positions) || throw(ArgumentError(
            "capture-window packet positions are not distinct"))
        positions
    end
end

file_sha256(path) = open(path) do io
    bytes2hex(sha256(io))
end

snapshot_seconds(capture, snapshot) =
    (Int(snapshot) - 1) * capture.step / capture.fs

function replay_support_end_seconds(capture, snapshot, frame_samples)
    passband_samples = Int(frame_samples) + 22
    channel_samples = ceil(Int, passband_samples * capture.fs / 9_600.0)
    last_offset = channel_samples + size(capture.h, 1) - 2
    snapshot_seconds(capture, snapshot) + last_offset / capture.fs
end

function cropped_capture(channel::Symbol, lane::Integer)
    file = joinpath(DATA_DIR, getproperty(A.CHANNEL_FILES, channel))
    full = B.load_capture(file; receiver=Int(lane))
    tap_snapshots = floor(Int, CAPTURE_SECONDS * full.fs / full.step) + 1
    phase_samples = floor(Int, CAPTURE_SECONDS * full.fs) + full.step
    expected_taps = floor(Int, CAPTURE_SECONDS * 96) + 1
    expected_phase = floor(Int, CAPTURE_SECONDS * 19_200) + 200
    tap_snapshots == expected_taps || error("tap crop differs")
    phase_samples == expected_phase || error("phase crop differs")
    B.ReplayLane.ReplayCapture(
        full.h[:, 1:tap_snapshots], full.phase[1:phase_samples],
        full.fs, full.fc, full.step, full.receiver,
        full.name * "_first$(CAPTURE_LABEL)s")
end

function write_csv(destination, rows, header)
    mkpath(dirname(destination))
    open(destination, "w") do io
        println(io, join(header, ','))
        for row in rows
            println(io, join((getproperty(row, Symbol(name)) for name in header), ','))
        end
    end
end

function marker(message)
    lock(MARKER_LOCK) do
        mkpath(EXPERIMENT_DIR)
        line = message * " " * string(Dates.now())
        println(line)
        open(joinpath(EXPERIMENT_DIR, RUN_LOG_NAME), "a") do io
            println(io, line)
        end
        flush(stdout)
    end
end

function result_paths(channel::Symbol, lane::Integer; partial=false)
    stem = "$(channel)_hydrophone$(Int(lane))"
    run_dir = joinpath(EXPERIMENT_DIR, "results", "runs", stem)
    suffix = partial ? ".partial" : ""
    (
        aggregate=joinpath(run_dir, RESULT_BASENAME * suffix),
        frame_trace=joinpath(run_dir, stem * FRAME_TRACE_SUFFIX * suffix),
        protected_trace=joinpath(
            run_dir, stem * SELECTION_TRACE_SUFFIX * suffix),
        contract=joinpath(run_dir, "n512_crc_no_harm_path_contract.txt" * suffix),
    )
end

function csv_shape(path, header, rows)
    isfile(path) || return false
    lines = readlines(path)
    length(lines) == rows + 1 || return false
    first(lines) == join(header, ',') || return false
    all(length(split(line, ',')) == length(header) for line in lines[2:end])
end

function data_shape(paths)
    csv_shape(paths.aggregate, AGGREGATE_HEADER, 80) &&
    csv_shape(paths.frame_trace, FRAME_TRACE_HEADER, 2_560) &&
    csv_shape(paths.protected_trace, PROTECTED_TRACE_HEADER, 1_024) &&
    isfile(paths.contract)
end

function path_contract(channel, lane, paths)
    join((
        "campaign=N512-CRC-GATED-NO-HARM-FIRST$(CAPTURE_LABEL)S",
        "experiment_id=$EXPERIMENT_ID",
        "channel=$channel",
        "hydrophone=$lane",
        "aggregate_sha256=$(file_sha256(paths.aggregate))",
        "frame_trace_sha256=$(file_sha256(paths.frame_trace))",
        "selection_trace_sha256=$(file_sha256(paths.protected_trace))",
        "aggregate_rows=80",
        "frame_trace_rows=2560",
        "selection_trace_rows=1024",
        "selection_rule=standard_crc_valid|crc_rescue|standard_fallback",
    ), '\n') * "\n"
end

function content_valid(channel, lane, paths)
    data_shape(paths) || return false
    read(paths.contract, String) == path_contract(channel, lane, paths)
end

function promote(staged, final)
    for field in keys(staged)
        mv(getproperty(staged, field), getproperty(final, field); force=true)
    end
end

function normalize_trace(trace)
    reason = trace.selection_reason
    normalized = reason === :lite_crc_valid_skip ? :standard_crc_valid :
        reason === :crc_rescue ? :crc_rescue :
        reason === :crc_fallback ? :standard_fallback :
        error("unexpected CRC no-harm selection reason: $reason")
    standard_valid = Bool(trace.lite_crc_valid)
    rescue_executed = normalized !== :standard_crc_valid
    rescue_valid = rescue_executed && Bool(trace.gradient_crc_valid)
    selected_gradient = Bool(trace.selected_gradient)
    normalized === :standard_crc_valid &&
        (standard_valid && !rescue_executed && !selected_gradient) ||
        normalized === :crc_rescue &&
        (!standard_valid && rescue_valid && selected_gradient) ||
        normalized === :standard_fallback &&
        (!standard_valid && !rescue_valid && !selected_gradient) ||
        error("CRC no-harm selection fields are inconsistent")
    (
        selected_source=selected_gradient ? :gradient : :standard,
        selection_reason=normalized,
        standard_crc_valid=standard_valid,
        rescue_executed,
        rescue_is_gradient=rescue_executed,
        rescue_crc_valid=rescue_valid,
        gradient_checkpoints=rescue_executed ? length(trace.candidates) : 0,
        selected_iteration=selected_gradient ? Int(trace.selected_iteration) : 0,
    )
end

function protected_trace_row(row, id, capture, decision)
    (
        workload_id=row.workload_id, snr_db=row.snr_db, frame=row.frame,
        algorithm_id=String(id), noise_model="awgn",
        capture_start_seconds=0.0, capture_stop_seconds=CAPTURE_SECONDS,
        snapshot_index=row.snapshot_index,
        snapshot_seconds=snapshot_seconds(capture, row.snapshot_index),
        replay_support_end_seconds=replay_support_end_seconds(
            capture, row.snapshot_index, row.frame_samples),
        frame_duration_seconds=row.frame_duration_seconds,
        bit_errors=row.bit_errors, success=row.success,
        decode_failure=row.decode_failure,
        selected_source=String(decision.selected_source),
        selection_reason=String(decision.selection_reason),
        standard_crc_valid=decision.standard_crc_valid,
        rescue_executed=decision.rescue_executed,
        rescue_is_gradient=decision.rescue_is_gradient,
        rescue_crc_valid=decision.rescue_crc_valid,
        gradient_checkpoints=decision.gradient_checkpoints,
        selected_iteration=decision.selected_iteration,
        optimized_variables=id === :profiled_cz ? "C+z" : "C+W+z",
        partial_fft_parts=row.partial_fft_parts,
        partial_fft_bands=row.partial_fft_bands,
    )
end

function frame_trace_row(row, id, capture)
    (
        workload_id=row.workload_id, snr_db=row.snr_db, frame=row.frame,
        algorithm_id=String(id), noise_model="awgn",
        capture_start_seconds=0.0, capture_stop_seconds=CAPTURE_SECONDS,
        snapshot_index=row.snapshot_index,
        snapshot_seconds=snapshot_seconds(capture, row.snapshot_index),
        replay_support_end_seconds=replay_support_end_seconds(
            capture, row.snapshot_index, row.frame_samples),
        frame_duration_seconds=row.frame_duration_seconds,
        frame_samples=row.frame_samples, payload_bits=row.payload_bits,
        payload_seed=row.payload_seed, noise_seed=row.noise_seed,
        replay_seed=row.replay_seed, optimizer_seed=row.optimizer_seed,
        bit_errors=row.bit_errors, success=row.success,
        decode_failure=row.decode_failure,
        partial_fft_parts=row.partial_fft_parts,
        partial_fft_bands=row.partial_fft_bands,
    )
end

function evaluate(capture, channel, lane, snr; frames=32)
    decisions = Dict{Symbol,Any}()
    frame_rows = NamedTuple[]
    protected_rows = NamedTuple[]
    ids_by_name = Dict(item.name => Symbol(item.id) for item in ALGORITHMS)

    function decode(item, payload_bits, input, fc, fs)
        metrics = first(Modulations.demodulate(
            item.receiver, payload_bits, input, fc, fs))
        id = Symbol(item.descriptor.id)
        if id in PROTECTED
            trace = Juna._cz_gradient_last_trace(item.receiver)
            decisions[id] = normalize_trace(trace)
        end
        metrics
    end

    function sink(row)
        id = ids_by_name[row.algorithm]
        push!(frame_rows, frame_trace_row(row, id, capture))
        if id in PROTECTED
            haskey(decisions, id) || error("missing protected no-harm decision")
            push!(protected_rows, protected_trace_row(
                row, id, capture, pop!(decisions, id)))
        end
    end

    measured = B.benchmark_frame_capture(
        capture;
        channel_id=String(channel), frames=frames,
        frame_blocks=nothing, frame_duration_s=1.0, frame_crc_bits=16,
        algorithms=ALGORITHMS, snr_db=Float64(snr), seed=4,
        modem_fs=9_600.0, modem_profile=:passband_replay,
        sync_profile=:lfm, nfft=CONFIG.nfft, cp=CONFIG.cp,
        code_rate=CONFIG.code_rate, check_degree=CONFIG.check_degree,
        ldpc_method=:auto, ldpc_seed=51_001, ldpc_no4cycle=true,
        outer_pilot_ratio=1 / CONFIG.outer_spacing,
        inner_pilot_ratio=1 / CONFIG.inner_spacing,
        frame_decode_function=decode, frame_sink=sink)
    isempty(decisions) || error("unconsumed no-harm decisions")
    rows = [(
        channel=String(channel), lane=Int(lane), snr_db=Float64(snr),
        algorithm_id=String(ALGORITHMS[index].id), seed=4, frames=frames,
        objective="configuration", noise_model="awgn",
        nfft=512, cp=64, code_rate=0.25,
        outer_spacing=5, inner_spacing=5, check_degree=14, horizon=0,
        partial_fft_parts=Int(row.partial_fft_parts),
        partial_fft_bands=Int(row.partial_fft_bands),
        payload_bits_per_frame=Int(row.payload_bits_per_frame),
        successful_frames=Int(row.successful_frames), psr=Float64(row.psr),
        payload_bits=Int(row.payload_bits), bit_errors=Int(row.bit_errors),
        ber=Float64(row.ber), decode_failures=Int(row.decode_failures),
        decode_seconds=Float64(row.mean_decode_seconds_per_frame),
        effective_rate_bps=Float64(row.effective_rate_bps),
        capture_start_seconds=0.0, capture_stop_seconds=CAPTURE_SECONDS,
        capture_tap_snapshots=size(capture.h, 2),
        capture_phase_samples=length(capture.phase),
    ) for (index, row) in pairs(measured)]
    rows, frame_rows, protected_rows
end

function validate_rows(rows, frames, protected; full=true)
    expected_snrs = full ? collect(0:2:30) : sort(unique(row.snr_db for row in rows))
    expected_frames = full ? 32 : maximum(row.frame for row in frames)
    length(rows) == 5 * length(expected_snrs) || error("aggregate count differs")
    length(frames) == 5 * length(expected_snrs) * expected_frames ||
        error("frame trace count differs")
    length(protected) == 2 * length(expected_snrs) * expected_frames ||
        error("selection trace count differs")
    all(!row.decode_failure for row in frames) || error("decode failure present")
    all(!row.decode_failure for row in protected) || error("protected failure present")
    for row in protected
        reason = row.selection_reason
        if reason == "standard_crc_valid"
            row.selected_source == "standard" && row.standard_crc_valid &&
                !row.rescue_executed && !row.rescue_crc_valid &&
                row.gradient_checkpoints == 0 || error("standard short circuit differs")
        elseif reason == "crc_rescue"
            row.selected_source == "gradient" && !row.standard_crc_valid &&
                row.rescue_executed && row.rescue_crc_valid &&
                row.gradient_checkpoints > 0 || error("CRC rescue differs")
        elseif reason == "standard_fallback"
            row.selected_source == "standard" && !row.standard_crc_valid &&
                row.rescue_executed && !row.rescue_crc_valid &&
                row.gradient_checkpoints > 0 || error("standard fallback differs")
        else
            error("unknown no-harm selection reason")
        end
        if row.selected_source == "standard"
            paired = [item for item in frames
                      if item.workload_id == row.workload_id &&
                         item.algorithm_id == "lite"]
            length(paired) == 1 || error(
                "expected one paired Lite row for $(row.workload_id), " *
                "found $(length(paired))")
            lite = only(paired)
            row.bit_errors == lite.bit_errors || error(
                "standard no-harm output differs from paired Lite")
        end
    end
    true
end

function evaluate_path(channel, lane)
    final = result_paths(channel, lane)
    content_valid(channel, lane, final) &&
        return marker("SKIP_VALID $channel hydrophone $lane")
    marker("PATH_START $channel hydrophone $lane")
    capture = cropped_capture(channel, lane)
    expected_taps = floor(Int, CAPTURE_SECONDS * 96) + 1
    expected_phase = floor(Int, CAPTURE_SECONDS * 19_200) + 200
    size(capture.h) == (768, expected_taps) || error("tap crop differs")
    length(capture.phase) == expected_phase || error("phase crop differs")
    snrs = collect(0:2:30)
    # `benchmark_frame_capture` is not safe for concurrent multi-frame calls:
    # its frame callbacks can acquire the SNR label from another active call.
    # Parallelism is therefore across isolated Julia worker processes, while
    # every worker evaluates its assigned paths' SNRs sequentially.
    groups = 1
    chunks = [snrs]
    aggregates = Vector{Vector{NamedTuple}}(undef, groups)
    frame_traces = Vector{Vector{NamedTuple}}(undef, groups)
    selection_traces = Vector{Vector{NamedTuple}}(undef, groups)
    tasks = map(eachindex(chunks)) do index
        chunk = copy(chunks[index])
        Threads.@spawn begin
            local_aggregates = NamedTuple[]
            local_frames = NamedTuple[]
            local_selections = NamedTuple[]
            for snr in chunk
                rows, frames, selections = evaluate(
                    capture, channel, lane, snr)
                append!(local_aggregates, rows)
                append!(local_frames, frames)
                append!(local_selections, selections)
                marker("SNR_VALID $channel hydrophone $lane snr=$snr")
            end
            (local_aggregates, local_frames, local_selections)
        end
    end
    for index in eachindex(tasks)
        aggregates[index], frame_traces[index], selection_traces[index] =
            fetch(tasks[index])
    end
    rows = sort(reduce(vcat, aggregates); by=row -> (row.snr_db, row.algorithm_id))
    frames = sort(reduce(vcat, frame_traces);
                  by=row -> (row.snr_db, row.algorithm_id, row.frame))
    selections = sort(reduce(vcat, selection_traces);
                      by=row -> (row.snr_db, row.algorithm_id, row.frame))
    staged = result_paths(channel, lane; partial=true)
    write_csv(staged.aggregate, rows, AGGREGATE_HEADER)
    write_csv(staged.frame_trace, frames, FRAME_TRACE_HEADER)
    write_csv(staged.protected_trace, selections, PROTECTED_TRACE_HEADER)
    validate_rows(rows, frames, selections)
    open(staged.contract, "w") do io
        write(io, path_contract(channel, lane, staged))
    end
    promote(staged, final)
    content_valid(channel, lane, final) || error("promoted path contract differs")
    marker("PATH_VALID $channel hydrophone $lane")
    GC.gc()
end

function contract_probe()
    capture = cropped_capture(:red1, 1)
    all_rows = NamedTuple[]
    all_frames = NamedTuple[]
    all_selections = NamedTuple[]
    for snr in (0, 30)
        rows, frames, selections = evaluate(capture, :red1, 1, snr; frames=1)
        append!(all_rows, rows)
        append!(all_frames, frames)
        append!(all_selections, selections)
    end
    validate_rows(all_rows, all_frames, all_selections; full=false)
    reasons = sort(unique(row.selection_reason for row in all_selections))
    println("N512_CRC_NO_HARM_CONTRACT_PASS receivers=5 payload=",
            only(unique(row.payload_bits_per_frame for row in all_rows)),
            " reasons=", join(reasons, ','))
end

function parallel_contract_probe()
    capture = cropped_capture(:red1, 1)
    snrs = [0, 2, 4, 6]
    tasks = map(snrs) do snr
        Threads.@spawn evaluate(capture, :red1, 1, snr; frames=1)
    end
    rows = NamedTuple[]
    frames = NamedTuple[]
    selections = NamedTuple[]
    for task in tasks
        task_rows, task_frames, task_selections = fetch(task)
        append!(rows, task_rows)
        append!(frames, task_frames)
        append!(selections, task_selections)
    end
    sort(unique(row.snr_db for row in rows)) == Float64.(snrs) ||
        error("parallel aggregate SNR labels collided")
    sort(unique(row.snr_db for row in frames)) == Float64.(snrs) ||
        error("parallel trace SNR labels collided")
    validate_rows(rows, frames, selections; full=false)
    println("N512_CRC_NO_HARM_PARALLEL_CONTRACT_PASS snrs=0,2,4,6")
end

function main()
    if ARGS == ["contract"]
        contract_probe()
        return
    elseif ARGS == ["parallel-contract"]
        parallel_contract_probe()
        return
    end
    selected_paths = if length(ARGS) >= 2 && ARGS[1] == "worker"
        indices = parse.(Int, split(ARGS[2], ','))
        all(index -> index in eachindex(PATHS), indices) ||
            error("worker path index outside 1:$(length(PATHS))")
        PATHS[indices]
    else
        PATHS
    end
    marker("N512_CRC_NO_HARM_START paths=$(length(selected_paths))")
    foreach(path -> evaluate_path(path...), selected_paths)
    marker("N512_CRC_NO_HARM_COMPUTE_COMPLETE paths=$(length(selected_paths))")
end

main()
