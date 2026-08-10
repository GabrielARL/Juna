#
# Julia port of uwa-channels/python src/uwa_channels/noisegen.py, mixing path.
#
# Reference: https://github.com/uwa-channels/python (public toolbox named by
# the Zenodo record the red_*.mat captures come from). The model is
#
#     w[n, i] = sum_j sum_k beta[i, j, k] * z[n+k, j]
#
# with z an iid unit-pseudo-power driver: standard Gaussian when alpha == 2,
# symmetric alpha-stable with scale 1/sqrt(2) when alpha < 2. `beta` carries
# both the cross-hydrophone correlation and the bandpass shaping. Red's model
# has alpha = 1.7, so this noise is impulsive, not Gaussian.
#
# Two deliberate additions over the reference, each because our harness works
# where the reference does not:
#
#   1. The reference adds noise at passband rate Fs around fc. Our decoder
#      runs at complex baseband, modem rate. So after mixing we apply exactly
#      the transformation replay.py applies to its input signal (replay.py:77)
#      -- multiply by exp(-2i*pi*fc*n/Fs), then resample -- so signal and
#      noise land in the same domain.
#   2. SNR follows Mahmood & Chitre, JOE 42(3) 2017, eq. (35): the measure is
#      E*theta^2 / (2*delta^2), the alpha-stable SCALE, because second-order
#      moments do not exist for alpha < 2. We therefore normalise the noise to
#      2*delta^2 = 1 and let the caller scale by the target noise power. The
#      scale through a linear filter is the alpha-norm (sum |h|^alpha)^(1/alpha),
#      not the 2-norm, so the normalising gain is measured by pushing an
#      impulse through the same chain.
#
module UwaNoise

using MAT, Random, Statistics
import DSP

struct NoiseModel
    alpha::Float64
    beta::Array{Float64,3}   # (M, M, K)
    fc::Float64
    Fs::Float64              # rate the statistics were measured at
    R::Float64               # signal bandwidth
end

function load_model(path::AbstractString)
    d = matread(path)
    beta = Array{Float64,3}(d["beta"])
    size(beta, 1) == size(beta, 2) ||
        error("beta must be (M, M, K); got $(size(beta))")
    NoiseModel(Float64(d["alpha"]), beta, Float64(d["fc"]),
               Float64(d["Fs"]), Float64(d["R"]))
end

"""Symmetric alpha-stable draws, scale `c`, via Chambers-Mallows-Stuck.

Matches scipy's `levy_stable.rvs(alpha, 0, scale=c)` in distribution, which is
what the reference uses. At alpha == 2 this reduces to N(0, 2c^2), so c =
1/sqrt(2) gives the unit-variance standard normal the reference draws there.
"""
function sas_rand(rng::AbstractRNG, alpha::Real, c::Real, dims...)
    alpha == 2 && return sqrt(2) * c .* randn(rng, dims...)
    u = (rand(rng, dims...) .- 0.5) .* pi          # Uniform(-pi/2, pi/2)
    w = -log.(rand(rng, dims...))                  # Exponential(1)
    @. c * sin(alpha * u) / cos(u)^(1 / alpha) *
       (cos(u - alpha * u) / w)^((1 - alpha) / alpha)
end

"""Mixed noise at the model's own rate Fs, for one hydrophone (1-based)."""
function _mix(rng::AbstractRNG, model::NoiseModel, lane::Integer,
              nsamples::Integer)
    M, _, K = size(model.beta)
    1 <= lane <= M || error("lane $lane outside the model's $M hydrophones")
    z = sas_rand(rng, model.alpha, 1 / sqrt(2), nsamples + K, M)
    w = zeros(Float64, nsamples)
    for k in 1:K, j in 1:M
        b = model.beta[lane, j, k]
        b == 0 && continue
        @views w .+= b .* z[k:(k + nsamples - 1), j]
    end
    w
end

"""This lane's alpha-stable scale multiplier out of the mixing, sqrt(2*delta^2)."""
lane_scale(model::NoiseModel, lane::Integer) =
    (sum(abs.(model.beta[lane, :, :]) .^ model.alpha))^(1 / model.alpha)

"""Downconvert by fc and resample Fs -> fs_out, as replay.py does its input."""
function _to_baseband(w::AbstractVector{<:Real}, model::NoiseModel,
                      fs_out::Real)
    n = 0:(length(w) - 1)
    bb = ComplexF64.(w) .* cis.(-2pi * model.fc .* n ./ model.Fs)
    ratio = fs_out / model.Fs
    num, den = numerator(rationalize(ratio; tol=1e-9)),
               denominator(rationalize(ratio; tol=1e-9))
    DSP.resample(bb, num // den)
end

"""Gain the baseband chain applies to the alpha-stable SCALE.

For a stable law a linear filter maps scale by the alpha-norm of the impulse
response, (sum |h|^alpha)^(1/alpha) -- not the 2-norm. Measured, not assumed.
"""
function _chain_scale_gain(model::NoiseModel, fs_out::Real; n::Integer=8192)
    ratio = rationalize(fs_out / model.Fs; tol=1e-9)
    phases = denominator(ratio)          # input samples consumed per output
    # A decimating resampler is polyphase: an impulse at one offset excites
    # only one branch, so a single probe sees one tap in `phases`. Sweep every
    # offset to recover the whole response, or the scale comes out low by
    # roughly that factor.
    taps = ComplexF64[]
    for offset in 0:(phases - 1)
        impulse = zeros(Float64, n)
        impulse[n ÷ 2 + offset] = 1.0
        append!(taps, _to_baseband(impulse, model, fs_out))
    end
    (sum(abs.(taps) .^ model.alpha))^(1 / model.alpha)
end

"""Complex baseband noise at `fs_out` normalised to 2*delta^2 == 1.

`nsamples` is counted at `fs_out`. The caller multiplies by sqrt(noise_power)
to hit a target SNR under eq. (35).
"""
function baseband_noise(rng::AbstractRNG, model::NoiseModel, lane::Integer,
                        nsamples::Integer, fs_out::Real;
                        scale_gain::Union{Nothing,Float64}=nothing)
    need = ceil(Int, nsamples * model.Fs / fs_out) + 64
    w = _mix(rng, model, lane, need)
    bb = _to_baseband(w, model, fs_out)
    length(bb) >= nsamples || error("baseband noise short: $(length(bb)) < $nsamples")
    gain = scale_gain === nothing ? _chain_scale_gain(model, fs_out) : scale_gain
    # beta is normalised so the pseudo-powers SUM to M, not so each equals 1:
    # measured on this model they are 1.028, 1.013, 0.959, summing to 3.0000.
    # So divide by this lane's own alpha-norm as well as the chain gain, giving
    # 2*delta^2 == 1 for the lane actually being decoded.
    (bb[1:nsamples] ./ (gain * lane_scale(model, lane)))
end

end # module
