#!/usr/bin/env julia
#
# JUNA-full / W,z refinement - reduced-gradient objective and candidate selection.
#
# Paper claims protected (reference papers/gab/joe.tex):
#   ssec:gradient-juna         JUNA-Wz refines the combiner weights W and bit
#                              latents z through a reduced-gradient objective.
#   sec:solver                 The full receiver keeps the best decoded candidate
#                              produced by the gradient trajectory.
#
# If this fails: the full receiver may still pass a clean public loopback while
# its W,z objective, gradients, candidate construction, or best-candidate logic is
# broken.
#
# Run alone:  julia --project=. test/juna_full_refinement.jl
# Via runner: julia --project=. test/runtests.jl full

using Statistics
using Test
using JunaCore

const FullRefineJuna = JunaCore.Juna
const FullRefineModulations = JunaCore.Modulations
const FULL_REFINE_FS = 24_000.0

full_payload_pattern(n::Integer) =
    Bool[isodd(count_ones(19i + 4)) for i in 1:n]

full_pm(bit::Bool) = bit ? -1.0 : 1.0

function full_qpsk_symbol(codeword::AbstractVector{Bool}, carrier::Integer)
    j = 2 * (Int(carrier) - 1) + 1
    bI = codeword[j]
    bQ = j + 1 <= length(codeword) ? codeword[j + 1] : false
    ComplexF64(full_pm(bI), full_pm(bQ)) / sqrt(2)
end

function full_refinement_fixture(; initial_candidate_valid::Bool = false)
    m = FullRefineJuna.FullModulation(partial_fft_parts = 1)
    layout = FullRefineJuna._layout(m, FULL_REFINE_FS)
    code = FullRefineJuna._code(m)
    bits = full_payload_pattern(FullRefineModulations.bitspersymbol(m))
    message = FullRefineJuna._build_message(m, code, bits)
    codeword = FullRefineJuna._encode(code, message)
    equalized = zeros(ComplexF64, Int(m.fft_length))
    equalized[layout.pilot_idx] .= layout.pilot_syms
    ncarriers = FullRefineJuna._ndata_tones(m, code.n)
    for t in 1:ncarriers
        equalized[layout.data_idx[t]] = full_qpsk_symbol(codeword, t)
    end
    for t in ncarriers+1:length(layout.data_idx)
        equalized[layout.data_idx[t]] = one(ComplexF64)
    end
    yparts = zeros(ComplexF64, 1, Int(m.fft_length))
    yparts[1, :] .= equalized
    metrics = Float64[bit ? 6.0 : -6.0 for bit in codeword]
    initial_candidate = (
        posterior_metric = metrics,
        ldpc_valid = initial_candidate_valid,
        syndrome_weight = initial_candidate_valid ? 0 : 77,
        mean_absolute_posterior_metric = mean(abs, metrics),
        pilot_mse = initial_candidate_valid ? 0.0 : 0.3,
        tie_mse = initial_candidate_valid ? 0.0 : 0.7,
        selection_score = initial_candidate_valid ? -0.001 : 0.8,
    )
    (m = m, layout = layout, code = code, bits = bits, codeword = codeword,
     yparts = yparts, metrics = metrics,
     initial_candidate = initial_candidate)
end

function assert_full_candidate_contract(m, code, bits, codeword, candidate)
    @test keys(candidate) == (:posterior_metric, :ldpc_valid, :syndrome_weight,
                              :mean_absolute_posterior_metric, :pilot_mse,
                              :tie_mse, :selection_score)
    @test candidate.posterior_metric isa Vector{Float64}
    @test length(candidate.posterior_metric) == code.n
    @test all(isfinite, candidate.posterior_metric)
    @test all(isfinite, (candidate.mean_absolute_posterior_metric,
                         candidate.pilot_mse, candidate.tie_mse,
                         candidate.selection_score))
    @test candidate.ldpc_valid
    @test candidate.syndrome_weight == 0
    @test (candidate.posterior_metric .> 0) == codeword
    @test FullRefineJuna._payload_from_metrics(
        m, code, candidate.posterior_metric) == bits
end

function full_gradient_state(f)
    W = FullRefineJuna._initial_pilot_W(f.m, f.yparts, f.layout)
    z = -copy(f.metrics)
    W0 = copy(W)
    z0 = copy(z)
    confidence = FullRefineJuna._posterior_confidence(f.m, z0)
    gW = similar(W)
    gz = zeros(Float64, length(z))
    scratch = FullRefineJuna._WzGradientScratch(f.m, f.code)
    (W = W, z = z, W0 = W0, z0 = z0, confidence = confidence,
     gW = gW, gz = gz, scratch = scratch)
end

function full_wz_loss_value(f, s, W, z)
    gW = similar(W)
    gz = zeros(Float64, length(z))
    scratch = FullRefineJuna._WzGradientScratch(f.m, f.code)
    FullRefineJuna._wz_loss_and_gradient!(
        f.m, f.code, f.layout, gW, gz, W, z, s.W0, s.z0, f.yparts,
        s.confidence, f.code.check_vars, scratch)
end

function full_centered_w_fd(f, s, W, z, idx, delta; component::Symbol)
    Wp = copy(W)
    Wm = copy(W)
    step = component === :real ? delta : im * delta
    Wp[idx] += step
    Wm[idx] -= step
    (full_wz_loss_value(f, s, Wp, z) - full_wz_loss_value(f, s, Wm, z)) / (2 * delta)
end

function full_centered_z_fd(f, s, W, z, idx, delta)
    zp = copy(z)
    zm = copy(z)
    zp[idx] += delta
    zm[idx] -= delta
    (full_wz_loss_value(f, s, W, zp) - full_wz_loss_value(f, s, W, zm)) / (2 * delta)
end

@testset verbose = true "W,z loss and gradients" begin
    @testset "_wz_symbol_grid! maps z to QPSK latents and rejects BPSK" begin
        m = FullRefineJuna.FullModulation()
        z = [2.0, -2.0, 0.0, 4.0, -6.0]
        symbols = Vector{ComplexF64}(undef,
            FullRefineJuna._ndata_tones(m, length(z)))
        relaxed_bits = zeros(Float64, length(z))
        returned = FullRefineJuna._wz_symbol_grid!(m, symbols, relaxed_bits, z)
        invsqrt2 = 1 / sqrt(2)

        @test returned === symbols
        @test relaxed_bits ≈
              [tanh(1.0), -tanh(1.0), 0.0, tanh(2.0), -tanh(3.0)] atol=1e-15
        @test symbols ≈ ComplexF64[
            tanh(1.0) - im * tanh(1.0),
            0.0 + im * tanh(2.0),
            -tanh(3.0) + 0.0im,
        ] .* invsqrt2 atol=1e-15

        bpsk = FullRefineJuna.FullModulation(
            bits_per_data_carrier = 1, ldpc_k = 170, ldpc_n = 680)
        @test_throws ArgumentError FullRefineJuna._wz_symbol_grid!(
            bpsk, Vector{ComplexF64}(undef, 3), zeros(Float64, 3), zeros(Float64, 3))
    end

    @testset "_parity_penalty_and_bit_gradient! has finite directional gradient" begin
        bit_gradient = zeros(Float64, 3)
        relaxed_bits = [1.0, -1.0, 1.0]
        parity_sets = [[1, 2]]
        prefix = zeros(Float64, 2)
        clamped = zeros(Float64, 2)
        lambda = 0.25

        function expected_pair_penalty_and_grad(x1, x2)
            c1 = clamp(x1, -0.999, 0.999)
            c2 = clamp(x2, -0.999, 0.999)
            residual = 1.0 - c1 * c2
            scale = -2.0 * lambda * residual
            lambda * residual^2, [scale * c2, scale * c1, 0.0]
        end

        penalty = FullRefineJuna._parity_penalty_and_bit_gradient!(
            bit_gradient, relaxed_bits, parity_sets, lambda, prefix, clamped)

        expected_penalty, expected_grad = expected_pair_penalty_and_grad(1.0, -1.0)
        @test penalty ≈ expected_penalty atol=1e-15
        @test bit_gradient ≈ expected_grad atol=1e-15
        @test penalty < 4 * lambda

        fill!(bit_gradient, 0.0)
        nearly_satisfied = FullRefineJuna._parity_penalty_and_bit_gradient!(
            bit_gradient, [1.0, 1.0, -1.0], parity_sets, lambda, prefix, clamped)
        expected_tiny_penalty, expected_tiny_grad = expected_pair_penalty_and_grad(1.0, 1.0)
        @test nearly_satisfied ≈ expected_tiny_penalty atol=1e-15
        @test bit_gradient ≈ expected_tiny_grad atol=1e-15
        @test nearly_satisfied < 1e-5
        @test maximum(abs, bit_gradient) < 1e-2
    end

    @testset "_wz_loss_and_gradient! returns finite loss and gradients on a clean initial candidate" begin
        f = full_refinement_fixture()
        s = full_gradient_state(f)
        loss = FullRefineJuna._wz_loss_and_gradient!(
            f.m, f.code, f.layout, s.gW, s.gz, s.W, s.z, s.W0, s.z0, f.yparts,
            s.confidence, f.code.check_vars, s.scratch)

        @test size(s.W) == (Int(f.m.partial_fft_parts), length(f.layout.bands))
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), s.W)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)), s.gW)
        @test all(isfinite, s.gz)
        @test isfinite(loss)
        @test loss > 0.0
        @test sum(abs2, s.gW) > 0.0
        @test sum(abs2, s.gz) > 0.0
        @test length(s.scratch.symbols) ==
              FullRefineJuna._ndata_tones(f.m, f.code.n)
        @test all(x -> isfinite(real(x)) && isfinite(imag(x)),
                  s.scratch.symbols)
    end

    @testset "_wz_loss_and_gradient! matches finite differences away from the clean initial candidate" begin
        f = full_refinement_fixture()
        s = full_gradient_state(f)

        s.W[1, 3] += 0.13 - 0.07im
        s.W[1, 9] -= 0.05 + 0.11im
        s.z[1:10] .= [0.7, -0.9, 0.35, -0.2, 1.1, -0.4, 0.15, -0.65, 0.5, -1.2]

        loss = FullRefineJuna._wz_loss_and_gradient!(
            f.m, f.code, f.layout, s.gW, s.gz, s.W, s.z, s.W0, s.z0, f.yparts,
            s.confidence, f.code.check_vars, s.scratch)

        @test isfinite(loss)
        delta = 1e-6
        for idx in (CartesianIndex(1, 3), CartesianIndex(1, 9))
            fd_real = full_centered_w_fd(f, s, s.W, s.z, idx, delta; component=:real)
            fd_imag = full_centered_w_fd(f, s, s.W, s.z, idx, delta; component=:imag)
            @test fd_real ≈ 2 * real(s.gW[idx]) rtol=2e-5 atol=2e-8
            @test fd_imag ≈ 2 * imag(s.gW[idx]) rtol=2e-5 atol=2e-8
        end
        for idx in (1, 2, 5, 8)
            fd_z = full_centered_z_fd(f, s, s.W, s.z, idx, delta)
            @test fd_z ≈ s.gz[idx] rtol=2e-5 atol=2e-8
        end
    end

    @testset "_wz_state_candidate and _juna_wz_adam_refine return valid candidates" begin
        f = full_refinement_fixture()
        s = full_gradient_state(f)
        candidate = FullRefineJuna._wz_state_candidate(
            f.m, f.code, f.layout, f.yparts, s.W, s.z)
        solved = FullRefineJuna._juna_wz_adam_refine(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate)

        assert_full_candidate_contract(f.m, f.code, f.bits, f.codeword, candidate)
        assert_full_candidate_contract(f.m, f.code, f.bits, f.codeword, solved)
        @test FullRefineJuna._candidate_is_better(f.initial_candidate, solved)
        @test solved.selection_score < f.initial_candidate.selection_score
        @test solved.mean_absolute_posterior_metric >
              f.initial_candidate.mean_absolute_posterior_metric
    end

    @testset "_juna_wz_candidate keeps the best candidate and _juna_wz extracts payload" begin
        f = full_refinement_fixture()
        solved = FullRefineJuna._juna_wz_adam_refine(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate)
        selected = FullRefineJuna._juna_wz_candidate(f.m, f.code, f.layout,
                                                     f.yparts,
                                                     f.initial_candidate)
        payload = FullRefineJuna._juna_wz(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate)

        @test selected == solved
        assert_full_candidate_contract(f.m, f.code, f.bits, f.codeword, selected)
        @test payload == f.bits

        dominant_initial_candidate = (
            posterior_metric = f.metrics,
            ldpc_valid = true,
            syndrome_weight = 0,
            mean_absolute_posterior_metric = 1_000.0,
            pilot_mse = 0.0,
            tie_mse = 0.0,
            selection_score = -100.0,
        )
        preserved = FullRefineJuna._juna_wz_candidate(f.m, f.code, f.layout,
                                                      f.yparts,
                                                      dominant_initial_candidate)
        @test preserved == dominant_initial_candidate
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("C,z refinement checks passed")
end
