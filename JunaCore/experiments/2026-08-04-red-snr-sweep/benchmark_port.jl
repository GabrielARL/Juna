# Verbatim extraction from sonique research/JunaCoreTests
# tools/receiver_channel_benchmark.jl for the red Lite config search.
# Functions are copied unmodified except the deviations listed here:
#   D1 red_4 added to CHANNEL_DESCRIPTORS (identical measured geometry).
#   D2 _frame_feedback_diagnostics stubbed (diagnostics not ported).
#   D4 sync_profile/compatibility_profile row fields are literals ("lfm",
#      "juna"): CL-10 removed those Modulation fields.
#   D3 replay comes from ReplayLane (this directory), not
#      ReplayCoupledSegment; replay_passband stubbed (baseband only).
module BenchmarkPort

using JunaCore
using Printf
using Random
using SHA
using Statistics
import SignalAnalysis
include(joinpath(@__DIR__, "replay_lane.jl"))
using .ReplayLane: ReplayCapture, align_to_reference, apply_capture,
                   capture_from_dict, capture_snapshot_limit, load_capture
const Juna = JunaCore.Juna
const LDPC = JunaCore.LDPC
const Modulations = JunaCore.Modulations

# D3: baseband replay with modem-rate conversion (verbatim from
# replay_coupled_segment.jl).
function replay_at_modem_rate(capture::ReplayCapture,
                              transmitted::AbstractVector{<:Number};
                              snapshot::Integer=1,
                              modem_fs::Real)
    isempty(transmitted) && throw(ArgumentError("replay input must not be empty"))
    modem_rate = Float64(modem_fs)
    isfinite(modem_rate) && modem_rate > 0 ||
        throw(ArgumentError("modem fs must be positive"))
    channel_input = modem_rate == capture.fs ? ComplexF64.(transmitted) :
        vec(SignalAnalysis.resample(
            ComplexF64.(transmitted), capture.fs / modem_rate; dims=1,
        ))
    channel_output = apply_capture(capture, channel_input; snapshot=snapshot)
    modem_rate == capture.fs && return channel_output
    vec(SignalAnalysis.resample(
        channel_output, modem_rate / capture.fs; dims=1,
    ))
end
# D3 (revised): verbatim passband replay adapter from
# replay_coupled_segment.jl - rrcos interpolation, upconversion, analytic
# downmix onto the capture delay grid, replay, remodulation, downconversion.
function replay_passband_at_modem_rate(
        capture::ReplayCapture,
        transmitted::AbstractVector{<:Number};
        snapshot::Integer=1,
        modem_fs::Real,
        passband_oversample::Integer=12)
    isempty(transmitted) && throw(ArgumentError("replay input must not be empty"))
    modem_rate = Float64(modem_fs)
    isfinite(modem_rate) && modem_rate > 0 ||
        throw(ArgumentError("modem fs must be positive"))
    oversample = Int(passband_oversample)
    oversample > 0 || throw(ArgumentError("passband oversample must be positive"))

    pulse = SignalAnalysis.rrcosfir(0.25, oversample)
    baseband = SignalAnalysis.signal(ComplexF64.(transmitted), modem_rate)
    passband = SignalAnalysis.upconvert(
        baseband, oversample, capture.fc, pulse,
    )
    passband_rate = Float64(SignalAnalysis.framerate(passband))

    analytic_passband = SignalAnalysis.analytic(passband)
    mixed = ComplexF64.(SignalAnalysis.samples(analytic_passband))
    @inbounds for n in eachindex(mixed)
        mixed[n] *= cispi(-2 * capture.fc * (n - 1) / passband_rate)
    end
    channel_input = vec(SignalAnalysis.resample(
        mixed, capture.fs / passband_rate; dims=1,
    ))
    channel_output = apply_capture(
        capture, channel_input; snapshot=snapshot,
    )

    remodulated = vec(SignalAnalysis.resample(
        channel_output, passband_rate / capture.fs; dims=1,
    ))
    @inbounds for n in eachindex(remodulated)
        remodulated[n] *= cispi(2 * capture.fc * (n - 1) / passband_rate)
    end
    received_passband = SignalAnalysis.signal(real.(remodulated), passband_rate)
    recovered = SignalAnalysis.downconvert(
        received_passband, oversample, capture.fc, pulse,
    )
    ComplexF64.(vec(SignalAnalysis.samples(recovered)))
end
_frame_feedback_diagnostics(args...; kwargs...) =
    error("frame diagnostics not ported (D2)")

const DEFAULT_RECEIVER = 3

const ALGORITHM_DESCRIPTORS = (
    (id=:standard, name="Standard OFDM", profile=:standard, factory=Juna.StandardModulation),
    (id=:pfft, name="Partial FFT+FEC", profile=:pfft, factory=Juna.PartialFFTModulation),
    (id=:lite, name="JUNA-Lite", profile=:lite, factory=Juna.LiteModulation),
    (id=:fully_coupled, name="JUNA Fully Coupled", profile=:fully_coupled,
     factory=Juna.FullyCoupledModulation),
    (id=:turbo_map, name="JUNA Turbo MAP", profile=:turbo_map,
     factory=Juna.TurboMAPModulation),
    (id=:profiled_gradient, name="JUNA Profiled Gradient", profile=:profiled_gradient,
     factory=Juna.ProfiledGradientModulation),
)

# The published commit-history matrix is a frozen five-receiver experiment.
# New live-benchmark receivers must not silently change its row count or make
# old commits incomparable with new ones.
const COMMIT_ALGORITHM_DESCRIPTORS = (
    (id=:standard, name="Standard OFDM", profile=:standard, factory=Juna.StandardModulation),
    (id=:pfft, name="Partial FFT+FEC", profile=:pfft, factory=Juna.PartialFFTModulation),
    (id=:lite, name="JUNA-Lite", profile=:lite, factory=Juna.LiteModulation),
    (id=:wz, name="JUNA-Wz", profile=:full, factory=Juna.FullModulation),
    (id=:wcz, name="JUNA-WCz", profile=:coupled, factory=Juna.CoupledModulation),
)

const FRAME_ALGORITHM_DESCRIPTORS = (
    (id=:standard, name="Standard OFDM", profile=:standard),
    (id=:pfft, name="Partial FFT+FEC", profile=:pfft),
    (id=:lite, name="JUNA-Lite", profile=:lite),
    (id=:wz, name="JUNA-Wz", profile=:full),
    (id=:wcz, name="JUNA-WCz", profile=:coupled),
    (id=:fully_coupled, name="JUNA Fully Coupled", profile=:fully_coupled),
)

const MODEM_PROFILE_DESCRIPTORS = (
    (id=:default, name="JunaCore default", frame_packets=1, passband_oversample=1),
    (id=:passband_replay,
     name="Measured passband replay adapter (native JunaCore geometry)",
     frame_packets=1, passband_oversample=12),
    (id=:rpchan_winner, name="Rpchan winner geometry (JunaCore block projection)", frame_packets=10,
     passband_oversample=12),
)

const CHANNEL_DESCRIPTORS = (
    (id=:red1, label="Red 1", color=:red, filename="red_1.mat", capture_fs=19_200.0),
    (id=:red2, label="Red 2", color=:red, filename="red_2.mat", capture_fs=19_200.0),
    (id=:red3, label="Red 3", color=:red, filename="red_3.mat", capture_fs=19_200.0),
    (id=:red4, label="Red 4", color=:red, filename="red_4.mat", capture_fs=19_200.0),  # D1 — appended to the channel registry
    (id=:blue1, label="Blue 1", color=:blue, filename="blue_1.mat", capture_fs=9_765.625),
    (id=:blue2, label="Blue 2", color=:blue, filename="blue_2.mat", capture_fs=9_765.625),
    (id=:blue3, label="Blue 3", color=:blue, filename="blue_3.mat", capture_fs=9_765.625),
    (id=:yellow1, label="Yellow 1", color=:yellow, filename="yellow_1.mat", capture_fs=12_500.0),
    (id=:yellow2, label="Yellow 2", color=:yellow, filename="yellow_2.mat", capture_fs=12_500.0),
    (id=:yellow3, label="Yellow 3", color=:yellow, filename="yellow_3.mat", capture_fs=12_500.0),
    (id=:yellow4, label="Yellow 4", color=:yellow, filename="yellow_4.mat", capture_fs=12_500.0),
    (id=:yellow5, label="Yellow 5", color=:yellow, filename="yellow_5.mat", capture_fs=12_500.0),
    (id=:yellow6, label="Yellow 6", color=:yellow, filename="yellow_6.mat", capture_fs=12_500.0),
)

function _select(values, descriptors, kind::String)
    isempty(values) && throw(ArgumentError("select at least one $kind"))
    requested = Symbol.(lowercase.(String.(values)))
    unknown = setdiff(requested, [entry.id for entry in descriptors])
    isempty(unknown) || throw(ArgumentError("unknown $kind: $(join(unknown, ", "))"))
    Tuple(entry for entry in descriptors if entry.id in requested)
end

select_algorithms(values) = _select(values, ALGORITHM_DESCRIPTORS, "algorithm")
select_channels(values) = _select(values, CHANNEL_DESCRIPTORS, "channel")

function select_modem_profile(value)
    requested = Symbol(replace(lowercase(String(value)), '-' => '_'))
    index = findfirst(profile -> profile.id === requested, MODEM_PROFILE_DESCRIPTORS)
    index === nothing && throw(ArgumentError("unknown modem profile: $value"))
    MODEM_PROFILE_DESCRIPTORS[index]
end

_uses_passband_replay(profile) = profile.passband_oversample > 1

function _wilson_interval(successes::Integer, trials::Integer;
                          z::Real=1.959963984540054)
    n = Int(trials)
    k = Int(successes)
    n > 0 || throw(ArgumentError("Wilson interval needs at least one trial"))
    0 <= k <= n || throw(ArgumentError("successes must be in 0:trials"))
    isfinite(z) && z > 0 || throw(ArgumentError("Wilson z must be positive"))
    p = k / n
    z2 = Float64(z)^2
    denominator = 1 + z2 / n
    center = (p + z2 / (2n)) / denominator
    radius = Float64(z) * sqrt(p * (1 - p) / n + z2 / (4n^2)) / denominator
    # Roundoff can put the k=0 lower endpoint a few ulps above zero (or the
    # k=n upper endpoint below one), violating the interval's own containment
    # contract. Clamp each endpoint through the observed proportion as well.
    (min(p, max(0.0, center - radius)),
     max(p, min(1.0, center + radius)))
end

function _timing_summary(samples)
    values = Float64.(collect(samples))
    isempty(values) && throw(ArgumentError("timing summary needs at least one sample"))
    all(value -> isfinite(value) && value >= 0, values) ||
        throw(ArgumentError("timing samples must be finite and nonnegative"))
    total = sum(values)
    (total=total, mean=total / length(values), median=median(values),
     p95=quantile(values, 0.95))
end

_digest_bytes(bytes) = bytes2hex(SHA.sha256(bytes))

function _digest_bits(bits)
    _digest_bytes(UInt8.(Bool.(bits)))
end

function _digest_complex(samples)
    values = ComplexF64.(vec(samples))
    _digest_bytes(collect(reinterpret(UInt8, values)))
end

function _digest_code(code)
    io = IOBuffer()
    for value in (code.k, code.n, code.npc, code.seed, Int(code.no4cycle))
        write(io, Int64(value))
    end
    write(io, code.method)
    write(io, UInt8(0))
    write(io, Int64(size(code.H, 1)))
    write(io, Int64(size(code.H, 2)))
    write(io, UInt8.(vec(code.H)))
    _digest_bytes(take!(io))
end

function _digest_workload(payload_digest::AbstractString,
                          code_digest::AbstractString,
                          transmitted_digest::AbstractString,
                          received_digest::AbstractString)
    _digest_bytes(Vector{UInt8}(codeunits(
        join((payload_digest, code_digest, transmitted_digest,
              received_digest), ':'))))
end

function _digest_sequence(digests)
    _digest_bytes(Vector{UInt8}(codeunits(join(digests, ':'))))
end

function _digest_file_streaming(path::AbstractString)
    open(path) do io
        bytes2hex(SHA.sha256(io))
    end
end

# Experiment B traverses cells family-major. Keep only the current source/lane
# resident: this avoids re-reading a 183--784 MB MAT file for every pilot and
# horizon cell without accumulating all three channel families in memory.
const _EXPERIMENT_B_CAPTURE_CACHE = Ref{Any}(nothing)

function _experiment_b_capture(path::AbstractString, receiver::Integer)
    resolved = realpath(path)
    info = stat(resolved)
    key = (
        path=resolved,
        receiver=Int(receiver),
        bytes=Int(info.size),
        modified=Float64(info.mtime),
    )
    cached = _EXPERIMENT_B_CAPTURE_CACHE[]
    if cached !== nothing && cached.key == key
        return cached.capture, cached.source_digest
    end
    # Drop the previous family's expanded lane before MAT.matread allocates the
    # next large source. Otherwise both can coexist at a family transition.
    if cached !== nothing
        _EXPERIMENT_B_CAPTURE_CACHE[] = nothing
        cached = nothing
        GC.gc()
    end
    source_digest = _digest_file_streaming(resolved)
    capture = load_capture(resolved; receiver=Int(receiver))
    _EXPERIMENT_B_CAPTURE_CACHE[] = (; key, capture, source_digest)
    capture, source_digest
end

function _compact_capture_digest(capture::ReplayCapture)
    io = IOBuffer()
    write(io, Int64(capture.receiver))
    write(io, Float64(capture.fs))
    write(io, Float64(capture.fc))
    write(io, Int64(capture.step))
    write(io, Int64(size(capture.h, 1)))
    write(io, Int64(size(capture.h, 2)))
    write(io, Int64(length(capture.phase)))
    write(io, capture.name)
    write(io, UInt8(0))
    for index in unique((1, cld(length(capture.h), 2), length(capture.h)))
        write(io, ComplexF64(capture.h[index]))
    end
    for index in unique((
            1, cld(length(capture.phase), 2), length(capture.phase)))
        write(io, Float64(capture.phase[index]))
    end
    _digest_bytes(take!(io))
end

const _EXPERIMENT_B_NOISE_REFERENCE_CACHE = Ref{Any}(nothing)

function _validate_benchmark(packets::Integer, snr_db::Real, seed::Integer)
    1 <= packets <= 1_000 || throw(ArgumentError("packets must be in 1:1000"))
    (isinf(snr_db) && snr_db > 0) || (-30 <= snr_db <= 100) ||
        throw(ArgumentError("SNR must be Inf or between -30 and 100 dB"))
    seed >= 0 || throw(ArgumentError("seed must be nonnegative"))
    nothing
end

function _resolve_modem_fs(capture::ReplayCapture, requested)
    requested === nothing && return capture.fs
    requested === :capture && return capture.fs
    requested === :rpchan && return capture.fs / 2
    requested isa Real ||
        throw(ArgumentError("modem fs must be :capture, :rpchan, or a positive rate"))
    rate = Float64(requested)
    isfinite(rate) && rate > 0 || throw(ArgumentError("modem fs must be positive"))
    rate
end

function _effective_bandwidth_geometry(channel_bandwidth_hz::Real,
                                       modem_fs::Real,
                                       modem_bw::Real)
    channel_width = Float64(channel_bandwidth_hz)
    rate = Float64(modem_fs)
    requested_bw = Float64(modem_bw)
    isfinite(channel_width) && channel_width > 0 || throw(ArgumentError(
        "channel bandwidth must be positive"))
    isfinite(rate) && rate > 0 || throw(ArgumentError(
        "modem fs must be positive"))
    isfinite(requested_bw) && 0 < requested_bw <= 1 || throw(ArgumentError(
        "modem bw must be finite and in (0, 1]"))
    requested_width = requested_bw * Juna._REFERENCE_BANDWIDTH_HZ
    effective_width = min(channel_width, requested_width, rate)
    (
        channel_bandwidth_hz=channel_width,
        requested_modem_bw=requested_bw,
        requested_modem_bandwidth_hz=requested_width,
        effective_bandwidth_hz=effective_width,
        normalized_bw=effective_width / Juna._REFERENCE_BANDWIDTH_HZ,
    )
end

function _effective_bandwidth_geometry(capture::ReplayCapture,
                                       modem_fs::Real,
                                       modem_bw::Real=1.0)
    # Rpchan defines the maximum complex baseband profile as fs_delay / 2.
    _effective_bandwidth_geometry(capture.fs / 2, modem_fs, modem_bw)
end

function _validate_rate_request(requested)
    requested === nothing && return nothing
    requested in (:capture, :rpchan) && return nothing
    requested isa Real ||
        throw(ArgumentError("modem fs must be :capture, :rpchan, or a positive rate"))
    isfinite(requested) && requested > 0 ||
        throw(ArgumentError("modem fs must be positive"))
    nothing
end

# Sweep hook (CL-30). When set, this replaces the Gaussian draw with the
# uwa-channels mixing model, so the sweep runs on impulsive, array-correlated
# noise instead of AWGN. The callback receives (nsamples, noise_power, rng)
# and must return complex noise whose alpha-stable pseudo-power 2*delta^2
# equals noise_power -- which is what makes the SNR axis eq. (35) of
# Mahmood & Chitre, JOE 42(3) 2017. At alpha = 2 it reduces to the AWGN case.
# Task-local, not a global Ref: paths run on separate threads with different
# hydrophones, and Julia tasks may migrate between threads, so a thread-indexed
# store could silently hand one lane's noise to another lane's decode.
const NOISE_OVERRIDE_KEY = :juna_noise_override
_noise_override() = get(task_local_storage(), NOISE_OVERRIDE_KEY, nothing)

function _add_awgn(signal::AbstractVector{<:Number}, snr_db::Real,
                   rng::AbstractRNG; reference_power=nothing)
    isinf(snr_db) && return ComplexF64.(signal)
    power = reference_power === nothing ?
        sum(abs2, signal) / length(signal) : Float64(reference_power)
    isfinite(power) && power >= 0 || throw(ArgumentError(
        "AWGN reference power must be finite and nonnegative"))
    power == 0 && return ComplexF64.(signal)
    noise_power = power / 10.0^(Float64(snr_db) / 10)
    let override = _noise_override()
        override === nothing || return ComplexF64.(signal) .+
            override(length(signal), noise_power, rng)
    end
    sigma = sqrt(noise_power / 2)
    ComplexF64.(signal) .+ sigma .* (randn(rng, length(signal)) .+
                                     im .* randn(rng, length(signal)))
end

function _add_awgn_recorded(signal::AbstractVector{<:Number}, snr_db::Real,
                            rng::AbstractRNG; reference_power=nothing)
    base = ComplexF64.(signal)
    isinf(snr_db) &&
        return (; noisy=base, noise=zeros(ComplexF64, length(base)))
    power = reference_power === nothing ?
        sum(abs2, base) / length(base) : Float64(reference_power)
    isfinite(power) && power >= 0 || throw(ArgumentError(
        "AWGN reference power must be finite and nonnegative"))
    power == 0 &&
        return (; noisy=base, noise=zeros(ComplexF64, length(base)))
    noise_power = power / 10.0^(Float64(snr_db) / 10)
    sigma = sqrt(noise_power / 2)
    # Preserve `_add_awgn`'s draw order exactly: all real samples, then all
    # imaginary samples. Hash this generated vector directly rather than
    # subtracting it back out of a horizon-dependent signal.
    noise = sigma .* (randn(rng, length(base)) .+
                      im .* randn(rng, length(base)))
    (; noisy=base .+ noise, noise)
end

function _snapshot_positions(capture::ReplayCapture, packets::Integer,
                             waveform_length::Integer, modem_fs::Real)
    count = Int(packets)
    count > 0 || throw(ArgumentError("packets must be positive"))
    waveform_length > 0 || throw(ArgumentError("waveform length must be positive"))
    rate = Float64(modem_fs)
    isfinite(rate) && rate > 0 || throw(ArgumentError("modem fs must be positive"))
    channel_samples, stop = _capture_position_limit(
        capture, waveform_length, rate)
    count <= stop || throw(ArgumentError(
        "capture has only $stop distinct packet positions, requested $count"))
    packets == 1 && return [1]
    positions = round.(Int, range(1, stop; length=count))
    allunique(positions) || throw(ArgumentError("packet positions are not distinct"))
    positions
end

function _capture_position_limit(capture::ReplayCapture,
                                 waveform_length::Integer,
                                 modem_fs::Real)
    waveform_length > 0 || throw(ArgumentError("waveform length must be positive"))
    rate = Float64(modem_fs)
    isfinite(rate) && rate > 0 || throw(ArgumentError("modem fs must be positive"))
    channel_samples = ceil(Int, waveform_length * capture.fs / rate)
    # Delegate the tracking-specific UACR bounds. phi_hat needs one more phase
    # sample than theta_hat for its delay-warp coordinates, and both modes must
    # remain inside measured cubic tap support.
    stop = capture_snapshot_limit(capture, channel_samples)
    stop >= 1 || throw(ArgumentError("capture is too short for one waveform"))
    channel_samples, stop
end

function _full_capture_positions(capture::ReplayCapture,
                                 waveform_length::Integer,
                                 modem_fs::Real)
    channel_samples, stop = _capture_position_limit(
        capture, waveform_length, modem_fs)
    count = fld((stop - 1) * capture.step, channel_samples) + 1
    positions = unique(round.(Int,
        1 .+ (0:(count - 1)) .* (channel_samples / capture.step)))
    isempty(positions) && throw(ArgumentError("capture has no complete block positions"))
    last(positions) <= stop ||
        throw(ArgumentError("full-capture position exceeds channel support"))
    positions
end
function _configure_pilot_budget!(receiver, pilot_ratio)
    geometry = _pilot_budget_geometry(pilot_ratio)
    geometry === nothing && return receiver
    receiver.pilot_ratio = geometry.per_domain
    receiver.inner_pilot_ratio = geometry.per_domain
    receiver.layout = nothing
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _configure_independent_pilots!(receiver, outer_ratio, inner_ratio)
    if outer_ratio !== nothing
        outer_ratio isa Real || throw(ArgumentError(
            "outer pilot ratio must be real"))
        outer = Float64(outer_ratio)
        isfinite(outer) && 0 < outer <= 1 || throw(ArgumentError(
            "outer pilot ratio must be finite and in (0, 1]"))
        receiver.pilot_ratio = outer
    end
    if inner_ratio !== nothing
        inner_ratio isa Real || throw(ArgumentError(
            "inner pilot ratio must be real"))
        inner = Float64(inner_ratio)
        isfinite(inner) && 0 <= inner <= 1 || throw(ArgumentError(
            "inner pilot ratio must be finite and in [0, 1]"))
        receiver.inner_pilot_ratio = inner
    end
    if outer_ratio !== nothing || inner_ratio !== nothing
        receiver.layout = nothing
        receiver.code = nothing
        receiver.bp_scratch = nothing
    end
    receiver
end

function _configure_code_rate!(receiver, code_rate)
    code_rate === nothing && return receiver
    code_rate isa Real || throw(ArgumentError("code rate must be real"))
    rate = Float64(code_rate)
    isfinite(rate) && 0 < rate < 1 ||
        throw(ArgumentError("code rate must be finite and strictly between zero and one"))
    block_n = Int(receiver.ldpc_n)
    block_k = round(Int, rate * block_n)
    block_k / block_n == rate || throw(ArgumentError(
        "code rate $rate is not exactly representable with LDPC block length $block_n"))
    receiver.ldpc_k = block_k
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _configure_bpc!(receiver, bpc)
    bpc === nothing && return receiver
    bpc isa Integer || throw(ArgumentError(
        "bits per carrier must be an integer"))
    bits = Int(bpc)
    bits in (1, 2) || throw(ArgumentError(
        "bits per carrier must be 1 (BPSK) or 2 (QPSK)"))
    receiver.bpc = bits
    receiver.layout = nothing
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _configure_partial_fft_parts!(receiver, partial_fft_parts)
    partial_fft_parts === nothing && return receiver
    partial_fft_parts isa Integer || throw(ArgumentError(
        "partial-FFT parts must be an integer"))
    parts = Int(partial_fft_parts)
    0 < parts <= Int(receiver.nc) || throw(ArgumentError(
        "partial-FFT parts must lie in 1:N"))
    receiver.partial_fft_parts = parts
    receiver.layout = nothing
    receiver
end

function _configure_partial_fft_bands!(receiver, partial_fft_bands)
    partial_fft_bands === nothing && return receiver
    partial_fft_bands isa Integer || throw(ArgumentError(
        "partial-FFT band count must be an integer"))
    bands = Int(partial_fft_bands)
    0 < bands <= Int(receiver.nc) || throw(ArgumentError(
        "partial-FFT band count must lie in 1:N"))
    receiver.partial_fft_nbands = bands
    receiver.layout = nothing
    receiver
end

function _configure_check_degree!(receiver, check_degree)
    check_degree === nothing && return receiver
    check_degree isa Integer || throw(ArgumentError(
        "LDPC check degree must be an integer"))
    degree = Int(check_degree)
    maximum_degree = Int(receiver.ldpc_n) - Int(receiver.ldpc_k)
    0 < degree <= maximum_degree || throw(ArgumentError(
        "LDPC check degree must be in 1:$maximum_degree"))
    receiver.ldpc_npc = degree
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _configure_ldpc_method!(receiver, ldpc_method)
    ldpc_method === nothing && return receiver
    method = Symbol(ldpc_method)
    method in (:auto, :evencol, :evenboth) || throw(ArgumentError(
        "LDPC method must be :auto, :evencol, or :evenboth"))
    receiver.ldpc_method = method
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _configure_ldpc_seed!(receiver, ldpc_seed)
    ldpc_seed === nothing && return receiver
    ldpc_seed isa Integer || throw(ArgumentError(
        "LDPC seed must be an integer"))
    seed = Int(ldpc_seed)
    0 <= seed <= LDPC._MAX_TOOL_SEED || throw(ArgumentError(
        "LDPC seed must be in 0:$(LDPC._MAX_TOOL_SEED)"))
    receiver.ldpc_seed = seed
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _configure_ldpc_no4cycle!(receiver, ldpc_no4cycle)
    ldpc_no4cycle === nothing && return receiver
    ldpc_no4cycle isa Bool || throw(ArgumentError(
        "LDPC no4cycle flag must be boolean"))
    receiver.ldpc_no4cycle = ldpc_no4cycle
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _configure_fft_geometry!(receiver, fs::Real, nfft, cp;
                                  refit_capacity::Bool=false)
    nfft === nothing && cp === nothing && !refit_capacity && return receiver
    nfft === nothing || nfft isa Integer ||
        throw(ArgumentError("FFT size must be an integer"))
    cp === nothing || cp isa Integer ||
        throw(ArgumentError("cyclic-prefix length must be an integer"))
    N = nfft === nothing ? Int(receiver.nc) : Int(nfft)
    L = cp === nothing ? Int(receiver.np) : Int(cp)
    2 < N <= typemax(UInt16) && iseven(N) || throw(ArgumentError(
        "FFT size must be an even UInt16-representable integer greater than two"))
    0 <= L < N ||
        throw(ArgumentError("cyclic-prefix length must satisfy 0 <= CP < N"))

    original_rate = Int(receiver.ldpc_k) / Int(receiver.ldpc_n)
    receiver.nc = UInt16(N)
    receiver.np = UInt16(L)
    receiver.layout = nothing
    layout = Juna._layout(receiver, fs)
    coded_capacity = Int(receiver.bpc) * length(layout.data_idx)
    block_n = coded_capacity - mod(coded_capacity, 16)
    block_n >= 16 || throw(ArgumentError(
        "FFT geometry has insufficient coded-bit capacity"))
    block_k = round(Int, original_rate * block_n)
    receiver.ldpc_n = block_n
    receiver.ldpc_k = block_k
    receiver.code = nothing
    receiver.bp_scratch = nothing
    receiver
end

function _fit_partial_fft_bands!(receiver, fs::Real)
    maximum_bands = min(Int(receiver.partial_fft_nbands), Int(receiver.nc))
    for bands in maximum_bands:-1:1
        receiver.partial_fft_nbands = bands
        receiver.layout = nothing
        layout = Juna._layout(receiver, fs)
        Juna._pilot_training_sufficient(receiver, layout) && return receiver
    end
    throw(ArgumentError(
        "pilot geometry cannot train even one partial-FFT band"))
end

function _configure_modem!(receiver, fc::Real, fs::Real, modem_profile;
                           nfft=nothing, cp=nothing, bpc=nothing,
                           code_rate=nothing, partial_fft_parts=nothing,
                           partial_fft_bands=nothing,
                           check_degree=nothing, ldpc_method=nothing,
                           ldpc_seed=nothing,
                           ldpc_no4cycle=nothing,
                           sync_profile=nothing,
                           compatibility_profile=nothing,
                           frame_duration_s=nothing,
                           pilot_ratio=nothing,
                           outer_pilot_ratio=nothing,
                           inner_pilot_ratio=nothing,
                           bw::Real=1.0)
    profile = select_modem_profile(modem_profile)
    Modulations.init(receiver, fc, fs)
    isfinite(bw) && 0 < bw <= 1 || throw(ArgumentError(
        "effective modem bw must be finite and in (0, 1]"))
    receiver.bw = Float64(bw)
    receiver.layout = nothing
    if profile.id === :rpchan_winner
        receiver.nc = UInt16(1024)
        receiver.np = UInt16(32)
        receiver.bpc = 2
        receiver.pilot_ratio = 1 / 5
        receiver.inner_pilot_ratio = 1 / 10
        receiver.ldpc_k = 817
        receiver.ldpc_n = 1634
        receiver.ldpc_npc = 9
        receiver.partial_fft_parts = 4
        receiver.partial_fft_nbands = 4
        receiver.sync = true
        receiver.sync_profile = :rpchan
        receiver.rpchan_guard_s = 0.0
        receiver.rpchan_doppler_ppm = 0.0
        receiver.rpchan_doppler_steps = 1
        receiver.rpchan_sync_max_lag = 400
        receiver.code = nothing
        receiver.layout = nothing
        receiver.bp_scratch = nothing
    end
    if sync_profile !== nothing
        Symbol(sync_profile) === :lfm || throw(ArgumentError(
            "only the :lfm sync profile exists in this package (D5)"))
        receiver.sync = true   # D5: sync_profile field removed in CL-10
    end
    compatibility_profile === nothing ||
        (receiver.compatibility_profile = Symbol(compatibility_profile))
    frame_duration_s === nothing ||
        (receiver.frame_duration_s = Float64(frame_duration_s))
    if sync_profile !== nothing || compatibility_profile !== nothing ||
       frame_duration_s !== nothing
        receiver.code = nothing
        receiver.layout = nothing
        receiver.bp_scratch = nothing
    end
    _configure_bpc!(receiver, bpc)
    _configure_pilot_budget!(receiver, pilot_ratio)
    _configure_independent_pilots!(
        receiver, outer_pilot_ratio, inner_pilot_ratio)
    occupancy = Juna._baseband_occupancy(receiver, fs)
    _configure_fft_geometry!(
        receiver, fs, nfft, cp;
        refit_capacity=occupancy < 1.0 - 64eps(1.0))
    _configure_partial_fft_parts!(receiver, partial_fft_parts)
    _configure_partial_fft_bands!(receiver, partial_fft_bands)
    _configure_code_rate!(receiver, code_rate)
    _configure_check_degree!(receiver, check_degree)
    _configure_ldpc_method!(receiver, ldpc_method)
    _configure_ldpc_seed!(receiver, ldpc_seed)
    _configure_ldpc_no4cycle!(receiver, ldpc_no4cycle)
    _fit_partial_fft_bands!(receiver, fs)
end

function _receiver_set(algorithms, fc::Real, fs::Real;
                       modem_profile=:default, nfft=nothing, cp=nothing,
                       code_rate=nothing, check_degree=nothing,
                       ldpc_method=nothing, ldpc_seed=nothing,
                       ldpc_no4cycle=nothing, pilot_ratio=nothing,
                       outer_pilot_ratio=nothing,
                       inner_pilot_ratio=nothing,
                       rpchan_guard_s=nothing,
                       rpchan_doppler_ppm=nothing,
                       rpchan_doppler_steps=nothing,
                       channel_bandwidth_hz::Real=fs,
                       modem_bw::Real=1.0)
    bandwidth = _effective_bandwidth_geometry(
        channel_bandwidth_hz, fs, modem_bw)
    receivers = map(algorithms) do descriptor
        receiver = _configure_modem!(
            descriptor.factory(), fc, fs, modem_profile;
            nfft=nfft, cp=cp, code_rate=code_rate,
            check_degree=check_degree, ldpc_method=ldpc_method,
            ldpc_seed=ldpc_seed, ldpc_no4cycle=ldpc_no4cycle,
            pilot_ratio=pilot_ratio,
            outer_pilot_ratio=outer_pilot_ratio,
            inner_pilot_ratio=inner_pilot_ratio,
            bw=bandwidth.normalized_bw)
        rpchan_guard_s === nothing ||
            (receiver.rpchan_guard_s = Float64(rpchan_guard_s))
        rpchan_doppler_ppm === nothing ||
            (receiver.rpchan_doppler_ppm = Float64(rpchan_doppler_ppm))
        rpchan_doppler_steps === nothing ||
            (receiver.rpchan_doppler_steps = Int(rpchan_doppler_steps))
        isvalid(receiver, fc, fs) ||
            throw(ArgumentError("$(descriptor.name) is invalid at fc=$fc, fs=$fs"))
        (descriptor=descriptor, receiver=receiver)
    end
    payload_sizes = unique(Modulations.bitspersymbol(item.receiver) for item in receivers)
    length(payload_sizes) == 1 ||
        throw(ArgumentError("selected receivers do not share one payload geometry"))
    receivers, only(payload_sizes)
end

function _frame_receiver_set(algorithms, fc::Real, fs::Real;
                             frame_blocks::Union{Nothing,Integer},
                             frame_duration_s::Real=1.0,
                             frame_crc_bits::Integer=0,
                             frame_code_horizon::Integer=0,
                             modem_profile=:default,
                             nfft=nothing,
                             cp=nothing,
                             bpc=nothing,
                             code_rate=nothing,
                             check_degree=nothing,
                             ldpc_method=nothing,
                             ldpc_seed=nothing,
                             ldpc_no4cycle=nothing,
                             sync_profile=nothing,
                             compatibility_profile=nothing,
                             pilot_ratio=nothing,
                             outer_pilot_ratio=nothing,
                             inner_pilot_ratio=nothing,
                             rpchan_guard_s=nothing,
                             rpchan_doppler_ppm=nothing,
                             rpchan_doppler_steps=nothing,
                             channel_bandwidth_hz::Real=fs,
                             modem_bw::Real=1.0)
    frame_blocks === nothing || Int(frame_blocks) > 0 ||
        throw(ArgumentError("frame block count must be positive"))
    bandwidth = _effective_bandwidth_geometry(
        channel_bandwidth_hz, fs, modem_bw)
    receivers = map(algorithms) do descriptor
        refinement_steps = hasproperty(descriptor, :refinement_steps) ?
            Int(descriptor.refinement_steps) : -1
        cz_restarts = hasproperty(descriptor, :cz_restarts) ?
            Int(descriptor.cz_restarts) : 1
        cz_restart_seed = hasproperty(descriptor, :cz_restart_seed) ?
            Int(descriptor.cz_restart_seed) : 17_071
        cz_parity_weight = hasproperty(descriptor, :cz_parity_weight) ?
            Float64(descriptor.cz_parity_weight) : 0.08
        cz_crc_gate = hasproperty(descriptor, :cz_crc_gate) ?
            Bool(descriptor.cz_crc_gate) : true
        cz_gate_selection_only =
            hasproperty(descriptor, :cz_gate_selection_only) ?
            Bool(descriptor.cz_gate_selection_only) : false
        cz_em_enabled = hasproperty(descriptor, :cz_em_enabled) ?
            Bool(descriptor.cz_em_enabled) : false
        cz_em_trust = hasproperty(descriptor, :cz_em_trust) ?
            Float64(descriptor.cz_em_trust) : 0.05
        cz_em_damping = hasproperty(descriptor, :cz_em_damping) ?
            Float64(descriptor.cz_em_damping) : 0.5
        cz_independent_w = hasproperty(descriptor, :cz_independent_w) ?
            Bool(descriptor.cz_independent_w) : false
        cz_bp_feedback = hasproperty(descriptor, :cz_bp_feedback) ?
            Float64(descriptor.cz_bp_feedback) : 0.0
        cz_feedback_source = hasproperty(descriptor, :cz_feedback_source) ?
            Symbol(descriptor.cz_feedback_source) : :legacy
        cz_vp_gradient = hasproperty(descriptor, :cz_vp_gradient) ?
            Bool(descriptor.cz_vp_gradient) : false
        cz_conditioned_joint = hasproperty(descriptor, :cz_conditioned_joint) ?
            Bool(descriptor.cz_conditioned_joint) : false
        cz_gradient_only = hasproperty(descriptor, :cz_gradient_only) ?
            Bool(descriptor.cz_gradient_only) : false
        cz_joint_c_radius = hasproperty(descriptor, :cz_joint_c_radius) ?
            Float64(descriptor.cz_joint_c_radius) : 0.05
        cz_joint_w_radius = hasproperty(descriptor, :cz_joint_w_radius) ?
            Float64(descriptor.cz_joint_w_radius) : 0.01
        cz_joint_z_radius = hasproperty(descriptor, :cz_joint_z_radius) ?
            Float64(descriptor.cz_joint_z_radius) : 0.5
        cz_joint_w_start = hasproperty(descriptor, :cz_joint_w_start) ?
            Int(descriptor.cz_joint_w_start) : 2
        cz_joint_pilot_tolerance =
            hasproperty(descriptor, :cz_joint_pilot_tolerance) ?
            Float64(descriptor.cz_joint_pilot_tolerance) : 0.01
        cz_temporal_c_smoothness =
            hasproperty(descriptor, :cz_temporal_c_smoothness) ?
            Float64(descriptor.cz_temporal_c_smoothness) : 0.0
        partial_fft_parts = hasproperty(descriptor, :partial_fft_parts) ?
            Int(descriptor.partial_fft_parts) : nothing
        partial_fft_bands = hasproperty(descriptor, :partial_fft_bands) ?
            Int(descriptor.partial_fft_bands) : nothing
        # Mechanism-experiment arm. Absent from a descriptor means the deployed
        # receiver, so every existing tool keeps its current behaviour.
        feedback_mode = hasproperty(descriptor, :feedback_mode) ?
            Symbol(descriptor.feedback_mode) : :real
        feedback_graded_p = hasproperty(descriptor, :feedback_graded_p) ?
            Float64(descriptor.feedback_graded_p) : 0.0
        receiver = _configure_modem!(
            Juna.FrameWideLDPCModulation(
                frame_receiver=descriptor.profile,
                feedback_mode=feedback_mode,
                feedback_graded_p=feedback_graded_p,
                frame_crc_bits=Int(frame_crc_bits),
                frame_code_horizon=Int(frame_code_horizon),
                cz_crc_gate=cz_crc_gate,
                cz_gate_selection_only=cz_gate_selection_only,
                frame_duration_s=Float64(frame_duration_s),
                cz_restarts=cz_restarts,
                cz_restart_seed=cz_restart_seed,
                cz_parity_weight=cz_parity_weight,
                cz_em_enabled=cz_em_enabled,
                cz_em_trust=cz_em_trust,
                cz_em_damping=cz_em_damping,
                cz_independent_w=cz_independent_w,
                cz_bp_feedback=cz_bp_feedback,
                cz_feedback_source=cz_feedback_source,
                cz_vp_gradient=cz_vp_gradient,
                cz_conditioned_joint=cz_conditioned_joint,
                cz_gradient_only=cz_gradient_only,
                cz_joint_c_radius=cz_joint_c_radius,
                cz_joint_w_radius=cz_joint_w_radius,
                cz_joint_z_radius=cz_joint_z_radius,
                cz_joint_w_start=cz_joint_w_start,
                cz_joint_pilot_tolerance=cz_joint_pilot_tolerance,
                cz_temporal_c_smoothness=cz_temporal_c_smoothness,
                refinement_steps=refinement_steps),
            fc,
            fs,
            modem_profile;
            nfft=nfft,
            cp=cp,
            bpc=bpc,
            partial_fft_parts=partial_fft_parts,
            partial_fft_bands=partial_fft_bands,
            code_rate=code_rate,
            check_degree=check_degree,
            ldpc_method=ldpc_method,
            ldpc_seed=ldpc_seed,
            ldpc_no4cycle=ldpc_no4cycle,
            sync_profile=sync_profile,
            compatibility_profile=compatibility_profile,
            frame_duration_s=frame_duration_s,
            pilot_ratio=pilot_ratio,
            outer_pilot_ratio=outer_pilot_ratio,
            inner_pilot_ratio=inner_pilot_ratio,
            bw=bandwidth.normalized_bw,
        )
        rpchan_guard_s === nothing ||
            (receiver.rpchan_guard_s = Float64(rpchan_guard_s))
        rpchan_doppler_ppm === nothing ||
            (receiver.rpchan_doppler_ppm = Float64(rpchan_doppler_ppm))
        rpchan_doppler_steps === nothing ||
            (receiver.rpchan_doppler_steps = Int(rpchan_doppler_steps))
        isvalid(receiver, fc, fs) || throw(ArgumentError(
            "$(descriptor.name) frame receiver is invalid at fc=$fc, fs=$fs"))
        (descriptor=descriptor, receiver=receiver)
    end
    block_counts = unique(
        frame_blocks === nothing ?
            Juna.frameblockcount(item.receiver, fs) : Int(frame_blocks)
        for item in receivers
    )
    length(block_counts) == 1 || throw(ArgumentError(
        "selected frame receivers do not share one duration-derived block count"))
    blocks = only(block_counts)
    payload_sizes = unique(
        Juna._frame_payload_capacity(item.receiver, blocks)
        for item in receivers
    )
    length(payload_sizes) == 1 || throw(ArgumentError(
        "selected frame receivers do not share one payload geometry"))
    receivers, only(payload_sizes)
end

function _paper_duration_receiver_set(config, algorithms, fc::Real, fs::Real;
                                      frame_duration_s::Real,
                                      frame_crc_bits::Integer)
    receivers = map(algorithms) do descriptor
        receiver = _paper_frame_wide_modem(config, fc, fs)
        receiver.frame_receiver = descriptor.profile
        receiver.frame_duration_s = Float64(frame_duration_s)
        receiver.frame_crc_bits = Int(frame_crc_bits)
        receiver.refinement_steps = hasproperty(descriptor, :refinement_steps) ?
            Int(descriptor.refinement_steps) : -1
        receiver.cz_restarts = hasproperty(descriptor, :cz_restarts) ?
            Int(descriptor.cz_restarts) : 1
        receiver.cz_restart_seed = hasproperty(descriptor, :cz_restart_seed) ?
            Int(descriptor.cz_restart_seed) : 17_071
        receiver.cz_parity_weight =
            hasproperty(descriptor, :cz_parity_weight) ?
            Float64(descriptor.cz_parity_weight) : 0.08
        receiver.cz_em_enabled =
            hasproperty(descriptor, :cz_em_enabled) ?
            Bool(descriptor.cz_em_enabled) : false
        receiver.cz_em_trust =
            hasproperty(descriptor, :cz_em_trust) ?
            Float64(descriptor.cz_em_trust) : 0.05
        receiver.cz_em_damping =
            hasproperty(descriptor, :cz_em_damping) ?
            Float64(descriptor.cz_em_damping) : 0.5
        receiver.cz_independent_w =
            hasproperty(descriptor, :cz_independent_w) ?
            Bool(descriptor.cz_independent_w) : false
        receiver.cz_bp_feedback =
            hasproperty(descriptor, :cz_bp_feedback) ?
            Float64(descriptor.cz_bp_feedback) : 0.0
        receiver.cz_vp_gradient =
            hasproperty(descriptor, :cz_vp_gradient) ?
            Bool(descriptor.cz_vp_gradient) : false
        receiver.cz_conditioned_joint =
            hasproperty(descriptor, :cz_conditioned_joint) ?
            Bool(descriptor.cz_conditioned_joint) : false
        receiver.cz_joint_c_radius =
            hasproperty(descriptor, :cz_joint_c_radius) ?
            Float64(descriptor.cz_joint_c_radius) : 0.05
        receiver.cz_joint_w_radius =
            hasproperty(descriptor, :cz_joint_w_radius) ?
            Float64(descriptor.cz_joint_w_radius) : 0.01
        receiver.cz_joint_z_radius =
            hasproperty(descriptor, :cz_joint_z_radius) ?
            Float64(descriptor.cz_joint_z_radius) : 0.5
        receiver.cz_joint_w_start =
            hasproperty(descriptor, :cz_joint_w_start) ?
            Int(descriptor.cz_joint_w_start) : 2
        receiver.cz_joint_pilot_tolerance =
            hasproperty(descriptor, :cz_joint_pilot_tolerance) ?
            Float64(descriptor.cz_joint_pilot_tolerance) : 0.01
        receiver.cz_temporal_c_smoothness =
            hasproperty(descriptor, :cz_temporal_c_smoothness) ?
            Float64(descriptor.cz_temporal_c_smoothness) : 0.0
        receiver.code = nothing
        receiver.bp_scratch = nothing
        isvalid(receiver, fc, fs) || throw(ArgumentError(
            "$(descriptor.name) native paper receiver is invalid"))
        (descriptor=descriptor, receiver=receiver)
    end
    block_counts = unique(
        Juna.frameblockcount(item.receiver, fs) for item in receivers)
    length(block_counts) == 1 || throw(ArgumentError(
        "native paper receivers disagree on duration-derived block count"))
    blocks = only(block_counts)
    payload_sizes = unique(
        Juna._frame_payload_capacity(item.receiver, blocks)
        for item in receivers)
    length(payload_sizes) == 1 || throw(ArgumentError(
        "native paper receivers disagree on payload geometry"))
    receivers, blocks, only(payload_sizes)
end

function _warm_receivers!(receivers, waveform, payload_bits, fc, fs)
    for item in receivers
        Modulations.demodulate(item.receiver, payload_bits, waveform, fc, fs)
    end
    nothing
end

function _warm_frame_receivers!(receivers, waveform, payload_bits, fc, fs)
    for item in receivers
        Modulations.demodulate(
            item.receiver, payload_bits, waveform, fc, fs)
    end
    nothing
end

function _channel_color(channel_id::AbstractString)
    descriptor = findfirst(entry -> String(entry.id) == channel_id,
                           CHANNEL_DESCRIPTORS)
    descriptor === nothing ? "fixture" : String(CHANNEL_DESCRIPTORS[descriptor].color)
end

function _stable_digest(value)
    io = IOBuffer()
    show(io, MIME"text/plain"(), value)
    _digest_bytes(take!(io))
end

function _binary_logloss_sum(metrics, payload, scale::Real)
    total = 0.0
    @inbounds for index in eachindex(payload)
        signed_metric = (payload[index] ? 1.0 : -1.0) *
                        Float64(metrics[index])
        x = -Float64(scale) * signed_metric
        # log2(1 + exp(x)), evaluated without overflow.
        total += (max(x, 0.0) + log1p(exp(-abs(x)))) / log(2.0)
    end
    total
end

"""
    _frame_soft_payload_metrics(receiver, code, lpost_metric, blocks, nbits)

Experiment-only counterpart of JunaCore's public frame-payload extraction.
The public method intentionally returns hard `+/-1` decisions; GMI needs the
selected BP posterior magnitudes, so this helper applies the identical
deinterleaving and inner-pilot omission without discarding LLR magnitude.
"""
function _frame_soft_payload_metrics(receiver, code, lpost_metric,
                                     blocks::Integer, nbits::Integer)
    block_count = Int(blocks)
    block_k = Int(receiver.ldpc_k)
    code.k == block_count * block_k || throw(ArgumentError(
        "frame LDPC message length does not match its OFDM block count"))
    output = Vector{Float64}(undef, Int(nbits))
    parity_bits = code.n - code.k
    inner_spacing = Juna._inner_pilot_spacing(receiver)
    output_position = 1
    @inbounds for message_position in 1:code.k
        inner_spacing >= 1 &&
            (message_position - 1) % inner_spacing == 0 && continue
        output_position > nbits && break
        output[output_position] = Float64(
            lpost_metric[code.invperm[parity_bits + message_position]])
        output_position += 1
    end
    output_position == nbits + 1 || throw(ArgumentError(
        "frame LDPC did not expose the requested payload length"))
    output
end

"""
    benchmark_frame_capture(capture; ...)

Compare the frame receiver algorithms with one LDPC codeword and one BP graph.
When `frame_blocks` is `nothing`, the largest whole-symbol frame that fits
`frame_duration_s` is derived from the configured FFT, CP, sample rate, sync,
and guard. A frame succeeds only when every payload bit in that complete frame
is recovered exactly. Decode timing ends when the selected payload posterior
has been produced; optional diagnostic trace replays are timed separately.
"""
function benchmark_frame_capture(capture::ReplayCapture;
                                 channel_id::AbstractString=capture.name,
                                 frames::Integer=1,
                                 frame_blocks::Union{Nothing,Integer}=nothing,
                                 frame_duration_s::Real=1.0,
                                 frame_crc_bits::Integer=0,
                                 frame_code_horizon::Integer=0,
                                 algorithms=FRAME_ALGORITHM_DESCRIPTORS,
                                 snr_db::Real=Inf,
                                 seed::Integer=1,
                                 modem_fs=nothing,
                                 modem_profile=:default,
                                 paper_config=nothing,
                                 nfft=nothing,
                                 cp=nothing,
                                 bpc=nothing,
                                 code_rate=nothing,
                                 check_degree=nothing,
                                 ldpc_method=nothing,
                                 ldpc_seed=nothing,
                                 ldpc_no4cycle=nothing,
                                 sync_profile=nothing,
                                 compatibility_profile=nothing,
                                 pilot_ratio=nothing,
                                 outer_pilot_ratio=nothing,
                                 inner_pilot_ratio=nothing,
                                 rpchan_guard_s=nothing,
                                 rpchan_doppler_ppm=nothing,
                                 rpchan_doppler_steps=nothing,
                                 modem_bw::Real=1.0,
                                 full_capture::Bool=false,
                                 warmup::Bool=true,
                                 payload_bits_per_frame=nothing,
                                 frame_sink::Function=_row -> nothing,
                                 # Experiment-only paired seed hook. Existing
                                 # callers keep the historical single RNG
                                 # stream when this is `nothing`.
                                 frame_seed_function::Union{Nothing,Function}=
                                     nothing,
                                 # Legacy opt-in: scale a shared raw noise draw
                                 # by the per-horizon all-zero warm waveform.
                                 paired_noise_reference::Bool=false,
                                 # When positive, build the paired-noise power
                                 # reference from an all-false frame with this
                                 # code horizon. This makes the reference
                                 # independent of the horizon under test while
                                 # retaining received-signal-power SNR.
                                 canonical_noise_reference_horizon::Integer=0,
                                 # An explicit experiment-wide power reference
                                 # takes precedence over the per-horizon warm
                                 # waveform.
                                 common_noise_reference_power=nothing,
                                 # Measured experiments should provide the
                                 # streaming SHA-256 of the MAT source. Generic
                                 # callers fall back to a compact binary capture
                                 # signature without walking the large arrays.
                                 replay_source_digest=nothing,
                                 llr_gmi_scale_grid=(),
                                 # Optional decode-boundary injection used by
                                 # contract tests and external instrumentation.
                                 # `nothing` preserves the production path.
                                 frame_decode_function::Union{Nothing,Function}=
                                     nothing,
                                 # Mechanism instrumentation. Off by default:
                                 # it re-runs the receiver trace outside the
                                 # timed region, so enabling it roughly doubles
                                 # decode work. Leaving it off keeps every
                                 # existing tool's timing and results identical.
                                 frame_diagnostics::Bool=false,
                                 strict_frame_diagnostics::Bool=false,
                                 frame_diagnostics_function::Function=
                                     _frame_feedback_diagnostics,
                                 candidate_sink::Function=_row -> nothing)
    full_capture && frames != 1 && throw(ArgumentError(
        "full-capture frame benchmark derives its frame count; leave frames=1"))
    frame_blocks === nothing || Int(frame_blocks) > 0 ||
        throw(ArgumentError("frame block count must be positive"))
    _validate_benchmark(full_capture ? 1 : frames, snr_db, seed)
    isempty(algorithms) && throw(ArgumentError(
        "select at least one frame algorithm"))
    fs = _resolve_modem_fs(capture, modem_fs)
    fc = capture.fc
    bandwidth = _effective_bandwidth_geometry(capture, fs, modem_bw)
    profile = select_modem_profile(modem_profile)
    if paper_config === nothing
        receivers, frame_capacity = _frame_receiver_set(
            algorithms,
            fc,
            fs;
            frame_blocks=frame_blocks,
            frame_duration_s=frame_duration_s,
            frame_crc_bits=frame_crc_bits,
            frame_code_horizon=frame_code_horizon,
            modem_profile=profile.id,
            nfft=nfft,
            cp=cp,
            bpc=bpc,
            code_rate=code_rate,
            check_degree=check_degree,
            ldpc_method=ldpc_method,
            ldpc_seed=ldpc_seed,
            ldpc_no4cycle=ldpc_no4cycle,
            sync_profile=sync_profile,
            compatibility_profile=compatibility_profile,
            pilot_ratio=pilot_ratio,
            outer_pilot_ratio=outer_pilot_ratio,
            inner_pilot_ratio=inner_pilot_ratio,
            rpchan_guard_s=rpchan_guard_s,
            rpchan_doppler_ppm=rpchan_doppler_ppm,
            rpchan_doppler_steps=rpchan_doppler_steps,
            channel_bandwidth_hz=bandwidth.channel_bandwidth_hz,
            modem_bw=bandwidth.requested_modem_bw,
        )
        blocks = frame_blocks === nothing ?
            Juna.frameblockcount(first(receivers).receiver, fs) :
            Int(frame_blocks)
    else
        frame_blocks === nothing || throw(ArgumentError(
            "native paper configuration derives blocks from frame duration"))
        receivers, blocks, frame_capacity = _paper_duration_receiver_set(
            paper_config, algorithms, fc, fs;
            frame_duration_s=frame_duration_s,
            frame_crc_bits=frame_crc_bits)
    end
    blocks <= 100 || throw(ArgumentError(
        "frame block count must not exceed 100"))
    payload_per_frame = payload_bits_per_frame === nothing ? frame_capacity :
        Int(payload_bits_per_frame)
    0 < payload_per_frame <= frame_capacity || throw(ArgumentError(
        "frame payload must be in 1:$frame_capacity bits"))
    all(item -> Juna._frame_nblocks(item.receiver, payload_per_frame) == blocks,
        receivers) || throw(ArgumentError(
            "requested payload does not preserve the declared frame block count"))
    transmitter = if paper_config === nothing
        _configure_modem!(
            Juna.FrameWideLDPCModulation(
                frame_receiver=:standard,
                frame_crc_bits=Int(frame_crc_bits),
                frame_code_horizon=Int(frame_code_horizon),
                frame_duration_s=Float64(frame_duration_s)),
            fc,
            fs,
            profile.id;
            nfft=nfft,
            cp=cp,
            bpc=bpc,
            partial_fft_parts=Int(first(receivers).receiver.partial_fft_parts),
            partial_fft_bands=Int(first(receivers).receiver.partial_fft_nbands),
            code_rate=code_rate,
            check_degree=check_degree,
            ldpc_method=ldpc_method,
            ldpc_seed=ldpc_seed,
            ldpc_no4cycle=ldpc_no4cycle,
            sync_profile=sync_profile,
            compatibility_profile=compatibility_profile,
            frame_duration_s=frame_duration_s,
            pilot_ratio=pilot_ratio,
            outer_pilot_ratio=outer_pilot_ratio,
            inner_pilot_ratio=inner_pilot_ratio,
            bw=bandwidth.normalized_bw,
        )
    else
        sync_profile === nothing || throw(ArgumentError(
            "paper_config fixes the synchronization profile"))
        compatibility_profile === nothing || throw(ArgumentError(
            "paper_config fixes the compatibility profile"))
        native = _paper_frame_wide_modem(paper_config, fc, fs)
        native.frame_receiver = :standard
        native.frame_crc_bits = Int(frame_crc_bits)
        native.frame_duration_s = Float64(frame_duration_s)
        native.code = nothing
        native.bp_scratch = nothing
        native
    end
    if paper_config === nothing
        rpchan_guard_s === nothing ||
            (transmitter.rpchan_guard_s = Float64(rpchan_guard_s))
        rpchan_doppler_ppm === nothing ||
            (transmitter.rpchan_doppler_ppm = Float64(rpchan_doppler_ppm))
        rpchan_doppler_steps === nothing ||
            (transmitter.rpchan_doppler_steps = Int(rpchan_doppler_steps))
    end
    Juna._frame_payload_capacity(transmitter, blocks) == frame_capacity ||
        throw(ArgumentError(
            "frame transmitter and receivers disagree on payload geometry"))

    # Realized pilot overhead. The configured outer/inner ratios are only
    # requests: JunaCore snaps them to the nearest 1/k comb, so they must not be
    # used as the overhead covariate. These are frame-invariant, so compute once.
    tx_layout = Juna._layout(transmitter, fs)
    tx_code = Juna._frame_code(transmitter, blocks)
    ldpc_method_requested = String(transmitter.ldpc_method)
    ldpc_base_method = String(Juna._frame_base_code_method(transmitter))
    ldpc_code_method = String(tx_code.method)
    ldpc_seed_requested = Int(transmitter.ldpc_seed)
    ldpc_code_seed = Int(tx_code.seed)
    ldpc_component_seed =
        Int(Juna._frame_component_code_seed(transmitter, blocks))
    ldpc_no4cycle_requested = Bool(transmitter.ldpc_no4cycle)
    # `frame_sparse` constructs its graph internally and never invokes
    # make-ldpc's no-four-cycle pass. `_Code.no4cycle` records the request, so
    # expose the effective behavior separately.
    ldpc_no4cycle_effective =
        ldpc_no4cycle_requested &&
        !occursin("frame_sparse", ldpc_code_method)
    realized_outer_pilot_fraction =
        length(tx_layout.pilot_idx) / length(tx_layout.active)
    realized_inner_pilot_fraction =
        Juna._n_inner(transmitter, tx_code.k) / tx_code.k
    coded_data_tones = Juna._ndata_tones(transmitter, Int(transmitter.ldpc_n))

    warm_payload = falses(payload_per_frame)
    warm_waveform = Modulations.modulate(
        transmitter, warm_payload, fc, fs)
    canonical_reference_waveform =
        if paired_noise_reference &&
           Int(canonical_noise_reference_horizon) > 0
            reference_transmitter = deepcopy(transmitter)
            reference_transmitter.frame_code_horizon =
                Int(canonical_noise_reference_horizon)
            reference_transmitter.code = nothing
            reference_transmitter.bp_scratch = nothing
            Modulations.modulate(
                reference_transmitter, warm_payload, fc, fs)
        else
            warm_waveform
        end
    length(canonical_reference_waveform) == length(warm_waveform) ||
        throw(ArgumentError(
            "canonical noise reference changed the physical frame length"))
    for item in receivers
        item.receiver.code = transmitter.code
        item.receiver.layout = transmitter.layout
        item.receiver.bp_scratch = nothing
    end
    if warmup
        warm_needs_truth = any(
            item -> item.receiver.feedback_mode in (:genie, :graded) ||
                    (hasproperty(item.receiver, :cz_feedback_source) &&
                     item.receiver.cz_feedback_source === :genie),
            receivers)
        if warm_needs_truth
            warm_truth = _frame_truth_symbols(
                transmitter, warm_payload, fs)
            warm_alphabet = _frame_constellation(transmitter)
            for (index, item) in pairs(receivers)
                _attach_feedback_truth!(
                    item.receiver, warm_truth, warm_alphabet,
                    MersenneTwister(Int(seed) + index),
                    coded_data_tones)
            end
        end
        _warm_frame_receivers!(
            receivers, warm_waveform, payload_per_frame, fc, fs)
    end

    snapshots = if full_capture
        frame_seed_function === nothing || throw(ArgumentError(
            "seeded replay positions are incompatible with full_capture"))
        _full_capture_positions(capture, length(warm_waveform), fs)
    elseif frame_seed_function === nothing
        _snapshot_positions(capture, frames, length(warm_waveform), fs)
    else
        _, stop = _capture_position_limit(
            capture, length(warm_waveform), fs)
        Int(frames) <= stop || throw(ArgumentError(
            "capture has only $stop seeded replay positions, requested $frames"))
        selected = Int[]
        occupied = Set{Int}()
        for frame in 1:Int(frames)
            candidate = rand(
                MersenneTwister(Int(frame_seed_function(frame, :replay))),
                1:stop)
            while candidate in occupied
                candidate = candidate == stop ? 1 : candidate + 1
            end
            push!(selected, candidate)
            push!(occupied, candidate)
        end
        selected
    end
    frame_count = length(snapshots)
    successful = zeros(Int, length(receivers))
    bit_errors = zeros(Int, length(receivers))
    failures = zeros(Int, length(receivers))
    decode_samples = [Float64[] for _ in receivers]
    errors = fill("", length(receivers))
    color = _channel_color(String(channel_id))
    workload_digests = String[]
    code_digests = String[]
    transmitted_digests = String[]
    received_digests = String[]
    code_digest = _digest_code(transmitter.code)
    scale_grid = Float64.(collect(llr_gmi_scale_grid))
    all(scale -> isfinite(scale) && scale >= 0, scale_grid) ||
        throw(ArgumentError("LLR GMI scale grid must be finite and nonnegative"))
    Int(canonical_noise_reference_horizon) >= 0 || throw(ArgumentError(
        "canonical noise-reference horizon must be nonnegative"))
    capture_source_digest = replay_source_digest === nothing ?
        _compact_capture_digest(capture) : String(replay_source_digest)
    isempty(capture_source_digest) && throw(ArgumentError(
        "replay source digest must not be empty"))
    replay_capture_digest = _stable_digest((
        capture_source_digest, capture.name, capture.receiver,
        capture.fs, capture.fc, capture.step, size(capture.h),
        length(capture.phase)))
    reference_powers = if common_noise_reference_power !== nothing
        power = Float64(common_noise_reference_power)
        isfinite(power) && power > 0 || throw(ArgumentError(
            "common noise reference power must be finite and positive"))
        fill(power, frame_count)
    elseif paired_noise_reference && !isinf(snr_db)
        reference_key = _stable_digest((
            replay_capture_digest, snapshots,
            _digest_complex(canonical_reference_waveform),
            fs, profile.id, profile.passband_oversample,
            Int(canonical_noise_reference_horizon)))
        cached = _EXPERIMENT_B_NOISE_REFERENCE_CACHE[]
        if cached !== nothing && cached.key == reference_key
            copy(cached.powers)
        else
            powers = map(snapshots) do snapshot
                reference = if _uses_passband_replay(profile)
                    replay_passband_at_modem_rate(
                        capture, canonical_reference_waveform; snapshot,
                        modem_fs=fs,
                        passband_oversample=profile.passband_oversample)
                else
                    replay_at_modem_rate(
                        capture, canonical_reference_waveform;
                        snapshot, modem_fs=fs)
                end
                power = sum(abs2, reference) / length(reference)
                isfinite(power) && power > 0 || throw(ArgumentError(
                    "canonical received noise reference has invalid power"))
                power
            end
            _EXPERIMENT_B_NOISE_REFERENCE_CACHE[] =
                (; key=reference_key, powers=copy(powers))
            powers
        end
    else
        fill(nothing, frame_count)
    end

    for frame in 1:frame_count
        payload_seed = frame_seed_function === nothing ?
            Int(seed) + frame - 1 : Int(frame_seed_function(frame, :payload))
        noise_seed = frame_seed_function === nothing ?
            payload_seed : Int(frame_seed_function(frame, :noise))
        replay_seed = frame_seed_function === nothing ?
            payload_seed : Int(frame_seed_function(frame, :replay))
        optimizer_seed = frame_seed_function === nothing ?
            Int(seed) : Int(frame_seed_function(frame, :optimizer))
        genie_seed = frame_seed_function === nothing ?
            Int(seed) + 1_000_003 * frame :
            Int(frame_seed_function(frame, :genie))
        payload_rng = MersenneTwister(payload_seed)
        # Preserve the historical single-stream draw exactly unless the
        # experiment-only hook is active.
        noise_rng = frame_seed_function === nothing ?
            payload_rng : MersenneTwister(noise_seed)
        payload = rand(payload_rng, Bool, payload_per_frame)
        transmitted = Modulations.modulate(
            transmitter, payload, fc, fs)
        replayed = if _uses_passband_replay(profile)
            replay_passband_at_modem_rate(
                capture, transmitted; snapshot=snapshots[frame], modem_fs=fs,
                passband_oversample=profile.passband_oversample,
            )
        else
            replay_at_modem_rate(
                capture, transmitted; snapshot=snapshots[frame], modem_fs=fs)
        end
        recorded_awgn = frame_seed_function === nothing ? nothing :
            _add_awgn_recorded(
                replayed, snr_db, noise_rng;
                reference_power=reference_powers[frame])
        noisy = recorded_awgn === nothing ?
            _add_awgn(
                replayed, snr_db, noise_rng;
                reference_power=reference_powers[frame]) :
            recorded_awgn.noisy
        received = _uses_passband_replay(profile) ? noisy : align_to_reference(
            noisy, transmitted; max_lag=length(noisy) - length(transmitted),
        ).waveform
        payload_digest = _digest_bits(payload)
        additive_noise = recorded_awgn === nothing ?
            noisy .- replayed : recorded_awgn.noise
        noise_digest = _digest_complex(additive_noise)
        replay_digest = _stable_digest((
            replay_capture_digest, snapshots[frame], replay_seed))
        transmitted_digest = _digest_complex(transmitted)
        received_digest = _digest_complex(received)
        workload_digest = _digest_workload(
            payload_digest, code_digest, transmitted_digest, received_digest)
        push!(workload_digests, workload_digest)
        push!(code_digests, code_digest)
        push!(transmitted_digests, transmitted_digest)
        push!(received_digests, received_digest)

        # Ground truth for the oracle feedback arms. Built once per frame and
        # only when some receiver actually needs it, so the deployed arms pay
        # nothing. Graded corruption is seeded from this frame's stream so a run
        # reproduces exactly.
        needs_truth = any(
            item -> item.receiver.feedback_mode in (:genie, :graded) ||
                    (hasproperty(item.receiver, :cz_feedback_source) &&
                     item.receiver.cz_feedback_source === :genie),
            receivers)
        truth_grid = (needs_truth || frame_diagnostics) ?
            _frame_truth_symbols(transmitter, payload, fs) : nothing
        if needs_truth
            alphabet = _frame_constellation(transmitter)
            for (index, item) in pairs(receivers)
                _attach_feedback_truth!(
                    item.receiver, truth_grid, alphabet,
                    MersenneTwister(genie_seed + index - 1),
                    coded_data_tones)
            end
        end

        for (index, item) in pairs(receivers)
            item.receiver.cz_restart_seed = optimizer_seed
            started = time_ns()
            frame_errors = payload_per_frame
            decode_failed = false
            decoder_valid = missing
            crc_valid = missing
            baseline_valid = missing
            accepted_update = missing
            selection_reason = missing
            selected_iteration = missing
            lite_syndrome = missing
            gradient_syndrome = missing
            lite_score = missing
            gradient_score = missing
            lite_mean_abs_lpost = missing
            gradient_mean_abs_lpost = missing
            selected_mean_abs_lpost = missing
            conditioned_accepted_steps = missing
            conditioned_rejected_steps = missing
            conditioned_mean_step_scale = missing
            # Mechanism instrumentation; stays `missing` unless diagnostics are
            # enabled, and must be declared before the try because Julia's
            # try/catch opens a new scope.
            seed_bit_errors = missing
            seed_ber = missing
            seed_equalized_mse = missing
            best_equalized_mse = missing
            refinement_iteration = missing
            data_anchor_total = missing
            llr_gmi_logloss_sums = missing
            candidate_trajectory_digest = missing
            feedback_source = missing
            feedback_support_digest = missing
            feedback_weights_digest = missing
            feedback_values_digest = missing
            feedback_checkpoint_count = missing
            decode_seconds = 0.0
            diagnostic_seconds = missing
            decode_finished = false
            decode_failure_message = ""
            decode_failure_stage = ""
            active_stage = "decode"
            decoder_input = copy(received)
            try
                metrics = if frame_decode_function !== nothing
                    frame_decode_function(
                        item, payload_per_frame, decoder_input, fc, fs)
                elseif !isempty(scale_grid)
                    # Experiment B opts into the selected posterior. Calling
                    # the same internal trace used by the public demodulator
                    # preserves decisions while retaining LLR magnitude.
                    nbits2, code, layout, nblocks, observations, _ =
                        Juna._prepare_frame_observations(
                            item.receiver, payload_per_frame,
                            decoder_input, fc, fs)
                    selected_trace = Juna._frame_receiver_trace(
                        item.receiver, code, layout, observations;
                        payload_nbits=nbits2)
                    decoder_valid = selected_trace.best.valid
                    selected_mean_abs_lpost =
                        hasproperty(selected_trace.best, :mean_abs_lpost) ?
                        selected_trace.best.mean_abs_lpost :
                        sum(abs, selected_trace.best.lpost_metric) /
                        length(selected_trace.best.lpost_metric)
                    framed_posterior = _frame_soft_payload_metrics(
                        item.receiver, code,
                        selected_trace.best.lpost_metric, nblocks,
                        payload_per_frame + Int(frame_crc_bits))
                    crc_valid = Juna._frame_crc_valid(
                        framed_posterior .> 0, Int(frame_crc_bits))
                    @view framed_posterior[1:payload_per_frame]
                elseif item.descriptor.profile in (:standard, :pfft)
                    nbits2, code, layout, nblocks, observations, _ =
                        Juna._prepare_frame_observations(
                            item.receiver, payload_per_frame,
                            decoder_input, fc, fs)
                    trace = Juna._frame_receiver_trace(
                        item.receiver, code, layout, observations;
                        payload_nbits=nbits2)
                    decoder_valid = trace.best.valid
                    selected_mean_abs_lpost =
                        hasproperty(trace.best, :mean_abs_lpost) ?
                        trace.best.mean_abs_lpost :
                        sum(abs, trace.best.lpost_metric) /
                        length(trace.best.lpost_metric)
                    framed_metrics = Juna._frame_payload_metrics(
                        item.receiver, code, trace.best.lpost_metric, nblocks,
                        payload_per_frame + Int(frame_crc_bits))
                    crc_valid = Juna._frame_crc_valid(
                        framed_metrics .> 0, Int(frame_crc_bits))
                    @view framed_metrics[1:payload_per_frame]
                else
                    first(Modulations.demodulate(
                        item.receiver,
                        payload_per_frame,
                        decoder_input,
                        fc,
                        fs,
                    ))
                end
                length(metrics) == payload_per_frame ||
                    throw(DimensionMismatch(
                        "frame decoder returned $(length(metrics)) metrics"))
                # Stop the decode clock at the receiver output boundary.
                # Candidate bookkeeping and the optional diagnostic trace
                # replay below are measurement work, not decoder latency.
                decode_seconds = (time_ns() - started) / 1e9
                decode_finished = true
                active_stage = "postdecode"
                frame_errors = count((metrics .> 0) .!= payload)
                llr_gmi_logloss_sums = isempty(scale_grid) ? missing :
                    join((_binary_logloss_sum(metrics, payload, scale)
                          for scale in scale_grid), ';')
                bit_errors[index] += frame_errors
                successful[index] += iszero(frame_errors)
                if item.descriptor.profile === :fully_coupled
                    trace = Juna._fully_coupled_last_trace(item.receiver)
                    decoder_valid = trace.final_valid
                    baseline_valid = trace.baseline_valid
                    accepted_update = trace.accepted_update
                elseif item.descriptor.profile === :profiled_gradient
                    trace = Juna._profiled_gradient_last_trace(item.receiver)
                    decoder_valid = trace.gradient.valid
                    baseline_valid = trace.lite.valid
                    accepted_update = trace.selected_gradient
                    selection_reason = trace.selection_reason
                    selected_iteration = trace.selected_iteration
                    lite_syndrome = trace.lite.syndrome
                    gradient_syndrome = trace.gradient.syndrome
                    lite_score = trace.lite.score
                    gradient_score = trace.gradient.score
                    lite_mean_abs_lpost = trace.lite.mean_abs_lpost
                    gradient_mean_abs_lpost = trace.gradient.mean_abs_lpost
                elseif item.descriptor.profile === :profiled_cz
                    trace = Juna._cz_gradient_last_trace(item.receiver)
                    decoder_valid = trace.gradient.valid
                    baseline_valid = trace.lite.valid
                    accepted_update = trace.selected_gradient
                    selection_reason = trace.selection_reason
                    selected_iteration = trace.selected_iteration
                    lite_syndrome = trace.lite.syndrome
                    gradient_syndrome = trace.gradient.syndrome
                    lite_score = trace.lite.score
                    gradient_score = trace.gradient.score
                    conditioned_accepted_steps =
                        trace.conditioned_accepted_steps
                    conditioned_rejected_steps =
                        trace.conditioned_rejected_steps
                    conditioned_mean_step_scale =
                        isempty(trace.conditioned_step_scales) ? 0.0 :
                        sum(trace.conditioned_step_scales) /
                        length(trace.conditioned_step_scales)
                    candidate_trajectory_digest =
                        _stable_digest(trace.candidates)
                    feedback_source = String(trace.feedback_source)
                    feedback_support_digest =
                        _stable_digest(trace.feedback_support)
                    feedback_weights_digest =
                        _stable_digest(trace.feedback_weights)
                    feedback_values_digest =
                        _stable_digest(trace.feedback_value_history)
                    feedback_checkpoint_count =
                        length(trace.feedback_value_history)
                end
                trace_candidates =
                    item.descriptor.profile === :profiled_cz ?
                    Juna._cz_gradient_last_trace(item.receiver).candidates :
                    NamedTuple[]
                candidate_sink((
                    workload_id="$(String(channel_id)):lane$(capture.receiver):" *
                                "snr$(Float64(snr_db)):seed$(Int(seed)):frame$frame",
                    algorithm=item.descriptor.name,
                    payload=copy(payload),
                    decoded=BitVector(metrics .> 0),
                    candidates=copy(trace_candidates),
                ))
                if frame_diagnostics
                    active_stage = "diagnostic"
                    diagnostic_started = time_ns()
                    diag = try
                        frame_diagnostics_function(
                            item, payload_per_frame, decoder_input, fc, fs,
                            payload, Int(frame_crc_bits), truth_grid)
                    finally
                        diagnostic_seconds =
                            (time_ns() - diagnostic_started) / 1e9
                    end
                    if strict_frame_diagnostics
                        diagnostic_failure =
                            hasproperty(diag, :diagnostic_failure_message) ?
                            String(diag.diagnostic_failure_message) : ""
                        isempty(diagnostic_failure) || error(
                            "frame diagnostics failed: " *
                            diagnostic_failure)
                        for field in (
                                :seed_ber, :seed_equalized_mse,
                                :best_equalized_mse)
                            value = getproperty(diag, field)
                            value === missing && continue
                            value isa Real && isfinite(value) || error(
                                "frame diagnostics produced nonfinite " *
                                String(field))
                        end
                    end
                    seed_bit_errors = diag.seed_bit_errors
                    seed_ber = diag.seed_ber
                    seed_equalized_mse = diag.seed_equalized_mse
                    best_equalized_mse = diag.best_equalized_mse
                    refinement_iteration = diag.refinement_iteration
                    data_anchor_total = diag.data_anchor_total
                end
                active_stage = "complete"
            catch exception
                decode_failed = true
                failures[index] += 1
                decode_failure_stage = active_stage
                if decode_finished
                    # The decoded result was already accumulated before the
                    # post-decode/diagnostic failure. Replace, rather than
                    # double-count, that result with the preregistered
                    # full-frame failure penalty.
                    bit_errors[index] += payload_per_frame - frame_errors
                    successful[index] -= iszero(frame_errors)
                else
                    bit_errors[index] += payload_per_frame
                end
                frame_errors = payload_per_frame
                decode_failure_message = sprint(
                    showerror, exception; context=:compact => true)
                isempty(errors[index]) &&
                    (errors[index] = decode_failure_message)
            finally
                decode_finished ||
                    (decode_seconds = (time_ns() - started) / 1e9)
                push!(decode_samples[index], decode_seconds)
            end
            frame_sink((
                workload_id="$(String(channel_id)):lane$(capture.receiver):" *
                            "snr$(Float64(snr_db)):seed$(Int(seed)):frame$frame",
                channel=String(channel_id),
                color=color,
                algorithm=item.descriptor.name,
                profile=String(item.descriptor.profile),
                modem_profile=String(profile.id),
                sync_profile="lfm",   # D4: field removed in CL-10
                compatibility_profile="juna",   # D4
                receiver=capture.receiver,
                snr_db=Float64(snr_db),
                seed=Int(seed),
                frame=frame,
                frame_blocks=blocks,
                frame_crc_bits=Int(frame_crc_bits),
                frame_payload_capacity=frame_capacity,
                frame_samples=length(transmitted),
                frame_duration_seconds=length(transmitted) / fs,
                partial_fft_parts=Int(item.receiver.partial_fft_parts),
                partial_fft_bands=Int(item.receiver.partial_fft_nbands),
                check_degree=Int(item.receiver.ldpc_npc),
                ldpc_method=String(item.receiver.ldpc_method),
                ldpc_seed=Int(item.receiver.ldpc_seed),
                ldpc_no4cycle=item.receiver.ldpc_no4cycle,
                ldpc_method_requested,
                ldpc_base_method,
                ldpc_code_method,
                ldpc_seed_requested,
                ldpc_code_seed,
                ldpc_component_seed,
                ldpc_no4cycle_requested,
                ldpc_no4cycle_effective,
                outer_pilot_ratio=item.receiver.pilot_ratio,
                inner_pilot_ratio=item.receiver.inner_pilot_ratio,
                realized_outer_pilot_fraction=realized_outer_pilot_fraction,
                realized_inner_pilot_fraction=realized_inner_pilot_fraction,
                snapshot_index=snapshots[frame],
                payload_seed,
                noise_seed,
                replay_seed,
                optimizer_seed,
                genie_seed,
                feedback_mode=String(item.receiver.feedback_mode),
                feedback_graded_p=Float64(item.receiver.feedback_graded_p),
                seed_bit_errors,
                seed_ber,
                seed_equalized_mse,
                best_equalized_mse,
                refinement_iteration,
                data_anchor_total,
                llr_gmi_scale_grid=join(scale_grid, ';'),
                llr_gmi_logloss_sums,
                llr_gmi_count=isempty(scale_grid) ? missing :
                    payload_per_frame,
                payload_bits=payload_per_frame,
                bit_errors=frame_errors,
                success=iszero(frame_errors),
                decode_failure=decode_failed,
                decode_failure_message,
                decode_failure_stage,
                decode_seconds,
                diagnostic_seconds,
                decoder_valid,
                crc_valid,
                baseline_valid,
                accepted_update,
                selection_reason,
                selected_iteration,
                lite_syndrome,
                gradient_syndrome,
                lite_score,
                gradient_score,
                lite_mean_abs_lpost,
                gradient_mean_abs_lpost,
                selected_mean_abs_lpost,
                conditioned_accepted_steps,
                conditioned_rejected_steps,
                conditioned_mean_step_scale,
                candidate_trajectory_digest,
                feedback_source,
                feedback_support_digest,
                feedback_weights_digest,
                feedback_values_digest,
                feedback_checkpoint_count,
                workload_digest,
                payload_digest,
                scored_digest=payload_digest,
                code_digest,
                transmitted_digest,
                received_digest,
                noise_digest,
                replay_digest,
            ))
        end
    end

    attempted_bits = frame_count * payload_per_frame
    map(eachindex(receivers)) do index
        descriptor = receivers[index].descriptor
        timing = _timing_summary(decode_samples[index])
        psr_interval = _wilson_interval(
            successful[index], frame_count)
        status = failures[index] == 0 ? "ok" :
                 "$(failures[index]) frame decode failure(s): $(errors[index])"
        (
            channel=String(channel_id),
            color=color,
            algorithm=descriptor.name,
            profile=String(descriptor.profile),
            modem_profile=String(profile.id),
            sync_profile="lfm",   # D4: field removed in CL-10
            compatibility_profile="juna",   # D4
            receiver=capture.receiver,
            modem_fs=fs,
            capture_fs=capture.fs,
            requested_modem_bw=bandwidth.requested_modem_bw,
            requested_modem_bandwidth_hz=
                bandwidth.requested_modem_bandwidth_hz,
            channel_bandwidth_hz=bandwidth.channel_bandwidth_hz,
            effective_bandwidth_hz=bandwidth.effective_bandwidth_hz,
            effective_bw=bandwidth.normalized_bw,
            frames=frame_count,
            frame_blocks=blocks,
            frame_crc_bits=Int(frame_crc_bits),
            frame_payload_capacity=frame_capacity,
            frame_samples=length(warm_waveform),
            frame_duration_seconds=length(warm_waveform) / fs,
            partial_fft_parts=Int(receivers[index].receiver.partial_fft_parts),
            partial_fft_bands=Int(receivers[index].receiver.partial_fft_nbands),
            check_degree=Int(receivers[index].receiver.ldpc_npc),
            ldpc_method=String(receivers[index].receiver.ldpc_method),
            ldpc_seed=Int(receivers[index].receiver.ldpc_seed),
            ldpc_no4cycle=receivers[index].receiver.ldpc_no4cycle,
            ldpc_method_requested,
            ldpc_base_method,
            ldpc_code_method,
            ldpc_seed_requested,
            ldpc_code_seed,
            ldpc_component_seed,
            ldpc_no4cycle_requested,
            ldpc_no4cycle_effective,
            outer_pilot_ratio=receivers[index].receiver.pilot_ratio,
            inner_pilot_ratio=receivers[index].receiver.inner_pilot_ratio,
            payload_bits_per_frame=payload_per_frame,
            successful_frames=successful[index],
            psr=successful[index] / frame_count,
            psr_ci95_low=psr_interval[1],
            psr_ci95_high=psr_interval[2],
            payload_bits=attempted_bits,
            bit_errors=bit_errors[index],
            ber=bit_errors[index] / attempted_bits,
            decode_failures=failures[index],
            mean_decode_seconds_per_frame=timing.mean,
            mean_decode_seconds_per_block=timing.mean / blocks,
            median_decode_seconds_per_frame=timing.median,
            p95_decode_seconds_per_frame=timing.p95,
            total_decode_seconds=timing.total,
            effective_rate_bps=
                successful[index] * payload_per_frame /
                (frame_count * length(warm_waveform) / fs),
            snr_db=Float64(snr_db),
            seed=Int(seed),
            workload_digest=_digest_sequence(workload_digests),
            code_digest=_digest_sequence(code_digests),
            transmitted_digest=_digest_sequence(transmitted_digests),
            received_digest=_digest_sequence(received_digests),
            status=status,
        )
    end
end

function _validate_capture_rate(channel, capture::ReplayCapture)
    isapprox(capture.fs, channel.capture_fs; rtol=0, atol=eps(channel.capture_fs)) ||
        throw(ArgumentError(
            "$(channel.id) declares fs_delay=$(capture.fs), expected $(channel.capture_fs)"))
    nothing
end

function _pilot_budget_geometry(pilot_ratio)
    pilot_ratio === nothing && return nothing
    pilot_ratio isa Real || throw(ArgumentError("pilot ratio must be real"))
    requested = Float64(pilot_ratio)
    isfinite(requested) && 0 < requested <= 1 ||
        throw(ArgumentError("pilot ratio must be finite and in (0, 1]"))
    per_domain = requested / 2
    outer_spacing = Juna._ratio_spacing(per_domain, 2)
    inner_spacing = Juna._ratio_spacing(per_domain, 1)
    (
        requested=requested,
        per_domain=per_domain,
        outer_spacing=outer_spacing,
        inner_spacing=inner_spacing,
        outer_density=1 / outer_spacing,
        inner_density=1 / inner_spacing,
    )
end


end # module
