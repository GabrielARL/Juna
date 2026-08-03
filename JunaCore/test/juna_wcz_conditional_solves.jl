#!/usr/bin/env julia

using Test
using JunaCore

const ConditionalWCz = JunaCore.Juna

function conditional_fixture()
    problem = ConditionalWCz._CoupledProblem(
        ComplexF64[
            0  1.0+0.2im  0.4-0.1im  -0.7+0.3im  0  -0.9+0.1im  0.2+0.4im  0.8-0.2im  0;
            0  0.7-0.1im  0.1+0.5im  -0.4-0.2im  0  -0.6-0.3im  0.5-0.2im  0.3+0.6im  0
        ];
        active=[2, 3, 4, 6, 7, 8], dc_index=5,
        pilot_idx=[2, 6], pilot_syms=ComplexF64[1, -1],
        data_idx=[3, 4, 7, 8], bands=[[2, 3, 4], [6, 7, 8]],
        nbits=6, inner_pilot_idx=[2], inner_pilot_bits=Bool[true],
        parity_sets=[[1, 2, 3, 4], [3, 4, 5, 6]],
    )
    state = ConditionalWCz._CoupledState(
        problem;
        W=fill(0.3 + 0.1im, 2, 2),
        C=fill(0.2 - 0.05im, 2, 3, 2, 1),
        z=Float64[0.4, -10.0, -0.7, 0.9, 0.2, -0.5],
    )
    weights = ConditionalWCz._CoupledWeights(
        observation=1.3, pilot=1.7, tie=0.6,
        response_regularization=0.03,
        combiner_regularization=0.04,
        smoothness=0.05, parity=0.08,
    )
    (; problem, state, weights)
end

@testset verbose=true "Profiled C,z" begin
    fixture = conditional_fixture()
    problem, state, weights = fixture.problem, fixture.state, fixture.weights

    before_c = ConditionalWCz._coupled_objective(problem, state; weights=weights).total
    ConditionalWCz._coupled_exact_C!(problem, state; weights=weights)
    after_c = ConditionalWCz._coupled_objective(problem, state; weights=weights).total
    gradient = ConditionalWCz._CoupledGradient(problem)
    ConditionalWCz._coupled_objective_and_gradient!(
        gradient, problem, state; weights=weights)
    @test after_c <= before_c + 1e-12
    @test maximum(abs, gradient.C) <= 2e-10

    before_w = after_c
    ConditionalWCz._coupled_exact_W!(problem, state; weights=weights)
    after_w = ConditionalWCz._coupled_objective(problem, state; weights=weights).total
    ConditionalWCz._coupled_objective_and_gradient!(
        gradient, problem, state; weights=weights)
    @test after_w <= before_w + 1e-12
    @test maximum(abs, gradient.W) <= 2e-10

    pilot_values = copy(state.z[problem.inner_pilot_mask])
    config = ConditionalWCz._CoupledOptimizerConfig(steps=3, alpha_z=0.002)
    result = ConditionalWCz._coupled_wcz_solve(
        problem, fixture.state; weights=weights, config=config)
    @test length(result.loss_history) == config.steps + 1
    @test result.state.z[problem.inner_pilot_mask] == pilot_values
    @test all(isfinite, result.loss_history)
end

@testset verbose=true "Profiled C,z" begin
    fixture = conditional_fixture()
    problem, weights = fixture.problem, fixture.weights

    uncertain = ConditionalWCz._copy_coupled_state(fixture.state)
    uncertain.z .= 0.0
    scratch = ConditionalWCz._CoupledScratch(problem)
    variances = ConditionalWCz._coupled_symbol_variances!(
        problem, uncertain, scratch)
    @test all(==(0.0), variances[problem.pilot_idx])
    @test all(v -> 0.0 <= v <= 1.0, variances)
    @test any(>(0.99), variances[problem.data_idx])

    mean_only = ConditionalWCz._copy_coupled_state(uncertain)
    em = ConditionalWCz._copy_coupled_state(uncertain)
    ConditionalWCz._coupled_exact_C!(
        problem, mean_only; weights=weights)
    anchor = copy(em.C)
    ConditionalWCz._coupled_em_C!(
        problem, em;
        weights=weights, anchor=anchor, trust=0.05, damping=0.5)
    @test all(isfinite, real.(em.C))
    @test all(isfinite, imag.(em.C))
    @test em.C != mean_only.C

    confident = ConditionalWCz._copy_coupled_state(fixture.state)
    confident.z .= 50.0
    exact = ConditionalWCz._copy_coupled_state(confident)
    moment = ConditionalWCz._copy_coupled_state(confident)
    ConditionalWCz._coupled_exact_C!(problem, exact; weights=weights)
    ConditionalWCz._coupled_em_C!(
        problem, moment;
        weights=weights, anchor=nothing, trust=0.0, damping=1.0)
    @test moment.C ≈ exact.C atol=1e-12 rtol=1e-12

    @test_throws ArgumentError ConditionalWCz._coupled_em_C!(
        problem, moment; weights=weights, trust=-eps())
    @test_throws ArgumentError ConditionalWCz._coupled_em_C!(
        problem, moment; weights=weights, damping=0.0)

    seed_a = ConditionalWCz._copy_coupled_state(fixture.state)
    seed_b = ConditionalWCz._copy_coupled_state(fixture.state)
    seed_a.z .= range(-4.0, 4.0; length=length(seed_a.z))
    seed_b.z .= reverse(seed_a.z)
    anchor_a = ConditionalWCz._cz_pilot_anchor_C(
        problem, seed_a, ConditionalWCz._CoupledScratch(problem), weights)
    anchor_b = ConditionalWCz._cz_pilot_anchor_C(
        problem, seed_b, ConditionalWCz._CoupledScratch(problem), weights)
    @test anchor_a == anchor_b
    @test all(isfinite, real.(anchor_a))
    @test all(isfinite, imag.(anchor_a))

    pseudo = ConditionalWCz._copy_coupled_state(uncertain)
    ConditionalWCz._coupled_posterior_W!(
        problem, pseudo; weights=weights, scratch=scratch)
    @test all(isfinite, real.(pseudo.W))
    @test all(isfinite, imag.(pseudo.W))
    @test pseudo.W != uncertain.W
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Profiled C,z checks passed")
end
