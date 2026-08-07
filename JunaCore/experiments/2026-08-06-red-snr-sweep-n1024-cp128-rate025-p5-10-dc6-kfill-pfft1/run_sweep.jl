#!/usr/bin/env julia

ENV["SWEEP_PARTIAL_FFT_PARTS"] = "1"

const SOURCE_EXPERIMENT = normpath(joinpath(
    @__DIR__, "..", "2026-08-04-red-snr-sweep"))
include(joinpath(SOURCE_EXPERIMENT, "snr_sweep.jl"))
using .SnrSweep

const FIXED_CONFIG = (
    nfft=1024,
    cp=128,
    code_rate=0.25,
    outer_spacing=5,
    inner_spacing=10,
    check_degree=6,
    horizon=0,
)
const EXPECTED_GEOMETRY = ("1024", "128", "0.25", "5", "10", "6", "0")
const EXPECTED_PAYLOAD_BITS_PER_FRAME = 1452
const EXPECTED_PARTIAL_FFT_PARTS = 1
const RESULT_LABEL = "configuration"
const PATHS = [(Symbol("red$channel"), lane)
               for channel in 1:4 for lane in 1:3]
const RECEIVERS = Set(("ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"))
const PROFILED_RECEIVERS = Set(("profiled_cz", "cwz_joint"))
const SNRS = Set(string(Float64(snr)) for snr in 0:2:30)

function csv_rows(path)
    lines = readlines(path)
    isempty(lines) && return Dict{String,Int}(), Vector{Vector{SubString{String}}}()
    header = split(first(lines), ',')
    index = Dict(name => i for (i, name) in pairs(header))
    index, [split(line, ',') for line in lines[2:end] if !isempty(strip(line))]
end

function aggregate_valid(path, channel, lane)
    isfile(path) || return false
    index, rows = csv_rows(path)
    length(rows) == 80 || return false
    required = ("channel", "lane", "snr_db", "algorithm_id", "seed", "frames",
                "objective", "nfft", "cp", "code_rate", "outer_spacing",
                "inner_spacing", "check_degree", "horizon",
                "partial_fft_parts", "partial_fft_bands",
                "payload_bits_per_frame", "successful_frames", "psr",
                "payload_bits", "bit_errors", "ber", "decode_failures")
    all(haskey(index, key) for key in required) || return false
    geometry = ("nfft", "cp", "code_rate", "outer_spacing",
                "inner_spacing", "check_degree", "horizon")
    all(row[index["channel"]] == String(channel) &&
        row[index["lane"]] == string(lane) &&
        row[index["seed"]] == "4" && row[index["frames"]] == "60" &&
        row[index["objective"]] == RESULT_LABEL &&
        Tuple(row[index[key]] for key in geometry) == EXPECTED_GEOMETRY &&
        parse(Int, row[index["partial_fft_parts"]]) ==
            EXPECTED_PARTIAL_FFT_PARTS &&
        parse(Int, row[index["partial_fft_bands"]]) > 0 &&
        parse(Int, row[index["payload_bits_per_frame"]]) ==
            EXPECTED_PAYLOAD_BITS_PER_FRAME for row in rows) || return false
    Set(row[index["algorithm_id"]] for row in rows) == RECEIVERS || return false
    Set(row[index["snr_db"]] for row in rows) == SNRS || return false
    length(Set((row[index["algorithm_id"]], row[index["snr_db"]])
               for row in rows)) == 80 || return false
    all(rows) do row
        payload = parse(Int, row[index["payload_bits"]])
        errors = parse(Int, row[index["bit_errors"]])
        successes = parse(Int, row[index["successful_frames"]])
        payload == 60 * EXPECTED_PAYLOAD_BITS_PER_FRAME &&
            isapprox(parse(Float64, row[index["ber"]]), errors / payload;
                     atol=1e-15, rtol=0) &&
            isapprox(parse(Float64, row[index["psr"]]), successes / 60;
                     atol=1e-15, rtol=0) &&
            parse(Int, row[index["decode_failures"]]) >= 0
    end
end

function trace_valid(path, channel, lane)
    isfile(path) || return false
    index, rows = csv_rows(path)
    length(rows) == 1920 || return false
    required = ("workload_id", "snr_db", "frame", "algorithm_id",
                "selection_reason", "bit_errors", "success", "decode_failure",
                "selected_iteration", "partial_fft_parts", "partial_fft_bands")
    all(haskey(index, key) for key in required) || return false
    Set(row[index["algorithm_id"]] for row in rows) == PROFILED_RECEIVERS ||
        return false
    Set(row[index["snr_db"]] for row in rows) == SNRS || return false
    Set(parse(Int, row[index["frame"]]) for row in rows) == Set(1:60) ||
        return false
    all(row[index["selection_reason"]] == "gradient_only" for row in rows) ||
        return false
    all(parse(Int, row[index["partial_fft_parts"]]) ==
        EXPECTED_PARTIAL_FFT_PARTS &&
        parse(Int, row[index["partial_fft_bands"]]) > 0 for row in rows) ||
        return false
    all(row[index["workload_id"]] ==
        "$(channel):lane$(lane):snr$(parse(Float64, row[index["snr_db"]])):seed4:frame$(parse(Int, row[index["frame"]]))"
        for row in rows) || return false
    length(Set((row[index["algorithm_id"]], row[index["snr_db"]],
                row[index["frame"]]) for row in rows)) == 1920 || return false
    all(row -> parse(Int, row[index["bit_errors"]]) >= 0 &&
               parse(Int, row[index["selected_iteration"]]) >= 0 &&
               row[index["success"]] in ("true", "false") &&
               row[index["decode_failure"]] in ("true", "false"), rows)
end

function pair_valid(aggregate_path, trace_path)
    aggregate_index, aggregate_rows = csv_rows(aggregate_path)
    trace_index, trace_rows = csv_rows(trace_path)
    for receiver in PROFILED_RECEIVERS, snr in SNRS
        aggregates = filter(aggregate_rows) do row
            row[aggregate_index["algorithm_id"]] == receiver &&
                row[aggregate_index["snr_db"]] == snr
        end
        length(aggregates) == 1 || return false
        aggregate = only(aggregates)
        frames = filter(trace_rows) do row
            row[trace_index["algorithm_id"]] == receiver &&
                row[trace_index["snr_db"]] == snr
        end
        length(frames) == 60 || return false
        sum(parse(Int, row[trace_index["bit_errors"]]) for row in frames) ==
            parse(Int, aggregate[aggregate_index["bit_errors"]]) || return false
        count(row -> row[trace_index["success"]] == "true", frames) ==
            parse(Int, aggregate[aggregate_index["successful_frames"]]) ||
            return false
        count(row -> row[trace_index["decode_failure"]] == "true", frames) ==
            parse(Int, aggregate[aggregate_index["decode_failures"]]) ||
            return false
    end
    true
end

function main()
    isempty(get(ENV, "SWEEP_ARMS", "")) ||
        error("SWEEP_ARMS must be unset so all five receivers run")
    for (channel, lane) in PATHS
        stage = joinpath(@__DIR__, "results", "runs",
                         "$(channel)_hydrophone$(lane)")
        mkpath(stage)
        aggregate = joinpath(stage, "red_snr_sweep_uwa_noise_configuration.csv")
        trace = joinpath(stage, "$(channel)_hydrophone$(lane)_selection_trace.csv")
        if aggregate_valid(aggregate, channel, lane) &&
                trace_valid(trace, channel, lane) &&
                pair_valid(aggregate, trace)
            println("SKIP_VALID ", channel, " hydrophone ", lane)
            flush(stdout)
            continue
        end

        aggregate_partial = aggregate * ".partial"
        trace_partial = trace * ".partial"
        println("PATH_START ", channel, " hydrophone ", lane)
        flush(stdout)
        rows = SnrSweep.run(channel, lane, :ber;
            config_override=FIXED_CONFIG,
            result_label=RESULT_LABEL,
            destination=aggregate_partial,
            trace_destination=trace_partial)
        length(rows) == 80 ||
            error("$(channel) hydrophone $(lane): aggregate rows differ")
        aggregate_valid(aggregate_partial, channel, lane) ||
            error("$(channel) hydrophone $(lane): aggregate validation failed")
        trace_valid(trace_partial, channel, lane) ||
            error("$(channel) hydrophone $(lane): trace validation failed")
        pair_valid(aggregate_partial, trace_partial) ||
            error("$(channel) hydrophone $(lane): aggregate/trace reconciliation failed")
        mv(aggregate_partial, aggregate; force=true)
        mv(trace_partial, trace; force=true)
        println("PATH_VALID ", channel, " hydrophone ", lane)
        flush(stdout)
        GC.gc()
    end
    println("FIXED_GEOMETRY_MATRIX_COMPLETE")
end

main()
