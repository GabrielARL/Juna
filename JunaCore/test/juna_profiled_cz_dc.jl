#!/usr/bin/env julia

using Test
using Random
using JunaCore

const CzDcJuna = JunaCore.Juna
const CzDcMods = JunaCore.Modulations

@testset verbose=true "Profiled C,z" begin
    base_kwargs = (
        nc=64, np=16, ldpc_k=20, ldpc_n=40,
        ldpc_method=:evenboth, ldpc_seed=1, ldpc_no4cycle=false,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
    )
    fc, fs = 24_000.0, 24_000.0
    frame_blocks = 2

    @testset "dc=$dc shares code provenance and runs theta=(C,z)" for dc in 2:4
        lite = CzDcJuna.FrameWideLDPCModulation(
            ; base_kwargs..., ldpc_npc=dc, frame_receiver=:lite,
            refinement_steps=0)
        gradient = JunaCore.JunaProfiledCzFrame.Modulation(
            ; base_kwargs..., ldpc_npc=dc, refinement_steps=1)

        lite_code = CzDcJuna._frame_code(lite, frame_blocks)
        gradient_code = CzDcJuna._frame_code(gradient, frame_blocks)
        @test (lite_code.k, lite_code.n, lite_code.npc,
               lite_code.method, lite_code.seed, lite_code.no4cycle) ==
              (gradient_code.k, gradient_code.n, gradient_code.npc,
               gradient_code.method, gradient_code.seed,
               gradient_code.no4cycle)
        @test lite_code.npc == dc
        @test lite_code.method == "evenboth"
        @test lite_code.seed == 1
        @test lite_code.no4cycle === false
        @test lite_code.H == gradient_code.H
        @test lite_code.gen == gradient_code.gen

        nbits = frame_blocks * CzDcMods.bitspersymbol(gradient) - 3
        payload = Bool[
            isodd(count_ones((31 + dc) * i + 7))
            for i in 1:nbits
        ]
        waveform = CzDcMods.modulate(gradient, payload, fc, fs)
        rng = Xoshiro(0x435a_0000 + dc)
        noisy = waveform .+ 0.8 .* (
            randn(rng, length(waveform)) .+
            im .* randn(rng, length(waveform)))

        _, code, layout, _, observations, _ =
            CzDcJuna._prepare_frame_observations(
                gradient, nbits, noisy, fc, fs)
        result = CzDcJuna._frame_receiver_trace(
            gradient, code, layout, observations)
        trace = CzDcJuna._cz_gradient_last_trace(gradient)

        @test result.profile === :profiled_cz
        @test code.npc == dc
        @test trace.scope === :frame
        @test trace.optimized_variables == (:C, :z)
        @test trace.independent_w_parameters == 0
        @test trace.bp_checkpoints >= 1
        @test length(result.best.lpost_metric) == code.n
        @test all(isfinite, result.best.lpost_metric)
    end

    @testset "invalid dc is rejected" begin
        invalid_dc = base_kwargs.ldpc_n - base_kwargs.ldpc_k + 1
        modem = JunaCore.JunaProfiledCzFrame.Modulation(
            ; base_kwargs..., ldpc_npc=invalid_dc)
        @test !CzDcMods.isvalid(modem, fc, fs)
    end
end
