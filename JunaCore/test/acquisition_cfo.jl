#!/usr/bin/env julia

using Test
using JunaCore
using FFTW

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
    @test abs(residual_frequency_hz(corrected, payload, fs)) <= 0.25
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
end

@testset "combined duration dilation and carrier drift are corrected" begin
    modem, fc, fs, payload, waveform = acquisition_fixture(nblocks=24)
    duration_scale = 1.001
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

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA acquisition CFO checks passed")
end
