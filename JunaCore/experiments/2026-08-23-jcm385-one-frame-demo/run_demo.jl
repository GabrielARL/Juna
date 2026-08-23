#!/usr/bin/env julia

using JunaCore
using SHA

const SOURCE_WORKTREE = "/home/gabiel/Documents/GitHub/Juna-worktrees/codex-direct-cz-ci"
const SOURCE_COMMIT = "827bbb217e717291090b014b8aba8ea2df4c6dbf"
const ACQUISITION_BASE_COMMIT = "261a4418327b2bbef77eeaad9e621d280f4617d3"
const PREVIOUS_SOURCE_COMMIT = "c7fce64af71fb75a23cffaa300a41171379622ae"
const SUPERSEDED_RESULT_SHA256 = "681add3a01a8a2e928c458b1221f7fb61fc7ba2d5618629ae12a14c7385dbfcb"
const HELPER_DIR = "/home/gabiel/Documents/GitHub/Juna-worktrees/codex-direct-cz-ci/JunaCore/experiments/2026-08-04-red-snr-sweep"
const BENCHMARK_PORT = joinpath(HELPER_DIR, "benchmark_port.jl")
const REPLAY_LANE = joinpath(HELPER_DIR, "replay_lane.jl")
const DIRECT_SOURCE = joinpath(SOURCE_WORKTREE, "JunaCore", "src", "juna", "direct_cz_frame.jl")
const RED_MAT = "/home/gabiel/Documents/GitHub/Juna/JunaCore/experiments/2026-08-01-red-lite-search/data/red_1.mat"
const BLUE_MAT = "/home/gabiel/Documents/GitHub/replaychan/data/blue_1.mat"
const OUTPUT = joinpath(@__DIR__, "frame_results.csv")
const MANIFEST = joinpath(@__DIR__, "demo_manifest.json")

const EXPECTED_HASHES = Dict(
    "benchmark_port" => "404685dcb0b98c5667b5391fdb8ee211f970db16880b5d566f9cd38a2b4b6ee8",
    "replay_lane" => "78f9e16f1cedd7512ae88c77de23022b2f506939fccfe723dea75d7c9fac31cf",
    "red_mat" => "09556b49e453a351f72b5c71435aab0048f68a80ab3b926ca4353dab47e89c45",
    "blue_mat" => "639830f78ea044b877284dc0058f1c25179ba2448c06f228c9f0a62d0b2162de",
    "direct_cz_source" => "6004c01aac1d98c685f204ac4b065e91af0d6307940dab9444a0b8014d8e7342",
)

include(BENCHMARK_PORT)
const B = BenchmarkPort
const J = JunaCore.Juna
const M = JunaCore.Modulations

const DIRECT_IDENTITY = (
    public_constructor="JunaCore.JunaDirectCzFrame.Modulation",
    concrete_receiver_type="JunaCore.Juna.DirectCzFrameModulation",
    descriptor_profile="lite",
    decode_adapter="frame_decode_function",
    objective_identity="direct_cz_frame",
    trace_accessor="JunaCore.Juna._direct_cz_last_trace",
    source_path=DIRECT_SOURCE,
    source_sha256=EXPECTED_HASHES["direct_cz_source"],
)

const RECEIVER_IDS = (:ofdm_fec, :pfft, :lite, :profiled_cz, :direct_cz)
const RECEIVER_LABELS = Dict(
    :ofdm_fec => "OFDM+LDPC",
    :pfft => "Partial-FFT+LDPC",
    :lite => "JUNA-Iterative",
    :profiled_cz => "profiled JUNA-(C,z)",
    :direct_cz => "JUNA-Direct-(C,z)",
)
const BENCHMARK_NAMES = Dict(
    "OFDM+LDPC" => :ofdm_fec,
    "Partial-FFT+LDPC" => :pfft,
    "JUNA-Iterative" => :lite,
    "profiled JUNA-(C,z)" => :profiled_cz,
    "JUNA-Direct-(C,z)" => :direct_cz,
)

function sha256_file(path::AbstractString)
    open(path, "r") do stream
        bytes2hex(SHA.sha256(stream))
    end
end

function require_equal(actual, expected, label)
    actual == expected || error("$label differs: expected $expected, got $actual")
end

function source_preflight()
    require_equal(readchomp(`git -C $SOURCE_WORKTREE rev-parse HEAD`),
                  SOURCE_COMMIT, "source commit")
    isempty(readchomp(`git -C $SOURCE_WORKTREE status --porcelain`)) ||
        error("source worktree is not clean")
    require_equal(realpath(pathof(JunaCore)),
                  realpath(joinpath(SOURCE_WORKTREE, "JunaCore", "src", "JunaCore.jl")),
                  "loaded JunaCore source")
    require_equal(readchomp(`git -C $SOURCE_WORKTREE merge-base $SOURCE_COMMIT $PREVIOUS_SOURCE_COMMIT`),
                  ACQUISITION_BASE_COMMIT, "acquisition merge base")
    for (label, path) in (
        ("benchmark_port", BENCHMARK_PORT),
        ("replay_lane", REPLAY_LANE),
        ("red_mat", RED_MAT),
        ("blue_mat", BLUE_MAT),
        ("direct_cz_source", DIRECT_SOURCE),
    )
        isfile(path) && !islink(path) || error("missing regular $label: $path")
        require_equal(sha256_file(path), EXPECTED_HASHES[label], "$label SHA-256")
    end

    isdefined(JunaCore, :JunaDirectCzFrame) ||
        error("JunaDirectCzFrame public facade is missing")
    JunaCore.JunaDirectCzFrame.Modulation === J.DirectCzFrameModulation ||
        error("JunaDirectCzFrame public facade differs")
    direct = JunaCore.JunaDirectCzFrame.Modulation(frame_duration_s=1.0)
    string(typeof(direct)) == DIRECT_IDENTITY.concrete_receiver_type ||
        error("Direct concrete receiver type differs")
    M.refinement_objective(direct) === :direct_cz_frame ||
        error("Direct refinement objective differs")
    direct.base.cz_crc_no_harm || error("Direct receiver lacks CRC no-harm selection")
    !direct.base.cz_crc_gate || error("Direct receiver unexpectedly uses the profiled CRC gate")
    direct.base.cz_gradient_only || error("Direct receiver boundary is not gradient-only")
end

function algorithms(partial_fft_bands::Int)
    (
        (id=:ofdm_fec, name=RECEIVER_LABELS[:ofdm_fec], profile=:standard,
         partial_fft_parts=4, partial_fft_bands=partial_fft_bands),
        (id=:pfft, name=RECEIVER_LABELS[:pfft], profile=:pfft,
         partial_fft_parts=4, partial_fft_bands=partial_fft_bands),
        (id=:lite, name=RECEIVER_LABELS[:lite], profile=:lite,
         partial_fft_parts=4, partial_fft_bands=partial_fft_bands),
        (id=:profiled_cz, name=RECEIVER_LABELS[:profiled_cz], profile=:profiled_cz,
         cz_crc_gate=true, cz_gate_selection_only=false,
         cz_gradient_only=false, partial_fft_parts=4,
         partial_fft_bands=partial_fft_bands),
        # The harness owns the shared Lite-shaped code/layout; the decode
        # boundary substitutes the public Direct C,z receiver below.
        (id=:direct_cz, name=RECEIVER_LABELS[:direct_cz], profile=:lite,
         partial_fft_parts=4,
         partial_fft_bands=partial_fft_bands),
    )
end

function configure_direct_receiver(capture, nfft::Int, bandwidth::Float64,
                                   partial_fft_bands::Int)
    receiver = JunaCore.JunaDirectCzFrame.Modulation(frame_duration_s=1.0)
    geometry = B._effective_bandwidth_geometry(capture, bandwidth, 1.0)
    B._configure_modem!(
        receiver.base, capture.fc, bandwidth, :passband_replay;
        nfft=nfft,
        cp=64,
        partial_fft_parts=4,
        partial_fft_bands=partial_fft_bands,
        code_rate=0.25,
        check_degree=14,
        ldpc_method=:auto,
        ldpc_seed=51_001,
        ldpc_no4cycle=true,
        sync_profile=:lfm,
        frame_duration_s=1.0,
        outer_pilot_ratio=1 / 6,
        inner_pilot_ratio=1 / 8,
        bw=geometry.normalized_bw,
    )
    M.isvalid(receiver, capture.fc, bandwidth) ||
        error("public Direct receiver is invalid for N=$nfft")
    receiver
end

function direct_trace_fields(trace)
    (
        selection_reason=String(trace.selection_reason),
        standard_crc_valid=Bool(trace.standard_crc_valid),
        rescue_executed=Bool(trace.rescue_executed),
        rescue_crc_valid=Bool(trace.rescue_crc_valid),
        gradient_checkpoints=Int(trace.gradient_checkpoints),
        accepted_steps=Int(trace.accepted_steps),
        rejected_steps=Int(trace.rejected_steps),
    )
end

function run_condition(dataset::String, channel::String, capture, nfft::Int,
                       bandwidth::Float64, partial_fft_bands::Int,
                       input_digest::String)
    frame_rows = NamedTuple[]
    descriptors = algorithms(partial_fft_bands)
    direct_receiver = configure_direct_receiver(
        capture, nfft, bandwidth, partial_fft_bands)
    direct_trace = Ref{Any}(nothing)
    concrete_types = Dict{Symbol,String}()

    function decode(item, payload_bits, decoder_input, fc, fs)
        receiver_id = Symbol(item.descriptor.id)
        if receiver_id !== :direct_cz
            concrete_types[receiver_id] = string(typeof(item.receiver))
            return first(M.demodulate(
                item.receiver, payload_bits, decoder_input, fc, fs))
        end

        # benchmark_port has already assigned the common transmitter code and
        # layout to this Lite-shaped slot. Reuse those exact objects at the
        # public Direct receiver boundary so all five arms share one frame.
        source_base = item.receiver
        source_base.code === nothing && error("Direct adapter source code is missing")
        source_base.layout === nothing && error("Direct adapter source layout is missing")
        base = direct_receiver.base
        base.code = source_base.code
        base.layout = source_base.layout
        base.bp_scratch = nothing
        base.cz_restart_seed = source_base.cz_restart_seed
        direct_receiver.direct_cz_trace = nothing
        concrete_types[receiver_id] = string(typeof(direct_receiver))
        metrics = first(M.demodulate(
            direct_receiver, payload_bits, decoder_input, fc, fs))
        direct_trace[] = direct_trace_fields(J._direct_cz_last_trace(direct_receiver))
        metrics
    end

    aggregate_rows = B.benchmark_frame_capture(
        capture;
        channel_id=channel,
        frames=1,
        frame_blocks=nothing,
        frame_duration_s=1.0,
        frame_crc_bits=16,
        algorithms=descriptors,
        snr_db=20.0,
        seed=4,
        modem_fs=bandwidth,
        modem_profile=:passband_replay,
        sync_profile=:lfm,
        nfft=nfft,
        cp=64,
        code_rate=0.25,
        check_degree=14,
        ldpc_method=:auto,
        ldpc_seed=51_001,
        ldpc_no4cycle=true,
        outer_pilot_ratio=1 / 6,
        inner_pilot_ratio=1 / 8,
        warmup=false,
        replay_source_digest=input_digest,
        frame_decode_function=decode,
        frame_sink=row -> push!(frame_rows, row),
    )
    length(frame_rows) == length(RECEIVER_IDS) ||
        error("$dataset N=$nfft emitted $(length(frame_rows)) frame rows")
    length(aggregate_rows) == length(RECEIVER_IDS) ||
        error("$dataset N=$nfft emitted $(length(aggregate_rows)) aggregate rows")
    direct_trace[] === nothing && error("$dataset N=$nfft emitted no Direct trace")
    Set(keys(concrete_types)) == Set(RECEIVER_IDS) ||
        error("$dataset N=$nfft did not execute all receiver decoders")

    by_name = Dict(String(row.algorithm) => row for row in frame_rows)
    rows = NamedTuple[]
    for receiver_id in RECEIVER_IDS
        label = RECEIVER_LABELS[receiver_id]
        haskey(by_name, label) || error("missing $label frame row")
        row = by_name[label]
        row.frame == 1 || error("unexpected frame index")
        row.receiver == 1 || error("unexpected hydrophone")
        success = Bool(row.success) && !Bool(row.decode_failure)
        payload = Int(row.payload_bits)
        errors = Int(row.bit_errors)
        is_direct = receiver_id === :direct_cz
        trace = is_direct ? direct_trace[] : nothing
        push!(rows, (
            dataset=dataset,
            channel=channel,
            hydrophone=1,
            configuration="n$(nfft)-cp64-p6-8",
            nfft=nfft,
            cp=64,
            code_rate=0.25,
            outer_spacing=6,
            inner_spacing=8,
            partial_fft_bands=partial_fft_bands,
            snr_db=20.0,
            frame=1,
            receiver_id=String(receiver_id),
            receiver_label=label,
            bandwidth_hz=bandwidth,
            useful_symbol_seconds=nfft / bandwidth,
            cp_seconds=64 / bandwidth,
            subcarrier_spacing_hz=bandwidth / nfft,
            frame_duration_seconds=Float64(row.frame_duration_seconds),
            frame_samples=Int(row.frame_samples),
            payload_bits=payload,
            bit_errors=errors,
            ber=errors / payload,
            success=success,
            configured_rate_bit_per_s_hz=success ? payload / bandwidth : 0.0,
            decode_failure=Bool(row.decode_failure),
            decode_seconds=Float64(row.decode_seconds),
            selection_reason=is_direct ? trace.selection_reason :
                (ismissing(row.selection_reason) ? "" : String(row.selection_reason)),
            public_constructor=is_direct ? DIRECT_IDENTITY.public_constructor : "benchmark-native",
            concrete_receiver_type=concrete_types[receiver_id],
            descriptor_profile=String(only(
                descriptor.profile for descriptor in descriptors
                if descriptor.id === receiver_id)),
            decode_adapter=is_direct ? DIRECT_IDENTITY.decode_adapter : "benchmark-native",
            objective_identity=is_direct ? DIRECT_IDENTITY.objective_identity : "",
            trace_accessor=is_direct ? DIRECT_IDENTITY.trace_accessor : "",
            receiver_source_path=is_direct ? DIRECT_IDENTITY.source_path : "",
            receiver_source_sha256=is_direct ? DIRECT_IDENTITY.source_sha256 : "",
            standard_crc_valid=is_direct ? trace.standard_crc_valid : "",
            rescue_executed=is_direct ? trace.rescue_executed : "",
            rescue_crc_valid=is_direct ? trace.rescue_crc_valid : "",
            gradient_checkpoints=is_direct ? trace.gradient_checkpoints : "",
            accepted_steps=is_direct ? trace.accepted_steps : "",
            rejected_steps=is_direct ? trace.rejected_steps : "",
            snapshot_index=Int(row.snapshot_index),
            payload_seed=Int(row.payload_seed),
            noise_seed=Int(row.noise_seed),
            replay_seed=Int(row.replay_seed),
            optimizer_seed=Int(row.optimizer_seed),
            workload_digest=String(row.workload_digest),
            payload_digest=String(row.payload_digest),
            code_digest=String(row.code_digest),
            transmitted_digest=String(row.transmitted_digest),
            received_digest=String(row.received_digest),
            noise_digest=String(row.noise_digest),
            replay_digest=String(row.replay_digest),
        ))
    end
    println("condition complete: dataset=$dataset channel=$channel H1 N=$nfft rows=5")
    flush(stdout)
    rows
end

function csv_escape(value)
    text = string(value)
    if occursin(',', text) || occursin('"', text) || occursin('\n', text)
        return "\"" * replace(text, "\"" => "\"\"") * "\""
    end
    text
end

function write_csv(path::AbstractString, rows)
    isempty(rows) && error("cannot write empty results")
    names = propertynames(first(rows))
    temporary = path * ".tmp"
    open(temporary, "w") do stream
        println(stream, join(String.(names), ','))
        for row in rows
            println(stream, join((csv_escape(getproperty(row, name)) for name in names), ','))
        end
        flush(stream)
    end
    mv(temporary, path; force=true)
end

json_escape(text::AbstractString) = replace(
    replace(replace(replace(String(text), "\\" => "\\\\"), "\"" => "\\\""),
            "\n" => "\\n"), "\r" => "\\r")

function write_manifest(path::AbstractString, result_hash::String, runner_hash::String)
    entries = (
        ("benchmark_port", BENCHMARK_PORT),
        ("replay_lane", REPLAY_LANE),
        ("red_mat", RED_MAT),
        ("blue_mat", BLUE_MAT),
        ("direct_cz_source", DIRECT_SOURCE),
    )
    input_lines = String[]
    for (index, (label, input_path)) in enumerate(entries)
        suffix = index == length(entries) ? "" : ","
        push!(input_lines,
            "    \"$label\": {\"path\": \"$(json_escape(input_path))\", " *
            "\"sha256\": \"$(EXPECTED_HASHES[label])\"}$suffix")
    end
    content = join((
        "{",
        "  \"approval_id\": \"JCM-385\",",
        "  \"correction_approval_id\": \"JCM-386\",",
        "  \"superseded_result_sha256\": \"$SUPERSEDED_RESULT_SHA256\",",
        "  \"status\": \"complete\",",
        "  \"illustration_only\": true,",
        "  \"not_general_evidence\": true,",
        "  \"scope\": \"red1-h1-blue1-h1-n512-n1024\",",
        "  \"frames_per_condition\": 1,",
        "  \"snr_db\": 20,",
        "  \"seed\": 4,",
        "  \"noise_pairing\": \"shared across receivers within each condition; not byte-identical across configurations\",",
        "  \"blue_replay_note\": \"Blue 1 was preserved by the later acquisition-CFO refresh\",",
        "  \"source\": {",
        "    \"worktree\": \"$(json_escape(SOURCE_WORKTREE))\",",
        "    \"commit\": \"$SOURCE_COMMIT\",",
        "    \"acquisition_base_commit\": \"$ACQUISITION_BASE_COMMIT\",",
        "    \"clean\": true,",
        "    \"juna_core_path\": \"$(json_escape(joinpath(SOURCE_WORKTREE, "JunaCore")))\"",
        "  },",
        "  \"direct_receiver_identity\": {",
        "    \"public_constructor\": \"$(DIRECT_IDENTITY.public_constructor)\",",
        "    \"concrete_receiver_type\": \"$(DIRECT_IDENTITY.concrete_receiver_type)\",",
        "    \"descriptor_profile\": \"$(DIRECT_IDENTITY.descriptor_profile)\",",
        "    \"decode_adapter\": \"$(DIRECT_IDENTITY.decode_adapter)\",",
        "    \"objective_identity\": \"$(DIRECT_IDENTITY.objective_identity)\",",
        "    \"trace_accessor\": \"$(DIRECT_IDENTITY.trace_accessor)\",",
        "    \"source_path\": \"$(json_escape(DIRECT_IDENTITY.source_path))\",",
        "    \"source_sha256\": \"$(DIRECT_IDENTITY.source_sha256)\"",
        "  },",
        "  \"inputs\": {",
        input_lines...,
        "  },",
        "  \"outputs\": {",
        "    \"runner_sha256\": \"$runner_hash\",",
        "    \"frame_results\": {",
        "      \"path\": \"$(json_escape(OUTPUT))\",",
        "      \"sha256\": \"$result_hash\",",
        "      \"rows\": 20",
        "    }",
        "  }",
        "}",
        "",
    ), '\n')
    temporary = path * ".tmp"
    open(temporary, "w") do stream
        write(stream, content)
        flush(stream)
    end
    mv(temporary, path; force=true)
end

function install_blue_native_sync!()
    target = B.Juna
    Core.eval(target, quote
        _synclen(m::Modulation) = m.sync ? 1042 : 0
        _sync_overhead(m::Modulation, fs) = m.sync ? 2084 : 0
    end)
end

function main()
    source_preflight()
    rows = NamedTuple[]

    red_capture = B.load_capture(RED_MAT; receiver=1)
    for nfft in (512, 1024)
        append!(rows, run_condition(
            "red", "red1", red_capture, nfft, 9_600.0, 6,
            EXPECTED_HASHES["red_mat"],
        ))
    end

    install_blue_native_sync!()
    blue_capture = B.load_capture(BLUE_MAT; receiver=1)
    for nfft in (512, 1024)
        # The sync methods are installed at run time, so enter the latest
        # Julia method world for the Blue calls.
        append!(rows, Base.invokelatest(run_condition,
            "blue", "blue1", blue_capture, nfft, 4_882.8125, 16,
            EXPECTED_HASHES["blue_mat"],
        ))
    end

    length(rows) == 20 || error("expected 20 rows, got $(length(rows))")
    staging = mktempdir(@__DIR__; prefix=".jcm386-direct-")
    try
        staged_output = joinpath(staging, basename(OUTPUT))
        staged_manifest = joinpath(staging, basename(MANIFEST))
        write_csv(staged_output, rows)
        write_manifest(
            staged_manifest, sha256_file(staged_output), sha256_file(@__FILE__))
        mv(staged_output, OUTPUT; force=true)
        mv(staged_manifest, MANIFEST; force=true)
    finally
        rm(staging; recursive=true, force=true)
    end
    println("JCM386_DIRECT_CORRECTION_BUILT conditions=4 rows=20 receivers=5 frames=1")
end

main()
