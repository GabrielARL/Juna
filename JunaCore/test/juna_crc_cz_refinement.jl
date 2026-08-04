#!/usr/bin/env julia

using Test
using JunaCore
using LinearAlgebra

const CrcJuna = JunaCore.Juna
const CrcMods = JunaCore.Modulations

function _joint_cwz_diagnostic_trace(;
        joint_cwz_pilot_tolerance::Real=0.0)
    kwargs = (
        fft_length=64, cyclic_prefix_length=16,
        ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
        refinement_steps=2, cz_crc_gate_at_selection_only=true,
        synchronization_enabled=false,
        joint_cwz_c_radius=0.5,
        joint_cwz_w_radius=0.5,
        joint_cwz_z_radius=0.5,
        joint_cwz_first_w_iteration=1,
    )
    valid_receiver = CrcJuna.CrcJointCwzModulation(
        ; kwargs..., joint_cwz_pilot_tolerance=0.0)
    payload = Bool[isodd(count_ones(29i + 11)) for i in 1:24]
    fc, fs = 24_000.0, 24_000.0
    waveform = CrcMods.modulate(valid_receiver, payload, fc, fs)
    payload_nbits, code, layout, _, observations, _ =
        CrcJuna._prepare_frame_observations(
            valid_receiver, length(payload), waveform, fc, fs)

    # Public decoding rejects a negative tolerance as an invalid setting. The
    # direct internal call below uses it only to force every trial to reject,
    # so this test can observe the outer counter without changing solver math.
    receiver = CrcJuna.CrcJointCwzModulation(
        ; kwargs...,
          joint_cwz_pilot_tolerance=Float64(joint_cwz_pilot_tolerance))
    CrcJuna._frame_cz_refine(
        receiver, code, layout, observations; payload_nbits)
    CrcJuna._cz_refinement_last_trace(receiver)
end

@testset verbose=true "CRC, turbo, and joint C,W,z forms" begin
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
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40,
            inner_pilot_ratio=0.0)
        crc_gated_receiver = JunaCore.JunaCrcCzRefinement.Modulation(
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40,
            inner_pilot_ratio=0.0)
        @test CrcJuna._frame_payload_capacity(plain, 3) == 60
        @test CrcJuna._frame_payload_capacity(crc_gated_receiver, 3) == 44
        @test CrcJuna._frame_code(plain, 3).n ==
              CrcJuna._frame_code(crc_gated_receiver, 3).n
        @test crc_gated_receiver.frame_crc_bits == 16
        @test crc_gated_receiver.mode === :crc_cz_refinement
    end

    @testset "CRC gate keeps Lite except for a certified rescue" begin
        @test CrcJuna._cz_crc_choose_refinement(false, true)
        @test !CrcJuna._cz_crc_choose_refinement(false, false)
        @test !CrcJuna._cz_crc_choose_refinement(true, true)
        @test !CrcJuna._cz_crc_choose_refinement(true, false)
        @test CrcJuna.CrcCzRefinementModulation().
              cz_require_crc_for_replacement
        @test !CrcJuna.CrcCzRefinementModulation(
            cz_require_crc_for_replacement=false).
            cz_require_crc_for_replacement
    end

    @testset "CRC C,z uses posterior-moment channel refinement" begin
        posterior_moment_receiver =
            JunaCore.JunaCrcCzRefinement.Modulation()
        mean_only_receiver = JunaCore.JunaCrcCzRefinement.Modulation(
            cz_posterior_moment_update_enabled=false)
        @test posterior_moment_receiver.cz_posterior_moment_update_enabled
        @test !mean_only_receiver.cz_posterior_moment_update_enabled
        @test 0.0 <= posterior_moment_receiver.cz_response_anchor_weight
        @test 0.0 < posterior_moment_receiver.cz_response_update_fraction <= 1.0
        @test isvalid(posterior_moment_receiver, 24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcCzRefinement.Modulation(
                cz_response_anchor_weight=-eps()),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcCzRefinement.Modulation(
                cz_response_update_fraction=0.0),
            24_000.0, 24_000.0)
    end

    @testset "turbo C,W,z feeds BP posteriors back as pseudo-pilots" begin
        turbo = CrcJuna.CrcTurboCwzModulation()
        @test turbo.cz_posterior_moment_update_enabled
        @test turbo.cz_refit_w_from_decoder_posteriors
        @test turbo.cz_decoder_posterior_weight == 0.5
        @test isvalid(turbo, 24_000.0, 24_000.0)

        z = Float64[2.0, -1.0, 0.5, -0.25]
        posterior = Float64[-4.0, 3.0, -2.0, 1.0]
        inner_mask = BitVector([false, true, false, false])
        inner_bits = BitVector([false, true, false, false])
        CrcJuna._cz_apply_decoder_posterior_feedback!(
            z, posterior, inner_mask, inner_bits, 0.5, 6.0)
        @test z ≈ Float64[3.0, -6.0, 1.25, -0.625]
        @test_throws ArgumentError CrcJuna._cz_apply_decoder_posterior_feedback!(
            z, posterior, inner_mask, inner_bits, -eps(), 6.0)
        @test_throws DimensionMismatch CrcJuna._cz_apply_decoder_posterior_feedback!(
            z, posterior[1:3], inner_mask, inner_bits, 0.5, 6.0)
    end

    @testset "C,z decoder feedback changes values only" begin
        default = CrcJuna.CrcCzRefinementModulation()
        @test default.cz_feedback_source === :decoder_posterior
        @test CrcJuna._CZ_FEEDBACK_SOURCES ==
              (:initial_logits, :decoder_posterior, :transmitted_symbols)
        for source in CrcJuna._CZ_FEEDBACK_SOURCES
            @test isvalid(
                CrcJuna.CrcCzRefinementModulation(
                    cz_feedback_source=source),
                24_000.0, 24_000.0)
        end
        @test !isvalid(
            CrcJuna.CrcCzRefinementModulation(
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
        for source in (:initial_logits, :decoder_posterior,
                       :transmitted_symbols)
            modem = CrcJuna.CrcCzRefinementModulation(
                cz_feedback_source=source,
                cz_decoder_posterior_weight=0.4,
                transmitted_symbols=
                    source === :transmitted_symbols ? truth : nothing)
            plans[source] = CrcJuna._cz_feedback_plan(
                modem, initial, posterior, inner_mask, inner_bits,
                1, 8, 6.0)
        end

        initial_logits_plan = plans[:initial_logits]
        decoder_posterior_plan = plans[:decoder_posterior]
        transmitted_symbols_plan = plans[:transmitted_symbols]
        @test initial_logits_plan.support ==
              decoder_posterior_plan.support ==
              transmitted_symbols_plan.support ==
              findall(!, inner_mask)
        @test initial_logits_plan.weights ==
              decoder_posterior_plan.weights ==
              transmitted_symbols_plan.weights ==
              fill(0.4, count(!, inner_mask))
        @test initial_logits_plan.values == initial[initial_logits_plan.support]
        @test decoder_posterior_plan.values ==
              clamp.(-posterior[decoder_posterior_plan.support], -6.0, 6.0)
        @test transmitted_symbols_plan.values ==
              Float64[6.0, -6.0, 6.0, 6.0, -6.0, -6.0]
        @test length(unique((
            initial_logits_plan.values, decoder_posterior_plan.values,
            transmitted_symbols_plan.values))) == 3

        for source in (:initial_logits, :decoder_posterior,
                       :transmitted_symbols)
            z = copy(initial)
            CrcJuna._cz_apply_feedback!(
                z, plans[source], inner_mask, inner_bits, 6.0)
            @test z[inner_mask] == Float64[-6.0, 6.0]
        end
        @test_throws ArgumentError CrcJuna._cz_feedback_plan(
            CrcJuna.CrcCzRefinementModulation(
                cz_feedback_source=:transmitted_symbols,
                cz_decoder_posterior_weight=0.4),
            initial, posterior, inner_mask, inner_bits, 1, 8, 6.0)
        @test_throws DimensionMismatch CrcJuna._cz_feedback_plan(
            CrcJuna.CrcCzRefinementModulation(
                cz_feedback_source=:transmitted_symbols,
                cz_decoder_posterior_weight=0.4,
                transmitted_symbols=reshape(truth[1:2], :, 1)),
            initial, posterior, inner_mask, inner_bits, 1, 8, 6.0)
    end

    @testset "joint C,W,z control differs by one setting" begin
        control = CrcJuna.CrcJointCwzComparisonModulation(
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            cz_refit_w_from_decoder_posteriors=true,
            cz_decoder_posterior_weight=0.25,
            cz_variable_projection_gradient=false,
            joint_cwz_enabled=false)
        treatment = CrcJuna.CrcJointCwzComparisonModulation(
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            cz_refit_w_from_decoder_posteriors=true,
            cz_decoder_posterior_weight=0.25,
            cz_variable_projection_gradient=false,
            joint_cwz_enabled=true)
        differing = Symbol[
            name for name in fieldnames(typeof(control))
            if getfield(control, name) != getfield(treatment, name)
        ]
        @test differing == [:joint_cwz_enabled]
        @test control.cz_refit_w_from_decoder_posteriors
        @test control.cz_decoder_posterior_weight == 0.25
        @test !control.cz_variable_projection_gradient
        @test !control.joint_cwz_enabled
        @test treatment.joint_cwz_enabled
        joint_facade = CrcJuna.CrcJointCwzModulation(
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0)
        expected_treatment = CrcJuna.CrcJointCwzComparisonModulation(
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            joint_cwz_enabled=true)
        @test all(
            getfield(joint_facade, name) == getfield(expected_treatment, name)
            for name in fieldnames(typeof(expected_treatment)))
    end

    @testset "CRC gate changes selection only" begin
        kwargs = (
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            frame_crc_bits=16, refinement_steps=2,
            cz_crc_gate_at_selection_only=true,
            cz_feedback_source=:decoder_posterior,
            cz_decoder_posterior_weight=0.5,
        )
        transmitter = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard)
        ungated = CrcJuna.CrcCzRefinementModulation(
            ; kwargs..., cz_require_crc_for_replacement=false)
        crc_gated_receiver = CrcJuna.CrcCzRefinementModulation(
            ; kwargs..., cz_require_crc_for_replacement=true)
        payload = Bool[isodd(count_ones(17i + 3)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(transmitter, payload, fc, fs)

        CrcMods.demodulate(ungated, length(payload), waveform, fc, fs)
        CrcMods.demodulate(
            crc_gated_receiver, length(payload), waveform, fc, fs)
        ungated_trace = CrcJuna._cz_refinement_last_trace(ungated)
        gated_trace = CrcJuna._cz_refinement_last_trace(crc_gated_receiver)
        @test ungated_trace.bp_checkpoints == gated_trace.bp_checkpoints
        @test ungated_trace.restart_count == gated_trace.restart_count
        @test ungated_trace.candidates == gated_trace.candidates
        @test ungated_trace.feedback_source == gated_trace.feedback_source ==
              :decoder_posterior
        @test ungated_trace.feedback_support == gated_trace.feedback_support
        @test ungated_trace.feedback_weights == gated_trace.feedback_weights
        @test ungated_trace.feedback_value_history ==
              gated_trace.feedback_value_history
        @test length(ungated_trace.feedback_value_history) ==
              ungated_trace.bp_checkpoints - 1
        @test all(
            entry -> (
                keys(entry) == (:restart, :iteration, :values) &&
                length(entry.values) == length(ungated_trace.feedback_support) &&
                all(isfinite, entry.values)
            ),
            ungated_trace.feedback_value_history,
        )
        @test [(entry.restart, entry.iteration)
               for entry in ungated_trace.feedback_value_history] ==
              [(restart, iteration)
               for restart in 1:ungated_trace.restart_count
               for iteration in 1:ungated.refinement_steps]
        @test ungated_trace.selection_gate === :candidate_order
        @test gated_trace.selection_gate === :crc
    end

    @testset "joint C,W,z is CRC/Lite anchored" begin
        joint = CrcJuna.CrcJointCwzModulation(
            cz_temporal_c_penalty_weight=0.2)
        @test joint.joint_cwz_enabled
        @test joint.cz_posterior_moment_update_enabled
        @test joint.cz_decoder_posterior_weight == 0.5
        @test joint.frame_crc_bits == 16
        @test joint.joint_cwz_c_radius == 0.05
        @test joint.joint_cwz_w_radius == 0.01
        @test joint.joint_cwz_z_radius == 0.5
        @test joint.joint_cwz_first_w_iteration == 2
        @test joint.cz_temporal_c_penalty_weight == 0.2
        @test isvalid(joint, 24_000.0, 24_000.0)

        @test !isvalid(
            CrcJuna.CrcJointCwzModulation(
                joint_cwz_c_radius=0.0),
            24_000.0, 24_000.0)
        @test !isvalid(
            CrcJuna.CrcJointCwzModulation(
                joint_cwz_pilot_tolerance=-eps()),
            24_000.0, 24_000.0)
        @test !isvalid(
            CrcJuna.CrcJointCwzModulation(
                cz_temporal_c_penalty_weight=-eps()),
            24_000.0, 24_000.0)
    end

    @testset "temporal C penalty has the analytical gradient" begin
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

    @testset "joint C,W,z directions respect relative trust radii" begin
        x = ComplexF64[2 + 1im, -1 + 0.5im, 0.25 - 0.75im]
        g = ComplexF64[10 - 3im, -7 + 2im, 1 + 9im]
        direction = CrcJuna._joint_cwz_direction(x, g, 0.05)
        @test all(isfinite, direction)
        direction_limit = 0.05 * max(norm(x), sqrt(length(x)))
        @test norm(direction) ≈ direction_limit rtol=8eps(Float64)
        @test real(dot(g, direction)) < 0

        z = Float64[0.0, 1.0, -2.0, 0.25]
        gz = Float64[4.0, -3.0, 1.0, 8.0]
        dz = CrcJuna._joint_cwz_direction(z, gz, 0.5)
        @test maximum(abs, dz) ≈ 0.5 rtol=8eps(Float64)
        @test dot(gz, dz) < 0
        @test iszero(norm(CrcJuna._joint_cwz_direction(z, zero(gz), 0.5)))
    end

    @testset "joint C,W,z acceptance protects objective and pilots" begin
        @test CrcJuna._joint_cwz_step_is_accepted(
            10.0, 9.0, 2.0, 2.01, 0.01)
        @test !CrcJuna._joint_cwz_step_is_accepted(
            10.0, 10.1, 2.0, 1.9, 0.01)
        @test !CrcJuna._joint_cwz_step_is_accepted(
            10.0, 9.0, 2.0, 2.1, 0.01)
        @test !CrcJuna._joint_cwz_step_is_accepted(
            10.0, NaN, 2.0, 2.0, 0.01)
    end

    @testset "joint C,W,z trace distinguishes backtracking and outer rejection" begin
        backtracked = _joint_cwz_diagnostic_trace()
        @test backtracked.joint_cwz_accepted_steps == 2
        @test backtracked.joint_cwz_rejected_steps == 0
        @test length(backtracked.joint_cwz_step_scales) == 2
        @test all(scale -> 0.0 < scale < 1.0,
                  backtracked.joint_cwz_step_scales)

        rejected = _joint_cwz_diagnostic_trace(
            joint_cwz_pilot_tolerance=-1.0)
        @test rejected.joint_cwz_accepted_steps == 0
        @test rejected.joint_cwz_rejected_steps == 2
        @test isempty(rejected.joint_cwz_step_scales)
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
            JunaCore.JunaCrcCzRefinement.Modulation(cz_restarts=5),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcCzRefinement.Modulation(cz_restarts=0),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcCzRefinement.Modulation(cz_restarts=6),
            24_000.0, 24_000.0)
    end

    @testset "parity weight is an explicit nonnegative ablation control" begin
        default = JunaCore.JunaCrcCzRefinement.Modulation()
        disabled = JunaCore.JunaCrcCzRefinement.Modulation(
            cz_parity_weight=0.0)
        @test default.cz_parity_weight == 0.08
        @test disabled.cz_parity_weight == 0.0
        @test isvalid(disabled, 24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcCzRefinement.Modulation(
                cz_parity_weight=-eps()),
            24_000.0, 24_000.0)
        @test !isvalid(
            JunaCore.JunaCrcCzRefinement.Modulation(
                cz_parity_weight=Inf),
            24_000.0, 24_000.0)
    end

    @testset "parity ablation reaches the constrained C,z objective" begin
        zero_parity_weight_receiver = JunaCore.JunaCrcCzRefinement.Modulation(
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            inner_pilot_ratio=0.0, cz_parity_weight=0.0)
        default_parity_weight_receiver =
            JunaCore.JunaCrcCzRefinement.Modulation(
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            inner_pilot_ratio=0.0, cz_parity_weight=0.08)
        weights0 = CrcJuna._cz_runtime_weights(zero_parity_weight_receiver)
        weights8 = CrcJuna._cz_runtime_weights(default_parity_weight_receiver)
        @test weights0.parity == 0.0
        @test weights8.parity == 0.08

        code = CrcJuna._frame_code(zero_parity_weight_receiver, 1)
        z = collect(range(-1.1, 1.3; length=code.n))
        inner_mask = falses(code.n)
        inner_bits = falses(code.n)
        relaxed = zeros(code.n)
        parity_gradient = zeros(code.n)
        prefix = zeros(maximum(length, code.check_vars))
        clamped = similar(prefix)

        function parity_objective_gradient(weights)
            gradient = zeros(code.n)
            loss = CrcJuna._frame_coupled_loss_and_gradient!(
                zero_parity_weight_receiver, code,
                Any[], Any[], Any[], Any[],
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
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            frame_crc_bits=16,
        )
        transmitter = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:standard)
        lite = CrcJuna.FrameWideLDPCModulation(
            ; kwargs..., frame_receiver=:lite, refinement_steps=0)
        crc_gated_receiver = JunaCore.JunaCrcCzRefinement.Modulation(
            ; kwargs..., refinement_steps=0)
        payload = Bool[isodd(count_ones(13i + 7)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        waveform = CrcMods.modulate(transmitter, payload, fc, fs)
        lite_metrics, _ = CrcMods.demodulate(
            lite, length(payload), waveform, fc, fs)
        crc_gated_metrics, _ = CrcMods.demodulate(
            crc_gated_receiver, length(payload), waveform, fc, fs)
        @test length(lite_metrics) == length(payload)
        @test crc_gated_metrics == lite_metrics
        @test (crc_gated_metrics .> 0) == payload
        trace = CrcJuna._cz_refinement_last_trace(crc_gated_receiver)
        @test trace.crc_bits == 16
        @test trace.c_estimator === :posterior_moment_update
        @test trace.c_anchor === :pilots_and_unknown_energy
        @test trace.c_response_anchor_weight ==
              crc_gated_receiver.cz_response_anchor_weight
        @test trace.c_response_update_fraction ==
              crc_gated_receiver.cz_response_update_fraction
        @test isempty(trace.feedback_value_history)
        @test !trace.selected_refinement
        @test trace.configured_update_variables == (:C, :z)
        @test trace.executed_update_variables == ()
        @test !trace.refinement_executed
        @test trace.lite_ldpc_valid isa Bool
        @test trace.refinement_ldpc_valid === nothing
        @test trace.lite_crc_valid isa Bool
        @test trace.refinement_crc_valid === nothing
        @test keys(trace.baseline) ==
              (:ldpc_valid, :syndrome_weight, :selection_score)
        @test trace.refinement === nothing
    end

    @testset "complete C,z refinement family executes one update" begin
        kwargs = (
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1/3, inner_pilot_ratio=0.0,
            refinement_steps=2, cz_crc_gate_at_selection_only=true,
        )
        family = (
            (:base, JunaCore.JunaCzRefinement.Modulation(; kwargs...),
             (:C, :z)),
            (:crc, JunaCore.JunaCrcCzRefinement.Modulation(; kwargs...),
             (:C, :z)),
            (:turbo, CrcJuna.CrcTurboCwzModulation(; kwargs...),
             (:C, :W, :z)),
            (:joint_cwz_control,
             CrcJuna.CrcJointCwzComparisonModulation(; kwargs...),
             (:C, :z)),
            (:joint_cwz_treatment,
             CrcJuna.CrcJointCwzComparisonModulation(
                 ; kwargs..., joint_cwz_enabled=true),
             (:C, :W, :z)),
            (:joint_cwz_facade,
             JunaCore.JunaCrcJointCwz.Modulation(; kwargs...),
             (:C, :W, :z)),
        )
        payload = Bool[isodd(count_ones(29i + 11)) for i in 1:24]
        fc, fs = 24_000.0, 24_000.0
        for (name, modem, optimized) in family
            @testset "$name" begin
                waveform = CrcMods.modulate(modem, payload, fc, fs)
                metrics, _ = CrcMods.demodulate(
                    modem, length(payload), waveform, fc, fs)
                trace = CrcJuna._cz_refinement_last_trace(modem)
                @test length(metrics) == length(payload)
                @test all(isfinite, metrics)
                @test (metrics .> 0) == payload
                @test trace.configured_update_variables == optimized
                @test trace.executed_update_variables == optimized
                @test trace.refinement_executed
                @test trace.bp_checkpoints >= 3
                @test trace.requested_restarts == 1
                @test trace.selected_refinement isa Bool
                @test trace.lite_ldpc_valid isa Bool
                @test trace.refinement_ldpc_valid isa Bool
                if modem.frame_crc_bits == 0
                    @test trace.lite_crc_valid === nothing
                    @test trace.refinement_crc_valid === nothing
                else
                    @test trace.lite_crc_valid isa Bool
                    @test trace.refinement_crc_valid isa Bool
                end
                @test keys(trace.baseline) ==
                      (:ldpc_valid, :syndrome_weight, :selection_score)
                @test keys(trace.refinement) ==
                      (:ldpc_valid, :syndrome_weight, :selection_score)
                @test trace.joint_cwz_enabled == modem.joint_cwz_enabled
                @test trace.joint_cwz_accepted_steps +
                      trace.joint_cwz_rejected_steps >= 0
                @test length(trace.joint_cwz_step_scales) ==
                      trace.joint_cwz_accepted_steps
            end
        end
    end
end
