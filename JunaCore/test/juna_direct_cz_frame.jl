#!/usr/bin/env julia
#
# Direct C,z frame receiver contract.
#
# This suite fixes the two-variable objective and update requested in JCM-237:
# C follows its analytical Wirtinger gradient and z follows its analytical real
# gradient in one simultaneous proposal.  W is absent from the objective and is
# derived only when an accepted state reaches the decoder.  Backtracking,
# clipping, fixed inner-pilot bits, best-checkpoint retention, and CRC no-harm
# selection protect the receiver boundary.
#
# Run alone: julia --project=. test/juna_direct_cz_frame.jl
# Via runner: julia --project=. test/runtests.jl direct-cz

using Test
using LinearAlgebra
using Random
using JunaCore

const DirectCzJuna = JunaCore.Juna
const DirectCzMods = JunaCore.Modulations
const DIRECT_CZ_ROOT = get(
    ENV, "JUNA_CORE_ROOT", normpath(joinpath(@__DIR__, "..")))

function direct_cz_fixture()
    problem = DirectCzJuna._CoupledProblem(
        zeros(ComplexF64, 2, 9);
        active=[2, 3, 4, 6, 7, 8],
        dc_index=5,
        pilot_idx=[2, 6],
        pilot_syms=ComplexF64[1, -1],
        data_idx=[3, 4, 7, 8],
        bands=[[2, 3, 4], [6, 7, 8]],
        nbits=6,
        inner_pilot_idx=[2],
        inner_pilot_bits=Bool[true],
        parity_sets=[[1, 2, 3, 4], [3, 4, 5, 6]],
    )
    true_z = Float64[1.8, -10.0, -1.6, 1.4, 1.2, -1.1]
    true_C = zeros(ComplexF64, 2, 3, 2, 1)
    true_C[1, :, 1, 1] .= ComplexF64[0.10 - 0.04im, 1.00 + 0.08im,
                                                0.06 + 0.02im]
    true_C[2, :, 1, 1] .= ComplexF64[-0.08 + 0.03im, 0.82 - 0.11im,
                                                 0.04 - 0.03im]
    true_C[1, :, 2, 1] .= ComplexF64[0.04 + 0.02im, 0.91 - 0.06im,
                                                -0.07 + 0.01im]
    true_C[2, :, 2, 1] .= ComplexF64[-0.05 - 0.01im, 1.08 + 0.09im,
                                                 0.09 + 0.04im]
    truth = DirectCzJuna._CoupledState(
        problem;
        W=fill(0.5 + 0.0im, 2, 2),
        C=true_C,
        z=true_z,
    )
    scratch = DirectCzJuna._CoupledScratch(problem)
    DirectCzJuna._coupled_symbols!(problem, truth, scratch)
    @inbounds for k in problem.active
        group = problem.band_ids[k]
        for offset_pos in axes(problem.neighbor_idx, 1)
            q = problem.neighbor_idx[offset_pos, k]
            q == 0 && continue
            for branch in axes(problem.observations, 1)
                problem.observations[branch, k] +=
                    true_C[branch, offset_pos, group, 1] * scratch.symbols[q]
            end
        end
    end

    initial_C = 0.72 .* true_C
    initial_C[1, 2, 1, 1] += 0.14 - 0.08im
    initial_z = Float64[-0.45, -10.0, 0.35, -0.25, 0.30, 0.40]
    initial_W = ComplexF64[0.8 + 0.2im 0.4 - 0.1im;
                           0.1 - 0.3im 0.9 + 0.2im]
    initial = DirectCzJuna._CoupledState(
        problem; W=initial_W, C=initial_C, z=initial_z)
    modem = DirectCzJuna.DirectCzFrameModulation()
    weights = DirectCzJuna._direct_cz_runtime_weights(modem)
    (; problem, truth, initial, modem, weights)
end

function direct_cz_fd(problem, state, weights, field::Symbol, index;
                      component::Symbol=:real, epsilon::Float64=1e-6)
    plus = DirectCzJuna._copy_coupled_state(state)
    minus = DirectCzJuna._copy_coupled_state(state)
    if field === :C
        delta = component === :real ? epsilon : im * epsilon
        plus.C[index] += delta
        minus.C[index] -= delta
    elseif field === :z
        plus.z[index] += epsilon
        minus.z[index] -= epsilon
    else
        throw(ArgumentError("Direct C,z finite difference supports C or z"))
    end
    plus_loss = DirectCzJuna._direct_cz_objective(
        problem, plus; weights=weights).total
    minus_loss = DirectCzJuna._direct_cz_objective(
        problem, minus; weights=weights).total
    (plus_loss - minus_loss) / (2epsilon)
end

function direct_cz_clipped_complex(value::ComplexF64, limit::Float64)
    magnitude = abs(value)
    magnitude > limit ? value * (limit / magnitude) : value
end

function direct_cz_expected_trial(initial, gradient, problem, config,
                                  scale::Float64)
    expected = DirectCzJuna._copy_coupled_state(initial)
    @inbounds for index in eachindex(expected.C)
        direction = direct_cz_clipped_complex(
            gradient.C[index], config.gradient_clip)
        expected.C[index] = direct_cz_clipped_complex(
            initial.C[index] - scale * config.alpha_C * direction,
            config.complex_value_clip)
    end
    @inbounds for index in eachindex(expected.z)
        if problem.inner_pilot_mask[index]
            expected.z[index] = initial.z[index]
        else
            direction = clamp(
                gradient.z[index], -config.gradient_clip,
                config.gradient_clip)
            expected.z[index] = clamp(
                initial.z[index] - scale * config.alpha_z * direction,
                -config.logit_clip, config.logit_clip)
        end
    end
    expected
end

function direct_cz_candidate(; valid::Bool, syndrome::Int, score::Float64,
                             mean_abs_lpost::Float64)
    (; valid, syndrome, score, mean_abs_lpost)
end

function disturb_direct_cz_base!(base)
    base.nc = 128
    base.np = 8
    base.bw = 0.25
    base.dc0 = -3
    base.bpc = 1
    base.pilot_ratio = 1/5
    base.inner_pilot_ratio = 1/4
    base.ldpc_k = 20
    base.ldpc_n = 40
    base.ldpc_npc = 2
    base.partial_fft_parts = 2
    base.partial_fft_nbands = 2
    base.code = :stale_code
    base.layout = :stale_layout
    base.bp_scratch = :stale_bp_scratch
    base.cz_gradient_trace = :stale_gradient_trace
    base.cz_crc_no_harm_trace = :stale_crc_trace
    base
end

@testset verbose=true "Direct C,z frame receiver" begin
    source = joinpath(DIRECT_CZ_ROOT, "src", "juna", "direct_cz_frame.jl")
    wrapper = joinpath(DIRECT_CZ_ROOT, "src", "Juna.jl")
    chain = joinpath(DIRECT_CZ_ROOT, "tools", "explorer", "chain.json")
    wrapper_text = read(wrapper, String)
    chain_text = read(chain, String)
    include_direct =
        "include(joinpath(@__DIR__, \"juna\", \"direct_cz_frame.jl\"))"
    required_juna_symbols = (
        :DirectCzFrameModulation,
        :_DirectCzConfig,
        :_validate_direct_cz_config,
        :_direct_cz_runtime_weights,
        :_direct_cz_objective,
        :_direct_cz_objective_and_gradient!,
        :_direct_cz_solve,
        :_direct_cz_keep_best,
        :_direct_cz_crc_select,
        :_frame_direct_cz_refine,
        :_direct_cz_last_trace,
    )
    wiring = Pair{String,Bool}[
        "src/juna/direct_cz_frame.jl" => isfile(source),
        "Juna.jl include" => occursin(include_direct, wrapper_text),
        "JunaDirectCzFrame facade" =>
            isdefined(JunaCore, :JunaDirectCzFrame),
    ]
    append!(wiring, Pair{String,Bool}[
        String(symbol) => isdefined(DirectCzJuna, symbol)
        for symbol in required_juna_symbols
    ])
    append!(wiring, Pair{String,Bool}[
        "chain receiver direct_cz" =>
            occursin("\"id\": \"direct_cz\"", chain_text),
        "chain facade JunaDirectCzFrame" =>
            occursin("\"facade\": \"JunaDirectCzFrame\"", chain_text),
        "chain objective symbol" =>
            occursin("\"_direct_cz_objective_and_gradient!\"", chain_text),
        "chain solver symbol" =>
            occursin("\"_direct_cz_solve\"", chain_text),
        "chain protecting suite" =>
            occursin("\"direct-cz\"", chain_text),
    ])
    missing = first.(filter(pair -> !last(pair), wiring))

    @testset "source, facade, symbols, and chain are wired together" begin
        isempty(missing) || @info(
            "Direct C,z implementation is not wired yet", missing)
        @test isempty(missing)
    end

    if isempty(missing)
        @testset "public facade fixes the CRC no-harm direct receiver" begin
            modem = JunaCore.JunaDirectCzFrame.Modulation(
                nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
                partial_fft_parts=2, partial_fft_nbands=2,
                pilot_ratio=1/3, inner_pilot_ratio=0.0,
                refinement_steps=1,
            )
            @test modem isa DirectCzMods.Modulation
            @test modem isa DirectCzJuna.DirectCzFrameModulation
            @test modem.base isa DirectCzJuna.Modulation
            @test modem.base.mode === :frame_wide_ldpc
            @test modem.base.frame_receiver === :profiled_cz
            @test modem.base.frame_crc_bits == 16
            @test modem.base.cz_crc_no_harm
            @test !modem.base.cz_crc_gate
            @test modem.base.cz_gradient_only
            @test DirectCzMods.refinement_objective(modem) === :direct_cz_frame
            @test isvalid(modem, 24_000.0, 24_000.0)
            @test_throws ArgumentError DirectCzJuna.DirectCzFrameModulation(
                frame_receiver=:standard)
            @test_throws ArgumentError DirectCzJuna.DirectCzFrameModulation(
                frame_crc_bits=0)
            @test_throws ArgumentError DirectCzJuna.DirectCzFrameModulation(
                cz_crc_no_harm=false)
        end

        @testset "public init delegates to base and clears wrapper trace" begin
            modem = DirectCzJuna.DirectCzFrameModulation()
            reference = DirectCzJuna.DirectCzFrameModulation().base
            disturb_direct_cz_base!(modem.base)
            disturb_direct_cz_base!(reference)
            owned_base = modem.base
            modem.direct_cz_trace = (sentinel=:stale_direct_trace,)
            fc, fs = 30_000.0, 12_000.0
            signature = Tuple{typeof(modem),Float64,Float64}
            reference_return = DirectCzMods.init(reference, fc, fs)
            wrapper_return = DirectCzMods.init(modem, fc, fs)
            base_matches = all(
                field -> isequal(
                    getfield(modem.base, field), getfield(reference, field)),
                fieldnames(DirectCzJuna.Modulation),
            )
            delegates_init =
                hasmethod(DirectCzMods.init, signature) &&
                wrapper_return === reference_return &&
                modem.base === owned_base &&
                base_matches &&
                modem.direct_cz_trace === nothing

            @test delegates_init
            if delegates_init
                @test wrapper_return === reference_return
                @test modem.base === owned_base
                @test base_matches
                @test Int(modem.base.nc) == 1024
                @test Int(modem.base.np) == 256
                @test modem.base.bw == 0.5
                @test Int(modem.base.dc0) == 6
                @test modem.base.bpc == 2
                @test modem.base.pilot_ratio == 1/3
                @test modem.base.inner_pilot_ratio == 1/2
                @test modem.base.ldpc_k == 340
                @test modem.base.ldpc_n == 1360
                @test modem.base.ldpc_npc == 3
                @test modem.base.partial_fft_parts == 4
                @test modem.base.partial_fft_nbands == 16
                @test modem.base.code === nothing
                @test modem.base.layout === nothing
                @test modem.base.bp_scratch === nothing
                @test modem.direct_cz_trace === nothing
            end
        end

        @testset "pure J(C,z) weights contain no W/read-out term" begin
            f = direct_cz_fixture()
            weights = f.weights
            @test weights.observation == 1.0
            @test weights.response_regularization == 0.002
            @test weights.parity == f.modem.base.cz_parity_weight == 0.08
            @test weights.pilot == 0.0
            @test weights.tie == 0.0
            @test weights.combiner_regularization == 0.0
            @test weights.smoothness == 0.0

            gradient = DirectCzJuna._CoupledGradient(f.problem)
            terms = DirectCzJuna._direct_cz_objective_and_gradient!(
                gradient, f.problem, f.initial; weights=weights)
            changed_W = DirectCzJuna._CoupledState(
                f.problem;
                W=fill(120.0 - 75.0im, size(f.initial.W)),
                C=f.initial.C,
                z=f.initial.z,
            )
            changed_gradient = DirectCzJuna._CoupledGradient(f.problem)
            changed_terms = DirectCzJuna._direct_cz_objective_and_gradient!(
                changed_gradient, f.problem, changed_W; weights=weights)
            @test isfinite(terms.total)
            @test terms.pilot == terms.tie == 0.0
            @test terms.combiner_regularization == terms.smoothness == 0.0
            @test iszero(gradient.W)
            @test changed_terms.total == terms.total
            @test changed_gradient.C == gradient.C
            @test changed_gradient.z == gradient.z
            @test iszero(changed_gradient.W)
        end

        @testset "analytical C and z gradients match centered differences" begin
            f = direct_cz_fixture()
            gradient = DirectCzJuna._CoupledGradient(f.problem)
            DirectCzJuna._direct_cz_objective_and_gradient!(
                gradient, f.problem, f.initial; weights=f.weights)
            for index in (
                    CartesianIndex(1, 2, 1, 1),
                    CartesianIndex(2, 1, 2, 1))
                for component in (:real, :imag)
                    finite_difference = direct_cz_fd(
                        f.problem, f.initial, f.weights, :C, index;
                        component)
                    analytic = component === :real ?
                        2real(gradient.C[index]) : 2imag(gradient.C[index])
                    @test finite_difference ≈ analytic rtol=3e-5 atol=5e-8
                end
            end
            for index in (1, 3, 4, 6)
                finite_difference = direct_cz_fd(
                    f.problem, f.initial, f.weights, :z, index)
                @test finite_difference ≈ gradient.z[index] rtol=3e-5 atol=5e-8
            end
            @test gradient.z[2] == 0.0
        end

        @testset "configuration exposes separate safe C and z steps" begin
            config = DirectCzJuna._validate_direct_cz_config(
                DirectCzJuna._DirectCzConfig())
            @test config.steps == 8
            @test config.alpha_C > 0.0
            @test config.alpha_z > 0.0
            @test 0.0 < config.shrink < 1.0
            @test 0.0 < config.min_scale <= 1.0
            @test config.gradient_clip > 0.0
            @test config.complex_value_clip > 0.0
            @test config.logit_clip > 0.0
            for invalid in (
                DirectCzJuna._DirectCzConfig(steps=-1),
                DirectCzJuna._DirectCzConfig(alpha_C=0.0),
                DirectCzJuna._DirectCzConfig(alpha_z=Inf),
                DirectCzJuna._DirectCzConfig(shrink=1.0),
                DirectCzJuna._DirectCzConfig(min_scale=0.0),
                DirectCzJuna._DirectCzConfig(gradient_clip=0.0),
                DirectCzJuna._DirectCzConfig(complex_value_clip=Inf),
                DirectCzJuna._DirectCzConfig(logit_clip=-1.0),
            )
                @test_throws ArgumentError DirectCzJuna._validate_direct_cz_config(invalid)
            end
        end

        @testset "one proposal moves C and z simultaneously from one gradient" begin
            f = direct_cz_fixture()
            gradient = DirectCzJuna._CoupledGradient(f.problem)
            DirectCzJuna._direct_cz_objective_and_gradient!(
                gradient, f.problem, f.initial; weights=f.weights)
            config = DirectCzJuna._DirectCzConfig(
                steps=1,
                alpha_C=1e-4,
                alpha_z=1e-4,
                shrink=0.5,
                min_scale=2.0^-20,
                gradient_clip=1e-3,
                complex_value_clip=25.0,
                logit_clip=10.0,
            )
            result = DirectCzJuna._direct_cz_solve(
                f.problem, f.initial; weights=f.weights, config)
            @test result.accepted_steps == 1
            @test result.rejected_steps == 0
            @test result.step_scales == [1.0]
            expected = direct_cz_expected_trial(
                f.initial, gradient, f.problem, config, 1.0)
            @test result.state.C ≈ expected.C rtol=0 atol=8eps(Float64)
            @test result.state.z ≈ expected.z rtol=0 atol=8eps(Float64)
            @test result.state.W == f.initial.W
            @test result.state.C != f.initial.C
            @test result.state.z != f.initial.z
            @test result.state.z[f.problem.inner_pilot_mask] ==
                  f.initial.z[f.problem.inner_pilot_mask]
        end

        @testset "backtracking, bounds, fixed pilots, and best state are retained" begin
            f = direct_cz_fixture()
            config = DirectCzJuna._DirectCzConfig(
                steps=4,
                alpha_C=1e5,
                alpha_z=1e5,
                shrink=0.5,
                min_scale=2.0^-8,
                gradient_clip=100.0,
                complex_value_clip=2.0,
                logit_clip=3.0,
            )
            result1 = DirectCzJuna._direct_cz_solve(
                f.problem, f.initial; weights=f.weights, config)
            result2 = DirectCzJuna._direct_cz_solve(
                f.problem, f.initial; weights=f.weights, config)
            @test result1.accepted_steps + result1.rejected_steps == config.steps
            @test length(result1.loss_history) == config.steps + 1
            @test length(result1.step_scales) == config.steps
            @test all(isfinite, result1.loss_history)
            @test all(diff(result1.loss_history) .<=
                      64eps(Float64) .* max.(1.0, result1.loss_history[1:end-1]))
            @test result1.best_loss == minimum(result1.loss_history)
            @test result1.best_loss <= result1.initial_loss
            @test result1.selected_iter in 0:config.steps
            @test any(scale -> scale < 1.0, result1.step_scales)
            @test maximum(abs, result1.state.C) <=
                  config.complex_value_clip + 8eps(Float64)
            @test maximum(abs, result1.state.z[.!f.problem.inner_pilot_mask]) <=
                  config.logit_clip + 8eps(Float64)
            @test result1.state.z[f.problem.inner_pilot_mask] ==
                  f.initial.z[f.problem.inner_pilot_mask]
            @test result1.state.W == f.initial.W
            @test result1.state.C == result2.state.C
            @test result1.state.z == result2.state.z
            @test result1.loss_history == result2.loss_history
            @test result1.step_scales == result2.step_scales
        end

        @testset "decoder checkpoint and CRC selectors retain the best safe output" begin
            base = direct_cz_candidate(
                valid=false, syndrome=5, score=10.0, mean_abs_lpost=0.8)
            better = direct_cz_candidate(
                valid=false, syndrome=2, score=12.0, mean_abs_lpost=0.5)
            worse = direct_cz_candidate(
                valid=false, syndrome=6, score=1.0, mean_abs_lpost=20.0)
            best = DirectCzJuna._direct_cz_keep_best(base, better)
            @test best == better
            @test DirectCzJuna._direct_cz_keep_best(best, worse) == best

            standard = (name=:standard,)
            rescue = (name=:direct_cz,)
            standard_first = DirectCzJuna._direct_cz_crc_select(
                standard, true, rescue, true)
            rescued = DirectCzJuna._direct_cz_crc_select(
                standard, false, rescue, true)
            fallback = DirectCzJuna._direct_cz_crc_select(
                standard, false, rescue, false)
            @test standard_first.selected == standard
            @test standard_first.selected_source === :standard
            @test standard_first.selection_reason === :standard_crc_valid
            @test rescued.selected == rescue
            @test rescued.selected_source === :direct_cz
            @test rescued.selection_reason === :crc_rescue
            @test fallback.selected == standard
            @test fallback.selected_source === :standard
            @test fallback.selection_reason === :standard_fallback
        end

        @testset "frame trace derives W only for accepted decoder checkpoints" begin
            kwargs = (
                nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
                partial_fft_parts=2, partial_fft_nbands=2,
                pilot_ratio=1/3, inner_pilot_ratio=0.0,
                refinement_steps=1,
            )
            modem = JunaCore.JunaDirectCzFrame.Modulation(; kwargs...)
            payload = Bool[true, false, true, true]
            fc, fs = 24_000.0, 24_000.0
            waveform = DirectCzMods.modulate(modem, payload, fc, fs)
            metrics, _ = DirectCzMods.demodulate(
                modem, length(payload), waveform, fc, fs)
            @test (metrics .> 0) == payload
            clean_trace = DirectCzJuna._direct_cz_last_trace(modem)
            @test clean_trace.standard_crc_valid
            @test !clean_trace.rescue_executed
            @test clean_trace.selected_source === :standard
            @test clean_trace.selection_reason === :standard_crc_valid
            @test clean_trace.gradient_checkpoints == 0
            @test clean_trace.w_derivations == 0

            code = DirectCzJuna._frame_code(modem.base, 1)
            layout = DirectCzJuna._layout(modem.base, fs)
            rng = Xoshiro(1)
            observations = randn(
                rng, ComplexF64, Int(modem.base.partial_fft_parts),
                Int(modem.base.nc), 1)
            result = DirectCzJuna._frame_direct_cz_refine(
                modem, code, layout, observations;
                payload_nbits=length(payload))
            trace = DirectCzJuna._direct_cz_last_trace(modem)
            @test result.profile === :direct_cz
            @test all(isfinite, result.best.lpost_metric)
            @test trace.scope === :frame
            @test trace.optimized_variables == (:C, :z)
            @test trace.independent_w_parameters == 0
            @test !trace.standard_crc_valid
            @test trace.rescue_executed
            @test trace.accepted_steps + trace.rejected_steps == 1
            @test trace.gradient_checkpoints == trace.accepted_steps
            @test trace.w_derivations == trace.gradient_checkpoints
            @test trace.selected_source ===
                  (trace.rescue_crc_valid ? :direct_cz : :standard)
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Direct C,z frame receiver checks passed")
end
