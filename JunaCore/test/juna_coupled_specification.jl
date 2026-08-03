#!/usr/bin/env julia
#
# JUNA-WCz objective specification: freeze the deployed solver scope, make its
# miniature problem/state indexing executable, pin every scalar objective
# family independently, validate the ideal per-carrier equation, prove the
# band-tied coupling is informative, and check analytic C/W/z gradients.
#
# The public solver remains practical and identifiable while the paper's ideal
# per-carrier C/W parameterization stays available as an explicit test path:
#   - QPSK, one OFDM symbol per solve, K=1
#   - band-tied C and W
#   - hard-clamped inner pilots and fixed filler symbols
#   - DC excluded; inactive/out-of-band neighbors contribute zero
#   - every loss family normalized by its own contributing count
#   - deterministic first implementation with BP projection disabled
#
# If this fails, the mathematical problem changed before its objective and
# discrimination tests were updated to justify that change.
#
# Run alone: julia --project=. test/juna_coupled_specification.jl

using Test
using JunaCore
using LinearAlgebra

const CoupledSpecJuna = JunaCore.Juna

function coupled_spec(; bits_per_symbol::Int = 2,
                      ofdm_symbols_per_solve::Int = 1,
                      ici_half_width::Int = 1,
                      response_parameterization::Symbol = :band_tied,
                      combiner_parameterization::Symbol = :band_tied,
                      inner_pilot_policy::Symbol = :hard_clamp,
                      filler_policy::Symbol = :fixed_known_symbol,
                      dc_policy::Symbol = :excluded,
                      inactive_neighbor_policy::Symbol = :zero,
                      normalization::Symbol = :per_term_count,
                      bp_projection::Bool = false)
    CoupledSpecJuna._CoupledSolverSpec(
        bits_per_symbol = bits_per_symbol,
        ofdm_symbols_per_solve = ofdm_symbols_per_solve,
        ici_half_width = ici_half_width,
        response_parameterization = response_parameterization,
        combiner_parameterization = combiner_parameterization,
        inner_pilot_policy = inner_pilot_policy,
        filler_policy = filler_policy,
        dc_policy = dc_policy,
        inactive_neighbor_policy = inactive_neighbor_policy,
        normalization = normalization,
        bp_projection = bp_projection,
    )
end

function miniature_coupled_problem(;
    active = [2, 3, 4, 6, 7, 8],
    dc_index = 5,
    pilot_idx = [2, 6],
    pilot_syms = ComplexF64[1, -1],
    data_idx = [3, 4, 7, 8],
    bands = [[2, 3, 4], [6, 7, 8]],
    nbits = 6,
    inner_pilot_idx = [2, 5],
    inner_pilot_bits = Bool[true, false],
    parity_sets = [[1, 2, 3], [4, 5, 6]],
    spec = CoupledSpecJuna._COUPLED_SOLVER_SPEC,
)
    observations = reshape(ComplexF64.(1:18), 2, 9)
    CoupledSpecJuna._CoupledProblem(
        observations;
        active = active,
        dc_index = dc_index,
        pilot_idx = pilot_idx,
        pilot_syms = pilot_syms,
        data_idx = data_idx,
        bands = bands,
        nbits = nbits,
        inner_pilot_idx = inner_pilot_idx,
        inner_pilot_bits = inner_pilot_bits,
        parity_sets = parity_sets,
        spec = spec,
    )
end

function informative_coupled_problem()
    active = vcat(collect(2:6), collect(8:12))
    CoupledSpecJuna._CoupledProblem(
        zeros(ComplexF64, 2, 13);
        active = active,
        dc_index = 7,
        pilot_idx = [2, 8],
        pilot_syms = ComplexF64[1, -1],
        data_idx = vcat(collect(3:6), collect(9:12)),
        bands = [collect(2:6), collect(8:12)],
        nbits = 16,
    )
end

@testset "coupled coordinates preserve wrapped carrier order" begin
    active = [6, 7, 8, 2, 3, 4]
    problem = CoupledSpecJuna._CoupledProblem(
        zeros(ComplexF64, 2, 8);
        active=active,
        dc_index=1,
        pilot_idx=[6, 2],
        pilot_syms=ComplexF64[1, -1],
        data_idx=[7, 8, 3, 4],
        bands=[[6, 7, 8], [2, 3, 4]],
        nbits=6,
    )

    @test problem.active == active
    @test problem.pilot_idx == [6, 2]
    @test problem.data_idx == [7, 8, 3, 4]
    @test CoupledSpecJuna._coupled_active_slot(problem, 6) == 1
    @test CoupledSpecJuna._coupled_active_slot(problem, 2) == 4
    @test problem.fixed_symbols[6] == 1
    @test problem.fixed_symbols[2] == -1
    @test problem.symbol_slots[[7, 8, 3]] == [1, 2, 3]
end

function independent_coupled_symbols(problem, z)
    relaxed_bits = tanh.(Float64.(z) ./ 2)
    for bit_idx in eachindex(relaxed_bits)
        problem.inner_pilot_mask[bit_idx] || continue
        relaxed_bits[bit_idx] = problem.inner_pilot_bits[bit_idx] ? -1.0 : 1.0
    end

    symbols = zeros(ComplexF64, size(problem.observations, 2))
    for k in problem.active
        slot = problem.symbol_slots[k]
        if slot == 0
            symbols[k] = problem.fixed_symbols[k]
        else
            bit_i = 2slot - 1
            bit_q = bit_i + 1
            symbols[k] = ComplexF64(relaxed_bits[bit_i], relaxed_bits[bit_q]) / sqrt(2)
        end
    end
    symbols
end

function independent_coupled_observations!(problem, C, z)
    symbols = independent_coupled_symbols(problem, z)
    fill!(problem.observations, 0)
    for k in problem.active
        band_id = problem.band_ids[k]
        for offset_pos in axes(problem.neighbor_idx, 1)
            q = problem.neighbor_idx[offset_pos, k]
            q == 0 && continue
            for branch in axes(problem.observations, 1)
                problem.observations[branch, k] +=
                    C[branch, offset_pos, band_id, 1] * symbols[q]
            end
        end
    end
    problem
end

function independently_profile_C(problem, z;
                                 observation_weight = 1.0,
                                 response_weight = 0.02,
                                 offset_positions = collect(axes(problem.neighbor_idx, 1)))
    symbols = independent_coupled_symbols(problem, z)
    nparts = size(problem.observations, 1)
    noffsets = size(problem.neighbor_idx, 1)
    nbands = length(problem.bands)
    alpha = response_weight * length(problem.active) /
            (observation_weight * noffsets * nbands)
    C = zeros(ComplexF64, nparts, noffsets, nbands, 1)

    for (band_id, targets) in enumerate(problem.bands), branch in 1:nparts
        design = zeros(ComplexF64, length(targets), length(offset_positions))
        for (row, k) in enumerate(targets), (column, offset_pos) in enumerate(offset_positions)
            q = problem.neighbor_idx[offset_pos, k]
            design[row, column] = q == 0 ? 0 : symbols[q]
        end
        response = design' * design + alpha * I
        fitted = response \ (design' * problem.observations[branch, targets])
        C[branch, offset_positions, band_id, 1] .= fitted
    end
    C
end

@testset verbose = true "Profiled C,z" begin
    @testset "the Stage 1 contract has stable types and frozen values" begin
        spec = CoupledSpecJuna._COUPLED_SOLVER_SPEC

        @test spec isa CoupledSpecJuna._CoupledSolverSpec
        @test !ismutabletype(typeof(spec))
        @test fieldtypes(typeof(spec)) == (
            Int, Int, Int, Symbol, Symbol, Symbol, Symbol, Symbol, Symbol, Symbol, Bool,
        )
        @test spec.bits_per_symbol == 2
        @test spec.ofdm_symbols_per_solve == 1
        @test spec.ici_half_width == 1
        @test spec.response_parameterization === :band_tied
        @test spec.combiner_parameterization === :band_tied
        @test spec.inner_pilot_policy === :hard_clamp
        @test spec.filler_policy === :fixed_known_symbol
        @test spec.dc_policy === :excluded
        @test spec.inactive_neighbor_policy === :zero
        @test spec.normalization === :per_term_count
        @test spec.bp_projection === false
        @test collect(CoupledSpecJuna._coupled_ici_offsets(spec)) == [-1, 0, 1]
        @test CoupledSpecJuna._validate_coupled_solver_spec(spec) === spec
    end

    @testset "unknown or unsupported solver variants are rejected loudly" begin
        invalid = (
            coupled_spec(bits_per_symbol = 1),
            coupled_spec(ofdm_symbols_per_solve = 2),
            coupled_spec(ici_half_width = 0),
            coupled_spec(ici_half_width = 2),
            coupled_spec(response_parameterization = :unknown),
            coupled_spec(combiner_parameterization = :unknown),
            coupled_spec(inner_pilot_policy = :soft_prior),
            coupled_spec(filler_policy = :optimized),
            coupled_spec(dc_policy = :modeled),
            coupled_spec(inactive_neighbor_policy = :wrap),
            coupled_spec(normalization = :global),
            coupled_spec(bp_projection = true),
        )

        for candidate in invalid
            @test_throws ArgumentError CoupledSpecJuna._validate_coupled_solver_spec(candidate)
        end
    end

    @testset "the ideal equation supports independent per-carrier C and W" begin
        ideal_spec = coupled_spec(
            response_parameterization = :per_carrier,
            combiner_parameterization = :per_carrier,
        )
        @test CoupledSpecJuna._validate_coupled_solver_spec(ideal_spec) === ideal_spec
        problem = miniature_coupled_problem(spec = ideal_spec)
        state = CoupledSpecJuna._CoupledState(problem)
        gradient = CoupledSpecJuna._CoupledGradient(problem)

        @test size(state.W) == (2, length(problem.active))
        @test size(state.C) == (2, 3, length(problem.active), 1)
        @test size(gradient.W) == size(state.W)
        @test size(gradient.C) == size(state.C)
        @test CoupledSpecJuna._coupled_response_group(problem, 2) == 1
        @test CoupledSpecJuna._coupled_response_group(problem, 8) == 6
        @test CoupledSpecJuna._coupled_combiner_group(problem, 2) == 1
        @test CoupledSpecJuna._coupled_combiner_group(problem, 8) == 6

        state.z .= [0.7, -0.9, -0.4, 0.6, 0.8, -0.5]
        state.W .= reshape(ComplexF64.(1:12) ./ 20, 2, 6)
        for index in CartesianIndices(state.C)
            branch, offset, carrier, _ = Tuple(index)
            state.C[index] = ComplexF64(0.03 * (branch + offset + carrier),
                                        0.02 * (branch - offset + carrier))
        end
        for k in problem.active, branch in axes(problem.observations, 1)
            problem.observations[branch, k] = ComplexF64(
                0.09 * (2branch + k), 0.04 * (branch - 2k),
            )
        end
        weights = CoupledSpecJuna._CoupledWeights(
            observation = 0.8,
            pilot = 1.1,
            tie = 0.9,
            response_regularization = 0.2,
            combiner_regularization = 0.3,
            smoothness = 0.4,
            parity = 0.7,
        )
        terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state; weights = weights,
        )

        @test isfinite(terms.total)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), gradient.C)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), gradient.W)
        @test all(isfinite, gradient.z)

        delta = 1e-6
        index = CartesianIndex(1, 2, 4, 1)
        original = state.C[index]
        state.C[index] = original + delta
        plus = CoupledSpecJuna._coupled_objective(problem, state; weights = weights).total
        state.C[index] = original - delta
        minus = CoupledSpecJuna._coupled_objective(problem, state; weights = weights).total
        state.C[index] = original
        @test (plus - minus) / (2delta) ≈ 2real(gradient.C[index]) rtol=3e-5 atol=5e-8

        windex = CartesianIndex(2, 5)
        woriginal = state.W[windex]
        state.W[windex] = woriginal + delta * im
        plus = CoupledSpecJuna._coupled_objective(problem, state; weights = weights).total
        state.W[windex] = woriginal - delta * im
        minus = CoupledSpecJuna._coupled_objective(problem, state; weights = weights).total
        state.W[windex] = woriginal
        @test (plus - minus) / (2delta) ≈ 2imag(gradient.W[windex]) rtol=3e-5 atol=5e-8
    end

    @testset "miniature problem classifies data, pilots, fillers, and clamps" begin
        problem = miniature_coupled_problem()

        @test problem isa CoupledSpecJuna._CoupledProblem
        @test size(problem.observations) == (2, 9)
        @test problem.active == [2, 3, 4, 6, 7, 8]
        @test problem.dc_index == 5
        @test problem.pilot_idx == [2, 6]
        @test problem.data_idx == [3, 4, 7, 8]
        @test problem.filler_idx == [8]
        @test problem.symbol_slots == [0, 0, 1, 2, 0, 0, 3, 0, 0]
        @test problem.fixed_symbols[[2, 6, 8]] == ComplexF64[1, -1, 1]
        @test all(iszero, problem.fixed_symbols[[1, 3, 4, 5, 7, 9]])
        @test findall(problem.inner_pilot_mask) == [2, 5]
        @test problem.inner_pilot_bits[[2, 5]] == Bool[true, false]
        @test problem.parity_sets == [[1, 2, 3], [4, 5, 6]]
    end

    @testset "K=1 neighborhoods truncate inactive, DC, and edge carriers" begin
        problem = miniature_coupled_problem()

        @test size(problem.neighbor_idx) == (3, 9)
        @test problem.neighbor_idx[:, 2] == [0, 2, 3]  # carrier 1 inactive
        @test problem.neighbor_idx[:, 3] == [2, 3, 4]
        @test problem.neighbor_idx[:, 4] == [3, 4, 0]  # carrier 5 is DC
        @test problem.neighbor_idx[:, 6] == [0, 6, 7]  # carrier 5 is DC
        @test problem.neighbor_idx[:, 8] == [7, 8, 0]  # carrier 9 inactive
        @test all(iszero, problem.neighbor_idx[:, problem.dc_index])
        @test !(problem.dc_index in problem.neighbor_idx)
        @test all(q -> q == 0 || q in problem.active, problem.neighbor_idx)
    end

    @testset "band-tied state dimensions share C and W across carriers" begin
        problem = miniature_coupled_problem()
        state = CoupledSpecJuna._CoupledState(problem)

        @test problem.bands == [[2, 3, 4], [6, 7, 8]]
        @test problem.band_ids[[2, 3, 4]] == fill(1, 3)
        @test problem.band_ids[[6, 7, 8]] == fill(2, 3)
        @test all(iszero, problem.band_ids[[1, 5, 9]])
        @test size(state.W) == (2, 2)
        @test size(state.C) == (2, 3, 2, 1)
        @test size(state.z) == (6,)
        @test all(iszero, state.W)
        @test all(iszero, state.C)
        @test all(iszero, state.z)

        @test_throws DimensionMismatch CoupledSpecJuna._CoupledState(
            problem; W = zeros(ComplexF64, 2, 3),
        )
        @test_throws DimensionMismatch CoupledSpecJuna._CoupledState(
            problem; C = zeros(ComplexF64, 2, 3, 2, 2),
        )
        @test_throws DimensionMismatch CoupledSpecJuna._CoupledState(
            problem; z = zeros(7),
        )
    end

    @testset "term record and scratch buffers have explicit stable shapes" begin
        problem = miniature_coupled_problem()
        terms = CoupledSpecJuna._CoupledTerms(
            observation = 1,
            pilot = 2,
            tie = 3,
            response_regularization = 4,
            combiner_regularization = 5,
            smoothness = 6,
            parity = 7,
        )
        scratch = CoupledSpecJuna._CoupledScratch(problem)

        @test fieldtypes(typeof(terms)) == ntuple(_ -> Float64, 8)
        @test terms.total == 28.0
        @test size(scratch.symbols) == (9,)
        @test size(scratch.predicted_observations) == (2, 9)
        @test size(scratch.combined_symbols) == (9,)
        @test size(scratch.relaxed_bits) == (6,)
        @test size(scratch.parity_prefix) == (3,)
        @test size(scratch.parity_clamped) == (3,)
        @test all(iszero, scratch.symbols)
        @test all(iszero, scratch.predicted_observations)
    end

    @testset "malformed miniature problems fail at construction" begin
        @test_throws ArgumentError miniature_coupled_problem(
            active = [2, 3, 4, 5, 6, 7, 8],
        )
        @test_throws ArgumentError miniature_coupled_problem(
            data_idx = [3, 4, 6, 7, 8],
        )
        @test_throws ArgumentError miniature_coupled_problem(
            bands = [[2, 3, 4], [6, 7]],
        )
        @test_throws DimensionMismatch miniature_coupled_problem(nbits = 9)
        @test_throws DimensionMismatch miniature_coupled_problem(
            inner_pilot_bits = Bool[true],
        )
        @test_throws ArgumentError miniature_coupled_problem(
            parity_sets = [[1, 2, 7]],
        )
    end

    @testset "observation term matches a hand-built K=1 forward model" begin
        problem = miniature_coupled_problem()
        state = CoupledSpecJuna._CoupledState(problem)
        scratch = CoupledSpecJuna._CoupledScratch(problem)
        invsqrt2 = 1 / sqrt(2)
        expected_symbols = zeros(ComplexF64, 9)
        expected_symbols[[2, 3, 4, 6, 7, 8]] .= ComplexF64[
            1,
            -im * invsqrt2,
            0,
            -1,
            invsqrt2,
            1,
        ]

        for band_id in 1:2
            state.C[:, 2, band_id, 1] .= ComplexF64[2, -1]
        end
        state.C[1, 1, 2, 1] = 0.5im
        fill!(problem.observations, 0)
        for k in problem.active
            problem.observations[:, k] .=
                state.C[:, 2, problem.band_ids[k], 1] .* expected_symbols[k]
        end
        problem.observations[1, 7] += -0.5im
        problem.observations[1, 8] += 0.5im * invsqrt2

        exact = CoupledSpecJuna._coupled_objective(
            problem,
            state;
            weights = CoupledSpecJuna._CoupledWeights(observation = 1),
            scratch = scratch,
        )
        @test exact.observation ≈ 0.0 atol = 1e-14
        @test exact.total ≈ 0.0 atol = 1e-14
        @test scratch.symbols ≈ expected_symbols atol = 1e-14

        problem.observations[1, 3] += 2
        perturbed = CoupledSpecJuna._coupled_objective(
            problem,
            state;
            weights = CoupledSpecJuna._CoupledWeights(observation = 3),
            scratch = scratch,
        )
        @test perturbed.observation ≈ 3 * 4 / (2 * 6) atol = 1e-14
        @test perturbed.total == perturbed.observation
    end

    @testset "pilot and symbol-tie terms match independent residuals" begin
        problem = miniature_coupled_problem()
        state = CoupledSpecJuna._CoupledState(problem)
        scratch = CoupledSpecJuna._CoupledScratch(problem)
        invsqrt2 = 1 / sqrt(2)
        state.W .= ComplexF64[1 0; 0 1]
        fill!(problem.observations, 0)

        problem.observations[:, 2] .= ComplexF64[3, 9]
        problem.observations[:, 6] .= ComplexF64[9, -3]
        problem.observations[:, 3] .= ComplexF64[-im * invsqrt2, 0]
        problem.observations[:, 4] .= ComplexF64[3, 0]
        problem.observations[:, 7] .= ComplexF64[0, invsqrt2]
        problem.observations[:, 8] .= ComplexF64[100, 100 + 100im]

        terms = CoupledSpecJuna._coupled_objective(
            problem,
            state;
            weights = CoupledSpecJuna._CoupledWeights(pilot = 0.5, tie = 2),
            scratch = scratch,
        )
        @test terms.pilot ≈ 0.5 * (4 + 4) / 2 atol = 1e-14
        @test terms.tie ≈ 2 * (0 + 9 + 0) / 3 atol = 1e-14
        @test terms.total ≈ 8.0 atol = 1e-14
        @test scratch.combined_symbols[8] == 100 + 100im
    end

    @testset "C and W penalties use independently counted coefficients" begin
        problem = miniature_coupled_problem()
        state = CoupledSpecJuna._CoupledState(problem)
        state.C[1, 1, 1, 1] = 3 + 4im
        state.C[2, 3, 2, 1] = im
        state.W .= ComplexF64[1 + im 2; -im -2im]

        terms = CoupledSpecJuna._coupled_objective(
            problem,
            state;
            weights = CoupledSpecJuna._CoupledWeights(
                response_regularization = 3,
                combiner_regularization = 4,
                smoothness = 2,
            ),
        )
        @test terms.response_regularization ≈ 3 * 26 / 12 atol = 1e-14
        @test terms.combiner_regularization ≈ 4 * 11 / 4 atol = 1e-14
        @test terms.smoothness ≈ 2 * 3 / 2 atol = 1e-14
        @test terms.total ≈ 20.5 atol = 1e-14
    end

    @testset "parity uses hard inner-pilot bits and the total is additive" begin
        problem = miniature_coupled_problem()
        state = CoupledSpecJuna._CoupledState(problem)
        scratch = CoupledSpecJuna._CoupledScratch(problem)
        state.z .= 2 .* atanh.([0.5, 0.9, 0.25, -0.5, -0.9, 0.5])

        parity_only = CoupledSpecJuna._coupled_objective(
            problem,
            state;
            weights = CoupledSpecJuna._CoupledWeights(parity = 4),
            scratch = scratch,
        )
        expected_bits = [0.5, -1.0, 0.25, -0.5, 1.0, 0.5]
        expected_parity = 4 * ((1 - prod(expected_bits[1:3]))^2 +
                               (1 - prod(expected_bits[4:6]))^2) / 2
        @test scratch.relaxed_bits ≈ expected_bits atol = 1e-14
        @test parity_only.parity ≈ expected_parity atol = 1e-14
        @test parity_only.total == parity_only.parity

        state.z[[2, 5]] .= [20, -20]
        reclamped = CoupledSpecJuna._coupled_objective(
            problem,
            state;
            weights = CoupledSpecJuna._CoupledWeights(parity = 4),
            scratch = scratch,
        )
        @test reclamped.parity ≈ expected_parity atol = 1e-14

        all_terms = CoupledSpecJuna._coupled_objective(problem, state; scratch = scratch)
        @test all(isfinite, (
            all_terms.observation,
            all_terms.pilot,
            all_terms.tie,
            all_terms.response_regularization,
            all_terms.combiner_regularization,
            all_terms.smoothness,
            all_terms.parity,
            all_terms.total,
        ))
        @test all_terms.total ≈ sum((
            all_terms.observation,
            all_terms.pilot,
            all_terms.tie,
            all_terms.response_regularization,
            all_terms.combiner_regularization,
            all_terms.smoothness,
            all_terms.parity,
        )) atol = 1e-14
    end

    @testset "outer pilots are intentionally double-anchored" begin
        problem = miniature_coupled_problem()
        state = CoupledSpecJuna._CoupledState(problem)
        fill!(problem.observations, 0)
        problem.observations[1, 2] = 2

        terms = CoupledSpecJuna._coupled_objective(
            problem,
            state;
            weights = CoupledSpecJuna._CoupledWeights(observation = 1, pilot = 1),
        )
        @test terms.observation ≈ 4 / (2 * 6) atol = 1e-14
        @test terms.pilot ≈ 1.0 atol = 1e-14
        @test terms.total ≈ 4 / 12 + 1 atol = 1e-14
        @test_throws ArgumentError CoupledSpecJuna._CoupledWeights(observation = -1)
        @test_throws ArgumentError CoupledSpecJuna._CoupledWeights(parity = NaN)
    end

    @testset "band-tied C makes ICI and z jointly discriminative" begin
        problem = informative_coupled_problem()
        true_bits = [
            0.80, -0.55, -0.70, 0.45, 0.60, 0.75, -0.50, -0.80,
            0.65, -0.40, -0.75, 0.55, 0.45, 0.70, -0.85, -0.50,
        ]
        true_z = 2 .* atanh.(true_bits)
        wrong_bits = copy(true_bits)
        wrong_bits[[5, 12]] .*= -1
        wrong_z = 2 .* atanh.(wrong_bits)
        generating_C = zeros(ComplexF64, 2, 3, 2, 1)
        generating_C[:, :, 1, 1] .= ComplexF64[
            0.35 + 0.10im  1.00             -0.20 + 0.15im
           -0.10 + 0.25im  0.30 + 0.80im    0.20 - 0.10im
        ]
        generating_C[:, :, 2, 1] .= ComplexF64[
           -0.25 + 0.20im  0.75 - 0.15im    0.30 + 0.10im
            0.15 - 0.20im -0.20 + 0.90im   -0.10 + 0.25im
        ]
        independent_coupled_observations!(problem, generating_C, true_z)

        weights = CoupledSpecJuna._CoupledWeights(
            observation = 1,
            response_regularization = 0.02,
        )
        true_C = independently_profile_C(
            problem,
            true_z;
            observation_weight = weights.observation,
            response_weight = weights.response_regularization,
        )
        diagonal_C = independently_profile_C(
            problem,
            true_z;
            observation_weight = weights.observation,
            response_weight = weights.response_regularization,
            offset_positions = [2],
        )
        wrong_C = independently_profile_C(
            problem,
            wrong_z;
            observation_weight = weights.observation,
            response_weight = weights.response_regularization,
        )
        true_terms = CoupledSpecJuna._coupled_objective(
            problem,
            CoupledSpecJuna._CoupledState(problem; C = true_C, z = true_z);
            weights = weights,
        )
        diagonal_terms = CoupledSpecJuna._coupled_objective(
            problem,
            CoupledSpecJuna._CoupledState(problem; C = diagonal_C, z = true_z);
            weights = weights,
        )
        wrong_terms = CoupledSpecJuna._coupled_objective(
            problem,
            CoupledSpecJuna._CoupledState(problem; C = wrong_C, z = wrong_z);
            weights = weights,
        )

        @test length(problem.bands[1]) > size(problem.neighbor_idx, 1)
        @test sum(abs2, true_C[:, [1, 3], :, :]) > 0.01
        @test true_terms.total < diagonal_terms.total
        @test true_terms.total < wrong_terms.total
        @test wrong_terms.observation > true_terms.observation
        @test all(isfinite, (true_terms.total, diagonal_terms.total, wrong_terms.total))
    end

    @testset "fixed physics weight overrules a misleading W-z tie" begin
        problem = informative_coupled_problem()
        true_bits = [
            0.80, -0.55, -0.70, 0.45, 0.60, 0.75, -0.50, -0.80,
            0.65, -0.40, -0.75, 0.55, 0.45, 0.70, -0.85, -0.50,
        ]
        true_z = 2 .* atanh.(true_bits)
        generating_C = zeros(ComplexF64, 2, 3, 2, 1)
        generating_C[:, :, 1, 1] .= ComplexF64[
            0.35 + 0.10im  1.00             -0.20 + 0.15im
           -0.10 + 0.25im  0.30 + 0.80im    0.20 - 0.10im
        ]
        generating_C[:, :, 2, 1] .= ComplexF64[
           -0.25 + 0.20im  0.75 - 0.15im    0.30 + 0.10im
            0.15 - 0.20im -0.20 + 0.90im   -0.10 + 0.25im
        ]
        independent_coupled_observations!(problem, generating_C, true_z)

        phase = cis(pi / 5)
        raw_combined = ComplexF64[
            conj(phase) * problem.observations[1, k] for k in problem.data_idx
        ]
        max_axis = sqrt(2) * maximum(
            max(abs(real(value)), abs(imag(value))) for value in raw_combined
        )
        combiner_scale = 0.80 / max_axis
        misleading_W = zeros(ComplexF64, 2, 2)
        misleading_W[1, :] .= combiner_scale * phase
        wrong_bits = zeros(Float64, problem.nbits)
        for k in problem.data_idx
            slot = problem.symbol_slots[k]
            combined = conj(misleading_W[1, problem.band_ids[k]]) *
                       problem.observations[1, k]
            wrong_bits[2slot - 1] = sqrt(2) * real(combined)
            wrong_bits[2slot] = sqrt(2) * imag(combined)
        end
        wrong_z = 2 .* atanh.(wrong_bits)

        physics_weights = CoupledSpecJuna._CoupledWeights(
            observation = 1,
            response_regularization = 0.02,
        )
        true_C = independently_profile_C(
            problem,
            true_z;
            observation_weight = physics_weights.observation,
            response_weight = physics_weights.response_regularization,
        )
        wrong_C = independently_profile_C(
            problem,
            wrong_z;
            observation_weight = physics_weights.observation,
            response_weight = physics_weights.response_regularization,
        )
        true_state = CoupledSpecJuna._CoupledState(
            problem; C = true_C, W = misleading_W, z = true_z,
        )
        wrong_state = CoupledSpecJuna._CoupledState(
            problem; C = wrong_C, W = misleading_W, z = wrong_z,
        )

        true_physics = CoupledSpecJuna._coupled_objective(
            problem, true_state; weights = physics_weights,
        )
        wrong_physics = CoupledSpecJuna._coupled_objective(
            problem, wrong_state; weights = physics_weights,
        )
        tie_weights = CoupledSpecJuna._CoupledWeights(tie = 1)
        true_tie = CoupledSpecJuna._coupled_objective(
            problem, true_state; weights = tie_weights,
        )
        wrong_tie = CoupledSpecJuna._coupled_objective(
            problem, wrong_state; weights = tie_weights,
        )

        combined_weights = CoupledSpecJuna._CoupledWeights(
            observation = 1,
            response_regularization = 0.02,
            tie = 0.1,
        )
        true_combined = CoupledSpecJuna._coupled_objective(
            problem, true_state; weights = combined_weights,
        )
        wrong_combined = CoupledSpecJuna._coupled_objective(
            problem, wrong_state; weights = combined_weights,
        )
        true_runtime = CoupledSpecJuna._coupled_objective(
            problem, true_state; weights = CoupledSpecJuna._COUPLED_RUNTIME_WEIGHTS,
        )
        wrong_runtime = CoupledSpecJuna._coupled_objective(
            problem, wrong_state; weights = CoupledSpecJuna._COUPLED_RUNTIME_WEIGHTS,
        )
        @test maximum(abs, wrong_bits) <= 0.80 + eps()
        @test any(sign.(wrong_bits) .!= sign.(true_bits))
        @test wrong_tie.tie ≈ 0.0 atol = 1e-20
        @test wrong_tie.tie < true_tie.tie
        @test true_physics.total < wrong_physics.total
        # A literal policy weight prevents the fixture from deriving its own pass condition.
        @test true_combined.total < wrong_combined.total
        @test CoupledSpecJuna._COUPLED_RUNTIME_WEIGHTS.observation == 1.0
        @test CoupledSpecJuna._COUPLED_RUNTIME_WEIGHTS.tie == 0.1
        @test true_runtime.total < wrong_runtime.total
        @test isfinite(true_combined.total)
        @test isfinite(wrong_combined.total)
        @test isfinite(true_runtime.total)
        @test isfinite(wrong_runtime.total)
    end

    @testset "independently profiled C satisfies analytic stationarity" begin
        problem = informative_coupled_problem()
        z = [
            0.80, -0.55, -0.70, 0.45, 0.60, 0.75, -0.50, -0.80,
            0.65, -0.40, -0.75, 0.55, 0.45, 0.70, -0.85, -0.50,
        ]
        generating_C = reshape(
            ComplexF64[
                0.35 + 0.10im, -0.10 + 0.25im,
                1.00 + 0.00im, 0.30 + 0.80im,
                -0.20 + 0.15im, 0.20 - 0.10im,
                -0.25 + 0.20im, 0.15 - 0.20im,
                0.75 - 0.15im, -0.20 + 0.90im,
                0.30 + 0.10im, -0.10 + 0.25im,
            ],
            2, 3, 2, 1,
        )
        independent_coupled_observations!(problem, generating_C, z)
        weights = CoupledSpecJuna._CoupledWeights(
            observation = 0.8,
            response_regularization = 0.2,
        )
        profiled_C = independently_profile_C(
            problem,
            z;
            observation_weight = weights.observation,
            response_weight = weights.response_regularization,
        )
        state = CoupledSpecJuna._CoupledState(problem; C = profiled_C, z = z)
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state; weights = weights,
        )

        @test isfinite(terms.total)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), profiled_C)
        @test maximum(abs, gradient.C) < 2e-14
    end

    @testset "soft parity has valid minima and a restoring invalid-bit gradient" begin
        problem = miniature_coupled_problem(
            inner_pilot_idx = Int[],
            inner_pilot_bits = Bool[],
            parity_sets = [[1, 2, 3]],
        )
        weights = CoupledSpecJuna._CoupledWeights(parity = 1)
        valid_z = 10.0 .* [1, -1, -1, 1, 1, 1]
        invalid_z = copy(valid_z)
        invalid_z[1] *= -1
        valid_state = CoupledSpecJuna._CoupledState(problem; z = valid_z)
        invalid_state = CoupledSpecJuna._CoupledState(problem; z = invalid_z)
        valid_gradient = CoupledSpecJuna._CoupledGradient(problem)
        invalid_gradient = CoupledSpecJuna._CoupledGradient(problem)
        valid_terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            valid_gradient, problem, valid_state; weights = weights,
        )
        invalid_terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            invalid_gradient, problem, invalid_state; weights = weights,
        )
        correction = valid_z[1] - invalid_z[1]

        @test valid_terms.parity < 1e-6
        @test maximum(abs, valid_gradient.z) < 1e-6
        @test invalid_terms.parity > 3.9
        @test invalid_terms.parity > 1e6 * valid_terms.parity
        @test correction * invalid_gradient.z[1] < 0
    end

    @testset "degenerate odd-bit geometry stays finite without pilots or parity" begin
        problem = CoupledSpecJuna._CoupledProblem(
            reshape(ComplexF64[0, 1 + 0.2im, -0.4 + 0.7im, 0.3 - 0.8im], 1, 4);
            active = [2, 3, 4],
            dc_index = 1,
            pilot_idx = Int[],
            pilot_syms = ComplexF64[],
            data_idx = [2, 3, 4],
            bands = [[2, 3, 4]],
            nbits = 5,
            parity_sets = Vector{Vector{Int}}(),
        )
        state = CoupledSpecJuna._CoupledState(problem)
        state.W[1, 1] = 0.8 + 0.1im
        state.C[1, :, 1, 1] .= ComplexF64[0.2 + 0.1im, 0.9 - 0.2im, -0.1 + 0.3im]
        state.z .= [0.4, -0.7, 0.8, -0.3, 0.5]
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state,
        )

        @test isempty(problem.pilot_idx)
        @test isempty(problem.parity_sets)
        @test terms.pilot == 0.0
        @test terms.parity == 0.0
        @test terms.smoothness == 0.0
        @test all(isfinite, (
            terms.observation,
            terms.pilot,
            terms.tie,
            terms.response_regularization,
            terms.combiner_regularization,
            terms.smoothness,
            terms.parity,
            terms.total,
        ))
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), gradient.W)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), gradient.C)
        @test all(isfinite, gradient.z)
        @test gradient.z[end] != 0.0
    end

    gradient_fixture = function ()
        problem = miniature_coupled_problem()
        for k in problem.active, branch in axes(problem.observations, 1)
            problem.observations[branch, k] =
                ComplexF64(0.09 * (2branch + k), 0.04 * (branch - 2k))
        end

        state = CoupledSpecJuna._CoupledState(problem)
        state.W .= ComplexF64[
             0.60 + 0.20im  -0.35 + 0.40im
            -0.20 + 0.10im   0.50 - 0.30im
        ]
        for index in CartesianIndices(state.C)
            branch, offset_pos, band_id, _ = Tuple(index)
            state.C[index] = ComplexF64(
                0.08 * (branch + 2offset_pos - band_id),
                0.05 * (2branch - offset_pos + band_id),
            )
        end
        state.z .= [0.70, -0.90, -0.40, 0.60, 0.80, -0.50]
        problem, state
    end

    centered_coupled_fd = function (problem, state, weights, field, index;
                                    component = :real, delta = 1e-6,
                                    expected_variance = false)
        values = getfield(state, field)
        original = values[index]
        step = field === :z ? delta : component === :real ? delta : delta * im
        try
            values[index] = original + step
            plus = CoupledSpecJuna._coupled_objective(
                problem, state; weights = weights,
                expected_variance = expected_variance,
            ).total
            values[index] = original - step
            minus = CoupledSpecJuna._coupled_objective(
                problem, state; weights = weights,
                expected_variance = expected_variance,
            ).total
            (plus - minus) / (2delta)
        finally
            values[index] = original
        end
    end

    @testset "gradient buffers are typed, reusable, and clamp-safe" begin
        problem, state = gradient_fixture()
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        scratch = CoupledSpecJuna._CoupledScratch(problem)
        weights = CoupledSpecJuna._CoupledWeights(
            observation = 0.8,
            pilot = 1.1,
            tie = 0.9,
            response_regularization = 0.2,
            combiner_regularization = 0.3,
            smoothness = 0.4,
            parity = 0.7,
        )

        @test fieldtypes(typeof(gradient)) == (
            Matrix{ComplexF64}, Array{ComplexF64,4}, Vector{Float64},
        )
        @test size(gradient.W) == size(state.W)
        @test size(gradient.C) == size(state.C)
        @test size(gradient.z) == size(state.z)
        @test size(scratch.symbol_gradient) == size(scratch.symbols)
        @test size(scratch.bit_gradient) == size(scratch.relaxed_bits)

        fill!(gradient.W, ComplexF64(NaN, NaN))
        fill!(gradient.C, ComplexF64(NaN, NaN))
        fill!(gradient.z, NaN)
        terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state; weights = weights, scratch = scratch,
        )
        @test terms isa CoupledSpecJuna._CoupledTerms
        @test all(isfinite, (terms.total, real(sum(gradient.W)), imag(sum(gradient.W)),
                             real(sum(gradient.C)), imag(sum(gradient.C)),
                             sum(gradient.z)))
        @test gradient.z[[2, 5]] == [0.0, 0.0]
        @test centered_coupled_fd(problem, state, weights, :z, 2) == 0.0
        @test centered_coupled_fd(problem, state, weights, :z, 5) == 0.0

        malformed = CoupledSpecJuna._CoupledGradient(
            zeros(ComplexF64, 1, 1), copy(gradient.C), copy(gradient.z),
        )
        @test_throws DimensionMismatch CoupledSpecJuna._coupled_objective_and_gradient!(
            malformed, problem, state; weights = weights, scratch = scratch,
        )
    end

    @testset "each analytic objective family matches centered finite differences" begin
        problem, state = gradient_fixture()
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        cases = (
            ("observation C real", :C, CartesianIndex(1, 1, 1, 1), :real,
             CoupledSpecJuna._CoupledWeights(observation = 0.8)),
            ("observation C imaginary", :C, CartesianIndex(2, 3, 2, 1), :imag,
             CoupledSpecJuna._CoupledWeights(observation = 0.8)),
            ("observation z", :z, 3, :real,
             CoupledSpecJuna._CoupledWeights(observation = 0.8)),
            ("outer-pilot W", :W, CartesianIndex(1, 1), :imag,
             CoupledSpecJuna._CoupledWeights(pilot = 1.1)),
            ("symbol-tie W", :W, CartesianIndex(2, 2), :real,
             CoupledSpecJuna._CoupledWeights(tie = 0.9)),
            ("symbol-tie z", :z, 4, :real,
             CoupledSpecJuna._CoupledWeights(tie = 0.9)),
            ("C regularization", :C, CartesianIndex(1, 2, 2, 1), :imag,
             CoupledSpecJuna._CoupledWeights(response_regularization = 0.2)),
            ("W regularization", :W, CartesianIndex(1, 2), :real,
             CoupledSpecJuna._CoupledWeights(combiner_regularization = 0.3)),
            ("W smoothness", :W, CartesianIndex(2, 1), :imag,
             CoupledSpecJuna._CoupledWeights(smoothness = 0.4)),
            ("soft parity", :z, 6, :real,
             CoupledSpecJuna._CoupledWeights(parity = 0.7)),
        )

        for (label, field, index, component, weights) in cases
            @testset "$label" begin
                CoupledSpecJuna._coupled_objective_and_gradient!(
                    gradient, problem, state; weights = weights,
                )
                value = getfield(gradient, field)[index]
                analytic = if field === :z
                    value
                elseif component === :real
                    2real(value)
                else
                    2imag(value)
                end
                finite_difference = centered_coupled_fd(
                    problem, state, weights, field, index; component = component,
                )
                @test finite_difference ≈ analytic rtol = 3e-5 atol = 5e-8
            end
        end
    end

    @testset "the complete C W z gradient matches centered finite differences" begin
        problem, state = gradient_fixture()
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        weights = CoupledSpecJuna._CoupledWeights(
            observation = 0.8,
            pilot = 1.1,
            tie = 0.9,
            response_regularization = 0.2,
            combiner_regularization = 0.3,
            smoothness = 0.4,
            parity = 0.7,
        )
        terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state; weights = weights,
        )

        @test isfinite(terms.total)
        for index in (CartesianIndex(1, 2, 1, 1), CartesianIndex(2, 3, 2, 1))
            for component in (:real, :imag)
                finite_difference = centered_coupled_fd(
                    problem, state, weights, :C, index; component = component,
                )
                analytic = component === :real ? 2real(gradient.C[index]) :
                           2imag(gradient.C[index])
                @test finite_difference ≈ analytic rtol = 3e-5 atol = 5e-8
            end
        end
        for index in (CartesianIndex(1, 1), CartesianIndex(2, 2))
            for component in (:real, :imag)
                finite_difference = centered_coupled_fd(
                    problem, state, weights, :W, index; component = component,
                )
                analytic = component === :real ? 2real(gradient.W[index]) :
                           2imag(gradient.W[index])
                @test finite_difference ≈ analytic rtol = 3e-5 atol = 5e-8
            end
        end
        for index in (1, 3, 4, 6)
            finite_difference = centered_coupled_fd(problem, state, weights, :z, index)
            @test finite_difference ≈ gradient.z[index] rtol = 3e-5 atol = 5e-8
        end
    end

    @testset "expected-variance (VP) objective gradient matches centered finite differences" begin
        problem, state = gradient_fixture()
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        weights = CoupledSpecJuna._CoupledWeights(observation = 0.8)
        terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state; weights = weights, expected_variance = true,
        )
        @test isfinite(terms.total)

        # The posterior-variance term must actually move both objective and gradient.
        mean_only = CoupledSpecJuna._CoupledGradient(problem)
        mean_terms = CoupledSpecJuna._coupled_objective_and_gradient!(
            mean_only, problem, state; weights = weights, expected_variance = false,
        )
        @test terms.total > mean_terms.total          # E|y-Cx|^2 >= |y-Cmu|^2
        @test gradient.z != mean_only.z

        # C-gradient (holding z fixed -> variances constant): 2Re/2Im vs centered FD.
        for index in (CartesianIndex(1, 2, 1, 1), CartesianIndex(2, 3, 2, 1))
            for component in (:real, :imag)
                fd = centered_coupled_fd(
                    problem, state, weights, :C, index;
                    component = component, expected_variance = true,
                )
                analytic = component === :real ? 2real(gradient.C[index]) :
                           2imag(gradient.C[index])
                @test fd ≈ analytic rtol = 3e-5 atol = 5e-8
            end
        end
        # z-gradient (variances depend on z through 1-|s(z)|^2): full total derivative.
        for index in (1, 3, 4, 6)
            fd = centered_coupled_fd(
                problem, state, weights, :z, index; expected_variance = true,
            )
            @test fd ≈ gradient.z[index] rtol = 3e-5 atol = 5e-8
        end
    end

    @testset "all 38 real gradient coordinates match centered finite differences" begin
        problem, state = gradient_fixture()
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        weights = CoupledSpecJuna._CoupledWeights(
            observation = 0.8,
            pilot = 1.1,
            tie = 0.9,
            response_regularization = 0.2,
            combiner_regularization = 0.3,
            smoothness = 0.4,
            parity = 0.7,
        )
        CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state; weights = weights,
        )

        checked = 0
        max_relative_error = 0.0
        for field in (:W, :C)
            values = getfield(gradient, field)
            for index in CartesianIndices(values), component in (:real, :imag)
                finite_difference = centered_coupled_fd(
                    problem, state, weights, field, index; component = component,
                )
                value = values[index]
                analytic = component === :real ? 2real(value) : 2imag(value)
                scale = max(abs(finite_difference), abs(analytic), 1e-8)
                max_relative_error = max(
                    max_relative_error,
                    abs(finite_difference - analytic) / scale,
                )
                @test finite_difference ≈ analytic rtol = 3e-5 atol = 5e-8
                checked += 1
            end
        end
        for index in eachindex(gradient.z)
            finite_difference = centered_coupled_fd(
                problem, state, weights, :z, index,
            )
            analytic = gradient.z[index]
            scale = max(abs(finite_difference), abs(analytic), 1e-8)
            max_relative_error = max(
                max_relative_error,
                abs(finite_difference - analytic) / scale,
            )
            @test finite_difference ≈ analytic rtol = 3e-5 atol = 5e-8
            checked += 1
        end

        @test checked == 38
        @test max_relative_error < 3e-5
        @info "Profiled C,z exhaustive finite differences" checked max_relative_error
    end

    @testset "joint C W z Taylor remainder converges quadratically" begin
        problem, state = gradient_fixture()
        gradient = CoupledSpecJuna._CoupledGradient(problem)
        weights = CoupledSpecJuna._CoupledWeights(
            observation = 0.8,
            pilot = 1.1,
            tie = 0.9,
            response_regularization = 0.2,
            combiner_regularization = 0.3,
            smoothness = 0.4,
            parity = 0.7,
        )
        base = CoupledSpecJuna._coupled_objective_and_gradient!(
            gradient, problem, state; weights = weights,
        ).total

        direction_W = similar(state.W)
        direction_C = similar(state.C)
        direction_z = similar(state.z)
        for (position, index) in enumerate(eachindex(direction_W))
            direction_W[index] = ComplexF64(sin(0.7position), cos(1.1position))
        end
        for (position, index) in enumerate(eachindex(direction_C))
            direction_C[index] = ComplexF64(cos(0.4position), sin(1.3position))
        end
        for index in eachindex(direction_z)
            direction_z[index] = sin(0.5index) + 0.2cos(1.7index)
        end
        direction_norm = sqrt(
            sum(abs2, direction_W) + sum(abs2, direction_C) + sum(abs2, direction_z),
        )
        direction_W ./= direction_norm
        direction_C ./= direction_norm
        direction_z ./= direction_norm
        directional_derivative = 2real(dot(gradient.W, direction_W)) +
                                 2real(dot(gradient.C, direction_C)) +
                                 dot(gradient.z, direction_z)

        epsilons = [1e-2, 5e-3, 2.5e-3]
        remainders = Float64[]
        normalized = Float64[]
        for epsilon in epsilons
            shifted = CoupledSpecJuna._CoupledState(
                state.W .+ epsilon .* direction_W,
                state.C .+ epsilon .* direction_C,
                state.z .+ epsilon .* direction_z,
            )
            shifted_loss = CoupledSpecJuna._coupled_objective(
                problem, shifted; weights = weights,
            ).total
            remainder = abs(shifted_loss - base - epsilon * directional_derivative)
            push!(remainders, remainder)
            push!(normalized, remainder / epsilon^2)
        end

        @test all(isfinite, remainders)
        @test all(>(0.0), remainders)
        @test 0.20 < remainders[2] / remainders[1] < 0.30
        @test 0.20 < remainders[3] / remainders[2] < 0.30
        @test maximum(normalized) / minimum(normalized) < 1.1
        @info "Profiled C,z Taylor remainder" epsilons normalized
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Profiled C,z checks passed")
end
