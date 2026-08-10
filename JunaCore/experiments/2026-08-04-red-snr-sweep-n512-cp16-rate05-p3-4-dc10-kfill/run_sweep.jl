#!/usr/bin/env julia

const SOURCE_EXPERIMENT = normpath(joinpath(
    @__DIR__, "..", "2026-08-04-red-snr-sweep"))
include(joinpath(SOURCE_EXPERIMENT, "snr_sweep.jl"))
using .SnrSweep

const FIXED_CONFIG = (
    nfft=512,
    cp=16,
    code_rate=0.5,
    outer_spacing=3,
    inner_spacing=4,
    check_degree=10,
    horizon=0,
)
const RESULT_LABEL = "configuration"
const PATHS = [(Symbol("red$channel"), lane)
               for channel in 1:4 for lane in 1:3]
const RECEIVERS = Set(("ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"))
const SNRS = Set(string(Float64(snr)) for snr in 0:2:30)

function csv_rows(path)
    lines = readlines(path)
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
                "inner_spacing", "check_degree", "horizon")
    all(haskey(index, key) for key in required) || return false
    expected = ("512", "16", "0.5", "3", "4", "10", "0")
    geometry = ("nfft", "cp", "code_rate", "outer_spacing",
                "inner_spacing", "check_degree", "horizon")
    all(row[index["channel"]] == String(channel) &&
        row[index["lane"]] == string(lane) &&
        row[index["seed"]] == "4" && row[index["frames"]] == "60" &&
        row[index["objective"]] == RESULT_LABEL &&
        Tuple(row[index[key]] for key in geometry) == expected for row in rows) ||
        return false
    Set(row[index["algorithm_id"]] for row in rows) == RECEIVERS || return false
    Set(row[index["snr_db"]] for row in rows) == SNRS || return false
    length(Set((row[index["algorithm_id"]], row[index["snr_db"]])
               for row in rows)) == 80
end

function trace_valid(path)
    isfile(path) || return false
    index, rows = csv_rows(path)
    length(rows) == 1920 || return false
    required = ("snr_db", "frame", "algorithm_id", "selection_reason")
    all(haskey(index, key) for key in required) || return false
    Set(row[index["algorithm_id"]] for row in rows) ==
        Set(("profiled_cz", "cwz_joint")) || return false
    Set(row[index["snr_db"]] for row in rows) == SNRS || return false
    Set(parse(Int, row[index["frame"]]) for row in rows) == Set(1:60) ||
        return false
    all(row[index["selection_reason"]] == "gradient_only" for row in rows) ||
        return false
    length(Set((row[index["algorithm_id"]], row[index["snr_db"]],
                row[index["frame"]]) for row in rows)) == 1920
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
        if aggregate_valid(aggregate, channel, lane) && trace_valid(trace)
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
        trace_valid(trace_partial) ||
            error("$(channel) hydrophone $(lane): trace validation failed")
        mv(aggregate_partial, aggregate; force=true)
        mv(trace_partial, trace; force=true)
        println("PATH_VALID ", channel, " hydrophone ", lane)
        flush(stdout)
        GC.gc()
    end
    println("FIXED_GEOMETRY_MATRIX_COMPLETE")
end

main()
