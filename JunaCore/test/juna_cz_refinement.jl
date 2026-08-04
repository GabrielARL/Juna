#!/usr/bin/env julia

using Test
using Random
using JunaCore

const CZJuna = JunaCore.Juna
const CZMods = JunaCore.Modulations

@testset verbose=true "C,z refinement receiver" begin
    kwargs = (
        fft_length=64, cyclic_prefix_length=16,
        ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
    )

    @testset "public identity and frame-wide code" begin
        modem = JunaCore.JunaCzRefinement.Modulation(; kwargs...)
        @test modem.mode === :frame_wide_ldpc
        @test modem.frame_receiver === :cz_refinement
        @test CZMods.refinement_objective(modem) === :cz_refinement
        code = CZJuna._frame_code(modem, 3)
        @test (code.k, code.n) == (3modem.ldpc_k, 3modem.ldpc_n)
    end

    @testset "combiner is derived only from central C" begin
        C = zeros(ComplexF64, 2, 3, 2, 1)
        C[:, 2, 1, 1] .= ComplexF64[1 + 2im, 2 - im]
        C[:, 2, 2, 1] .= ComplexF64[-1 + im, 3 + 0.5im]
        W = zeros(ComplexF64, 2, 2)
        CZJuna._cz_regularized_mrc_weights!(W, C; ridge=0.25)
        for group in axes(W, 2)
            h = @view C[:, 2, group, 1]
            @test W[:, group] ≈ h ./ (sum(abs2, h) + 0.25)
        end
        before = copy(W)
        C[:, 1, :, :] .= 100 + 70im
        C[:, 3, :, :] .= -90 + 20im
        CZJuna._cz_regularized_mrc_weights!(W, C; ridge=0.25)
        @test W ≈ before

        fill!(C, 0.0 + 0.0im)
        fill!(W, 3.0 - 2.0im)
        CZJuna._cz_regularized_mrc_weights!(W, C; ridge=0.0)
        @test all(iszero, W)
    end

    @testset "zero steps exactly reproduce frame Lite" begin
        lite = CZJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:lite, refinement_steps=0)
        refinement = JunaCore.JunaCzRefinement.Modulation(
            ; kwargs..., refinement_steps=0)
        fc, fs = 24_000.0, 24_000.0
        nbits = 2 * CZMods.bitspersymbol(lite) - 3
        payload = Bool[isodd(i) for i in 1:nbits]
        waveform = CZMods.modulate(refinement, payload, fc, fs)
        lite_metrics, _ = CZMods.demodulate(lite, nbits, waveform, fc, fs)
        refinement_metrics, _ = CZMods.demodulate(
            refinement, nbits, waveform, fc, fs)
        @test refinement_metrics == lite_metrics
        @test signbit.(refinement_metrics) == .!payload
        trace = CZJuna._cz_refinement_last_trace(refinement)
        @test trace.selection_reason === :zero_steps
        @test !trace.selected_refinement
        @test trace.configured_update_variables == (:C, :z)
        @test trace.executed_update_variables == ()
        @test !trace.refinement_executed
        @test trace.lite_ldpc_valid isa Bool
        @test trace.refinement_ldpc_valid === nothing
        @test trace.lite_crc_valid === nothing
        @test trace.refinement_crc_valid === nothing
        @test keys(trace.baseline) ==
              (:ldpc_valid, :syndrome_weight, :selection_score)
        @test trace.refinement === nothing
    end

    @testset "zero steps use frame Lite for every C,z refinement form" begin
        forms = (
            CZJuna.CzRefinementModulation,
            CZJuna.CrcCzRefinementModulation,
            CZJuna.CrcTurboCwzModulation,
            CZJuna.CrcJointCwzComparisonModulation,
            CZJuna.CrcJointCwzModulation,
        )
        fc, fs = 24_000.0, 24_000.0
        for form in forms
            receiver = form(; kwargs..., refinement_steps=0)
            lite = CZJuna.FrameWideLDPCModulation(
                ; kwargs..., frame_receiver=:lite,
                frame_crc_bits=receiver.frame_crc_bits,
                refinement_steps=0)
            nbits = receiver.frame_crc_bits == 0 ? 17 : 3
            payload = Bool[isodd(i) for i in 1:nbits]
            waveform = CZMods.modulate(receiver, payload, fc, fs)
            distorted = copy(waveform)
            gains = ComplexF64[1.2 + 0.2im, 0.8 - 0.2im]
            for view in 1:Int(receiver.partial_fft_parts)
                lo, hi = CZJuna._part_bounds(
                    Int(receiver.fft_length),
                    Int(receiver.partial_fft_parts), view)
                prefix_length = Int(receiver.cyclic_prefix_length)
                @views distorted[prefix_length+lo:prefix_length+hi] .*= gains[view]
            end
            lite_metrics, _ = CZMods.demodulate(
                lite, nbits, distorted, fc, fs)
            refinement_metrics, _ = CZMods.demodulate(
                receiver, nbits, distorted, fc, fs)
            methods = CZJuna.demodulate_methods(
                receiver, nbits, distorted, fc, fs)
            _, code, layout, nblocks, observations, _ =
                CZJuna._prepare_frame_observations(
                    receiver, nbits, distorted, fc, fs)
            lite_trace = CZJuna._frame_lite_refine(
                receiver, code, layout, observations)
            refinement_trace = CZJuna._frame_receiver_trace(
                receiver, code, layout, observations;
                payload_nbits=nbits)
            ofdm_trace = CZJuna._frame_static_trace(
                receiver, code, layout, observations, :ofdm_fec)
            expected_ofdm = CZJuna._frame_payload_metrics(
                receiver, code, ofdm_trace.best.posterior_metric,
                nblocks, nbits)
            @test refinement_metrics == lite_metrics
            @test methods.selected_receiver == lite_metrics
            @test methods.standard === methods.ofdm_fec
            @test refinement_trace.best.posterior_metric ==
                  lite_trace.best.posterior_metric
            @test methods.ofdm_fec == expected_ofdm
            if form === CZJuna.CzRefinementModulation
                @test ofdm_trace.best.posterior_metric !=
                      lite_trace.best.posterior_metric
            end
        end
    end

    @testset "C,z trajectory executes and finishes with BP" begin
        modem = JunaCore.JunaCzRefinement.Modulation(
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
        @test result.profile === :cz_refinement
        @test length(result.best.posterior_metric) == code.n
        @test all(isfinite, result.best.posterior_metric)
        trace = CZJuna._cz_refinement_last_trace(modem)
        @test trace.scope === :frame
        @test trace.configured_update_variables == (:C, :z)
        @test trace.executed_update_variables == (:C, :z)
        @test trace.refinement_executed
        @test trace.independent_w_parameters == 0
        @test trace.bp_checkpoints >= 1
        @test trace.selected_refinement isa Bool
        @test trace.lite_ldpc_valid isa Bool
        @test trace.refinement_ldpc_valid isa Bool
        @test trace.lite_crc_valid === nothing
        @test trace.refinement_crc_valid === nothing
        @test keys(trace.baseline) ==
              (:ldpc_valid, :syndrome_weight, :selection_score)
        @test keys(trace.refinement) ==
              (:ldpc_valid, :syndrome_weight, :selection_score)
        @test trace.selection_reason in (
            :lite_ldpc_valid_skip, :zero_steps, :validity, :syndrome, :score,
            :posterior_magnitude, :lite_fallback)
    end
end
