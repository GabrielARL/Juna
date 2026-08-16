#!/usr/bin/env julia

using Test
using JunaCore
using FFTW
using Random
using SHA

const AcquisitionJuna = JunaCore.Juna

function acquisition_fixture(; nblocks::Int=2)
    fs = 24_000.0
    fc = 24_000.0
    modem = AcquisitionJuna.LiteModulation(nc=128, np=16, sync=true)
    AcquisitionJuna.Modulations.init(modem, fc, fs)
    modem.nc = 128
    modem.np = 16
    modem.sync = true
    block_samples = nblocks * AcquisitionJuna._blocklen(modem)
    payload = ComplexF64[
        cispi(2 * 0.037 * sample) for sample in 0:block_samples-1
    ]
    sync = AcquisitionJuna._sync_waveform(modem, fs)
    modem, fc, fs, payload, vcat(sync, payload, sync)
end

function residual_frequency_hz(corrected, reference, fs)
    residual = corrected .* conj.(reference)
    increment = sum(
        @view(residual[2:end]) .* conj.(@view(residual[1:end-1])))
    angle(increment) * fs / (2pi)
end

@testset "synchronization observation exposes runner geometry" begin
    modem, _, fs, payload, waveform = acquisition_fixture()
    sync_samples = length(AcquisitionJuna._sync_waveform(modem, fs))

    observation = AcquisitionJuna._sync_body_observation(
        modem, waveform, fs, 2)

    @test observation.pre_start ≈ 1.0 atol=1.0
    @test observation.post_start ≈
        sync_samples + length(payload) + 1 atol=1.0
    @test observation.duration_scale ≈ 1.0 atol=1e-3
    @test observation.post_start - observation.pre_start ≈
        observation.sync_spacing atol=eps(observation.sync_spacing)
    @test observation.duration_scale ≈ observation.sync_spacing /
        (sync_samples + length(payload)) atol=eps(observation.duration_scale)
    @test observation.quality == observation.differential_quality
    @test observation.quality >= 0.1
end

@testset "differential synchronization remains selective under carrier offset" begin
    fs = 4_882.8125
    reference = AcquisitionJuna._sync_chirp(521, fs, 1.0)
    received = zeros(ComplexF64, 1_700)
    false_start = 101
    true_start = 901

    # An amplitude-gated copy has a larger ordinary coherent match than the
    # carrier-shifted complete chirp, but it lacks adjacent-sample continuity.
    gated = zeros(ComplexF64, length(reference))
    gated[1:5:end] .= reference[1:5:end]
    received[false_start:false_start+length(reference)-1] .+= gated
    sample = collect(0:length(reference)-1)
    received[true_start:true_start+length(reference)-1] .+=
        reference .* cispi.(2 * 17.0 .* sample ./ fs)

    ordinary = AcquisitionJuna._matched_corr(received, reference)
    differential = AcquisitionJuna._differential_corr(received, reference)

    @test ordinary[false_start] > ordinary[true_start]
    @test differential[true_start] >= 0.95
    @test differential[false_start] <= 0.05
    @test argmax(differential) == true_start

    @test all(iszero,
        AcquisitionJuna._differential_corr(zero(received), reference))
    noise_rng = MersenneTwister(52_104)
    noise = randn(noise_rng, length(received)) .+
            im .* randn(noise_rng, length(received))
    @test maximum(AcquisitionJuna._differential_corr(noise, reference)) < 0.25
end

@testset "pilot carrier score is defined without a cyclic prefix" begin
    fs = 4_882.8125
    fc = 13_000.0
    modem = AcquisitionJuna.LiteModulation(
        nc=128, np=0, sync=true, pilot_ratio=0.1)
    AcquisitionJuna.Modulations.init(modem, fc, fs)
    modem.nc = 128
    modem.np = 0
    modem.sync = true
    rng = MersenneTwister(12_800)
    waveform = randn(rng, ComplexF64, 2 * Int(modem.nc))

    score = AcquisitionJuna._pilot_cfo_score(modem, waveform, fs, 2)

    @test isfinite(score.temporal)
    @test isfinite(score.causal)
    @test score.cp == 0.0
    @test score.cp_residual_hz == 0.0
end

@testset "bounded affine CP fit recovers one continuous OFDM clock" begin
    fs = 4_882.8125
    fc = 13_000.0
    modem = AcquisitionJuna.LiteModulation(
        nc=512, np=64, sync=true, pilot_ratio=0.1)
    AcquisitionJuna.Modulations.init(modem, fc, fs)
    modem.nc = 512
    modem.np = 64
    modem.sync = true
    nblocks = 4
    N = Int(modem.nc)
    L = Int(modem.np)
    rng = MersenneTwister(41_064)
    body = ComplexF64[]
    for _ in 1:nblocks
        symbol = randn(rng, ComplexF64, N)
        append!(body, @view symbol[end-L+1:end])
        append!(body, symbol)
    end

    actual_start = 25.0
    predicted_start = actual_start

    waveform = ComplexF64[]
    for requested_scale in (0.9985, 1.0015)
        stretched = AcquisitionJuna._resample_to(
            body, round(Int, requested_scale * length(body)))
        actual_scale = (length(stretched) - 1) / (length(body) - 1)
        waveform = vcat(
            zeros(ComplexF64, Int(actual_start) - 1),
            stretched,
            zeros(ComplexF64, 32))

        fit = AcquisitionJuna._affine_cp_body_fit(
            waveform, modem, nblocks, predicted_start)

        @test fit !== nothing
        @test fit.refined
        @test abs(fit.start - predicted_start) < L / 4
        @test fit.start >= 1
        @test fit.start + (length(body) - 1) * fit.scale <=
            length(waveform)
        @test sign(fit.scale - 1) == sign(actual_scale - 1)
        @test fit.scale ≈ actual_scale atol=5e-4
        @test fit.score >= 0.2
        @test fit.score > 1.05 * fit.baseline_score
        @test length(fit.body) == length(body)

        candidate_hz = 7.0
        derotated = AcquisitionJuna._derotate_affine_cp_body(
            fit, candidate_hz, fs)
        raw_coordinates = fit.start - 1 .+
            fit.scale .* collect(0:length(fit.body)-1)
        expected = fit.body .*
            cispi.(-2 .* candidate_hz .* raw_coordinates ./ fs)
        @test derotated ≈ expected atol=1e-12 rtol=1e-12
        @test abs.(derotated) ≈ abs.(fit.body) atol=1e-12 rtol=1e-12
    end

    # The score must reject unsupported interpolation coordinates instead of
    # inheriting `_scaled_segment`'s edge clamping.
    @test !isfinite(AcquisitionJuna._affine_cp_body_score(
        waveform, modem, nblocks, 0.75, 1.0))
    @test !isfinite(AcquisitionJuna._affine_cp_body_score(
        waveform, modem, nblocks, length(waveform) - 10.0, 1.0))

    aligned_waveform = vcat(
        zeros(ComplexF64, 24), body, zeros(ComplexF64, 32))
    baseline = AcquisitionJuna._affine_cp_body_fit(
        aligned_waveform, modem, nblocks, 25.0)
    @test baseline !== nothing
    @test !baseline.refined
    @test baseline.start == 25.0
    @test baseline.offset == 0.0
    @test baseline.scale == 1.0
    @test baseline.score == baseline.baseline_score
    @test baseline.body == body
end

@testset "affine CP fit falls back without credible prefix evidence" begin
    fs = 4_882.8125
    fc = 13_000.0
    modem = AcquisitionJuna.LiteModulation(nc=128, np=16, sync=true)
    AcquisitionJuna.Modulations.init(modem, fc, fs)
    modem.nc = 128
    modem.np = 16
    modem.sync = true
    samples = 4 * AcquisitionJuna._blocklen(modem) + 64

    @test AcquisitionJuna._affine_cp_body_fit(
        zeros(ComplexF64, samples), modem, 4, 17.0) === nothing
    noise = randn(MersenneTwister(128_016), ComplexF64, samples)
    @test AcquisitionJuna._affine_cp_body_fit(
        noise, modem, 4, 17.0) === nothing
    @test AcquisitionJuna._affine_cp_body_fit(
        noise, modem, 1, 17.0) === nothing
    @test AcquisitionJuna._affine_cp_body_fit(
        @view(noise[1:100]), modem, 4, 17.0) === nothing

    modem.np = 0
    @test AcquisitionJuna._affine_cp_body_fit(
        noise, modem, 4, 17.0) === nothing
end

function smooth_affine_warp(body, start, scale, amplitude)
    samples = ceil(Int,
        start + (length(body) - 1) * scale + abs(amplitude) + 32)
    warped = zeros(ComplexF64, samples)
    period = max(length(body) - 1, 1)
    @inbounds for raw_index in eachindex(warped)
        coordinate = 1 + (raw_index - start) / scale
        for _ in 1:8
            phase = 2pi * (coordinate - 1) / period
            value = start + (coordinate - 1) * scale +
                amplitude * sin(phase) - raw_index
            derivative = scale + amplitude * 2pi / period * cos(phase)
            coordinate -= value / derivative
        end
        1 <= coordinate <= length(body) || continue
        lo = floor(Int, coordinate)
        hi = min(lo + 1, length(body))
        fraction = coordinate - lo
        warped[raw_index] =
            (1 - fraction) * body[lo] + fraction * body[hi]
    end
    warped
end

@testset "affine CP fit tolerates bounded smooth timing residual" begin
    fc = 24_000.0
    fs = 24_000.0
    modem = JunaCore.JunaLite.Modulation()
    capacity = JunaCore.Modulations.bitspersymbol(modem)
    bits = Bool[isodd(count_ones(index)) for index in 1:2capacity]
    body = JunaCore.Modulations.modulate(modem, bits, fc, fs)
    actual_start = 33.0

    for affine_scale in (0.9985, 1.0015), amplitude in (-0.5, 0.5)
        predicted_start = actual_start + 8amplitude
        warped = smooth_affine_warp(
            body, actual_start, affine_scale, amplitude)
        fit = AcquisitionJuna._affine_cp_body_fit(
            warped, modem, 2, predicted_start)

        @test fit !== nothing
        @test fit.refined
        @test length(fit.body) == length(body)
        @test abs(fit.start - predicted_start) < Int(modem.np) / 4
        @test fit.start >= 1
        @test fit.start + (length(body) - 1) * fit.scale <=
            length(warped)
        metrics, cfo = JunaCore.Modulations.demodulate(
            modem, length(bits), fit.body, fc, fs)
        @test (metrics .> 0) == bits
        @test cfo == 0.0
    end
end

@testset "public acquisition uses the shared affine CP timing map" begin
    fc = 24_000.0
    fs = 24_000.0
    receiver = JunaCore.JunaLite.Modulation(sync=true)
    body_modem = deepcopy(receiver)
    body_modem.sync = false
    capacity = JunaCore.Modulations.bitspersymbol(body_modem)
    nblocks = 4
    bits = Bool[isodd(count_ones(index)) for index in 1:nblocks*capacity]
    body = JunaCore.Modulations.modulate(
        body_modem, bits, fc, fs)
    sync = AcquisitionJuna._sync_waveform(receiver, fs)
    warped_body = smooth_affine_warp(body, 1.0, 1.0018, 0.5)
    unrotated = vcat(sync, warped_body, sync)

    injected_hz = 7.0
    raw_sample = collect(0:length(unrotated)-1)
    received = unrotated .*
        cispi.(2 .* injected_hz .* raw_sample ./ fs)

    initial = AcquisitionJuna._sync_body_observation(
        receiver, received, fs, nblocks)
    sync_scale = AcquisitionJuna._plausible_duration_scale(
        initial.duration_scale) ? initial.duration_scale : 1.0
    predicted_start = initial.pre_start +
        sync_scale * length(sync)
    fit = AcquisitionJuna._affine_cp_body_fit(
        received, receiver, nblocks, predicted_start;
        baseline_scale=sync_scale,
        scale_origin=length(sync) / 2)

    @test fit !== nothing
    @test fit.refined
    @test abs(fit.offset) < Int(receiver.np) / 4
    @test fit.start >= 1
    @test fit.start + (length(body) - 1) * fit.scale <=
        length(received)
    @test fit.score > 1.05 * fit.baseline_score

    # Pin the integration, not only the helpers: `_coarse_doppler` must return
    # the selected carrier candidate on the one accepted raw-coordinate map.
    # A candidate-specific synchronization body can still decode this clean
    # fixture, so payload success alone would not prove this branch is wired.
    corrected_body, direct_cfo = AcquisitionJuna._coarse_doppler(
        receiver, received, fc, fs, nblocks)
    expected_body = AcquisitionJuna._derotate_affine_cp_body(
        fit, direct_cfo, fs)
    @test corrected_body == expected_body

    metrics, estimated_hz = JunaCore.Modulations.demodulate(
        receiver, length(bits), received, fc, fs)

    @test (metrics .> 0) == bits
    @test estimated_hz ≈ injected_hz atol=0.75
    @test estimated_hz == direct_cfo
end

@testset "public synchronization-disabled metrics remain byte-exact" begin
    fc = 24_000.0
    fs = 24_000.0
    modem = JunaCore.JunaLite.Modulation()
    nbits = min(96, JunaCore.Modulations.bitspersymbol(modem))
    bits = Bool[isodd(count_ones(index)) for index in 1:nbits]
    waveform = JunaCore.Modulations.modulate(modem, bits, fc, fs)

    metrics, cfo = JunaCore.Modulations.demodulate(
        modem, nbits, waveform, fc, fs)

    @test bytes2hex(sha256(reinterpret(UInt8, metrics))) ==
        "32a3ec38e96c84c60ff41aca2368b4c8d683c163893a0a8db0195babdf2df63a"
    @test (metrics .> 0) == bits
    @test cfo == 0.0
end

@testset "packet method columns share synchronization acquisition" begin
    fc = 24_000.0
    fs = 24_000.0
    modem = AcquisitionJuna.StandardModulation(sync=true)
    bits = Bool[
        isodd(count_ones(17index + 3)) for index in 1:127]
    transmitted = JunaCore.Modulations.modulate(
        modem, bits, fc, fs)
    raw_sample = collect(0:length(transmitted)-1)

    for injected_hz in (-12.0, 12.0)
        received = transmitted .*
            cispi.(2 .* injected_hz .* raw_sample ./ fs)
        paths = AcquisitionJuna.demodulate_methods(
            modem, length(bits), received, fc, fs)

        @test keys(paths) == (:standard, :partial, :juna, :provenance)
        for metrics in (paths.standard, paths.partial, paths.juna)
            @test (metrics .> 0) == bits
        end
    end
end

@testset "baseline map ranks CFO without bypassing reliable correction" begin
    modem, fc, fs, payload, waveform = acquisition_fixture()
    injected_hz = -12.0
    raw_sample = collect(0:length(waveform)-1)
    received = waveform .*
        cispi.(2 .* injected_hz .* raw_sample ./ fs)
    initial = AcquisitionJuna._sync_body_observation(
        modem, received, fs, 2)
    sync_scale = AcquisitionJuna._plausible_duration_scale(
        initial.duration_scale) ? initial.duration_scale : 1.0
    fit = AcquisitionJuna._affine_cp_body_fit(
        received, modem, 2,
        initial.pre_start + sync_scale * AcquisitionJuna._synclen(modem);
        baseline_scale=sync_scale,
        scale_origin=AcquisitionJuna._synclen(modem) / 2)

    @test fit !== nothing
    @test !fit.refined
    corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
        modem, received, fc, fs, 2)
    baseline_body = AcquisitionJuna._derotate_affine_cp_body(
        fit, estimated_hz, fs)
    @test sum(abs2, corrected - baseline_body) / sum(abs2, corrected) > 1e-6
    @test estimated_hz ≈ injected_hz atol=0.75
    @test abs(residual_frequency_hz(corrected, payload, fs)) <= 0.25
    @test abs(residual_frequency_hz(baseline_body, payload, fs)) > 0.5
end

@testset "LFM acquisition separates carrier offset and duration" begin
    modem, fc, fs, payload, waveform = acquisition_fixture()
    sample = collect(0:length(waveform)-1)

    for injected_hz in (-12.0, 0.0, 12.0)
        impaired = waveform .* cispi.(2 * injected_hz .* sample ./ fs)
        corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
            modem, impaired, fc, fs, 2)

        @test length(corrected) == length(payload)
        @test estimated_hz ≈ injected_hz atol=0.75
        @test abs(residual_frequency_hz(corrected, payload, fs)) <= 0.25
    end

    duration_scale = 1.001
    dilated = AcquisitionJuna._resample_to(
        waveform, round(Int, duration_scale * length(waveform)))
    corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
        modem, dilated, fc, fs, 2)
    phase = sum(corrected .* conj.(payload))
    aligned = corrected .* cis(-angle(phase))

    @test length(corrected) == length(payload)
    @test isfinite(estimated_hz)
    # At two short blocks, the synthetic linear-resampler edge between the
    # sync and payload biases a one-lag frequency statistic despite a small
    # waveform error. The long-frame tests below retain the strict 0.25 Hz
    # residual-frequency contract for both signs of duration error.
    @test sum(abs2, aligned - payload) / sum(abs2, payload) <= 0.02
end

@testset "LFM acquisition removes linear carrier drift across a frame" begin
    modem, fc, fs, payload, waveform = acquisition_fixture(nblocks=24)
    duration = (length(waveform) - 1) / fs
    start_hz = -10.0
    stop_hz = 10.0
    slope_hz_per_second = (stop_hz - start_hz) / duration
    time = collect(0:length(waveform)-1) ./ fs
    impaired = waveform .* cispi.(
        2 .* (start_hz .* time .+
              0.5 .* slope_hz_per_second .* time .^ 2))

    corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
        modem, impaired, fc, fs, 24)
    phase = sum(corrected .* conj.(payload))
    aligned = corrected .* cis(-angle(phase))

    @test length(corrected) == length(payload)
    @test isfinite(estimated_hz)
    @test sum(abs2, aligned - payload) / sum(abs2, payload) <= 0.02
    @test abs(residual_frequency_hz(corrected, payload, fs)) <= 0.25
end

@testset "cyclic prefix tracks residual block carrier" begin
    modem, _, _, _, _ = acquisition_fixture()
    N = Int(modem.nc)
    L = Int(modem.np)
    symbol = ComplexF64[
        cispi(2 * 0.071 * sample) for sample in 0:N-1]
    block = vcat(symbol[end-L+1:end], symbol)
    phase_per_sample = 2pi * 0.24 / N
    impaired = block .* cis.(phase_per_sample .* (0:length(block)-1))
    corrected = AcquisitionJuna._track_block_carrier(modem, impaired)
    phase = sum(corrected .* conj.(block))
    aligned = corrected .* cis(-angle(phase))

    @test sum(abs2, aligned - block) / sum(abs2, block) <= 1e-12
end

@testset "acquisition rejects an implausible trailing-sync displacement" begin
    modem, fc, fs, payload, waveform = acquisition_fixture(nblocks=24)
    sync = AcquisitionJuna._sync_waveform(modem, fs)
    payload_start = length(sync) + 1
    payload_stop = payload_start + length(payload) - 1
    displaced = vcat(
        waveform[1:payload_stop], zeros(ComplexF64, 24), sync)

    corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
        modem, displaced, fc, fs, 24)
    phase = sum(corrected .* conj.(payload))
    aligned = corrected .* cis(-angle(phase))

    @test isfinite(estimated_hz)
    @test length(corrected) == length(payload)
    @test sum(abs2, aligned - payload) / sum(abs2, payload) <= 0.02
end

@testset "synchronization-disabled observations do not track carrier" begin
    modem = AcquisitionJuna.LiteModulation(
        nc=128, np=16, sync=false, partial_fft_parts=1)
    N = Int(modem.nc)
    L = Int(modem.np)
    symbol = ComplexF64[
        cispi(2 * 0.071 * sample) for sample in 0:N-1]
    block = vcat(symbol[end-L+1:end], symbol)
    phase_per_sample = 2pi * 0.24 / N
    impaired = block .* cis.(phase_per_sample .* (0:length(block)-1))
    expected = fft(copy(@view impaired[L+1:L+N]))

    tracked = AcquisitionJuna._track_block_carrier(modem, impaired)
    observed = AcquisitionJuna._branch_observations(modem, impaired)

    @test maximum(abs, tracked - impaired) > 1e-3
    @test vec(observed) ≈ expected atol=1e-12 rtol=1e-12
end

@testset "zero-energy waveform is not reliable synchronization" begin
    modem, fc, fs, _, waveform = acquisition_fixture()
    silent = zeros(ComplexF64, length(waveform))
    impairments = AcquisitionJuna._sync_impairments(modem, silent, fs, 2)

    @test !impairments.sync_reliable
    @test !impairments.duration_reliable
    @test_throws ArgumentError AcquisitionJuna._coarse_doppler(
        modem, silent, fc, fs, 2)

    for seed in 9_001:9_003
        noise_rng = MersenneTwister(seed)
        noise = randn(noise_rng, ComplexF64, length(waveform))
        @test_throws ArgumentError AcquisitionJuna._coarse_doppler(
            modem, noise, fc, fs, 2)
    end
end

@testset "combined duration dilation and carrier drift are corrected" begin
    modem, fc, fs, payload, waveform = acquisition_fixture(nblocks=24)
    for duration_scale in (0.999, 1.001)
        dilated = AcquisitionJuna._resample_to(
            waveform, round(Int, duration_scale * length(waveform)))
        duration = (length(dilated) - 1) / fs
        start_hz = -10.0
        stop_hz = 10.0
        slope_hz_per_second = (stop_hz - start_hz) / duration
        time = collect(0:length(dilated)-1) ./ fs
        impaired = dilated .* cispi.(
            2 .* (start_hz .* time .+
                  0.5 .* slope_hz_per_second .* time .^ 2))

        corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
            modem, impaired, fc, fs, 24)
        phase = sum(corrected .* conj.(payload))
        aligned = corrected .* cis(-angle(phase))

        @test length(corrected) == length(payload)
        @test isfinite(estimated_hz)
        @test abs(residual_frequency_hz(corrected, payload, fs)) <= 0.25
        @test sum(abs2, aligned - payload) / sum(abs2, payload) <= 0.02
    end
end

@testset "constant carrier and duration errors are jointly corrected" begin
    modem, fc, fs, payload, waveform = acquisition_fixture(nblocks=24)
    injected_hz = 5.0
    for duration_scale in (0.999, 1.001)
        dilated = AcquisitionJuna._resample_to(
            waveform, round(Int, duration_scale * length(waveform)))
        sample = collect(0:length(dilated)-1)
        impaired = dilated .* cispi.(2 * injected_hz .* sample ./ fs)

        corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
            modem, impaired, fc, fs, 24)
        phase = sum(corrected .* conj.(payload))
        aligned = corrected .* cis(-angle(phase))

        @test length(corrected) == length(payload)
        @test estimated_hz ≈ injected_hz atol=0.75
        @test abs(residual_frequency_hz(corrected, payload, fs)) <= 0.25
        @test sum(abs2, aligned - payload) / sum(abs2, payload) <= 0.02
    end
end

@testset "production FFT resolves cyclic-prefix carrier aliases" begin
    fs = 4_882.8125
    fc = 13_000.0
    modem = AcquisitionJuna.LiteModulation(nc=512, np=64, sync=true)
    AcquisitionJuna.Modulations.init(modem, fc, fs)
    modem.nc = 512
    modem.np = 64
    modem.sync = true
    nblocks = 4
    N = Int(modem.nc)
    L = Int(modem.np)
    blocks = ComplexF64[]
    for block in 1:nblocks
        symbol = ComplexF64[
            cispi(2 * (0.013 + 0.002 * block) * sample) +
            0.35 * cispi(2 * (0.071 - 0.003 * block) * sample)
            for sample in 0:N-1
        ]
        append!(blocks, @view symbol[end-L+1:end])
        append!(blocks, symbol)
    end
    sync = AcquisitionJuna._sync_waveform(modem, fs)
    waveform = vcat(sync, blocks, sync)
    sample = collect(0:length(waveform)-1)

    layout = AcquisitionJuna._layout(modem, fs)
    pilot_carriers = zeros(ComplexF64, N)
    pilot_carriers[layout.pilot_idx] .= layout.pilot_syms
    pilot_symbol = ifft(pilot_carriers)
    pilot_block = vcat(@view(pilot_symbol[end-L+1:end]), pilot_symbol)
    pilot_blocks = repeat(pilot_block, nblocks)
    residual_hz = 1.4
    block_sample = collect(0:length(pilot_blocks)-1)
    residual_blocks = pilot_blocks .*
        cispi.(2 * residual_hz .* block_sample ./ fs)
    residual_score = AcquisitionJuna._pilot_cfo_score(
        modem, residual_blocks, fs, nblocks)
    @test residual_score.cp_residual_hz ≈ residual_hz atol=1e-10

    for injected_hz in (-14.8, -11.0)
        impaired = waveform .* cispi.(2 * injected_hz .* sample ./ fs)
        corrected, estimated_hz = AcquisitionJuna._coarse_doppler(
            modem, impaired, fc, fs, nblocks)
        phase = sum(corrected .* conj.(blocks))
        aligned = corrected .* cis(-angle(phase))

        @test length(corrected) == length(blocks)
        @test estimated_hz ≈ injected_hz atol=0.75
        @test abs(residual_frequency_hz(corrected, blocks, fs)) <= 0.25
        @test sum(abs2, aligned - blocks) / sum(abs2, blocks) <= 0.02
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA acquisition CFO checks passed")
end
