#!/usr/bin/env julia
#
# JUNA-WCz Step 7: translate one real receiver block into the constrained
# coupled problem and construct a deterministic, feasible C/W/z starting point.
#
# The adapter is the boundary between the proven miniature objective and the
# deployed OFDM/LDPC receiver. The initializer must use the Partial-FFT/BP seed;
# an all-zero z start would make many LDPC parity gradients uninformative.
#
# Run alone: julia --project=. test/juna_coupled_initialization.jl
# Via runner: julia --project=. test/runtests.jl coupled-init

using Test
using JunaCore

const CoupledInitJuna = JunaCore.Juna

function coupled_receiver_fixture()
    m = CoupledInitJuna.LiteModulation()
    code = CoupledInitJuna._code(m)
    layout = CoupledInitJuna._layout(m, 24_000.0)
    payload = Bool[isodd(count_ones(31i + 7)) for i in 1:JunaCore.Modulations.bitspersymbol(m)]
    message = CoupledInitJuna._build_message(m, code, payload)
    codeword = CoupledInitJuna._encode(code, message)
    waveform = CoupledInitJuna._modulate_block(m, layout, codeword)
    yparts = CoupledInitJuna._branch_observations(m, waveform)
    seed = CoupledInitJuna._seed_candidate(m, code, layout, yparts)
    (; m, code, layout, payload, codeword, yparts, seed)
end

@testset verbose = true "Profiled C,z" begin
    @testset "receiver block maps exactly into the coupled problem" begin
        f = coupled_receiver_fixture()
        problem = CoupledInitJuna._coupled_problem_from_receiver(
            f.m, f.code, f.layout, f.yparts,
        )
        inner_idx = findall(problem.inner_pilot_mask)

        @test problem.observations == f.yparts
        @test problem.active == f.layout.active
        @test problem.pilot_idx == f.layout.pilot_idx
        @test problem.pilot_syms == f.layout.pilot_syms
        @test problem.data_idx == f.layout.data_idx
        @test problem.bands == f.layout.bands
        @test problem.dc_index == 1
        @test problem.nbits == f.code.n
        @test problem.parity_sets == f.code.check_vars
        @test length(inner_idx) == CoupledInitJuna._n_inner(f.m, f.code.k)
        @test problem.inner_pilot_bits[inner_idx] == f.codeword[inner_idx]
        @test problem.filler_idx == f.layout.data_idx[cld(f.code.n, 2)+1:end]
        @test all(problem.neighbor_idx[:, problem.dc_index] .== 0)
    end

    @testset "receiver adapter rejects unsupported or inconsistent inputs" begin
        f = coupled_receiver_fixture()
        bpsk = CoupledInitJuna.Modulation(bpc = 1)

        @test_throws ArgumentError CoupledInitJuna._coupled_problem_from_receiver(
            bpsk, f.code, f.layout, f.yparts,
        )
        @test_throws DimensionMismatch CoupledInitJuna._coupled_problem_from_receiver(
            f.m, f.code, f.layout, f.yparts[:, 1:end-1],
        )
    end

    @testset "seed initialization is deterministic finite and clamp-safe" begin
        f = coupled_receiver_fixture()
        problem = CoupledInitJuna._coupled_problem_from_receiver(
            f.m, f.code, f.layout, f.yparts,
        )
        state1 = CoupledInitJuna._initial_coupled_state(
            f.m, f.code, f.layout, problem, f.seed,
        )
        state2 = CoupledInitJuna._initial_coupled_state(
            f.m, f.code, f.layout, problem, f.seed,
        )

        @test state1.W == state2.W
        @test state1.C == state2.C
        @test state1.z == state2.z
        @test size(state1.W) == (f.m.partial_fft_parts, length(f.layout.bands))
        @test size(state1.C) == (f.m.partial_fft_parts, 3, length(f.layout.bands), 1)
        @test length(state1.z) == f.code.n
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), state1.W)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), state1.C)
        @test all(isfinite, state1.z)
        @test sum(abs2, state1.W) > 0
        @test sum(abs2, state1.C) > 0

        unclamped = findall(.!problem.inner_pilot_mask)
        expected_z = clamp.(-f.seed.lpost_metric, -10.0, 10.0)
        @test state1.z[unclamped] == expected_z[unclamped]
        @test tanh.(state1.z[problem.inner_pilot_mask] ./ 2) ≈
              [bit ? -tanh(5.0) : tanh(5.0)
               for bit in problem.inner_pilot_bits[problem.inner_pilot_mask]]

        gradient = CoupledInitJuna._CoupledGradient(problem)
        terms = CoupledInitJuna._coupled_objective_and_gradient!(
            gradient, problem, state1,
        )
        @test isfinite(terms.total)
        @test all(isfinite, gradient.z)
        @test gradient.z[problem.inner_pilot_mask] == zeros(count(problem.inner_pilot_mask))
    end

    @testset "profiled C and pilot-trained W improve their own objective families" begin
        f = coupled_receiver_fixture()
        problem = CoupledInitJuna._coupled_problem_from_receiver(
            f.m, f.code, f.layout, f.yparts,
        )
        initialized = CoupledInitJuna._initial_coupled_state(
            f.m, f.code, f.layout, problem, f.seed,
        )

        no_C = CoupledInitJuna._CoupledState(
            problem; W = initialized.W, z = initialized.z,
        )
        physical_weights = CoupledInitJuna._CoupledWeights(
            observation = 1.0, response_regularization = 1e-3,
        )
        @test CoupledInitJuna._coupled_objective(
            problem, initialized; weights = physical_weights,
        ).total < CoupledInitJuna._coupled_objective(
            problem, no_C; weights = physical_weights,
        ).total

        no_W = CoupledInitJuna._CoupledState(
            problem; C = initialized.C, z = initialized.z,
        )
        combiner_weights = CoupledInitJuna._CoupledWeights(
            pilot = 1.0, tie = 1.0, combiner_regularization = 1e-6,
        )
        @test CoupledInitJuna._coupled_objective(
            problem, initialized; weights = combiner_weights,
        ).total < CoupledInitJuna._coupled_objective(
            problem, no_W; weights = combiner_weights,
        ).total

        short_seed = merge(f.seed, (; lpost_metric = f.seed.lpost_metric[1:end-1]))
        @test_throws DimensionMismatch CoupledInitJuna._initial_coupled_state(
            f.m, f.code, f.layout, problem, short_seed,
        )
    end

    @testset "initialization rejects non-finite observations and posterior metrics" begin
        f = coupled_receiver_fixture()
        bad_observations = CoupledInitJuna._coupled_problem_from_receiver(
            f.m, f.code, f.layout, f.yparts,
        )
        bad_observations.observations[1, first(bad_observations.active)] =
            ComplexF64(NaN, 0)
        observation_error = try
            CoupledInitJuna._initial_coupled_state(
                f.m, f.code, f.layout, bad_observations, f.seed,
            )
            nothing
        catch err
            err
        end
        @test observation_error isa ArgumentError
        @test occursin("finite observations", lowercase(sprint(showerror, observation_error)))

        problem = CoupledInitJuna._coupled_problem_from_receiver(
            f.m, f.code, f.layout, f.yparts,
        )
        metrics = copy(f.seed.lpost_metric)
        metrics[1] = NaN
        bad_seed = merge(f.seed, (; lpost_metric = metrics))
        metric_error = try
            CoupledInitJuna._initial_coupled_state(
                f.m, f.code, f.layout, problem, bad_seed,
            )
            nothing
        catch err
            err
        end
        @test metric_error isa ArgumentError
        @test occursin("finite posterior metrics", lowercase(sprint(showerror, metric_error)))
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Profiled C,z checks passed")
end
