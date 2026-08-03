#!/usr/bin/env julia
#
# Safeguarded block-coordinate descent for the frozen JUNA-WCz objective.
# This diagnostic reference checks alternating gradient descent on the same
# objective used by the deployed exact-conditional solver.
#
# Run alone:  julia --project=. test/juna_coupled_block_coordinate.jl
# Via runner: julia --project=. test/runtests.jl coupled-bcd

using Test
using JunaCore

const CoupledBCDJuna = JunaCore.Juna

function coupled_bcd_fixture()
    problem = CoupledBCDJuna._CoupledProblem(
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
    truth = CoupledBCDJuna._CoupledState(
        problem;
        W = fill(ComplexF64(0.5), 2, 2),
        C = reshape(ComplexF64[
            0.12, -0.12, 1.0, 1.0, 0.05, -0.05,
            0.12, -0.12, 1.0, 1.0, 0.05, -0.05,
        ], 2, 3, 2, 1),
        z = Float64[2.5, -10.0, -2.5, 2.5, 2.5, -2.5],
    )
    scratch = CoupledBCDJuna._CoupledScratch(problem)
    CoupledBCDJuna._coupled_symbols!(problem, truth, scratch)
    for k in problem.active
        band = problem.band_ids[k]
        for offset_pos in axes(problem.neighbor_idx, 1)
            q = problem.neighbor_idx[offset_pos, k]
            q == 0 && continue
            for branch in axes(problem.observations, 1)
                problem.observations[branch, k] +=
                    truth.C[branch, offset_pos, band, 1] * scratch.symbols[q]
            end
        end
    end

    initial = CoupledBCDJuna._CoupledState(
        problem;
        W = truth.W .+ ComplexF64[0.15 -0.12; -0.12 0.15],
        C = 0.72 .* truth.C,
        z = Float64[-0.3, -10.0, -1.0, 1.0, 1.0, -1.0],
    )
    weights = CoupledBCDJuna._CoupledWeights(
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

@testset verbose = true "Profiled C,z" begin
    @testset "configuration rejects non-finite or non-positive line-search controls" begin
        config = CoupledBCDJuna._validate_coupled_bcd_config(
            CoupledBCDJuna._CoupledBCDConfig(),
        )
        @test config.cycles > 0
        @test all(>(0), (config.step_W, config.step_C, config.step_z))
        @test 0 < config.shrink < 1
        @test config.min_step > 0

        for invalid in (
            CoupledBCDJuna._CoupledBCDConfig(cycles = -1),
            CoupledBCDJuna._CoupledBCDConfig(step_C = 0.0),
            CoupledBCDJuna._CoupledBCDConfig(shrink = 1.0),
            CoupledBCDJuna._CoupledBCDConfig(min_step = Inf),
        )
            @test_throws ArgumentError CoupledBCDJuna._validate_coupled_bcd_config(invalid)
        end
    end

    @testset "zero cycles return a detached initial checkpoint" begin
        f = coupled_bcd_fixture()
        result = CoupledBCDJuna._coupled_bcd_solve(
            f.problem, f.initial;
            weights = f.weights,
            config = CoupledBCDJuna._CoupledBCDConfig(cycles = 0),
        )
        @test result.loss_history == [result.initial_loss]
        @test result.best_loss == result.initial_loss
        @test result.selected_iter == 0
        @test result.state.W == f.initial.W && result.state.W !== f.initial.W
        @test result.state.C == f.initial.C && result.state.C !== f.initial.C
        @test result.state.z == f.initial.z && result.state.z !== f.initial.z
    end

    @testset "every complete cycle is finite and monotonically non-increasing" begin
        f = coupled_bcd_fixture()
        config = CoupledBCDJuna._CoupledBCDConfig(
            cycles = 20, step_W = 2.0, step_C = 2.0, step_z = 2.0,
        )
        result1 = CoupledBCDJuna._coupled_bcd_solve(
            f.problem, f.initial; weights = f.weights, config = config,
        )
        result2 = CoupledBCDJuna._coupled_bcd_solve(
            f.problem, f.initial; weights = f.weights, config = config,
        )

        @test length(result1.loss_history) == config.cycles + 1
        @test all(isfinite, result1.loss_history)
        @test all(diff(result1.loss_history) .<= 2e-12)
        @test result1.best_loss == last(result1.loss_history)
        @test result1.best_loss < result1.initial_loss
        @test result1.selected_iter in 1:config.cycles
        @test result1.state.z[f.problem.inner_pilot_mask] ==
              f.initial.z[f.problem.inner_pilot_mask]
        @test all(z -> isfinite(real(z)) && isfinite(imag(z)), result1.state.W)
        @test all(z -> isfinite(real(z)) && isfinite(imag(z)), result1.state.C)
        @test all(isfinite, result1.state.z)
        @test result1.state.W == result2.state.W
        @test result1.state.C == result2.state.C
        @test result1.state.z == result2.state.z
    end

    @testset "diagnostic BCD and deployed solver share the frozen problem" begin
        f = coupled_bcd_fixture()
        bcd = CoupledBCDJuna._coupled_bcd_solve(
            f.problem, f.initial;
            weights = f.weights,
            config = CoupledBCDJuna._CoupledBCDConfig(cycles = 4),
        )
        adam = CoupledBCDJuna._coupled_wcz_solve(
            f.problem, f.initial;
            weights = f.weights,
            config = CoupledBCDJuna._CoupledOptimizerConfig(steps = 4),
        )

        @test bcd.initial_loss == adam.initial_loss
        @test bcd.best_loss <= bcd.initial_loss
        @test adam.best_loss <= adam.initial_loss
        @test size(bcd.state.W) == size(adam.state.W) == size(f.initial.W)
        @test size(bcd.state.C) == size(adam.state.C) == size(f.initial.C)
        @test length(bcd.state.z) == length(adam.state.z) == length(f.initial.z)
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Profiled C,z checks passed")
end
