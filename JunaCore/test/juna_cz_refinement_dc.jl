#!/usr/bin/env julia

using Test
using Random
using JunaCore

const CzDcJuna = JunaCore.Juna
const CzDcMods = JunaCore.Modulations

@testset verbose=true "C,z refinement code settings" begin
    base_kwargs = (
        fft_length=64, cyclic_prefix_length=16, ldpc_k=20, ldpc_n=40,
        ldpc_method=:evenboth, ldpc_seed=1,
        ldpc_eliminate_length_4_cycles=false,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
    )
    fc, fs = 24_000.0, 24_000.0
    frame_blocks = 2

    @testset "per-column check count $check_count uses the same code and updates C and z" for check_count in 2:4
        lite = CzDcJuna.FrameWideLDPCModulation(
            ; base_kwargs..., ldpc_checks_per_column=check_count,
            frame_receiver=:lite,
            refinement_steps=0)
        refinement = JunaCore.JunaCzRefinement.Modulation(
            ; base_kwargs..., ldpc_checks_per_column=check_count,
            refinement_steps=1)

        lite_code = CzDcJuna._frame_code(lite, frame_blocks)
        refinement_code = CzDcJuna._frame_code(refinement, frame_blocks)
        @test (lite_code.k, lite_code.n, lite_code.npc,
               lite_code.method, lite_code.seed, lite_code.no4cycle) ==
              (refinement_code.k, refinement_code.n, refinement_code.npc,
               refinement_code.method, refinement_code.seed,
               refinement_code.no4cycle)
        @test lite_code.npc == check_count
        @test lite_code.method == "evenboth"
        @test lite_code.seed == 1
        @test lite_code.no4cycle === false
        @test lite_code.H == refinement_code.H
        @test lite_code.gen == refinement_code.gen

        nbits = frame_blocks * CzDcMods.bitspersymbol(refinement) - 3
        payload = Bool[
            isodd(count_ones((31 + check_count) * i + 7))
            for i in 1:nbits
        ]
        waveform = CzDcMods.modulate(refinement, payload, fc, fs)
        rng = Xoshiro(0x435a_0000 + check_count)
        noisy = waveform .+ 0.8 .* (
            randn(rng, length(waveform)) .+
            im .* randn(rng, length(waveform)))

        _, code, layout, _, observations, _ =
            CzDcJuna._prepare_frame_observations(
                refinement, nbits, noisy, fc, fs)
        result = CzDcJuna._frame_receiver_trace(
            refinement, code, layout, observations)
        trace = CzDcJuna._cz_refinement_last_trace(refinement)

        @test result.profile === :cz_refinement
        @test code.npc == check_count
        @test trace.scope === :frame
        @test trace.configured_update_variables == (:C, :z)
        @test trace.independent_w_parameters == 0
        @test trace.bp_checkpoints >= 1
        @test length(result.best.posterior_metric) == code.n
        @test all(isfinite, result.best.posterior_metric)
        if trace.refinement_executed
            @test trace.executed_update_variables == (:C, :z)
            @test trace.refinement_ldpc_valid isa Bool
            @test keys(trace.refinement) ==
                  (:ldpc_valid, :syndrome_weight, :selection_score)
        else
            @test trace.executed_update_variables == ()
            @test trace.refinement_ldpc_valid === nothing
            @test trace.refinement === nothing
        end
        @test trace.lite_ldpc_valid isa Bool
        @test trace.lite_crc_valid === nothing
        @test trace.refinement_crc_valid === nothing
    end

    @testset "invalid per-column check count is rejected" begin
        invalid_check_count = base_kwargs.ldpc_n - base_kwargs.ldpc_k + 1
        modem = JunaCore.JunaCzRefinement.Modulation(
            ; base_kwargs..., ldpc_checks_per_column=invalid_check_count)
        @test !CzDcMods.isvalid(modem, fc, fs)
    end
end
