#!/usr/bin/env julia

using Test
using JunaCore

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

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA acquisition CFO checks passed")
end
