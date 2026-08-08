#!/usr/bin/env julia
#
# JUNA-WCz Step 8: exact conditional C/W solves with bounded Adam on z.
# The solver must preserve clamps and return its best finite
# checkpoint, even when later steps overshoot.
#
# Run alone: julia --project=. test/juna_coupled_optimization.jl
# Via runner: julia --project=. test/runtests.jl coupled-solver

using Test
using JunaCore

const CoupledSolveJuna = JunaCore.Juna

function synthetic_solver_fixture()
    problem = CoupledSolveJuna._CoupledProblem(
        zeros(ComplexF64, 2, 9);
        active = [2, 3, 4, 6, 7, 8],
        dc_index = 5,
        pilot_idx = [2, 6],
        pilot_syms = ComplexF64[1, -1],
        data_idx = [3, 4, 7, 8],
        bands = [[2, 3, 4], [6, 7, 8]],
        nbits = 6,
        inner_pilot_idx = [2],
        inner_pilot_bits = Bool[true],
        parity_sets = [[1, 2, 3, 4], [3, 4, 5, 6]],
    )
    true_z = Float64[2.5, -10.0, -2.5, 2.5, 2.5, -2.5]
    true_W = fill(ComplexF64(0.5), 2, 2)
    true_C = zeros(ComplexF64, 2, 3, 2, 1)
    for band in 1:2
        true_C[1, :, band, 1] .= ComplexF64[0.12, 1.0, 0.05]
        true_C[2, :, band, 1] .= ComplexF64[-0.12, 1.0, -0.05]
    end

    truth = CoupledSolveJuna._CoupledState(
        problem; W = true_W, C = true_C, z = true_z,
    )
    scratch = CoupledSolveJuna._CoupledScratch(problem)
    CoupledSolveJuna._coupled_symbols!(problem, truth, scratch)
    for k in problem.active
        band = problem.band_ids[k]
        for offset_pos in axes(problem.neighbor_idx, 1)
            q = problem.neighbor_idx[offset_pos, k]
            q == 0 && continue
            for branch in axes(problem.observations, 1)
                problem.observations[branch, k] +=
                    true_C[branch, offset_pos, band, 1] * scratch.symbols[q]
            end
        end
    end

    start_z = copy(true_z)
    start_z[1] = -0.3
    start_W = copy(true_W)
    start_W[1, :] .+= 0.15
    start_W[2, :] .-= 0.12
    start_C = 0.75 .* true_C
    initial = CoupledSolveJuna._CoupledState(
        problem; W = start_W, C = start_C, z = start_z,
    )
    weights = CoupledSolveJuna._CoupledWeights(
        observation = 2.0,
        pilot = 2.0,
        tie = 2.0,
        response_regularization = 1e-3,
        combiner_regularization = 1e-3,
        smoothness = 1e-3,
        parity = 0.1,
    )
    (; problem, truth, initial, weights)
end

function real_solver_fixture()
    m = CoupledSolveJuna.LiteModulation()
    code = CoupledSolveJuna._code(m)
    layout = CoupledSolveJuna._layout(m, 24_000.0)
    payload = Bool[isodd(count_ones(19i + 3)) for i in 1:JunaCore.Modulations.bitspersymbol(m)]
    message = CoupledSolveJuna._build_message(m, code, payload)
    waveform = CoupledSolveJuna._modulate_block(
        m, layout, CoupledSolveJuna._encode(code, message),
    )
    yparts = CoupledSolveJuna._branch_observations(m, waveform)
    initial_candidate = CoupledSolveJuna._initial_candidate(m, code, layout, yparts)
    problem = CoupledSolveJuna._coupled_problem_from_receiver(m, code, layout, yparts)
    initial = CoupledSolveJuna._initial_coupled_state(m, code, layout, problem, initial_candidate)
    (; m, code, layout, problem, initial)
end

@testset verbose = true "Profiled C,z" begin
    @testset "optimizer configuration is explicit and rejects unsafe values" begin
        config = CoupledSolveJuna._validate_coupled_optimizer_config(
            CoupledSolveJuna._CoupledOptimizerConfig(),
        )
        @test config.steps > 0
        @test config.alpha_z > 0
        @test 0 <= config.beta1 < 1
        @test 0 <= config.beta2 < 1
        @test config.gradient_clip > 0
        @test config.complex_value_clip > 0
        @test config.logit_clip > 0

        public_config = CoupledSolveJuna._COUPLED_PUBLIC_CONFIG
        @test public_config.steps == 8
        @test public_config.alpha_z == 0.004

        for invalid in (
            CoupledSolveJuna._CoupledOptimizerConfig(steps = -1),
            CoupledSolveJuna._CoupledOptimizerConfig(alpha_z = -0.1),
            CoupledSolveJuna._CoupledOptimizerConfig(beta1 = 1.0),
            CoupledSolveJuna._CoupledOptimizerConfig(gradient_clip = 0.0),
            CoupledSolveJuna._CoupledOptimizerConfig(logit_clip = Inf),
        )
            @test_throws ArgumentError CoupledSolveJuna._validate_coupled_optimizer_config(invalid)
        end
    end

    @testset "zero optimizer steps return an exact detached initial checkpoint" begin
        f = synthetic_solver_fixture()
        result = CoupledSolveJuna._coupled_wcz_solve(
            f.problem, f.initial;
            weights = f.weights,
            config = CoupledSolveJuna._CoupledOptimizerConfig(steps = 0),
        )

        @test result.selected_iter == 0
        @test result.loss_history == [result.initial_loss]
        @test result.best_loss == result.initial_loss
        @test result.state.W == f.initial.W
        @test result.state.C == f.initial.C
        @test result.state.z == f.initial.z
        @test result.state.W !== f.initial.W
        @test result.state.C !== f.initial.C
        @test result.state.z !== f.initial.z
    end

    @testset "exact C/W plus z Adam lowers the synthetic objective and recovers z signs" begin
        f = synthetic_solver_fixture()
        config = CoupledSolveJuna._CoupledOptimizerConfig(
            steps = 80, alpha_z = 0.08,
        )
        result1 = CoupledSolveJuna._coupled_wcz_solve(
            f.problem, f.initial; weights = f.weights, config = config,
        )
        result2 = CoupledSolveJuna._coupled_wcz_solve(
            f.problem, f.initial; weights = f.weights, config = config,
        )

        @test result1.initial_loss == result1.loss_history[1]
        @test result1.best_loss == minimum(result1.loss_history)
        @test result1.best_loss < 0.5 * result1.initial_loss
        @test 1 <= result1.selected_iter <= config.steps
        @test result1.state.W != f.initial.W
        @test result1.state.C != f.initial.C
        @test result1.state.z != f.initial.z
        @test sign.(result1.state.z[[1, 3, 4, 5, 6]]) ==
              sign.(f.truth.z[[1, 3, 4, 5, 6]])
        @test result1.state.z[2] == f.initial.z[2]
        @test all(isfinite, result1.loss_history)
        @test result1.state.W == result2.state.W
        @test result1.state.C == result2.state.C
        @test result1.state.z == result2.state.z
    end

    @testset "best-checkpoint rollback prevents a bad late step" begin
        f = synthetic_solver_fixture()
        config = CoupledSolveJuna._CoupledOptimizerConfig(
            steps = 4,
            alpha_z = 20.0,
            complex_value_clip = 1e3,
            logit_clip = 1e3,
        )
        result = CoupledSolveJuna._coupled_wcz_solve(
            f.problem, f.initial; weights = f.weights, config = config,
        )

        @test result.best_loss == minimum(result.loss_history)
        @test result.best_loss <= result.initial_loss
        @test result.selected_iter in 0:config.steps
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), result.state.W)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), result.state.C)
        @test all(isfinite, result.state.z)
    end

    @testset "real receiver initialization survives exact-conditional steps" begin
        f = real_solver_fixture()
        config = CoupledSolveJuna._CoupledOptimizerConfig(steps = 2)
        result = CoupledSolveJuna._coupled_wcz_solve(
            f.problem, f.initial;
            weights = CoupledSolveJuna._COUPLED_RUNTIME_WEIGHTS,
            config = config,
        )

        @test length(result.loss_history) == config.steps + 1
        @test isfinite(result.initial_loss)
        @test isfinite(result.best_loss)
        @test result.best_loss <= result.initial_loss
        @test size(result.state.W) == size(f.initial.W)
        @test size(result.state.C) == size(f.initial.C)
        @test size(result.state.z) == size(f.initial.z)
        @test result.state.z[f.problem.inner_pilot_mask] ==
              f.initial.z[f.problem.inner_pilot_mask]
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Profiled C,z checks passed")
end
