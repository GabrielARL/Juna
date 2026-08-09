#!/usr/bin/env julia

include(joinpath(@__DIR__, "awgn020_sweep.jl"))
using .Awgn020Sweep
using Dates
const A = Awgn020Sweep

const EXPERIMENTS = get(
    ENV, "JUNA_AWGN020_OUTPUT_EXPERIMENTS", dirname(@__DIR__))
const FIRST_EXPERIMENT = joinpath(EXPERIMENTS, first(A.CONFIGURATIONS).id)
const CAMPAIGN_LOG = joinpath(FIRST_EXPERIMENT, "awgn020_sweep.log")
const SWEEP_SOURCE = joinpath(@__DIR__, "awgn020_sweep.jl")
const SOURCE_CONTRACT = joinpath(@__DIR__, "source_contract.json")

function marker(message::AbstractString)
    mkpath(dirname(CAMPAIGN_LOG))
    line = message * " " * string(Dates.now())
    println(line)
    open(CAMPAIGN_LOG, "a") do io
        println(io, line)
    end
    flush(stdout)
end

function csv_shape_valid(path::AbstractString, header, rows::Integer)
    isfile(path) && !islink(path) || return false
    lines = readlines(path)
    length(lines) == Int(rows) + 1 || return false
    first(lines) == join(header, ',') || return false
    columns = length(header)
    all(!isempty(strip(line)) && length(split(line, ',')) == columns
        for line in @view(lines[2:end]))
end

function result_paths(experiment_dir::AbstractString, channel::Symbol,
                      hydrophone::Integer; partial::Bool=false)
    stem = "$(channel)_hydrophone$(Int(hydrophone))"
    run_dir = joinpath(experiment_dir, "results", "runs", stem)
    suffix = partial ? ".partial" : ""
    (
        aggregate=joinpath(run_dir, A.AGGREGATE_BASENAME * suffix),
        frame_trace=joinpath(
            run_dir, stem * A.FRAME_TRACE_BASENAME_SUFFIX * suffix),
        protected_trace=joinpath(
            run_dir, stem * A.PROTECTED_TRACE_BASENAME_SUFFIX * suffix),
        contract=joinpath(
            run_dir, "awgn020_path_contract.txt" * suffix),
    )
end

function data_shape_valid(paths)
    csv_shape_valid(paths.aggregate, A.AGGREGATE_HEADER,
                    A.expected_aggregate_rows()) &&
    csv_shape_valid(paths.frame_trace, A.FRAME_TRACE_HEADER,
                    A.expected_frame_trace_rows()) &&
    csv_shape_valid(paths.protected_trace, A.PROTECTED_TRACE_HEADER,
                    A.expected_protected_trace_rows())
end

function expected_path_contract(spec, channel::Symbol, hydrophone::Integer,
                                paths)
    join((
        "campaign=AWGN-020",
        "experiment_id=$(spec.id)",
        "channel=$(channel)",
        "hydrophone=$(Int(hydrophone))",
        "aggregate_sha256=$(A.file_sha256(paths.aggregate))",
        "frame_trace_sha256=$(A.file_sha256(paths.frame_trace))",
        "protected_trace_sha256=$(A.file_sha256(paths.protected_trace))",
        "source_contract_sha256=$(A.file_sha256(SOURCE_CONTRACT))",
        "runner_sha256=$(A.file_sha256(@__FILE__))",
        "sweep_sha256=$(A.file_sha256(SWEEP_SOURCE))",
        "aggregate_rows=$(A.expected_aggregate_rows())",
        "frame_trace_rows=$(A.expected_frame_trace_rows())",
        "protected_trace_rows=$(A.expected_protected_trace_rows())",
        "capture_seconds=$(A.CAPTURE_SECONDS)",
        "snapshot_indices=$(join(A.SNAPSHOT_INDICES, ','))",
    ), '\n') * "\n"
end

function content_valid(spec, channel::Symbol, hydrophone::Integer, paths)
    data_shape_valid(paths) || return false
    isfile(paths.contract) && !islink(paths.contract) || return false
    read(paths.contract, String) ==
        expected_path_contract(spec, channel, hydrophone, paths)
end

function write_path_contract(destination::AbstractString, spec,
                             channel::Symbol, hydrophone::Integer, paths)
    mkpath(dirname(destination))
    open(destination, "w") do io
        write(io, expected_path_contract(spec, channel, hydrophone, paths))
    end
    destination
end

function promote_path(staged, final)
    mv(staged.aggregate, final.aggregate; force=true)
    mv(staged.frame_trace, final.frame_trace; force=true)
    mv(staged.protected_trace, final.protected_trace; force=true)
    mv(staged.contract, final.contract; force=true)
end

function run_configuration(spec)
    experiment_dir = joinpath(EXPERIMENTS, spec.id)
    for (channel, hydrophone) in A.PATHS
        final = result_paths(experiment_dir, channel, hydrophone)
        if content_valid(spec, channel, hydrophone, final)
            marker("SKIP_VALID AWGN-020 $(spec.id) $(channel) hydrophone " *
                   string(hydrophone))
            continue
        end
        staged = result_paths(
            experiment_dir, channel, hydrophone; partial=true)
        marker("PATH_START AWGN-020 $(spec.id) $(channel) hydrophone " *
               string(hydrophone))
        rows, frame_traces, protected_traces = A.run_path(
            channel, hydrophone, spec.config;
            data_dir=A.DATA_DIR,
            aggregate_destination=staged.aggregate,
            frame_trace_destination=staged.frame_trace,
            protected_trace_destination=staged.protected_trace)
        A.validate_path_rows(rows, frame_traces, protected_traces)
        data_shape_valid(staged) || error(
            "AWGN-020 staged path files failed exact shape contract")
        write_path_contract(
            staged.contract, spec, channel, hydrophone, staged)
        promote_path(staged, final)
        content_valid(spec, channel, hydrophone, final) || error(
            "AWGN-020 final path content contract differs")
        marker("PATH_VALID AWGN-020 $(spec.id) $(channel) hydrophone " *
               string(hydrophone))
        GC.gc()
    end
    builder = joinpath(@__DIR__, "build_results.py")
    validator = joinpath(@__DIR__, "validate_results.py")
    run(`python3 $builder --experiment-dir $experiment_dir`)
    run(`python3 $validator --experiment-dir $experiment_dir`)
    marker("CONFIGURATION_COMPLETE AWGN-020 $(spec.id)")
end

function main()
    if ARGS == ["contract"]
        A.require_contract(; verify_data=false)
        println("AWGN_020_CONTRACT_VALID configurations=1 paths=12")
        return
    end
    marker("AWGN_020_QUEUE_START")
    A.require_contract(; verify_data=true)
    requested = Set(ARGS)
    targets = isempty(requested) ? A.CONFIGURATIONS :
        [spec for spec in A.CONFIGURATIONS if spec.id in requested]
    length(targets) == (isempty(requested) ? length(A.CONFIGURATIONS) :
                        length(requested)) || error(
        "AWGN-020 received an unknown or duplicate experiment ID")
    marker("AWGN_020_COMPUTE_START")
    foreach(run_configuration, targets)
    if isempty(requested)
        matrix_validator = joinpath(@__DIR__, "validate_matrix.py")
        run(`python3 $matrix_validator`)
    end
    marker("AWGN_020_COMPUTE_COMPLETE")
    println("AWGN_020_MATRIX_COMPLETE configurations=", length(targets),
            " paths=", length(targets) * length(A.PATHS))
end

main()
