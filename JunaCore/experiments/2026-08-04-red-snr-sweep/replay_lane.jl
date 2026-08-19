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
       load_capture, replay_snapshot_bounds, replay_support

struct ReplayCapture
    h::Matrix{ComplexF64}       # oldest-delay to zero-delay tap x snapshot
    h_second::Matrix{ComplexF64} # not-a-knot time-spline second derivatives
    phase::Vector{Float64}      # baseband phase track for that lane
    tracking::Symbol            # :phi_hat (phase + delay) or :theta_hat (phase)
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
                           name::String,
                           tracking::Symbol)
        size(h, 1) > 0 || throw(ArgumentError("replay capture needs at least one tap"))
        size(h, 2) >= 2 || throw(ArgumentError(
            "replay capture needs at least two snapshots"))
        isempty(phase) && throw(ArgumentError("replay capture phase track must not be empty"))
        isfinite(fs) && fs > 0 || throw(ArgumentError("replay capture fs must be positive"))
        isfinite(fc) && fc > 0 || throw(ArgumentError("replay capture fc must be positive"))
        step > 0 || throw(ArgumentError("replay capture step must be positive"))
        receiver > 0 || throw(ArgumentError("replay receiver must be positive"))
        isempty(name) && throw(ArgumentError("replay capture name must not be empty"))
        tracking in (:phi_hat, :theta_hat) || throw(ArgumentError(
            "replay tracking must be :phi_hat or :theta_hat"))
        all(x -> isfinite(real(x)) && isfinite(imag(x)), h) ||
            throw(ArgumentError("replay taps must be finite"))
        all(isfinite, phase) || throw(ArgumentError("replay phase must be finite"))
        h_second = similar(h)
        for tap in axes(h, 1)
            h_second[tap, :] = _not_a_knot_second_derivatives(
                collect(@view h[tap, :]))
        end
        new(h, h_second, phase, tracking, fs, fc, step, receiver, name)
    end
end

function ReplayCapture(h::AbstractMatrix,
                       phase::AbstractVector,
                       fs::Real,
                       fc::Real,
                       step::Integer,
                       receiver::Integer,
                       name::AbstractString;
                       tracking::Symbol)
    h2 = Matrix{ComplexF64}(h)
    phase2 = Float64.(phase)
    ReplayCapture(h2, phase2, Float64(fs), Float64(fc), Int(step),
                  Int(receiver), String(name), tracking)
end

ReplayCapture(h::AbstractMatrix, phase::AbstractVector, fs::Real, fc::Real,
              step::Integer, receiver::Integer, name::AbstractString,
              tracking::Symbol) = ReplayCapture(
    h, phase, fs, fc, step, receiver, name; tracking)

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
    ReplayCapture(h, phase, fs, fc, step, rx, name;
                  tracking=Symbol(phase_key))
end

function load_capture(path::AbstractString; receiver::Integer=1)
    isfile(path) || throw(ArgumentError("replay MAT file does not exist: $path"))
    filesize(path) > 1_000_000 ||
        throw(ArgumentError("replay MAT file is too small and may be truncated"))
    data = MAT.matread(path)
    name = first(splitext(basename(path)))
    capture_from_dict(data; receiver=receiver, name=name)
end

function _tap_support_stop(capture::ReplayCapture, nominal_samples::Int,
                           snapshot::Int)
    # The final time coordinate must remain below the last tap-spline knot.
    # Requiring the following snapshot also refuses the old clamp-to-last
    # behavior when the final sample lies exactly on a snapshot boundary.
    stop = snapshot + div(nominal_samples - 1, capture.step) + 1
    stop <= size(capture.h, 2) || throw(ArgumentError(
        "replay needs tap snapshot support through $stop, but the capture " *
        "ends at $(size(capture.h, 2))"))
    stop
end

function _phase_support(capture::ReplayCapture, first_offset::Int,
                        last_offset::Int, q0::Int)
    first = q0 + first_offset
    last = q0 + last_offset
    first >= 0 || throw(ArgumentError(
        "replay needs left phase support at zero-based offset $first"))
    last < length(capture.phase) || throw(ArgumentError(
        "replay needs right phase support through zero-based offset $last, " *
        "but the phase track ends at $(length(capture.phase) - 1)"))
    first, last
end

function _delay_samples(capture::ReplayCapture, q::Int)
    capture.phase[q + 1] * capture.fs / (2pi * capture.fc)
end

"""
    replay_support(capture, input_length; snapshot=1)

Return the exact measured support used to replay one input. `q0` is the
zero-based phase-sample index corresponding to the one-based channel snapshot:
`q0 = (snapshot - 1) * step`. A `phi_hat` capture grows left and right output
guards until the delay-warp interval is a fixed point. Missing tap or phase
samples and a non-monotone time map are errors; replay never clamps them.
"""
function replay_support(capture::ReplayCapture, input_length::Integer;
                        snapshot::Integer=1)
    input_samples = Int(input_length)
    input_samples > 0 || throw(ArgumentError(
        "replay input length must be positive"))
    start = Int(snapshot)
    1 <= start <= size(capture.h, 2) || throw(ArgumentError(
        "snapshot $start is outside 1:$(size(capture.h, 2))"))
    nominal_samples = input_samples + size(capture.h, 1) - 1
    tap_stop = _tap_support_stop(capture, nominal_samples, start)
    q0 = (start - 1) * capture.step

    left_guard = 0
    right_guard = 0
    delay_min = 0.0
    delay_max = 0.0
    map_min = 0.0
    map_max = Float64(nominal_samples - 1)
    if capture.tracking === :theta_hat
        _phase_support(capture, 0, nominal_samples - 1, q0)
    else
        converged = false
        # Each expansion retains the previous interval, so the extrema and
        # integer guards are monotone. The phase-track length is a finite hard
        # bound on the number of possible expansions.
        for _ in 1:(length(capture.phase) + 1)
            first_offset = -left_guard
            last_offset = nominal_samples - 1 + right_guard
            first_phase, last_phase = _phase_support(
                capture, first_offset, last_offset, q0)
            delays = [_delay_samples(capture, q)
                      for q in first_phase:last_phase]
            delay_min = minimum(delays)
            delay_max = maximum(delays)
            max(abs(delay_min), abs(delay_max)) <= typemax(Int) / 4 ||
                throw(ArgumentError("replay delay guard is too large"))
            next_left = ceil(Int, max(0.0, delay_max))
            next_right = ceil(Int, max(0.0, -delay_min))
            if next_left == left_guard && next_right == right_guard
                relative = first_offset:last_offset
                time_map = Float64.(relative) .+ delays
                all(diff(time_map) .> 0) || throw(ArgumentError(
                    "phi_hat replay time map must be strictly increasing"))
                map_min = first(time_map)
                map_max = last(time_map)
                converged = true
                break
            end
            left_guard = next_left
            right_guard = next_right
        end
        converged || throw(ArgumentError(
            "phi_hat replay guards did not reach a fixed point"))
    end

    first_offset = -left_guard
    last_offset = nominal_samples - 1 + right_guard
    first_phase, last_phase = _phase_support(
        capture, first_offset, last_offset, q0)
    output_samples = nominal_samples + left_guard + right_guard
    (
        tracking=capture.tracking,
        snapshot=start,
        q0=q0,
        input_samples=input_samples,
        nominal_samples=nominal_samples,
        output_samples=output_samples,
        left_guard=left_guard,
        right_guard=right_guard,
        relative_indices=first_offset:last_offset,
        nominal_indices=(left_guard + 1):(left_guard + nominal_samples),
        phase_start_index=first_phase + 1,
        phase_stop_index=last_phase + 1,
        tap_snapshot_start=start,
        tap_snapshot_stop=tap_stop,
        delay_samples_min=delay_min,
        delay_samples_max=delay_max,
        map_min=map_min,
        map_max=map_max,
        map_is_strictly_increasing=true,
    )
end

function replay_snapshot_bounds(capture::ReplayCapture,
                                input_length::Integer)
    input_samples = Int(input_length)
    input_samples > 0 || throw(ArgumentError(
        "replay input length must be positive"))
    nominal_samples = input_samples + size(capture.h, 1) - 1
    last_from_taps = size(capture.h, 2) -
                     div(nominal_samples - 1, capture.step) - 1
    last_from_phase = fld(length(capture.phase) - nominal_samples,
                          capture.step) + 1
    candidate_last = min(last_from_taps, last_from_phase)
    candidate_last >= 1 || throw(ArgumentError(
        "capture has no snapshot with nominal replay support"))

    first_supported = nothing
    for candidate in 1:candidate_last
        try
            replay_support(capture, input_samples; snapshot=candidate)
            first_supported = candidate
            break
        catch error
            error isa ArgumentError || rethrow()
        end
    end
    first_supported === nothing && throw(ArgumentError(
        "capture has no snapshot with complete replay support"))

    last_supported = nothing
    for candidate in candidate_last:-1:Int(first_supported)
        try
            replay_support(capture, input_samples; snapshot=candidate)
            last_supported = candidate
            break
        catch error
            error isa ArgumentError || rethrow()
        end
    end
    last_supported === nothing && throw(ArgumentError(
        "capture has no snapshot with complete replay support"))
    (first=Int(first_supported), last=Int(last_supported))
end

function _not_a_knot_second_derivatives(values::Vector{ComplexF64})
    count = length(values)
    count >= 2 || throw(ArgumentError(
        "cubic interpolation needs at least two knots"))
    count == 2 && return zeros(ComplexF64, 2)
    if count == 3
        curvature = values[3] - 2values[2] + values[1]
        return fill(curvature, 3)
    end

    interior_count = count - 2
    diagonal = fill(4.0, interior_count)
    lower = ones(Float64, interior_count - 1)
    upper = ones(Float64, interior_count - 1)
    rhs = Vector{ComplexF64}(undef, interior_count)
    diagonal[1] = 1.0
    rhs[1] = values[3] - 2values[2] + values[1]
    upper[1] = 0.0
    diagonal[end] = 1.0
    rhs[end] = values[end] - 2values[end - 1] + values[end - 2]
    lower[end] = 0.0
    for index in 2:(interior_count - 1)
        rhs[index] = 6 * (values[index + 2] -
                          2values[index + 1] + values[index])
    end
    for index in 2:interior_count
        multiplier = lower[index - 1] / diagonal[index - 1]
        diagonal[index] -= multiplier * upper[index - 1]
        rhs[index] -= multiplier * rhs[index - 1]
    end
    interior = Vector{ComplexF64}(undef, interior_count)
    interior[end] = rhs[end] / diagonal[end]
    for index in (interior_count - 1):-1:1
        interior[index] = (rhs[index] - upper[index] * interior[index + 1]) /
                          diagonal[index]
    end
    result = Vector{ComplexF64}(undef, count)
    result[2:end-1] = interior
    result[1] = 2result[2] - result[3]
    result[end] = 2result[end - 1] - result[end - 2]
    result
end

function _not_a_knot_value(values::Vector{ComplexF64},
                           second_derivatives::Vector{ComplexF64},
                           coordinate::Float64)
    last_coordinate = length(values) - 1
    (coordinate < 0 || coordinate > last_coordinate) &&
        return 0.0 + 0.0im
    coordinate == last_coordinate && return values[end]
    left_coordinate = floor(Int, coordinate)
    index = left_coordinate + 1
    right_weight = coordinate - left_coordinate
    left_weight = 1 - right_weight
    second_derivatives[index] * left_weight^3 / 6 +
        second_derivatives[index + 1] * right_weight^3 / 6 +
        (values[index] - second_derivatives[index] / 6) * left_weight +
        (values[index + 1] - second_derivatives[index + 1] / 6) * right_weight
end

function _not_a_knot_row_value(values::Matrix{ComplexF64},
                               second_derivatives::Matrix{ComplexF64},
                               row::Int, coordinate::Float64)
    last_coordinate = size(values, 2) - 1
    (coordinate < 0 || coordinate > last_coordinate) &&
        return 0.0 + 0.0im
    coordinate == last_coordinate && return values[row, end]
    left_coordinate = floor(Int, coordinate)
    index = left_coordinate + 1
    right_weight = coordinate - left_coordinate
    left_weight = 1 - right_weight
    second_derivatives[row, index] * left_weight^3 / 6 +
        second_derivatives[row, index + 1] * right_weight^3 / 6 +
        (values[row, index] - second_derivatives[row, index] / 6) *
            left_weight +
        (values[row, index + 1] - second_derivatives[row, index + 1] / 6) *
            right_weight
end

# ReplayCh-compatible time-varying FIR interpolation for one selected lane,
# with the UACR tracking key retained. theta_hat inserts phase only; phi_hat
# inserts phase first and then evaluates the not-a-knot cubic delay warp.
function apply_capture(capture::ReplayCapture,
                       input::AbstractVector{<:Number};
                       snapshot::Integer=1,
                       return_support::Bool=false)
    isempty(input) && throw(ArgumentError("replay input must not be empty"))
    x = ComplexF64.(input)
    support = replay_support(capture, length(x); snapshot)
    ntaps = size(capture.h, 1)
    phased = zeros(ComplexF64, support.nominal_samples)
    @inbounds for output_index in eachindex(phased)
        offset = output_index - 1
        channel_coordinate = support.snapshot - 1 + offset / capture.step
        base = output_index - ntaps
        acc = 0.0 + 0.0im
        for tap in 1:ntaps
            input_idx = base + tap
            1 <= input_idx <= length(x) || continue
            response = _not_a_knot_row_value(
                capture.h, capture.h_second, tap, channel_coordinate)
            acc += response * x[input_idx]
        end
        phase_index = support.q0 + offset + 1
        phased[output_index] = acc * cis(capture.phase[phase_index])
    end

    output = if capture.tracking === :theta_hat
        phased
    else
        source = [phased; 0.0 + 0.0im]
        second_derivatives = _not_a_knot_second_derivatives(source)
        warped = Vector{ComplexF64}(undef, support.output_samples)
        @inbounds for (index, relative) in enumerate(
                support.relative_indices)
            phase_index = support.q0 + relative + 1
            delay = capture.phase[phase_index] * capture.fs /
                    (2pi * capture.fc)
            coordinate = Float64(relative) + delay
            warped[index] = _not_a_knot_value(
                source, second_derivatives, coordinate)
        end
        warped
    end
    return_support ? (waveform=output, replay_support=support) : output
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
