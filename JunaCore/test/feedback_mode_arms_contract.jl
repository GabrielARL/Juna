#!/usr/bin/env julia
#
# Feedback-mode arms for the pilot-density mechanism experiment.
#
# The coupled receivers fold decoder output back into channel estimation. To
# separate the information that feedback recovers from the cost of feeding back
# wrong decisions, the same receiver must be runnable in four arms that share
# one code path, one iteration schedule and one acceptance rule:
#
#   :real    deployed behaviour -- posterior soft symbols anchor the re-fit
#   :frozen  full machinery, but data decisions never anchor the re-fit
#   :genie   transmitted symbols anchor the re-fit (upper bound on feedback)
#   :graded  genie symbols corrupted at a known rate (dose response)
#
# If this fails: an experiment arm may silently degrade into :real, which would
# look like a clean null result rather than a wiring bug. Every assertion below
# exists to make a mis-wired arm fail loudly instead.
#
# Run alone:  julia --project=. test/feedback_mode_arms_contract.jl
# Via runner: julia --project=. test/runtests.jl feedback-modes

using Random
using Statistics
using Test
using JunaCore

const FBJuna = JunaCore.Juna
const FBModulations = JunaCore.Modulations
const FB_FS = 24_000.0
const FB_FC = 24_000.0

fb_payload_pattern(n::Integer) = Bool[isodd(count_ones(13i + 2)) for i in 1:n]
fb_pm(bit::Bool) = bit ? -1.0 : 1.0

function fb_qpsk_symbol(codeword::AbstractVector{Bool}, tone::Integer)
    j = 2 * (Int(tone) - 1) + 1
    bI = codeword[j]
    bQ = j + 1 <= length(codeword) ? codeword[j + 1] : false
    ComplexF64(fb_pm(bI), fb_pm(bQ)) / sqrt(2)
end

const FB_QPSK = ComplexF64[
    ComplexF64(1, 1) / sqrt(2), ComplexF64(1, -1) / sqrt(2),
    ComplexF64(-1, 1) / sqrt(2), ComplexF64(-1, -1) / sqrt(2),
]

"""Layout, code, true codeword and a posterior metric vector for one block."""
function fb_fixture(; feedback_mode = :real, feedback_graded_p = 0.0)
    m = FBJuna.LiteModulation(partial_fft_parts = 1)
    m.feedback_mode = feedback_mode
    m.feedback_graded_p = feedback_graded_p
    layout = FBJuna._layout(m, FB_FS)
    code = FBJuna._code(m)
    bits = fb_payload_pattern(FBModulations.bitspersymbol(m))
    message = FBJuna._build_message(m, code, bits)
    codeword = FBJuna._encode(code, message)
    ntones = FBJuna._ndata_tones(m, code.n)
    truth = ComplexF64[t <= ntones ? fb_qpsk_symbol(codeword, t) : one(ComplexF64)
                       for t in 1:length(layout.data_idx)]
    metrics = Float64[bit ? 6.0 : -6.0 for bit in codeword]
    (; m, layout, code, codeword, truth, metrics, ntones)
end

@testset verbose = true "Feedback-mode arms" begin

    @testset "the mode is a validated receiver field, not a new receiver mode" begin
        default = FBJuna.LiteModulation()
        @test default.feedback_mode === :real
        @test default.feedback_graded_p == 0.0
        @test default.genie_symbols === nothing

        @test FBJuna._FEEDBACK_MODES == (:real, :frozen, :genie, :graded)
        for mode in FBJuna._FEEDBACK_MODES
            @test isvalid(FBJuna.LiteModulation(feedback_mode = mode), FB_FC, FB_FS)
        end
        # An unusable arm must be unconstructible, not merely wrong at runtime.
        @test !isvalid(FBJuna.LiteModulation(feedback_mode = :bogus), FB_FC, FB_FS)
        @test !isvalid(FBJuna.LiteModulation(feedback_graded_p = -0.1), FB_FC, FB_FS)
        @test !isvalid(FBJuna.LiteModulation(feedback_graded_p = 1.5), FB_FC, FB_FS)
        @test !isvalid(FBJuna.LiteModulation(feedback_graded_p = NaN), FB_FC, FB_FS)
        @test isvalid(FBJuna.LiteModulation(feedback_graded_p = 1.0), FB_FC, FB_FS)

        # The public receiver surface must not grow: these are arms, not modes.
        @test !(:frozen in FBJuna._RECEIVER_PROFILES)
        @test !(:genie in FBJuna._RECEIVER_PROFILES)
        @test !(:graded in FBJuna._RECEIVER_PROFILES)
    end

    @testset "genie symbols are sliced per codeword block" begin
        @test FBJuna._genie_block(nothing, 1) === nothing
        @test FBJuna._genie_block(nothing, 7) === nothing

        vec = ComplexF64[1, 2, 3]
        @test FBJuna._genie_block(vec, 1) === vec
        @test_throws DimensionMismatch FBJuna._genie_block(vec, 2)

        mat = ComplexF64[1 4; 2 5; 3 6]
        @test collect(FBJuna._genie_block(mat, 1)) == ComplexF64[1, 2, 3]
        @test collect(FBJuna._genie_block(mat, 2)) == ComplexF64[4, 5, 6]
        @test_throws DimensionMismatch FBJuna._genie_block(mat, 3)
        @test_throws DimensionMismatch FBJuna._genie_block(mat, 0)
    end

    @testset ":real is unchanged and still anchors on posterior decisions" begin
        fx = fb_fixture()
        plan = FBJuna._juna_anchor_targets(fx.m, fx.layout, fx.metrics)
        @test !isempty(plan.selected)
        @test length(plan.target_idx) == length(fx.layout.pilot_idx) + length(plan.selected)
        @test plan.target_idx[1:length(fx.layout.pilot_idx)] == fx.layout.pilot_idx
        # pilots weigh 1, data anchors weigh their posterior confidence
        @test all(==(1.0), plan.target_weights[1:length(fx.layout.pilot_idx)])
        @test plan.target_weights[length(fx.layout.pilot_idx)+1:end] ==
              plan.confidence[plan.selected]
        # A confident posterior points at the transmitted symbols but is shrunk
        # toward the origin by the tanh soft-decision map, so it is never equal
        # to the truth. That shrinkage is exactly what the oracle removes.
        data_targets = plan.targets[length(fx.layout.pilot_idx)+1:end]
        expected = fx.truth[plan.selected]
        @test all(isapprox.(data_targets, expected; atol = 0.01))
        @test all(abs.(data_targets) .< abs.(expected))
        @test all(real.(data_targets) .* real.(expected) .>= 0)
        @test all(imag.(data_targets) .* imag.(expected) .>= 0)
    end

    @testset ":frozen runs the machinery with no data anchor at all" begin
        fx = fb_fixture(feedback_mode = :frozen)
        plan = FBJuna._juna_anchor_targets(fx.m, fx.layout, fx.metrics)
        @test isempty(plan.selected)
        @test plan.target_idx == fx.layout.pilot_idx
        @test plan.targets == fx.layout.pilot_syms
        @test all(==(1.0), plan.target_weights)
        @test length(plan.target_weights) == length(fx.layout.pilot_idx)
        # frozen must not need ground truth
        @test FBJuna._juna_anchor_targets(fx.m, fx.layout, fx.metrics;
                                          truth = nothing).selected == Int[]
    end

    @testset ":genie substitutes transmitted symbols at unit weight" begin
        fx = fb_fixture(feedback_mode = :genie)
        plan = FBJuna._juna_anchor_targets(fx.m, fx.layout, fx.metrics;
                                           truth = fx.truth)
        @test !isempty(plan.selected)
        @test all(==(1.0), plan.target_weights)
        @test length(plan.target_weights) == length(plan.target_idx)
        data_targets = plan.targets[length(fx.layout.pilot_idx)+1:end]
        @test data_targets == ComplexF64.(fx.truth[plan.selected])

        # A mis-wired oracle must fail loudly rather than fall back to :real.
        @test_throws ArgumentError FBJuna._juna_anchor_targets(
            fx.m, fx.layout, fx.metrics)
        @test_throws DimensionMismatch FBJuna._juna_anchor_targets(
            fx.m, fx.layout, fx.metrics; truth = fx.truth[1:2])

        graded = fb_fixture(feedback_mode = :graded, feedback_graded_p = 0.25)
        gplan = FBJuna._juna_anchor_targets(graded.m, graded.layout,
                                            graded.metrics; truth = graded.truth)
        @test all(==(1.0), gplan.target_weights)
        @test_throws ArgumentError FBJuna._juna_anchor_targets(
            graded.m, graded.layout, graded.metrics)
    end

    @testset "the oracle ignores the confidence floor that guards :real" begin
        # The deployed floor is 0.0 and the deployed cap is unbounded, so on the
        # block path :real already anchors every data tone. Pin those defaults:
        # if they change, the arms' comparability changes with them.
        @test FBJuna._JUNA_CONFIDENCE_MIN == 0.0
        @test FBJuna._JUNA_MAX_DATA_ANCHORS == typemax(Int)

        # The floor exists for ablations that raise it. With it raised and an
        # unreliable posterior, :real is starved while the oracle -- which does
        # not need that protection -- still anchors. Otherwise the arm meant to
        # upper-bound feedback would be starved exactly where it matters most.
        fx = fb_fixture()
        weak = fill(1e-6, length(fx.metrics))
        real_plan = FBJuna._juna_anchor_targets(fx.m, fx.layout, weak;
                                                confidence_min = 0.5)
        @test isempty(real_plan.selected)

        oracle = fb_fixture(feedback_mode = :genie)
        oracle_plan = FBJuna._juna_anchor_targets(oracle.m, oracle.layout, weak;
                                                  confidence_min = 0.5,
                                                  truth = oracle.truth)
        @test !isempty(oracle_plan.selected)
        @test length(oracle_plan.selected) > length(real_plan.selected)
    end

    @testset "wrong posterior: the oracle anchors truth where :real anchors error" begin
        # Invert the posterior so every decision is confidently wrong. :real then
        # anchors the wrong constellation points; :genie must still anchor the
        # transmitted ones. This is the property the whole experiment rests on.
        fx = fb_fixture()
        wrong = -fx.metrics
        real_plan = FBJuna._juna_anchor_targets(fx.m, fx.layout, wrong)
        real_targets = real_plan.targets[length(fx.layout.pilot_idx)+1:end]
        @test !isempty(real_plan.selected)
        @test !any(isapprox.(real_targets, fx.truth[real_plan.selected]; atol = 1e-6))

        oracle = fb_fixture(feedback_mode = :genie)
        oracle_plan = FBJuna._juna_anchor_targets(oracle.m, oracle.layout, wrong;
                                                  truth = oracle.truth)
        oracle_targets = oracle_plan.targets[length(oracle.layout.pilot_idx)+1:end]
        @test oracle_targets == ComplexF64.(oracle.truth[oracle_plan.selected])
    end

    @testset "graded corruption is seeded, bounded and on-constellation" begin
        truth = ComplexF64[FB_QPSK[1 + (i % 4)] for i in 1:400]

        @test FBJuna.corrupt_feedback_symbols(truth, 0.0, MersenneTwister(1),
                                              FB_QPSK) == truth

        all_wrong = FBJuna.corrupt_feedback_symbols(truth, 1.0, MersenneTwister(2),
                                                    FB_QPSK)
        @test all(all_wrong .!= truth)
        @test all(s -> any(isapprox.(s, FB_QPSK; atol = 1e-12)), all_wrong)

        # same seed reproduces, different seed does not
        a = FBJuna.corrupt_feedback_symbols(truth, 0.3, MersenneTwister(7), FB_QPSK)
        b = FBJuna.corrupt_feedback_symbols(truth, 0.3, MersenneTwister(7), FB_QPSK)
        c = FBJuna.corrupt_feedback_symbols(truth, 0.3, MersenneTwister(8), FB_QPSK)
        @test a == b
        @test a != c

        # realized error rate tracks the requested one
        rate = count(a .!= truth) / length(truth)
        @test 0.2 < rate < 0.4
        @test all(s -> any(isapprox.(s, FB_QPSK; atol = 1e-12)), a)

        @test_throws ArgumentError FBJuna.corrupt_feedback_symbols(
            truth, -0.1, MersenneTwister(1), FB_QPSK)
        @test_throws ArgumentError FBJuna.corrupt_feedback_symbols(
            truth, 1.1, MersenneTwister(1), FB_QPSK)
        @test_throws ArgumentError FBJuna.corrupt_feedback_symbols(
            truth, 0.5, MersenneTwister(1), FB_QPSK[1:1])
    end

    @testset "the frame-wide anchor plan honours the same arms" begin
        fx = fb_fixture()
        frame = FBJuna.FrameWideLDPCModulation(frame_receiver = :stateful_lite)
        frame.ldpc_n = fx.m.ldpc_n
        flayout = FBJuna._layout(frame, FB_FS)
        metrics = fx.metrics

        idx_real, tgt_real, count_real =
            FBJuna._frame_anchor_plan(frame, flayout, metrics, 1)
        @test count_real >= 0
        @test idx_real[1:length(flayout.pilot_idx)] == flayout.pilot_idx

        frame.feedback_mode = :frozen
        idx_frozen, tgt_frozen, count_frozen =
            FBJuna._frame_anchor_plan(frame, flayout, metrics, 1)
        @test count_frozen == 0
        @test idx_frozen == flayout.pilot_idx
        @test tgt_frozen == flayout.pilot_syms

        # nothing-posterior was already exactly frozen; the arm must agree
        idx_none, tgt_none, count_none =
            FBJuna._frame_anchor_plan(frame, flayout, nothing, 1)
        @test (idx_none, tgt_none, count_none) == (idx_frozen, tgt_frozen, count_frozen)

        frame.feedback_mode = :genie
        truth = ComplexF64[t <= length(flayout.data_idx) ?
                           FB_QPSK[1 + (t % 4)] : one(ComplexF64)
                           for t in 1:length(flayout.data_idx)]
        frame.genie_symbols = reshape(truth, :, 1)
        idx_genie, tgt_genie, count_genie =
            FBJuna._frame_anchor_plan(frame, flayout, metrics, 1)
        @test count_genie > 0
        @test length(idx_genie) == length(flayout.pilot_idx) + count_genie
        @test all(s -> any(isapprox.(s, FB_QPSK; atol = 1e-12)),
                  tgt_genie[length(flayout.pilot_idx)+1:end])

        frame.genie_symbols = nothing
        @test_throws ArgumentError FBJuna._frame_anchor_plan(
            frame, flayout, metrics, 1)
    end

    @testset "the arms are not a no-op: refinement output actually diverges" begin
        # The single most important regression guard here. If a refactor ever
        # collapses the arms into the same computation, every mechanism
        # experiment would return a clean-looking null instead of failing.
        #
        # Divergence needs estimation to be imperfect. Under a noiseless,
        # fully-resolved observation the pilots alone recover everything and all
        # three arms agree exactly -- which is itself worth pinning, because it
        # says the arms differ only where feedback could matter.
        function distorted(mode; snr_db = 18.0, seed = 11)
            fx = fb_fixture(feedback_mode = mode)
            nc = Int(fx.m.nc)
            grid = zeros(ComplexF64, nc)
            grid[fx.layout.pilot_idx] .= fx.layout.pilot_syms
            for t in 1:length(fx.layout.data_idx)
                grid[fx.layout.data_idx[t]] = fx.truth[t]
            end
            rng = MersenneTwister(seed)
            # frequency-selective response the sparse pilot comb cannot resolve
            h = [(1.0 + 0.9 * sin(2pi * 4.5 * k / nc)) *
                 cis(2.2 * cos(2pi * 3.1 * k / nc)) for k in 1:nc]
            grid .*= h
            power = mean(abs2, grid)
            sigma = sqrt(power / 10^(snr_db / 10) / 2)
            grid .+= sigma .* (randn(rng, nc) .+ im .* randn(rng, nc))
            yparts = zeros(ComplexF64, 1, nc)
            yparts[1, :] .= grid
            fx.m.genie_symbols = fx.truth
            soft = Float64[bit ? 3.0 : -3.0 for bit in fx.codeword]
            initial_candidate = (lpost_metric = soft, valid = false, syndrome = 88,
                              mean_abs_lpost = mean(abs, soft), pilot_mse = 0.4,
                              tie_mse = 0.8, score = 0.9)
            (; fx, step = FBJuna._juna_step(fx.m, fx.code, fx.layout, yparts,
                                            initial_candidate))
        end

        frozen = distorted(:frozen)
        real_arm = distorted(:real)
        genie = distorted(:genie)

        @test frozen.step.lpost_metric != real_arm.step.lpost_metric
        @test frozen.step.lpost_metric != genie.step.lpost_metric
        @test real_arm.step.lpost_metric != genie.step.lpost_metric

        # Where feedback carries information, the oracle should not be beaten by
        # the decisions it replaces, and both should beat having no anchors.
        @test genie.step.score >= real_arm.step.score
        @test real_arm.step.score >= frozen.step.score

        # :frozen is idempotent -- with no data anchor the re-fit reaches a fixed
        # point immediately, so the refinement loop's early exit costs nothing.
        # This is why the control arm may report fewer iterations than :real
        # without that being a confound.
        fx = fb_fixture(feedback_mode = :frozen)
        yparts = zeros(ComplexF64, 1, Int(fx.m.nc))
        yparts[1, fx.layout.pilot_idx] .= fx.layout.pilot_syms
        for t in 1:length(fx.layout.data_idx)
            yparts[1, fx.layout.data_idx[t]] = fx.truth[t]
        end
        initial_candidate = (lpost_metric = fx.metrics, valid = false, syndrome = 88,
                          mean_abs_lpost = mean(abs, fx.metrics), pilot_mse = 0.4,
                          tie_mse = 0.8, score = 0.9)
        one_step = FBJuna._juna_step(fx.m, fx.code, fx.layout, yparts, initial_candidate)
        two_step = FBJuna._juna_step(fx.m, fx.code, fx.layout, yparts, one_step)
        @test one_step.lpost_metric == two_step.lpost_metric
        @test one_step.score == two_step.score
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("feedback-mode arm checks passed")
end
