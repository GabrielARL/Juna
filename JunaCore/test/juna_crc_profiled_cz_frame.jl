#!/usr/bin/env julia

using Test
using JunaCore
using LinearAlgebra
using Random
using SignalAnalysis: mseq

const CrcJuna = JunaCore.Juna
const CrcMods = JunaCore.Modulations

@testset verbose=true "Profiled C,z" begin
    @testset "CRC-16/CCITT framing" begin
        bytes = codeunits("123456789")
        bits = Bool[
            ((byte >> shift) & 0x01) == 0x01
            for byte in bytes for shift in 7:-1:0
        ]
        @test CrcJuna._frame_crc16_ccitt(bits) == 0x29b1

        framed = CrcJuna._frame_crc_append(bits, 16)
        @test length(framed) == length(bits) + 16
        @test CrcJuna._frame_crc_valid(framed, 16)
        corrupted = copy(framed)
        corrupted[17] = !corrupted[17]
        @test !CrcJuna._frame_crc_valid(corrupted, 16)
        @test_throws ArgumentError CrcJuna._frame_crc_append(bits, 8)
    end

    @testset "fixed codeword geometry reserves CRC from user payload" begin
        plain = CrcJuna.FrameWideLDPCModulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40,
            inner_pilot_ratio=0.0)
        guarded = JunaCore.JunaCrcProfiledCzFrame.Modulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40,
            inner_pilot_ratio=0.0)
        @test CrcJuna._frame_payload_capacity(plain, 3) == 60
        @test CrcJuna._frame_payload_capacity(guarded, 3) == 44
        @test CrcJuna._frame_code(plain, 3).n ==
              CrcJuna._frame_code(guarded, 3).n
        @test guarded.frame_crc_bits == 16
        @test guarded.mode === :crc_profiled_cz_frame
    end

    @testset "CRC gate keeps Lite except for a certified rescue" begin
        @test CrcJuna._cz_crc_choose_gradient(false, true)
        @test !CrcJuna._cz_crc_choose_gradient(false, false)
        @test !CrcJuna._cz_crc_choose_gradient(true, true)
        @test !CrcJuna._cz_crc_choose_gradient(true, false)
        @test CrcJuna.CrcProfiledCzFrameModulation().cz_crc_gate
        @test !CrcJuna.CrcProfiledCzFrameModulation().cz_gradient_only
        @test !CrcJuna.CrcProfiledCzFrameModulation(
            cz_crc_gate=false).cz_crc_gate
    end

    @testset "CRC no-harm is confined to the two gradient modules" begin
        cz = JunaCore.JunaProfiledCzFrame.Modulation()
        cwz = JunaCore.JunaCrcConditionedJointCwzFrame.Modulation()
        lite = JunaCore.JunaLite.Modulation()

        @test cz.cz_crc_no_harm
        @test cwz.cz_crc_no_harm
        @test !lite.cz_crc_no_harm
        @test cz.frame_crc_bits == 16
        @test cwz.frame_crc_bits == 16
        @test !cz.cz_crc_gate
        @test !cwz.cz_crc_gate
        @test cz.cz_gradient_only
        @test cwz.cz_gradient_only
        @test !cz.cz_conditioned_joint
        @test cwz.cz_conditioned_joint
        for unprotected in (
            CrcJuna.StandardModulation(),
            CrcJuna.PartialFFTModulation(),
            CrcJuna.ProfiledCzFrameModulation(),
            CrcJuna.CrcProfiledCzFrameModulation(),
            CrcJuna.CrcTurboCwzFrameModulation(),
            CrcJuna.CrcConditionedJointCwzFrameModulation(),
            JunaCore.JunaCrcProfiledCzFrame.Modulation(),
        )
            @test !unprotected.cz_crc_no_harm
        end
        @test isdefined(CrcJuna, :_frame_crc_no_harm_profiled_cz_refine)

        @test_throws ArgumentError CrcJuna.CrcNoHarmProfiledCzFrameModulation(
            cz_crc_no_harm=false)
        @test_throws ArgumentError CrcJuna.CrcNoHarmConditionedJointCwzFrameModulation(
            cz_conditioned_joint=false)

        invalid_cz = CrcJuna.CrcNoHarmProfiledCzFrameModulation()
        invalid_cz.cz_em_enabled = true
        @test !isvalid(invalid_cz, 24_000.0, 24_000.0)
        invalid_cwz =
            CrcJuna.CrcNoHarmConditionedJointCwzFrameModulation()
        invalid_cwz.cz_bp_feedback = 0.0
        @test !isvalid(invalid_cwz, 24_000.0, 24_000.0)
    end

    @testset "CRC no-harm selection keeps exact candidates" begin
        standard_equalized = ComplexF64[1 + 2im]
        rescue_equalized = ComplexF64[3 + 4im]
        standard = (best=(name=:standard,), best_equalized=standard_equalized)
        rescue = (best=(name=:gradient,), best_equalized=rescue_equalized)

        short_circuit = CrcJuna._cz_crc_no_harm_select(
            standard, true, nothing, false)
        @test short_circuit.selected === standard
        @test short_circuit.selected.best_equalized === standard_equalized
        @test short_circuit.selection_reason === :standard_crc_valid

        rescued = CrcJuna._cz_crc_no_harm_select(
            standard, false, rescue, true)
        @test rescued.selected === rescue
        @test rescued.selected.best_equalized === rescue_equalized
        @test rescued.selection_reason === :crc_rescue

        fallback = CrcJuna._cz_crc_no_harm_select(
            standard, false, rescue, false)
        @test fallback.selected === standard
        @test fallback.selected.best_equalized === standard_equalized
        @test fallback.selection_reason === :standard_fallback
    end

    @testset "CRC-valid Standard bypasses both gradient engines" begin
        kwargs = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            refinement_steps=1,
        )
        baseline = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard, frame_crc_bits=16)
        receivers = (
            (JunaCore.JunaProfiledCzFrame.Modulation(; kwargs...), (:C, :z)),
            (JunaCore.JunaCrcConditionedJointCwzFrame.Modulation(; kwargs...),
             (:C, :W, :z)),
        )
        payload = Bool[isodd(count_ones(37i + 5)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(baseline, payload, fc, fs)
        baseline_metrics, _ = CrcMods.demodulate(
            baseline, length(payload), waveform, fc, fs)

        for (receiver, optimized_variables) in receivers
            metrics, _ = CrcMods.demodulate(
                receiver, length(payload), waveform, fc, fs)
            trace = CrcJuna._cz_crc_no_harm_last_trace(receiver)
            @test metrics == baseline_metrics
            @test trace.optimized_variables == optimized_variables
            @test trace.selected_source === :standard
            @test trace.selection_reason === :standard_crc_valid
            @test trace.standard_crc_valid
            @test !trace.rescue_is_gradient
            @test !trace.rescue_crc_valid
            @test !trace.rescue_executed
            @test trace.gradient_checkpoints == 0
            @test receiver.cz_gradient_trace === nothing
        end
    end

    @testset "uncertified gradient output falls back exactly to Standard" begin
        kwargs = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            refinement_steps=1,
        )
        baseline = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard, frame_crc_bits=16)
        receivers = (
            JunaCore.JunaProfiledCzFrame.Modulation(; kwargs...),
            JunaCore.JunaCrcConditionedJointCwzFrame.Modulation(; kwargs...),
        )
        payload = Bool[isodd(count_ones(37i + 5)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(baseline, payload, fc, fs)
        missing = zeros(ComplexF64, length(waveform))
        baseline_metrics, _ = CrcMods.demodulate(
            baseline, length(payload), missing, fc, fs)

        for receiver in receivers
            metrics, _ = CrcMods.demodulate(
                receiver, length(payload), missing, fc, fs)
            trace = CrcJuna._cz_crc_no_harm_last_trace(receiver)
            gradient_trace = CrcJuna._cz_gradient_last_trace(receiver)
            @test metrics == baseline_metrics
            @test trace.selected_source === :standard
            @test trace.selection_reason === :standard_fallback
            @test !trace.standard_crc_valid
            @test !trace.rescue_crc_valid
            @test !trace.rescue_crc_valid || trace.rescue_is_gradient
            @test trace.rescue_executed
            @test trace.gradient_checkpoints == gradient_trace.bp_checkpoints
            @test trace.gradient_checkpoints >= 2
        end
    end

    @testset "both gradient engines supply a certified rescue" begin
        kwargs = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            refinement_steps=2,
        )
        baseline = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard, frame_crc_bits=16)
        receivers = (
            (
                JunaCore.JunaProfiledCzFrame.Modulation(; kwargs...),
                CrcJuna.CrcProfiledCzFrameModulation(
                    ; kwargs..., cz_em_enabled=false,
                    cz_crc_gate=false, cz_gradient_only=true),
                (:C, :z), 1, 0,
            ),
            (
                JunaCore.JunaCrcConditionedJointCwzFrame.Modulation(; kwargs...),
                CrcJuna.CrcConditionedJointCwzFrameModulation(
                    ; kwargs..., cz_crc_gate=false, cz_gradient_only=true),
                (:C, :W, :z), 2, 2,
            ),
        )
        payload = Bool[isodd(count_ones(37i + 5)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(baseline, payload, fc, fs)
        signal_power = sum(abs2, waveform) / length(waveform)
        sigma = sqrt(signal_power / (2 * 10^(2 / 10)))
        rng = MersenneTwister(211)
        received = waveform .+ sigma .* (
            randn(rng, length(waveform)) .+
            im .* randn(rng, length(waveform)))

        baseline_metrics, _ = CrcMods.demodulate(
            baseline, length(payload), received, fc, fs)
        @test count((baseline_metrics .> 0) .!= payload) == 2
        for (protected, unwrapped, optimized_variables,
             selected_iteration, accepted_steps) in receivers
            protected_metrics, _ = CrcMods.demodulate(
                protected, length(payload), received, fc, fs)
            unwrapped_metrics, _ = CrcMods.demodulate(
                unwrapped, length(payload), received, fc, fs)
            trace = CrcJuna._cz_crc_no_harm_last_trace(protected)
            gradient_trace = CrcJuna._cz_gradient_last_trace(protected)
            unwrapped_trace = CrcJuna._cz_gradient_last_trace(unwrapped)

            @test (protected_metrics .> 0) == payload
            @test protected_metrics == unwrapped_metrics
            @test trace.selected_source === :gradient
            @test trace.selection_reason === :crc_rescue
            @test !trace.standard_crc_valid
            @test trace.rescue_is_gradient
            @test trace.rescue_crc_valid
            @test trace.rescue_executed
            @test gradient_trace.optimized_variables == optimized_variables
            @test gradient_trace.selected_iteration == selected_iteration
            @test gradient_trace.bp_checkpoints ==
                  unwrapped_trace.bp_checkpoints == 3
            @test gradient_trace.conditioned_accepted_steps ==
                  unwrapped_trace.conditioned_accepted_steps == accepted_steps
        end
    end

    @testset "conditioned no-harm keeps a CRC-valid gradient checkpoint" begin
        receiver =
            JunaCore.JunaCrcConditionedJointCwzFrame.Modulation()
        payload = Vector{Bool}(mseq(7) .> 0)
        fc, fs = 24_000.0, 24_000.0
        distorted = CrcMods.modulate(receiver, payload, fc, fs)
        gains = ComplexF64[
            1.45 - 0.35im, 0.62 + 0.75im,
            -0.35 + 1.2im, 1.05 + 0.18im,
        ]
        @test CrcJuna._frame_nblocks(receiver, length(payload)) == 1
        for part in 1:Int(receiver.partial_fft_parts)
            lo, hi = CrcJuna._part_bounds(
                Int(receiver.nc), Int(receiver.partial_fft_parts), part)
            first_sample = Int(receiver.np) + lo
            last_sample = Int(receiver.np) + hi
            @views distorted[first_sample:last_sample] .*= gains[part]
        end

        paths = CrcJuna.demodulate_methods(
            receiver, length(payload), distorted, fc, fs)
        trace = CrcJuna._cz_crc_no_harm_last_trace(receiver)
        gradient_trace = CrcJuna._cz_gradient_last_trace(receiver)

        @test count((paths.standard .> 0) .!= payload) > 0
        @test (paths.partial .> 0) == payload
        @test (paths.juna .> 0) == payload
        @test trace.optimized_variables == (:C, :W, :z)
        @test trace.selected_source === :gradient
        @test trace.selection_reason === :crc_rescue
        @test !trace.standard_crc_valid
        @test trace.rescue_is_gradient
        @test trace.rescue_crc_valid
        @test trace.rescue_executed
        @test gradient_trace.gradient_crc_valid
        @test 1 <= gradient_trace.selected_iteration <=
              CrcJuna._wcz_optimizer_config(receiver).steps
        @test gradient_trace.conditioned_accepted_steps > 0
        @test trace.gradient_checkpoints == gradient_trace.bp_checkpoints
    end

    @testset "CRC C,z uses posterior-moment channel refinement" begin
        em = JunaCore.JunaCrcProfiledCzFrame.Modulation()
        legacy = JunaCore.JunaCrcProfiledCzFrame.Modulation(
            cz_em_enabled=false)
        @test em.cz_em_enabled
        @test !legacy.cz_em_enabled
        @test 0.0 <= em.cz_em_trust
        @test 0.0 < em.cz_em_damping <= 1.0
        @test isvalid(em, 24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcProfiledCzFrame.Modulation(
                cz_em_trust=-eps()),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcProfiledCzFrame.Modulation(
                cz_em_damping=0.0),
            24_000.0, 24_000.0)
    end

    @testset "turbo C,W,z feeds BP posteriors back as pseudo-pilots" begin
        turbo = CrcJuna.CrcTurboCwzFrameModulation()
        @test turbo.cz_em_enabled
        @test turbo.cz_independent_w
        @test turbo.cz_bp_feedback == 0.5
        @test isvalid(turbo, 24_000.0, 24_000.0)

        z = Float64[2.0, -1.0, 0.5, -0.25]
        posterior = Float64[-4.0, 3.0, -2.0, 1.0]
        inner_mask = BitVector([false, true, false, false])
        inner_bits = BitVector([false, true, false, false])
        CrcJuna._cz_bp_feedback!(
            z, posterior, inner_mask, inner_bits, 0.5, 6.0)
        @test z ≈ Float64[3.0, -6.0, 1.25, -0.625]
        @test_throws ArgumentError CrcJuna._cz_bp_feedback!(
            z, posterior, inner_mask, inner_bits, -eps(), 6.0)
        @test_throws DimensionMismatch CrcJuna._cz_bp_feedback!(
            z, posterior[1:3], inner_mask, inner_bits, 0.5, 6.0)
    end

    @testset "Experiment-B C,z feedback changes values only" begin
        default = CrcJuna.CrcProfiledCzFrameModulation()
        @test default.cz_feedback_source === :legacy
        @test CrcJuna._CZ_FEEDBACK_SOURCES ==
              (:legacy, :frozen, :real, :genie)
        for source in CrcJuna._CZ_FEEDBACK_SOURCES
            @test isvalid(
                CrcJuna.CrcProfiledCzFrameModulation(
                    cz_feedback_source=source),
                24_000.0, 24_000.0)
        end
        @test !isvalid(
            CrcJuna.CrcProfiledCzFrameModulation(
                cz_feedback_source=:bogus),
            24_000.0, 24_000.0)

        initial = Float64[1.5, -2.0, 0.25, -0.5, 0.8, -1.2, 2.2, -3.0]
        posterior = Float64[-4.0, 3.0, -2.0, 1.0, -0.7, 0.4, -5.0, 2.5]
        inner_mask = BitVector([false, true, false, false,
                                false, false, true, false])
        inner_bits = BitVector([false, true, false, false,
                                false, false, false, false])
        truth = ComplexF64[
            (1 + 1im) / sqrt(2)
            (-1 + 1im) / sqrt(2)
            (1 - 1im) / sqrt(2)
            (-1 - 1im) / sqrt(2)
        ]

        plans = Dict{Symbol,Any}()
        for source in (:frozen, :real, :genie)
            modem = CrcJuna.CrcProfiledCzFrameModulation(
                cz_feedback_source=source,
                cz_bp_feedback=0.4,
                genie_symbols=source === :genie ? truth : nothing)
            plans[source] = CrcJuna._cz_feedback_plan(
                modem, initial, posterior, inner_mask, inner_bits,
                1, 8, 6.0)
        end

        frozen = plans[:frozen]
        real_arm = plans[:real]
        genie = plans[:genie]
        @test frozen.support == real_arm.support == genie.support ==
              findall(!, inner_mask)
        @test frozen.weights == real_arm.weights == genie.weights ==
              fill(0.4, count(!, inner_mask))
        @test frozen.values == initial[frozen.support]
        @test real_arm.values ==
              clamp.(-posterior[real_arm.support], -6.0, 6.0)
        @test genie.values == Float64[6.0, -6.0, 6.0, 6.0, -6.0, -6.0]
        @test length(unique((
            frozen.values, real_arm.values, genie.values))) == 3

        for source in (:frozen, :real, :genie)
            z = copy(initial)
            CrcJuna._cz_apply_feedback!(
                z, plans[source], inner_mask, inner_bits, 6.0)
            @test z[inner_mask] == Float64[-6.0, 6.0]
        end
        @test_throws ArgumentError CrcJuna._cz_feedback_plan(
            CrcJuna.CrcProfiledCzFrameModulation(
                cz_feedback_source=:genie, cz_bp_feedback=0.4),
            initial, posterior, inner_mask, inner_bits, 1, 8, 6.0)
        @test_throws DimensionMismatch CrcJuna._cz_feedback_plan(
            CrcJuna.CrcProfiledCzFrameModulation(
                cz_feedback_source=:genie, cz_bp_feedback=0.4,
                genie_symbols=reshape(truth[1:2], :, 1)),
            initial, posterior, inner_mask, inner_bits, 1, 8, 6.0)
    end

    @testset "Experiment-B conditioned control differs by one knob" begin
        control = CrcJuna.CrcConditionedCwzFrameModulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            cz_independent_w=true, cz_bp_feedback=0.25,
            cz_vp_gradient=false,
            cz_conditioned_joint=false)
        treatment = CrcJuna.CrcConditionedCwzFrameModulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            cz_independent_w=true, cz_bp_feedback=0.25,
            cz_vp_gradient=false,
            cz_conditioned_joint=true)
        differing = Symbol[
            name for name in fieldnames(typeof(control))
            if getfield(control, name) != getfield(treatment, name)
        ]
        @test differing == [:cz_conditioned_joint]
        @test control.cz_independent_w
        @test control.cz_bp_feedback == 0.25
        @test !control.cz_vp_gradient
        @test !control.cz_conditioned_joint
        @test treatment.cz_conditioned_joint
        legacy_treatment = CrcJuna.CrcConditionedJointCwzFrameModulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0)
        expected_legacy = CrcJuna.CrcConditionedCwzFrameModulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            cz_conditioned_joint=true)
        @test all(
            getfield(legacy_treatment, name) == getfield(expected_legacy, name)
            for name in fieldnames(typeof(expected_legacy)))
    end

    @testset "Experiment-B CRC gate changes selection only" begin
        kwargs = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            frame_crc_bits=16, refinement_steps=2,
            cz_gate_selection_only=true,
            cz_feedback_source=:real, cz_bp_feedback=0.5,
        )
        transmitter = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard)
        ungated = CrcJuna.CrcProfiledCzFrameModulation(
            ; kwargs..., cz_crc_gate=false)
        guarded = CrcJuna.CrcProfiledCzFrameModulation(
            ; kwargs..., cz_crc_gate=true)
        payload = Bool[isodd(count_ones(17i + 3)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(transmitter, payload, fc, fs)

        CrcMods.demodulate(ungated, length(payload), waveform, fc, fs)
        CrcMods.demodulate(guarded, length(payload), waveform, fc, fs)
        utr = CrcJuna._cz_gradient_last_trace(ungated)
        gtr = CrcJuna._cz_gradient_last_trace(guarded)
        @test utr.bp_checkpoints == gtr.bp_checkpoints
        @test utr.restart_count == gtr.restart_count
        @test utr.candidates == gtr.candidates
        @test utr.feedback_source == gtr.feedback_source == :real
        @test utr.feedback_support == gtr.feedback_support
        @test utr.feedback_weights == gtr.feedback_weights
        @test utr.feedback_value_history == gtr.feedback_value_history
        @test length(utr.feedback_value_history) == utr.bp_checkpoints - 1
        @test all(
            entry -> (
                keys(entry) == (:restart, :iteration, :values) &&
                length(entry.values) == length(utr.feedback_support) &&
                all(isfinite, entry.values)
            ),
            utr.feedback_value_history,
        )
        @test [(entry.restart, entry.iteration)
               for entry in utr.feedback_value_history] ==
              [(restart, iteration)
               for restart in 1:utr.restart_count
               for iteration in 1:ungated.refinement_steps]
        @test utr.selection_gate === :score
        @test gtr.selection_gate === :crc
    end

    @testset "conditioned joint C,W,z is CRC/Lite anchored" begin
        joint = CrcJuna.CrcConditionedJointCwzFrameModulation(
            cz_temporal_c_smoothness=0.2)
        @test joint.cz_conditioned_joint
        @test joint.cz_em_enabled
        @test joint.cz_bp_feedback == 0.5
        @test joint.frame_crc_bits == 16
        @test joint.cz_joint_c_radius == 0.05
        @test joint.cz_joint_w_radius == 0.01
        @test joint.cz_joint_z_radius == 0.5
        @test joint.cz_joint_w_start == 2
        @test joint.cz_temporal_c_smoothness == 0.2
        @test isvalid(joint, 24_000.0, 24_000.0)

        @test !isvalid(
            CrcJuna.CrcConditionedJointCwzFrameModulation(
                cz_joint_c_radius=0.0),
            24_000.0, 24_000.0)
        @test !isvalid(
            CrcJuna.CrcConditionedJointCwzFrameModulation(
                cz_joint_pilot_tolerance=-eps()),
            24_000.0, 24_000.0)
        @test !isvalid(
            CrcJuna.CrcConditionedJointCwzFrameModulation(
                cz_temporal_c_smoothness=-eps()),
            24_000.0, 24_000.0)
    end

    @testset "temporal C penalty has the analytical complex gradient" begin
        states = [
            (C=ComplexF64[1.0 + 0.2im, -0.4 + 0.7im],),
            (C=ComplexF64[0.8 - 0.1im, -0.1 + 0.5im],),
            (C=ComplexF64[0.3 + 0.4im, 0.2 - 0.2im],),
        ]
        gradients = [(C=zeros(ComplexF64, 2),) for _ in states]
        weight = 0.2
        objective() = CrcJuna._cz_temporal_c_penalty!(
            [(C=zeros(ComplexF64, 2),) for _ in states], states, weight)
        loss = CrcJuna._cz_temporal_c_penalty!(
            gradients, states, weight)
        @test loss > 0
        @test norm(sum((gradient.C for gradient in gradients))) <=
              32eps(Float64)

        epsilon = 1e-6
        block, carrier = 2, 1
        analytic = gradients[block].C[carrier]
        original = states[block].C[carrier]
        states[block].C[carrier] = original + epsilon
        plus_real = objective()
        states[block].C[carrier] = original - epsilon
        minus_real = objective()
        states[block].C[carrier] = original + im * epsilon
        plus_imag = objective()
        states[block].C[carrier] = original - im * epsilon
        minus_imag = objective()
        states[block].C[carrier] = original
        @test (plus_real - minus_real) / (2epsilon) ≈
              2real(analytic) rtol=1e-7 atol=1e-9
        @test (plus_imag - minus_imag) / (2epsilon) ≈
              2imag(analytic) rtol=1e-7 atol=1e-9

        flat_states = [(C=copy(states[1].C),) for _ in 1:3]
        flat_gradients = [(C=zeros(ComplexF64, 2),) for _ in flat_states]
        @test CrcJuna._cz_temporal_c_penalty!(
            flat_gradients, flat_states, weight) == 0.0
        @test all(iszero, (gradient.C for gradient in flat_gradients))
    end

    @testset "conditioned directions respect relative trust radii" begin
        x = ComplexF64[2 + 1im, -1 + 0.5im, 0.25 - 0.75im]
        g = ComplexF64[10 - 3im, -7 + 2im, 1 + 9im]
        direction = CrcJuna._cz_conditioned_direction(x, g, 0.05)
        @test all(isfinite, direction)
        @test norm(direction) <= 0.05 * max(norm(x), sqrt(length(x))) +
              32eps(Float64)
        @test real(dot(g, direction)) < 0

        z = Float64[0.0, 1.0, -2.0, 0.25]
        gz = Float64[4.0, -3.0, 1.0, 8.0]
        dz = CrcJuna._cz_conditioned_direction(z, gz, 0.5)
        @test maximum(abs, dz) <= 0.5 + 32eps(Float64)
        @test dot(gz, dz) < 0
    end

    @testset "conditioned acceptance protects objective and pilots" begin
        @test CrcJuna._cz_conditioned_accept(10.0, 9.0, 2.0, 2.01, 0.01)
        @test !CrcJuna._cz_conditioned_accept(10.0, 10.1, 2.0, 1.9, 0.01)
        @test !CrcJuna._cz_conditioned_accept(10.0, 9.0, 2.0, 2.1, 0.01)
        @test !CrcJuna._cz_conditioned_accept(
            10.0, NaN, 2.0, 2.0, 0.01)
    end

    @testset "nested restart initializations are deterministic and clamped" begin
        base = collect(range(-2.0, 2.0; length=20))
        inner_mask = falses(20)
        inner_mask[[1, 7, 20]] .= true
        inner_bits = falses(20)
        inner_bits[7] = true
        starts = [
            CrcJuna._cz_restart_logits(
                base, restart, 0x435a, inner_mask, inner_bits, 6.0)
            for restart in 1:5
        ]
        expected_base = copy(base)
        expected_base[1] = 6.0
        expected_base[7] = -6.0
        expected_base[20] = 6.0
        @test starts[1] == expected_base
        @test starts == [
            CrcJuna._cz_restart_logits(
                base, restart, 0x435a, inner_mask, inner_bits, 6.0)
            for restart in 1:5
        ]
        @test length(unique(starts)) == 5
        for start in starts
            @test start[1] == 6.0
            @test start[7] == -6.0
            @test start[20] == 6.0
            @test all(abs.(start) .<= 6.0)
        end
        @test count(starts[4] .!= starts[1]) <= 3 + ceil(Int, 0.05 * 17)
        @test count(starts[5] .!= starts[1]) <= 3 + ceil(Int, 0.10 * 17)
    end

    @testset "restart controls are bounded" begin
        @test isvalid(
            JunaCore.JunaCrcProfiledCzFrame.Modulation(cz_restarts=5),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcProfiledCzFrame.Modulation(cz_restarts=0),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcProfiledCzFrame.Modulation(cz_restarts=6),
            24_000.0, 24_000.0)
    end

    @testset "parity weight is an explicit nonnegative ablation control" begin
        default = JunaCore.JunaCrcProfiledCzFrame.Modulation()
        disabled = JunaCore.JunaCrcProfiledCzFrame.Modulation(
            cz_parity_weight=0.0)
        @test default.cz_parity_weight == 0.08
        @test disabled.cz_parity_weight == 0.0
        @test isvalid(disabled, 24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcProfiledCzFrame.Modulation(
                cz_parity_weight=-eps()),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcProfiledCzFrame.Modulation(
                cz_parity_weight=Inf),
            24_000.0, 24_000.0)
    end

    @testset "parity ablation reaches the constrained C,z objective" begin
        m0 = JunaCore.JunaCrcProfiledCzFrame.Modulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            inner_pilot_ratio=0.0, cz_parity_weight=0.0)
        m8 = JunaCore.JunaCrcProfiledCzFrame.Modulation(
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            inner_pilot_ratio=0.0, cz_parity_weight=0.08)
        weights0 = CrcJuna._cz_runtime_weights(m0)
        weights8 = CrcJuna._cz_runtime_weights(m8)
        @test weights0.parity == 0.0
        @test weights8.parity == 0.08

        code = CrcJuna._frame_code(m0, 1)
        z = collect(range(-1.1, 1.3; length=code.n))
        inner_mask = falses(code.n)
        inner_bits = falses(code.n)
        relaxed = zeros(code.n)
        parity_gradient = zeros(code.n)
        prefix = zeros(maximum(length, code.check_vars))
        clamped = similar(prefix)

        function parity_objective_gradient(weights)
            gradient = zeros(code.n)
            loss = CrcJuna._frame_coupled_loss_and_grad!(
                m0, code, Any[], Any[], Any[], Any[],
                gradient, z, inner_mask, inner_bits,
                relaxed, parity_gradient, prefix, clamped;
                weights=weights)
            loss, copy(gradient)
        end

        loss0, gradient0 = parity_objective_gradient(weights0)
        loss8, gradient8 = parity_objective_gradient(weights8)
        @test loss8 > loss0
        @test gradient8 != gradient0
        @test norm(gradient8 - gradient0) > 0.0
    end

    @testset "clean round trip returns only user payload bits" begin
        kwargs = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            frame_crc_bits=16,
        )
        transmitter = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard)
        lite = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:lite, refinement_steps=0)
        guarded = JunaCore.JunaCrcProfiledCzFrame.Modulation(
            ; kwargs..., refinement_steps=0)
        payload = Bool[isodd(count_ones(13i + 7)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(transmitter, payload, fc, fs)
        lite_metrics, _ = CrcMods.demodulate(
            lite, length(payload), waveform, fc, fs)
        guarded_metrics, _ = CrcMods.demodulate(
            guarded, length(payload), waveform, fc, fs)
        @test length(lite_metrics) == length(payload)
        @test guarded_metrics == lite_metrics
        @test (guarded_metrics .> 0) == payload
        trace = CrcJuna._cz_gradient_last_trace(guarded)
        @test trace.crc_bits == 16
        @test trace.c_estimator === :posterior_moment_em
        @test trace.c_anchor === :pilots_and_unknown_energy
        @test trace.c_em_trust == guarded.cz_em_trust
        @test trace.c_em_damping == guarded.cz_em_damping
        @test isempty(trace.feedback_value_history)
        @test !trace.selected_gradient
    end

    @testset "gradient-only arm bypasses CRC and Lite selection" begin
        kwargs = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            frame_crc_bits=16,
        )
        transmitter = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard)
        gradient = CrcJuna.CrcProfiledCzFrameModulation(
            ; kwargs..., refinement_steps=1, cz_crc_gate=false,
            cz_gradient_only=true)
        payload = Bool[isodd(count_ones(13i + 7)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(transmitter, payload, fc, fs)
        metrics, _ = CrcMods.demodulate(
            gradient, length(payload), waveform, fc, fs)
        trace = CrcJuna._cz_gradient_last_trace(gradient)
        @test length(metrics) == length(payload)
        @test all(isfinite, metrics)
        @test trace.selection_reason === :gradient_only
        @test trace.selected_gradient
        @test trace.selection_gate === :score
        @test trace.bp_checkpoints >= 2
        @test trace.crc_bits == 16
    end

    @testset "complete Profiled C,z family executes one update" begin
        kwargs = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            refinement_steps=2, cz_gate_selection_only=true,
        )
        family = (
            (:base, CrcJuna.ProfiledCzFrameModulation(; kwargs...),
             (:C, :z)),
            (:crc, JunaCore.JunaCrcProfiledCzFrame.Modulation(; kwargs...),
             (:C, :z)),
            (:turbo, CrcJuna.CrcTurboCwzFrameModulation(; kwargs...),
             (:C, :W, :z)),
            (:conditioned_control,
             CrcJuna.CrcConditionedCwzFrameModulation(; kwargs...),
             (:C, :z)),
            (:conditioned_treatment,
             CrcJuna.CrcConditionedCwzFrameModulation(
                 ; kwargs..., cz_conditioned_joint=true),
             (:C, :W, :z)),
            (:conditioned_legacy,
             CrcJuna.CrcConditionedJointCwzFrameModulation(; kwargs...),
             (:C, :W, :z)),
        )
        payload = Bool[isodd(count_ones(29i + 11)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        for (name, modem, optimized) in family
            @testset "$name" begin
                waveform = CrcMods.modulate(modem, payload, fc, fs)
                metrics, _ = CrcMods.demodulate(
                    modem, length(payload), waveform, fc, fs)
                trace = CrcJuna._cz_gradient_last_trace(modem)
                @test length(metrics) == length(payload)
                @test all(isfinite, metrics)
                @test (metrics .> 0) == payload
                @test trace.optimized_variables == optimized
                @test trace.bp_checkpoints >= 3
                @test trace.requested_restarts == 1
            end
        end
    end
end
