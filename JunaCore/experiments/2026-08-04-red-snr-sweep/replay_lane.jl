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
       capture_snapshot_limit, load_capture

struct ReplayCapture
    h::Matrix{ComplexF64}       # oldest-delay to zero-delay tap x snapshot
    h_second::Matrix{ComplexF64} # cached not-a-knot spline derivatives
    phase::Vector{Float64}      # UACR theta_hat or phi_hat track for that lane
    fs::Float64
    fc::Float64
    step::Int
    receiver::Int
    name::String
    tracking::Symbol            # :phase for theta_hat; :delay_phase for phi_hat
    function ReplayCapture(h::Matrix{ComplexF64},
                           phase::Vector{Float64},
                           fs::Float64,
                           fc::Float64,
                           step::Int,
                           receiver::Int,
                           name::String,
                           tracking::Symbol)
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
        tracking in (:phase, :delay_phase) ||
            throw(ArgumentError("replay tracking must be :phase or :delay_phase"))
        h_second = similar(h)
        @inbounds for tap in axes(h, 1)
            h_second[tap, :] .= _cubic_second_derivatives(@view h[tap, :])
        end
        new(h, h_second, phase, fs, fc, step, receiver, name, tracking)
    end
end

function ReplayCapture(h::AbstractMatrix,
                       phase::AbstractVector,
                       fs::Real,
                       fc::Real,
                       step::Integer,
                       receiver::Integer,
                       name::AbstractString;
                       tracking::Symbol=:phase)
    h2 = Matrix{ComplexF64}(h)
    phase2 = Float64.(phase)
    ReplayCapture(h2, phase2, Float64(fs), Float64(fc), Int(step),
                  Int(receiver), String(name), tracking)
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
    tracking = phase_key == "phi_hat" ? :delay_phase : :phase
    ReplayCapture(h, phase, fs, fc, step, rx, name; tracking=tracking)
end

function load_capture(path::AbstractString; receiver::Integer=1)
    isfile(path) || throw(ArgumentError("replay MAT file does not exist: $path"))
    filesize(path) > 1_000_000 ||
        throw(ArgumentError("replay MAT file is too small and may be truncated"))
    data = MAT.matread(path)
    name = first(splitext(basename(path)))
    capture_from_dict(data; receiver=receiver, name=name)
end

# Not-a-knot cubic-spline second derivatives on a unit-spaced sample grid.
function _cubic_second_derivatives(values::AbstractVector{<:Complex})
    n = length(values)
    second = zeros(ComplexF64, n)
    n <= 2 && return second
    if n == 3
        second .= values[3] - 2values[2] + values[1]
        return second
    end

    second[2] = values[3] - 2values[2] + values[1]
    second[n-1] = values[n] - 2values[n-1] + values[n-2]
    unknowns = n - 4
    if unknowns > 0
        diagonal = fill(4.0, unknowns)
        upper = fill(1.0, max(0, unknowns - 1))
        lower = fill(1.0, max(0, unknowns - 1))
        rhs = ComplexF64[
            6 * (values[index+1] - 2values[index] + values[index-1])
            for index in 3:n-2
        ]
        rhs[1] -= second[2]
        rhs[end] -= second[n-1]
        @inbounds for index in 2:unknowns
            factor = lower[index-1] / diagonal[index-1]
            diagonal[index] -= factor * upper[index-1]
            rhs[index] -= factor * rhs[index-1]
        end
        solution = similar(rhs)
        solution[end] = rhs[end] / diagonal[end]
        @inbounds for index in unknowns-1:-1:1
            solution[index] =
                (rhs[index] - upper[index] * solution[index+1]) /
                diagonal[index]
        end
        second[3:n-2] .= solution
    end
    second[1] = 2second[2] - second[3]
    second[n] = 2second[n-1] - second[n-2]
    second
end

function _cubic_time_warp(values::AbstractVector{<:Complex},
                          offsets::AbstractVector{<:Real})
    length(values) == length(offsets) ||
        throw(DimensionMismatch("time-warp offsets must match replay output"))
    n = length(values)
    positions = Float64[index + offsets[index] for index in eachindex(values)]
    _cubic_interpolate(values, positions)
end

function _cubic_value(values::AbstractVector{<:Complex},
                      second::AbstractVector{<:Complex}, position::Real)
    n = length(values)
    1 <= position <= n || return 0.0 + 0.0im
    position == n && return ComplexF64(values[n])
    lo = floor(Int, position)
    fraction = position - lo
    complement = 1 - fraction
    complement * values[lo] + fraction * values[lo+1] +
        ((complement^3 - complement) * second[lo] +
         (fraction^3 - fraction) * second[lo+1]) / 6
end


function _cubic_interpolate(values::AbstractVector{<:Complex},
                            positions::AbstractVector{<:Real})
    isempty(values) && throw(ArgumentError("cubic source must not be empty"))
    second = _cubic_second_derivatives(values)
    ComplexF64[_cubic_value(values, second, position) for position in positions]
end


function capture_snapshot_limit(capture::ReplayCapture,
                                input_samples::Integer)
    samples = Int(input_samples)
    samples > 0 || throw(ArgumentError("replay input length must be positive"))
    ntaps, nsnapshots = size(capture.h)
    output_samples = samples + ntaps
    convolved_samples = output_samples - 1

    # The official replay evaluates h_hat on the fs_time grid with a cubic
    # spline and zero-fills outside that grid. Published packet positions must
    # nevertheless stay entirely inside measured tap support.
    last_tap_offset = convolved_samples - 1
    tap_limit = floor(Int, nsnapshots - last_tap_offset / capture.step)

    # phi_hat supplies one additional sample for its delay-warp coordinates;
    # theta_hat is consumed only for the nonzero convolution samples.
    phase_samples = capture.tracking === :delay_phase ?
        output_samples : convolved_samples
    last_phase_offset = phase_samples - 1
    phase_limit = fld(length(capture.phase) - 1 - last_phase_offset,
                      capture.step) + 1
    max(0, min(tap_limit, phase_limit))
end

# UACR-compatible time-varying FIR interpolation for one selected lane.
# theta_hat restores phase only. phi_hat restores phase and the corresponding
# delay drift phi_hat/(2*pi*fc) through cubic time interpolation.
function apply_capture(capture::ReplayCapture,
                       input::AbstractVector{<:Number};
                       snapshot::Integer=1)
    isempty(input) && throw(ArgumentError("replay input must not be empty"))
    start = Int(snapshot)
    1 <= start <= size(capture.h, 2) ||
        throw(ArgumentError("snapshot $start is outside 1:$(size(capture.h, 2))"))

    x = ComplexF64.(input)
    ntaps, nsnapshots = size(capture.h)
    # Match uwa_channels.replay exactly: T+L output samples, with T+L-1
    # convolution samples and one trailing zero used by phi_hat's time warp.
    output = zeros(ComplexF64, length(x) + ntaps)
    convolved_samples = length(output) - 1
    phase_samples = capture.tracking === :delay_phase ?
        length(output) : convolved_samples
    phase_start = (start - 1) * capture.step + 1
    phase_stop = phase_start + phase_samples - 1
    phase_stop <= length(capture.phase) || throw(ArgumentError(
        "snapshot $start needs phase samples $phase_start:$phase_stop, " *
        "but the capture has only $(length(capture.phase))"))
    phase_track = capture.phase[phase_start:phase_stop]
    @inbounds for output_idx in 1:convolved_samples
        offset = output_idx - 1
        snapshot_position = start + offset / capture.step
        1 <= snapshot_position <= nsnapshots || continue
        last_snapshot = snapshot_position == nsnapshots
        lo = last_snapshot ? nsnapshots : floor(Int, snapshot_position)
        fraction = last_snapshot ? 0.0 : snapshot_position - lo
        complement = 1 - fraction
        second_lo_weight = (complement^3 - complement) / 6
        second_hi_weight = (fraction^3 - fraction) / 6
        base = output_idx - ntaps
        acc = 0.0 + 0.0im
        for tap in 1:ntaps
            input_idx = base + tap
            1 <= input_idx <= length(x) || continue
            response = if last_snapshot
                capture.h[tap, nsnapshots]
            else
                complement * capture.h[tap, lo] +
                fraction * capture.h[tap, lo + 1] +
                second_lo_weight * capture.h_second[tap, lo] +
                second_hi_weight * capture.h_second[tap, lo + 1]
            end
            acc += response * x[input_idx]
        end
        output[output_idx] = acc * cis(phase_track[output_idx])
    end
    capture.tracking === :phase && return output
    drift_samples = phase_track .* (capture.fs / (2pi * capture.fc))
    _cubic_time_warp(output, drift_samples)
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
