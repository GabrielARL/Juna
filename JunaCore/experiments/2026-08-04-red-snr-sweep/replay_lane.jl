# Replay one measured channel lane over a modem waveform.
#
# Ported from sonique research/JunaCoreTests tools/replay_coupled_segment.jl
# (capture loading, time-varying FIR replay, alignment). Differences from the
# source, all deliberate:
#   * decode_segment and the coupled-receiver path are not ported (that
#     receiver is not in this package).
#   * replay_passband_at_modem_rate is not ported; this harness runs the
#     modem at the capture delay-grid rate, so no resampler is needed and
#     SignalAnalysis is not a dependency.
module ReplayLane

import MAT

export ReplayCapture, align_to_reference, apply_capture, capture_from_dict,
       load_capture

struct ReplayCapture
    h::Matrix{ComplexF64}       # oldest-delay to zero-delay tap x snapshot
    phase::Vector{Float64}      # baseband phase track for that lane
    fs::Float64
    fc::Float64
    step::Int
    receiver::Int
    name::String
    function ReplayCapture(h::Matrix{ComplexF64},
                           phase::Vector{Float64},
                           fs::Float64,
                           fc::Float64,
                           step::Int,
                           receiver::Int,
                           name::String)
        size(h, 1) > 0 || throw(ArgumentError("replay capture needs at least one tap"))
        size(h, 2) > 0 || throw(ArgumentError("replay capture needs at least one snapshot"))
        isempty(phase) && throw(ArgumentError("replay capture phase track must not be empty"))
        isfinite(fs) && fs > 0 || throw(ArgumentError("replay capture fs must be positive"))
        isfinite(fc) && fc > 0 || throw(ArgumentError("replay capture fc must be positive"))
        step > 0 || throw(ArgumentError("replay capture step must be positive"))
        receiver > 0 || throw(ArgumentError("replay receiver must be positive"))
        isempty(name) && throw(ArgumentError("replay capture name must not be empty"))
        all(x -> isfinite(real(x)) && isfinite(imag(x)), h) ||
            throw(ArgumentError("replay taps must be finite"))
        all(isfinite, phase) || throw(ArgumentError("replay phase must be finite"))
        new(h, phase, fs, fc, step, receiver, name)
    end
end

function ReplayCapture(h::AbstractMatrix,
                       phase::AbstractVector,
                       fs::Real,
                       fc::Real,
                       step::Integer,
                       receiver::Integer,
                       name::AbstractString)
    h2 = Matrix{ComplexF64}(h)
    phase2 = Float64.(phase)
    ReplayCapture(h2, phase2, Float64(fs), Float64(fc), Int(step),
                  Int(receiver), String(name))
end

_has(data, key::String) = haskey(data, key) || haskey(data, Symbol(key))
_get(data, key::String) = haskey(data, key) ? data[key] : data[Symbol(key)]

function _scalar(value, name::String)
    x = value isa AbstractArray ? only(value) : value
    x isa Number || throw(ArgumentError("$name must be numeric"))
    iszero(imag(x)) || throw(ArgumentError("$name must be real"))
    y = Float64(real(x))
    isfinite(y) || throw(ArgumentError("$name must be finite"))
    y
end

function capture_from_dict(data;
                           receiver::Integer=1,
                           name::AbstractString="replay")
    _has(data, "h_hat") || throw(ArgumentError("replay data is missing h_hat"))
    _has(data, "params") || throw(ArgumentError("replay data is missing params"))
    phase_key = _has(data, "phi_hat") ? "phi_hat" :
                (_has(data, "theta_hat") ? "theta_hat" : "")
    isempty(phase_key) &&
        throw(ArgumentError("replay data is missing phi_hat/theta_hat"))

    hraw = _get(data, "h_hat")
    ndims(hraw) == 3 || throw(ArgumentError("h_hat must be tap x receiver x snapshot"))
    rx = Int(receiver)
    1 <= rx <= size(hraw, 2) ||
        throw(ArgumentError("receiver $rx is outside h_hat lane count $(size(hraw, 2))"))
    # Match ReplayCh.open_red_ch: delay estimates are stored in reverse tap order.
    h = reverse(ComplexF64.(hraw[:, rx, :]); dims=1)

    phase_raw = _get(data, phase_key)
    ndims(phase_raw) == 2 || throw(ArgumentError("$phase_key must be receiver x sample"))
    size(phase_raw, 1) >= rx ||
        throw(ArgumentError("$phase_key has no receiver lane $rx"))
    phase = Float64.(vec(phase_raw[rx, :]))

    params = _get(data, "params")
    for key in ("fs_delay", "fc", "fs_time")
        _has(params, key) || throw(ArgumentError("replay params is missing $key"))
    end
    fs = _scalar(_get(params, "fs_delay"), "params.fs_delay")
    fc = _scalar(_get(params, "fc"), "params.fc")
    fs_time = _scalar(_get(params, "fs_time"), "params.fs_time")
    step = round(Int, fs / fs_time)
    ReplayCapture(h, phase, fs, fc, step, rx, name)
end

function load_capture(path::AbstractString; receiver::Integer=1)
    isfile(path) || throw(ArgumentError("replay MAT file does not exist: $path"))
    filesize(path) > 1_000_000 ||
        throw(ArgumentError("replay MAT file is too small and may be truncated"))
    data = MAT.matread(path)
    name = first(splitext(basename(path)))
    capture_from_dict(data; receiver=receiver, name=name)
end

# ReplayCh-compatible time-varying FIR interpolation for one selected lane.
function apply_capture(capture::ReplayCapture,
                       input::AbstractVector{<:Number};
                       snapshot::Integer=1)
    isempty(input) && throw(ArgumentError("replay input must not be empty"))
    start = Int(snapshot)
    1 <= start <= size(capture.h, 2) ||
        throw(ArgumentError("snapshot $start is outside 1:$(size(capture.h, 2))"))

    x = ComplexF64.(input)
    ntaps, nsnapshots = size(capture.h)
    output = zeros(ComplexF64, length(x) + ntaps - 1)
    @inbounds for output_idx in eachindex(output)
        offset = output_idx - 1
        snap = min(start + div(offset, capture.step), nsnapshots)
        next_snap = min(snap + 1, nsnapshots)
        alpha = mod(offset, capture.step) / capture.step
        base = output_idx - ntaps
        acc = 0.0 + 0.0im
        for tap in 1:ntaps
            input_idx = base + tap
            1 <= input_idx <= length(x) || continue
            response = (1 - alpha) * capture.h[tap, snap] +
                       alpha * capture.h[tap, next_snap]
            acc += response * x[input_idx]
        end
        phase_idx = min(
            (start - 1) * capture.step + offset + 1,
            length(capture.phase))
        output[output_idx] = acc * cis(capture.phase[phase_idx])
    end
    output
end

function align_to_reference(received::AbstractVector{<:Number},
                            reference::AbstractVector{<:Number};
                            max_lag::Integer)
    isempty(reference) && throw(ArgumentError("alignment reference must not be empty"))
    length(received) >= length(reference) ||
        throw(DimensionMismatch("received segment is shorter than its reference"))
    limit = min(Int(max_lag), length(received) - length(reference))
    limit >= 0 || throw(ArgumentError("max_lag must be nonnegative"))

    rx = ComplexF64.(received)
    tx = ComplexF64.(reference)
    tx_power = sum(abs2, tx)
    tx_power > 0 || throw(ArgumentError("alignment reference must have nonzero power"))
    best_lag = 0
    best_score = -Inf
    @inbounds for lag in 0:limit
        segment = @view rx[lag+1:lag+length(tx)]
        cross = sum(conj.(tx) .* segment)
        segment_power = sum(abs2, segment)
        score = segment_power == 0 ? 0.0 : abs(cross) / sqrt(tx_power * segment_power)
        if score > best_score
            best_lag = lag
            best_score = score
        end
    end

    segment = copy(@view rx[best_lag+1:best_lag+length(tx)])
    segment_power = sum(abs2, segment)
    gain = segment_power == 0 ? one(ComplexF64) :
           sum(conj.(segment) .* tx) / segment_power
    (waveform = gain .* segment, lag = best_lag, score = best_score, gain = gain)
end

end # module
