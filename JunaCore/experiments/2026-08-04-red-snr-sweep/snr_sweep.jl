#!/usr/bin/env julia
#
# BER versus added-noise SNR over red1-4 x hydrophones 1-3, five receivers.
#
# CL-28: twelve curves, one per capture-lane path, each held at that path's own
# best-BER geometry from the 20 dB search. No aggregate curve, so no mixing of
# operating points.
# CL-29/CL-30: noise is the uwa-channels mixing model from red_noise.mat --
# alpha = 1.7, impulsive, correlated across the three hydrophones -- injected
# in place of the harness's AWGN. This is a different channel-application path
# from the 20 dB confirmation, and the two must not be plotted together.
#
# SNR follows Mahmood & Chitre, JOE 42(3) 2017 eq. (35): signal power over the
# alpha-stable pseudo-power 2*delta^2. Second-order moments do not exist at
# alpha < 2, so a variance-based SNR would be meaningless.
#
# Usage:
#   julia --project=. -t auto snr_sweep.jl smoke
#   julia --project=. -t auto snr_sweep.jl

module SnrSweep

include(joinpath(@__DIR__, "benchmark_port.jl"))
include(joinpath(@__DIR__, "uwa_noise.jl"))
using .BenchmarkPort
using .UwaNoise
using Random
const B = BenchmarkPort

const SNR_DB = 0:2:30
const FRAMES = 60
const SEED = 4                     # the search's reserved report seed
const FRAME_DURATION_S = 1.0
const FRAME_CRC_BITS = 16
const MODEM_FS = 9_600.0
const CHANNEL_IDS = (:red1, :red2, :red3, :red4)
const LANES = (1, 2, 3)
const CHANNEL_FILES = (red1="red_1.mat", red2="red_2.mat",
                       red3="red_3.mat", red4="red_4.mat")
const SEARCH = normpath(joinpath(
    @__DIR__, "..", "2026-08-01-red-lite-search"))
const NOISE_MAT = joinpath(SEARCH, "data", "red_noise.mat")
const OBJECTIVE_LABEL = Ref("min-BER")
const CZ_RESULTS = SEARCH

const PARTIAL_FFT_PARTS = let
    raw = get(ENV, "SWEEP_PARTIAL_FFT_PARTS", "4")
    value = tryparse(Int, raw)
    value === nothing && error("SWEEP_PARTIAL_FFT_PARTS must be an integer")
    value > 0 || error("SWEEP_PARTIAL_FFT_PARTS must be positive")
    value
end

const ALGORITHMS = (
    (id=:ofdm_fec, name="OFDM + FEC", profile=:ofdm_fec,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    (id=:pfft, name="Partial-FFT + FEC", profile=:pfft,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    (id=:lite, name="JUNA-Lite", profile=:lite,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    (id=:profiled_cz, name="JUNA (C,z) Joint gradient", profile=:profiled_cz,
     cz_crc_gate=false, cz_gradient_only=true,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    (id=:cwz_joint, name="Juna joint (C,W,z)", profile=:profiled_cz,
     cz_em_enabled=true, cz_independent_w=false, cz_bp_feedback=0.5,
     cz_vp_gradient=true, cz_conditioned_joint=true,
     cz_crc_gate=false, cz_gradient_only=true,
     partial_fft_parts=PARTIAL_FFT_PARTS),
)

# SWEEP_ARMS=cwz_joint runs a subset, so one arm can be measured without
# recomputing the arms that are already finished.
const _ARM_FILTER = split(get(ENV, "SWEEP_ARMS", ""), ','; keepempty=false)
const SELECTED = isempty(_ARM_FILTER) ? ALGORITHMS :
    Tuple(a for a in ALGORITHMS if String(a.id) in _ARM_FILTER)

const CONFIG_KEYS = ("nfft", "cp", "code_rate", "outer_spacing",
                     "inner_spacing", "check_degree", "horizon")

"""Best geometry per path under one objective, from the 20 dB confirmation.

`:ber`  pools bit errors over every arm on a configuration and takes the
        lowest pooled BER. CL-28's rule.
`:rate` takes each configuration's best arm by mean effective rate and keeps
        the highest. This is the search's own ranking, so it reproduces the
        Results page winner.

The two objectives disagree sharply: minimum BER buys its errors back with
code rate and a bigger FFT, and gives up throughput to do it.
"""
function best_geometries(objective::Symbol=:ber)
    sources = [joinpath(SEARCH, "results",
                        "red_config_finalists_20db_seeds6to7.csv"),
               joinpath(SEARCH, "results_pfft",
                        "red_config_finalists_20db_seeds6to7.csv"),
               joinpath(CZ_RESULTS, "results_cz",
                        "red_profiled_cz_confirm_20db_seeds6to7.csv")]
    errors = Dict{Tuple,Int}()
    bits = Dict{Tuple,Int}()
    rate_sum = Dict{Tuple,Float64}()
    rate_n = Dict{Tuple,Int}()
    failures = Dict{Tuple,Int}()
    for source in sources
        isfile(source) || continue
        lines = readlines(source)
        header = split(lines[1], ',')
        index = Dict(name => i for (i, name) in pairs(header))
        for line in lines[2:end]
            isempty(strip(line)) && continue
            cells = split(line, ',')
            cells[index["algorithm_id"]] == "adaptive_lite" && continue
            key = (Symbol(cells[index["channel"]]),
                   parse(Int, cells[index["lane"]]),
                   Tuple(cells[index[k]] for k in CONFIG_KEYS))
            errors[key] = get(errors, key, 0) +
                parse(Int, cells[index["bit_errors"]])
            bits[key] = get(bits, key, 0) +
                parse(Int, cells[index["payload_bits"]])
            arm_key = (key..., cells[index["algorithm_id"]])
            rate_sum[arm_key] = get(rate_sum, arm_key, 0.0) +
                parse(Float64, cells[index["effective_rate_bps"]])
            rate_n[arm_key] = get(rate_n, arm_key, 0) + 1
            failures[arm_key] = get(failures, arm_key, 0) +
                parse(Int, cells[index["decode_failures"]])
        end
    end
    # Best mean effective rate achieved on each configuration, over its arms.
    config_rate = Dict{Tuple,Float64}()
    for (arm_key, total) in rate_sum
        rate_n[arm_key] == 2 || continue
        failures[arm_key] == 0 || continue
        key = arm_key[1:3]
        mean_rate = total / 2
        config_rate[key] = max(get(config_rate, key, -Inf), mean_rate)
    end

    best = Dict{Tuple{Symbol,Int},Any}()
    for (key, bit_count) in bits
        bit_count == 0 && continue
        ber = errors[key] / bit_count
        rate = get(config_rate, key, -Inf)
        path = (key[1], key[2])
        better = if objective === :rate
            rate > get(best, path, (rate=-Inf,)).rate
        else
            !haskey(best, path) || ber < best[path].ber
        end
        if better
            cells = key[3]
            best[path] = (ber=ber, rate=rate,
                          nfft=parse(Int, cells[1]), cp=parse(Int, cells[2]),
                          code_rate=parse(Float64, cells[3]),
                          outer_spacing=parse(Int, cells[4]),
                          inner_spacing=parse(Int, cells[5]),
                          check_degree=parse(Int, cells[6]),
                          horizon=parse(Int, cells[7]))
        end
    end
    best
end

"""Install the mixing-model noise for one hydrophone, then restore."""
function with_uwa_noise(body, model, lane::Integer, fs::Real;
                        gain=UwaNoise._chain_scale_gain(model, fs))
    task_local_storage(B.NOISE_OVERRIDE_KEY,
        (n, noise_power, rng) ->
            sqrt(noise_power) .* UwaNoise.baseband_noise(rng, model, lane, n,
                                                         fs; scale_gain=gain)) do
        body()
    end
end

function _evaluate(capture, channel_id, lane, config, snr_db;
                   frames=FRAMES, frame_sink::Function=_row -> nothing)
    rows = B.benchmark_frame_capture(
        capture;
        channel_id=String(channel_id), frames=Int(frames),
        frame_blocks=config.horizon == 0 ? nothing : Int(config.horizon),
        frame_duration_s=FRAME_DURATION_S, frame_crc_bits=FRAME_CRC_BITS,
        algorithms=SELECTED, snr_db=Float64(snr_db), seed=SEED,
        modem_fs=MODEM_FS, modem_profile=:passband_replay, sync_profile=:lfm,
        nfft=config.nfft, cp=config.cp, code_rate=config.code_rate,
        check_degree=config.check_degree, ldpc_method=:auto,
        ldpc_seed=51_001, ldpc_no4cycle=true,
        outer_pilot_ratio=1 / config.outer_spacing,
        inner_pilot_ratio=1 / config.inner_spacing,
        frame_sink=frame_sink)
    [(channel=String(channel_id), lane=lane, snr_db=Float64(snr_db),
      algorithm_id=String(SELECTED[i].id), seed=SEED, frames=Int(frames),
      objective=OBJECTIVE_LABEL[],
      nfft=config.nfft, cp=config.cp, code_rate=config.code_rate,
      outer_spacing=config.outer_spacing, inner_spacing=config.inner_spacing,
      check_degree=config.check_degree, horizon=config.horizon,
      partial_fft_parts=Int(row.partial_fft_parts),
      partial_fft_bands=Int(row.partial_fft_bands),
      payload_bits_per_frame=Int(row.payload_bits_per_frame),
      successful_frames=Int(row.successful_frames), psr=Float64(row.psr),
      payload_bits=Int(row.payload_bits), bit_errors=Int(row.bit_errors),
      ber=Float64(row.ber), decode_failures=Int(row.decode_failures),
      decode_seconds=Float64(row.mean_decode_seconds_per_frame),
      effective_rate_bps=Float64(row.effective_rate_bps))
     for (i, row) in pairs(rows)]
end

function _write_csv(destination, rows)
    isempty(rows) && return destination
    names = keys(first(rows))
    open(destination, "w") do io
        println(io, join(names, ','))
        for row in rows
            println(io, join((getproperty(row, n) for n in names), ','))
        end
    end
    destination
end

function smoke(data_dir=joinpath(SEARCH, "data"))
    model = UwaNoise.load_model(NOISE_MAT)
    geometries = best_geometries()
    config = geometries[(:red1, 1)]
    println("red1 lane 1 best-BER geometry: N=", config.nfft, " CP=", config.cp,
            " rate=", config.code_rate, " pilots=", config.outer_spacing, "/",
            config.inner_spacing, " dc=", config.check_degree,
            " K=", config.horizon, "  (20 dB BER ", round(config.ber, sigdigits=3), ")")
    capture = B.load_capture(joinpath(data_dir, CHANNEL_FILES.red1); receiver=1)
    with_uwa_noise(model, 1, MODEM_FS) do
        for snr in (0.0, 20.0)
            for row in _evaluate(capture, :red1, 1, config, snr; frames=3)
                println("  SNR ", rpad(snr, 5), " ", rpad(row.algorithm_id, 12),
                        " psr=", rpad(round(row.psr, digits=3), 6),
                        " ber=", round(row.ber, sigdigits=4))
            end
        end
    end
end

"""One capture-lane path, the SNR ladder split across threads.

With twelve paths the natural unit of parallelism was the path. For a single
path the ladder is the only thing left to split, so the sixteen SNR points are
dealt out one group per thread. Each group loads its own capture rather than
sharing one: the harness was not written for concurrent readers, and a silent
data race here would look like scatter in the curve.
"""
function run(channel::Symbol=:red1, lane::Integer=1,
             objective::Symbol=:ber;
             data_dir=joinpath(SEARCH, "data"), out_dir=@__DIR__,
             trace_destination::Union{Nothing,AbstractString}=nothing,
             config_override=nothing,
             result_label::Union{Nothing,AbstractString}=nothing,
             destination::Union{Nothing,AbstractString}=nothing)
    model = UwaNoise.load_model(NOISE_MAT)
    override = config_override !== nothing
    if override
        result_label === nothing &&
            throw(ArgumentError("config_override requires result_label"))
        destination === nothing &&
            throw(ArgumentError("config_override requires destination"))
    end
    config = override ? config_override : best_geometries(objective)[(channel, lane)]
    if override
        println(channel, " lane ", lane, " configuration: N=", config.nfft,
                " CP=", config.cp, " rate=", config.code_rate, " pilots=",
                config.outer_spacing, "/", config.inner_spacing, " dc=",
                config.check_degree, " K=",
                config.horizon == 0 ? "fill" : config.horizon)
    else
        println(channel, " lane ", lane, " ", objective === :rate ?
                "max-rate" : "min-BER", " geometry: N=", config.nfft,
                " CP=", config.cp, " rate=", config.code_rate, " pilots=",
                config.outer_spacing, "/", config.inner_spacing, " dc=",
                config.check_degree, " K=", config.horizon,
                "  (20 dB BER ", round(config.ber, sigdigits=3), ")")
    end
    flush(stdout)

    OBJECTIVE_LABEL[] = result_label === nothing ?
        (objective === :rate ? "max-rate" : "min-BER") : String(result_label)
    snrs = collect(SNR_DB)
    groups = max(1, min(Threads.nthreads(), length(snrs)))
    chunks = [snrs[i:groups:end] for i in 1:groups]
    rows_by_chunk = Vector{Vector{NamedTuple}}(undef, groups)
    traces_by_chunk = Vector{Vector{NamedTuple}}(undef, groups)
    algorithm_ids = Dict(a.name => String(a.id) for a in SELECTED)
    gain = UwaNoise._chain_scale_gain(model, MODEM_FS)
    file = joinpath(data_dir, getproperty(CHANNEL_FILES, channel))
    # Loaded once and shared. `ReplayCapture` is an immutable struct and
    # nothing in the replay path assigns into it, so concurrent readers are
    # safe. One copy per thread cost four 191 MB captures and pushed the
    # machine into memory pressure, which stalled the run.
    capture = B.load_capture(file; receiver=lane)
    println("capture loaded; sweeping ", length(snrs), " SNR points on ",
            groups, " threads")
    flush(stdout)

    Threads.@threads for index in 1:groups
        rows_by_chunk[index] = NamedTuple[]
        traces_by_chunk[index] = NamedTuple[]
        try
            frame_sink = row -> begin
                row.profile == "profiled_cz" || return nothing
                push!(traces_by_chunk[index], (
                    workload_id=row.workload_id,
                    snr_db=row.snr_db,
                    frame=row.frame,
                    algorithm_id=algorithm_ids[row.algorithm],
                    bit_errors=row.bit_errors,
                    success=row.success,
                    decode_failure=row.decode_failure,
                    decoder_valid=row.decoder_valid,
                    crc_valid=row.crc_valid,
                    baseline_valid=row.baseline_valid,
                    accepted_update=row.accepted_update,
                    selection_reason=row.selection_reason,
                    selected_iteration=row.selected_iteration,
                    partial_fft_parts=row.partial_fft_parts,
                    partial_fft_bands=row.partial_fft_bands,
                    lite_syndrome=row.lite_syndrome,
                    gradient_syndrome=row.gradient_syndrome,
                    lite_score=row.lite_score,
                    gradient_score=row.gradient_score,
                    selected_mean_abs_lpost=row.selected_mean_abs_lpost,
                ))
                nothing
            end
            for snr in chunks[index]
                rows = with_uwa_noise(model, lane, MODEM_FS; gain=gain) do
                    _evaluate(capture, channel, lane, config, snr;
                              frame_sink=frame_sink)
                end
                append!(rows_by_chunk[index], rows)
                println("  ", channel, " lane ", lane, " SNR ", snr, " done")
                flush(stdout)
            end
        catch exception
            exception isa InterruptException && rethrow()
            @warn "chunk failed" index exception
        end
    end

    rows = sort(reduce(vcat, rows_by_chunk); by = r -> (r.snr_db, r.algorithm_id))
    final_destination = if destination === nothing
        suffix = objective === :rate ? "_maxrate" : "_minber"
        isempty(_ARM_FILTER) || (suffix *= "_" * join(_ARM_FILTER, "-"))
        joinpath(out_dir, "red_snr_sweep_uwa_noise$suffix.csv")
    else
        String(destination)
    end
    final_destination = _write_csv(final_destination, rows)
    if trace_destination !== nothing
        traces = sort(reduce(vcat, traces_by_chunk);
                      by = r -> (r.snr_db, r.algorithm_id, r.frame))
        _write_csv(trace_destination, traces)
        println("wrote ", trace_destination, " (", length(traces),
                " profiled C,z frame rows)")
    end
    println("DONE ", channel, " lane ", lane)
    println("wrote ", final_destination, " (", length(rows), " rows)")
    rows
end

end # module

if abspath(PROGRAM_FILE) == @__FILE__
    if length(ARGS) >= 1 && ARGS[1] == "smoke"
        SnrSweep.smoke()
    else
        channel = length(ARGS) >= 1 ? Symbol(ARGS[1]) : :red1
        lane = length(ARGS) >= 2 ? parse(Int, ARGS[2]) : 1
        objective = length(ARGS) >= 3 ? Symbol(ARGS[3]) : :ber
        SnrSweep.run(channel, lane, objective)
    end
end
