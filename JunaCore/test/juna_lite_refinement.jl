#!/usr/bin/env julia
#
# JUNA-lite refinement - posterior anchors, candidate ordering, and forced refit.
#
# Paper claims protected (reference papers/gab/joe.tex):
#   ssec:junalite             JUNA-lite uses BP posterior information as soft
#                             constellation anchors for a second equalization pass.
#   sec:solver                The decoder/refit loop must improve or preserve the
#                             best candidate before final payload extraction.
#
# If this fails: the lite receiver may still pass clean loopbacks by returning a
# valid initial candidate, while the posterior-anchor refit path is broken or
# degraded.
#
# Run alone:  julia --project=. test/juna_lite_refinement.jl
# Via runner: julia --project=. test/runtests.jl lite

using Statistics
using Test
using JunaCore

const LiteRefineJuna = JunaCore.Juna
const LiteRefineModulations = JunaCore.Modulations
const LITE_REFINE_FS = 24_000.0

lite_payload_pattern(n::Integer) =
    Bool[isodd(count_ones(13i + 2)) for i in 1:n]

lite_pm(bit::Bool) = bit ? -1.0 : 1.0

function lite_qpsk_symbol(codeword::AbstractVector{Bool}, carrier::Integer)
    j = 2 * (Int(carrier) - 1) + 1
    bI = codeword[j]
    bQ = j + 1 <= length(codeword) ? codeword[j + 1] : false
    ComplexF64(lite_pm(bI), lite_pm(bQ)) / sqrt(2)
end

function lite_refinement_fixture()
    m = LiteRefineJuna.LiteModulation(partial_fft_parts = 1)
    layout = LiteRefineJuna._layout(m, LITE_REFINE_FS)
    code = LiteRefineJuna._code(m)
    bits = lite_payload_pattern(LiteRefineModulations.bitspersymbol(m))
    message = LiteRefineJuna._build_message(m, code, bits)
    codeword = LiteRefineJuna._encode(code, message)
    equalized = zeros(ComplexF64, Int(m.nc))
    equalized[layout.pilot_idx] .= layout.pilot_syms
    ncarriers = LiteRefineJuna._ndata_tones(m, code.n)
    for t in 1:ncarriers
        equalized[layout.data_idx[t]] = lite_qpsk_symbol(codeword, t)
    end
    for t in ncarriers+1:length(layout.data_idx)
        equalized[layout.data_idx[t]] = one(ComplexF64)
    end
    yparts = zeros(ComplexF64, 1, Int(m.nc))
    yparts[1, :] .= equalized
    metrics = Float64[bit ? 6.0 : -6.0 for bit in codeword]
    initial_candidate = (
        lpost_metric = metrics,
        valid = false,
        syndrome = 88,
        mean_abs_lpost = mean(abs, metrics),
        pilot_mse = 0.4,
        tie_mse = 0.8,
        score = 0.9,
    )
    (m = m, layout = layout, code = code, bits = bits, codeword = codeword,
     yparts = yparts, metrics = metrics,
     initial_candidate = initial_candidate)
end

function assert_lite_candidate_contract(m, code, bits, codeword, candidate)
    @test keys(candidate) == (:lpost_metric, :valid, :syndrome, :mean_abs_lpost,
                              :pilot_mse, :tie_mse, :score)
    @test candidate.lpost_metric isa Vector{Float64}
    @test length(candidate.lpost_metric) == code.n
    @test all(isfinite, candidate.lpost_metric)
    @test all(isfinite, (candidate.mean_abs_lpost, candidate.pilot_mse,
                         candidate.tie_mse, candidate.score))
    @test candidate.valid
    @test candidate.syndrome == 0
    @test (candidate.lpost_metric .> 0) == codeword
    @test LiteRefineJuna._payload_from_metrics(m, code, candidate.lpost_metric) == bits
end

@testset verbose = true "JUNA-lite refinement" begin
    @testset "_posterior_symbols and _posterior_confidence map metrics to soft anchors" begin
        qpsk = LiteRefineJuna.LiteModulation()
        qmetrics = [4.0, -2.0, -6.0, 0.0, 2.0]
        qanchors = LiteRefineJuna._posterior_symbols(qpsk, qmetrics)
        qconf = LiteRefineJuna._posterior_confidence(qpsk, qmetrics)
        invsqrt2 = 1 / sqrt(2)

        @test qanchors isa Vector{ComplexF64}
        @test qanchors ≈ ComplexF64[
            -tanh(2.0) + im * tanh(1.0),
            tanh(3.0) + 0im,
            -tanh(1.0) + 0im,
        ] .* invsqrt2 atol=1e-15
        @test qconf ≈ [
            min(abs(tanh(2.0)), abs(tanh(1.0))),
            0.0,
            abs(tanh(1.0)),
        ] atol=1e-15

        bpsk = LiteRefineJuna.LiteModulation(bpc = 1, ldpc_k = 170, ldpc_n = 680)
        bmetrics = [-4.0, 0.0, 2.0]
        @test LiteRefineJuna._posterior_symbols(bpsk, bmetrics) ≈
              ComplexF64[tanh(2.0), 0.0, -tanh(1.0)] atol=1e-15
        @test LiteRefineJuna._posterior_confidence(bpsk, bmetrics) ≈
              [abs(tanh(2.0)), 0.0, abs(tanh(1.0))] atol=1e-15
    end

    @testset "anchor selection keeps pilots and ranks eligible data by confidence" begin
        m = LiteRefineJuna.LiteModulation()
        layout = LiteRefineJuna._layout(m, LITE_REFINE_FS)
        metrics = [4.0, 4.0, 0.0, 0.0, 3.0, 1.0, 6.0, 5.0]
        anchors = LiteRefineJuna._posterior_symbols(m, metrics)
        confidence = LiteRefineJuna._posterior_confidence(m, metrics)
        selected = LiteRefineJuna._juna_anchor_targets(
            m, layout, metrics; confidence_min = 0.5, max_data_anchors = 1,
        )

        @test argmax(confidence) == 4
        @test selected.selected == [4]
        @test selected.target_idx == vcat(layout.pilot_idx, [layout.data_idx[4]])
        @test selected.targets == vcat(layout.pilot_syms, [anchors[4]])
        @test selected.confidence == confidence && selected.target_weights == vcat(ones(length(layout.pilot_idx)), [confidence[4]])

        pilots_only = LiteRefineJuna._juna_anchor_targets(
            m, layout, metrics; confidence_min = 0.0, max_data_anchors = 0,
        )
        @test isempty(pilots_only.selected)
        @test pilots_only.target_idx == layout.pilot_idx
        @test pilots_only.targets == layout.pilot_syms && pilots_only.target_weights == ones(length(layout.pilot_idx))
        @test_throws ArgumentError LiteRefineJuna._juna_anchor_targets(
            m, layout, metrics; confidence_min = -0.1,
        )
        @test_throws ArgumentError LiteRefineJuna._juna_anchor_targets(
            m, layout, metrics; max_data_anchors = -1,
        )
    end

    @testset "_juna_better orders validity, syndrome, score, then confidence" begin
        base = (valid = false, syndrome = 7, score = 10.0, mean_abs_lpost = 1.0)

        @test LiteRefineJuna._juna_better(base, (valid = true, syndrome = 100,
                                                score = 99.0, mean_abs_lpost = 0.0))
        @test !LiteRefineJuna._juna_better((valid = true, syndrome = 0,
                                            score = 1.0, mean_abs_lpost = 10.0),
                                           base)
        @test LiteRefineJuna._juna_better(base, (valid = false, syndrome = 6,
                                                score = 99.0, mean_abs_lpost = 0.0))
        @test LiteRefineJuna._juna_better(base, (valid = false, syndrome = 7,
                                                score = 9.94, mean_abs_lpost = 1.0))
        @test !LiteRefineJuna._juna_better(base, (valid = false, syndrome = 7,
                                                 score = 9.96, mean_abs_lpost = 1.0))
        @test LiteRefineJuna._juna_better(base, (valid = false, syndrome = 7,
                                                score = 10.0, mean_abs_lpost = 1.02))
    end

    @testset "_juna_step turns posterior anchors into a finite valid candidate" begin
        f = lite_refinement_fixture()
        candidate = LiteRefineJuna._juna_step(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate)

        assert_lite_candidate_contract(f.m, f.code, f.bits, f.codeword, candidate)
        @test LiteRefineJuna._juna_better(f.initial_candidate, candidate)
        @test candidate.score < f.initial_candidate.score
        @test candidate.mean_abs_lpost > f.initial_candidate.mean_abs_lpost
        @test candidate.pilot_mse == 0.0
        @test candidate.tie_mse < 1e-8
    end

    @testset "_juna_lite_candidate refines an invalid initial candidate and preserves a valid one" begin
        f = lite_refinement_fixture()
        step = LiteRefineJuna._juna_step(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate)
        refined = LiteRefineJuna._juna_lite_candidate(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate)
        payload = LiteRefineJuna._juna_lite(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate)
        bad_yparts = zeros(ComplexF64, 0, Int(f.m.nc))
        early = LiteRefineJuna._juna_lite_candidate(f.m, f.code, f.layout, bad_yparts, step)

        @test refined == step
        assert_lite_candidate_contract(f.m, f.code, f.bits, f.codeword, refined)
        @test payload == f.bits
        @test early == step
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA-lite refinement checks passed")
end
