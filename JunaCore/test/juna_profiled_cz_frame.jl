#!/usr/bin/env julia

using Test
using Random
using JunaCore

const CZJuna = JunaCore.Juna
const CZMods = JunaCore.Modulations

@testset verbose=true "Profiled C,z" begin
    kwargs = (
        nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
    )

    @testset "public identity and frame-wide code" begin
        modem = JunaCore.JunaProfiledCzFrame.Modulation(; kwargs...)
        @test modem.mode === :frame_wide_ldpc
        @test modem.frame_receiver === :profiled_cz
        @test CZMods.refinement_objective(modem) === :profiled_cz_frame
        code = CZJuna._frame_code(modem, 3)
        @test (code.k, code.n) == (3modem.ldpc_k, 3modem.ldpc_n)
    end

    @testset "combiner is derived only from central C" begin
        C = zeros(ComplexF64, 2, 3, 2, 1)
        C[:, 2, 1, 1] .= ComplexF64[1 + 2im, 2 - im]
        C[:, 2, 2, 1] .= ComplexF64[-1 + im, 3 + 0.5im]
        W = zeros(ComplexF64, 2, 2)
        CZJuna._cz_mmse_weights!(W, C; ridge=0.25)
        for group in axes(W, 2)
            h = @view C[:, 2, group, 1]
            @test W[:, group] ≈ h ./ (sum(abs2, h) + 0.25)
        end
        before = copy(W)
        C[:, 1, :, :] .= 100 + 70im
        C[:, 3, :, :] .= -90 + 20im
        CZJuna._cz_mmse_weights!(W, C; ridge=0.25)
        @test W ≈ before
    end

    @testset "zero steps exactly reproduce frame Lite" begin
        lite = CZJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:lite, refinement_steps=0)
        cz = JunaCore.JunaProfiledCzFrame.Modulation(
            ; kwargs..., refinement_steps=0)
        fc, fs = 24_000.0, 24_000.0
        nbits = 2 * CZMods.bitspersymbol(lite) - 3
        payload = Bool[isodd(i) for i in 1:nbits]
        waveform = CZMods.modulate(cz, payload, fc, fs)
        lite_metrics, _ = CZMods.demodulate(lite, nbits, waveform, fc, fs)
        cz_metrics, _ = CZMods.demodulate(cz, nbits, waveform, fc, fs)
        @test cz_metrics == lite_metrics
        @test signbit.(cz_metrics) == .!payload
        trace = CZJuna._cz_gradient_last_trace(cz)
        @test trace.selection_reason === :standard_valid_skip
    end

    @testset "C,z trajectory executes and finishes with BP" begin
        modem = JunaCore.JunaProfiledCzFrame.Modulation(
            ; kwargs..., refinement_steps=1)
        fc, fs = 24_000.0, 24_000.0
        nbits = 2 * CZMods.bitspersymbol(modem) - 3
        payload = Bool[isodd(count_ones(19i + 5)) for i in 1:nbits]
        waveform = CZMods.modulate(modem, payload, fc, fs)
        rng = Xoshiro(0x435a)
        noisy = waveform .+ 0.8 .* (randn(rng, length(waveform)) .+
                                    im .* randn(rng, length(waveform)))
        _, code, layout, _, observations, _ =
            CZJuna._prepare_frame_observations(modem, nbits, noisy, fc, fs)
        result = CZJuna._frame_receiver_trace(modem, code, layout, observations)
        @test result.profile === :profiled_cz
        @test length(result.best.lpost_metric) == code.n
        @test all(isfinite, result.best.lpost_metric)
        trace = CZJuna._cz_gradient_last_trace(modem)
        @test trace.scope === :frame
        @test trace.optimized_variables == (:C, :z)
        @test trace.independent_w_parameters == 0
        @test trace.bp_checkpoints >= 1
        @test trace.selection_reason in (
            :lite_valid_skip, :zero_steps, :validity, :syndrome, :score,
            :posterior_magnitude, :lite_fallback)
    end
end
