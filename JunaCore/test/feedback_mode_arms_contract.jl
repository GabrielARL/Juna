#!/usr/bin/env julia
#
# Decoder feedback settings for the pilot-density mechanism experiment.
#
# The coupled receivers fold decoder output back into channel estimation. To
# compare transmitted-symbol feedback with decoder results, the same receiver
# must be runnable in four settings that share
# one code path, one iteration schedule and one acceptance rule:
#
#   :decoder_posterior              posterior soft symbols anchor the re-fit
#   :pilots_only                    data decisions never anchor the re-fit
#   :transmitted_symbols            transmitted symbols anchor the re-fit
#   :corrupted_transmitted_symbols  caller-supplied corrupted symbols anchor it
#
# A null result limits what transmitted-symbol feedback contributes to this
# receiver's refit. A mis-wired setting must fail loudly instead of looking like
# that null result.
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

function fb_qpsk_symbol(codeword::AbstractVector{Bool}, carrier::Integer)
    j = 2 * (Int(carrier) - 1) + 1
    bI = codeword[j]
    bQ = j + 1 <= length(codeword) ? codeword[j + 1] : false
    ComplexF64(fb_pm(bI), fb_pm(bQ)) / sqrt(2)
end

const FB_QPSK = ComplexF64[
    ComplexF64(1, 1) / sqrt(2), ComplexF64(1, -1) / sqrt(2),
    ComplexF64(-1, 1) / sqrt(2), ComplexF64(-1, -1) / sqrt(2),
]

"""Layout, code, true codeword and a posterior metric vector for one block."""
function fb_fixture(; anchor_feedback_source = :decoder_posterior)
    m = FBJuna.LiteModulation(partial_fft_parts = 1)
    m.anchor_feedback_source = anchor_feedback_source
    layout = FBJuna._layout(m, FB_FS)
    code = FBJuna._code(m)
    bits = fb_payload_pattern(FBModulations.bitspersymbol(m))
    message = FBJuna._build_message(m, code, bits)
    codeword = FBJuna._encode(code, message)
    ncarriers = FBJuna._ndata_tones(m, code.n)
    truth = ComplexF64[t <= ncarriers ? fb_qpsk_symbol(codeword, t) : one(ComplexF64)
                       for t in 1:length(layout.data_idx)]
    metrics = Float64[bit ? 6.0 : -6.0 for bit in codeword]
    (; m, layout, code, codeword, truth, metrics, ncarriers)
end

@testset verbose = true "Decoder feedback settings" begin

    @testset "the mode is a validated receiver field, not a new receiver mode" begin
        default = FBJuna.LiteModulation()
        @test default.anchor_feedback_source === :decoder_posterior
        @test default.transmitted_symbols === nothing

        @test FBJuna._FEEDBACK_MODES ==
              (:decoder_posterior, :pilots_only, :transmitted_symbols,
               :corrupted_transmitted_symbols)
        for mode in FBJuna._FEEDBACK_MODES
            @test isvalid(
                FBJuna.LiteModulation(anchor_feedback_source=mode),
                FB_FC, FB_FS)
        end
        # An unusable arm must be unconstructible, not merely wrong at runtime.
        @test !isvalid(
            FBJuna.LiteModulation(anchor_feedback_source=:bogus),
            FB_FC, FB_FS)
        # The public receiver surface must not grow: these are settings, not modes.
        @test !(:pilots_only in FBJuna._RECEIVER_PROFILES)
        @test !(:transmitted_symbols in FBJuna._RECEIVER_PROFILES)
        @test !(:corrupted_transmitted_symbols in FBJuna._RECEIVER_PROFILES)
    end

    @testset "transmitted symbols are sliced per codeword block" begin
        @test FBJuna._transmitted_symbol_block(nothing, 1) === nothing
        @test FBJuna._transmitted_symbol_block(nothing, 7) === nothing

        vec = ComplexF64[1, 2, 3]
        @test FBJuna._transmitted_symbol_block(vec, 1) === vec
        @test_throws DimensionMismatch FBJuna._transmitted_symbol_block(vec, 2)

        mat = ComplexF64[1 4; 2 5; 3 6]
        @test collect(FBJuna._transmitted_symbol_block(mat, 1)) ==
              ComplexF64[1, 2, 3]
        @test collect(FBJuna._transmitted_symbol_block(mat, 2)) ==
              ComplexF64[4, 5, 6]
        @test_throws DimensionMismatch FBJuna._transmitted_symbol_block(mat, 3)
        @test_throws DimensionMismatch FBJuna._transmitted_symbol_block(mat, 0)
    end

    @testset ":decoder_posterior anchors on posterior decisions" begin
        fx = fb_fixture()
        plan = FBJuna._lite_anchor_targets(fx.m, fx.layout, fx.metrics)
        @test !isempty(plan.selected)
        @test length(plan.target_idx) == length(fx.layout.pilot_idx) + length(plan.selected)
        @test plan.target_idx[1:length(fx.layout.pilot_idx)] == fx.layout.pilot_idx
        # pilots weigh 1, data anchors weigh their posterior confidence
        @test all(==(1.0), plan.target_weights[1:length(fx.layout.pilot_idx)])
        @test plan.target_weights[length(fx.layout.pilot_idx)+1:end] ==
              plan.confidence[plan.selected]
        # A confident posterior points at the transmitted symbols but is shrunk
        # toward the origin by the tanh soft-decision map, so it is never equal
        # to the transmitted symbols. That setting removes the shrinkage.
        data_targets = plan.targets[length(fx.layout.pilot_idx)+1:end]
        expected = fx.truth[plan.selected]
        @test all(isapprox.(data_targets, expected; atol = 0.01))
        @test all(abs.(data_targets) .< abs.(expected))
        @test all(real.(data_targets) .* real.(expected) .>= 0)
        @test all(imag.(data_targets) .* imag.(expected) .>= 0)
    end

    @testset ":pilots_only runs the machinery with no data anchor at all" begin
        fx = fb_fixture(anchor_feedback_source = :pilots_only)
        plan = FBJuna._lite_anchor_targets(fx.m, fx.layout, fx.metrics)
        @test isempty(plan.selected)
        @test plan.target_idx == fx.layout.pilot_idx
        @test plan.targets == fx.layout.pilot_syms
        @test all(==(1.0), plan.target_weights)
        @test length(plan.target_weights) == length(fx.layout.pilot_idx)
        # the pilots-only setting must not need transmitted symbols
        @test FBJuna._lite_anchor_targets(
            fx.m, fx.layout, fx.metrics;
            transmitted_symbols=nothing).selected == Int[]
    end

    @testset ":transmitted_symbols substitutes transmitted symbols at unit weight" begin
        fx = fb_fixture(anchor_feedback_source = :transmitted_symbols)
        plan = FBJuna._lite_anchor_targets(
            fx.m, fx.layout, fx.metrics; transmitted_symbols=fx.truth)
        @test !isempty(plan.selected)
        @test all(==(1.0), plan.target_weights)
        @test length(plan.target_weights) == length(plan.target_idx)
        data_targets = plan.targets[length(fx.layout.pilot_idx)+1:end]
        @test data_targets == ComplexF64.(fx.truth[plan.selected])

        # A mis-wired transmitted-symbol setting must fail loudly rather than
        # fall back to decoder posteriors.
        @test_throws ArgumentError FBJuna._lite_anchor_targets(
            fx.m, fx.layout, fx.metrics)
        @test_throws DimensionMismatch FBJuna._lite_anchor_targets(
            fx.m, fx.layout, fx.metrics;
            transmitted_symbols=fx.truth[1:2])

        graded = fb_fixture(
            anchor_feedback_source = :corrupted_transmitted_symbols)
        corrupted = FBJuna.corrupt_feedback_symbols(
            graded.truth, 0.25, MersenneTwister(23), FB_QPSK)
        gplan = FBJuna._lite_anchor_targets(
            graded.m, graded.layout, graded.metrics;
            transmitted_symbols=corrupted)
        @test all(==(1.0), gplan.target_weights)
        @test gplan.targets[length(graded.layout.pilot_idx)+1:end] ==
              corrupted[gplan.selected]
        @test_throws ArgumentError FBJuna._lite_anchor_targets(
            graded.m, graded.layout, graded.metrics)
    end

    @testset "transmitted symbols are required before a clean-result early return" begin
        fx = fb_fixture(anchor_feedback_source=:transmitted_symbols)
        message = FBJuna._build_message(fx.m, fx.code,
                                        fb_payload_pattern(FBModulations.bitspersymbol(fx.m)))
        waveform = FBJuna._modulate_block(
            fx.m, fx.layout, FBJuna._encode(fx.code, message))
        observations = FBJuna._branch_observations(fx.m, waveform)
        decoded_candidate = FBJuna._initial_candidate(
            fx.m, fx.code, fx.layout, observations)
        @test decoded_candidate.ldpc_valid
        @test_throws ArgumentError FBJuna._juna_lite_candidate(
            fx.m, fx.code, fx.layout, observations, decoded_candidate)

        frame_kwargs = (
            fft_length=64, cyclic_prefix_length=16,
            ldpc_k=20, ldpc_n=40, ldpc_checks_per_column=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1 / 3, inner_pilot_ratio=0.0,
            refinement_steps=0,
        )
        frame = FBJuna.FrameWideLDPCModulation(
            ; frame_kwargs..., frame_receiver=:lite,
            anchor_feedback_source=:transmitted_symbols)
        payload = Bool[true, false, true]
        clean = FBModulations.modulate(frame, payload, FB_FC, FB_FS)
        @test_throws ArgumentError FBModulations.demodulate(
            frame, length(payload), clean, FB_FC, FB_FS)

        cz_refinement = FBJuna.CzRefinementModulation(
            ; frame_kwargs..., cz_feedback_source=:transmitted_symbols,
            cz_decoder_posterior_weight=0.5)
        refinement_clean = FBModulations.modulate(
            cz_refinement, payload, FB_FC, FB_FS)
        @test_throws ArgumentError FBModulations.demodulate(
            cz_refinement, length(payload), refinement_clean, FB_FC, FB_FS)
    end

    @testset "transmitted-symbol feedback does not use the posterior confidence floor" begin
        # The deployed floor is 0.0 and the deployed cap is unbounded, so on the
        # OFDM-symbol path :decoder_posterior already anchors every data carrier.
        # if they change, the settings' comparability changes with them.
        @test FBJuna._JUNA_CONFIDENCE_MIN == 0.0
        @test FBJuna._JUNA_MAX_DATA_ANCHORS == typemax(Int)

        # The floor exists for ablations that raise it. With it raised and an
        # unreliable posterior, decoder feedback has no data anchors while the
        # transmitted-symbol setting still
        # uses the supplied transmitted symbols.
        fx = fb_fixture()
        weak = fill(1e-6, length(fx.metrics))
        real_plan = FBJuna._lite_anchor_targets(fx.m, fx.layout, weak;
                                                confidence_min = 0.5)
        @test isempty(real_plan.selected)

        transmitted_symbol_setting =
            fb_fixture(anchor_feedback_source=:transmitted_symbols)
        transmitted_symbol_plan = FBJuna._lite_anchor_targets(
            transmitted_symbol_setting.m, transmitted_symbol_setting.layout, weak;
                                                 confidence_min = 0.5,
            transmitted_symbols=transmitted_symbol_setting.truth)
        @test !isempty(transmitted_symbol_plan.selected)
        @test length(transmitted_symbol_plan.selected) >
              length(real_plan.selected)
    end

    @testset "wrong posterior: transmitted-symbol feedback anchors the transmitted symbols" begin
        # Invert the posterior so every decision is confidently wrong. Decoder
        # feedback then anchors the wrong constellation points; transmitted-symbol
        # feedback must still anchor the
        # transmitted ones. This is the property the whole experiment rests on.
        fx = fb_fixture()
        wrong = -fx.metrics
        real_plan = FBJuna._lite_anchor_targets(fx.m, fx.layout, wrong)
        real_targets = real_plan.targets[length(fx.layout.pilot_idx)+1:end]
        @test !isempty(real_plan.selected)
        @test !any(isapprox.(real_targets, fx.truth[real_plan.selected]; atol = 1e-6))

        transmitted_symbol_setting =
            fb_fixture(anchor_feedback_source=:transmitted_symbols)
        transmitted_symbol_plan = FBJuna._lite_anchor_targets(
            transmitted_symbol_setting.m, transmitted_symbol_setting.layout, wrong;
            transmitted_symbols=transmitted_symbol_setting.truth)
        transmitted_symbol_targets = transmitted_symbol_plan.targets[
            length(transmitted_symbol_setting.layout.pilot_idx)+1:end]
        @test transmitted_symbol_targets == ComplexF64.(
            transmitted_symbol_setting.truth[transmitted_symbol_plan.selected])
    end

    @testset "caller-supplied corruption is bounded and on-constellation" begin
        truth = ComplexF64[FB_QPSK[1 + (i % 4)] for i in 1:400]

        @test FBJuna.corrupt_feedback_symbols(truth, 0.0, MersenneTwister(1),
                                              FB_QPSK) == truth

        all_wrong = FBJuna.corrupt_feedback_symbols(truth, 1.0, MersenneTwister(2),
                                                    FB_QPSK)
        @test all(all_wrong .!= truth)
        @test all(s -> any(isapprox.(s, FB_QPSK; atol = 1e-12)), all_wrong)

        # The caller chooses reproducible or distinct corruption inputs.
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

    @testset "the frame-wide anchor plan uses the same feedback settings" begin
        fx = fb_fixture()
        frame = FBJuna.FrameWideLDPCModulation(frame_receiver = :stateful_lite)
        frame.ldpc_n = fx.m.ldpc_n
        flayout = FBJuna._layout(frame, FB_FS)
        metrics = fx.metrics

        idx_real, tgt_real, count_real =
            FBJuna._frame_anchor_plan(frame, flayout, metrics, 1)
        @test count_real > 0
        @test idx_real[1:length(flayout.pilot_idx)] == flayout.pilot_idx

        frame.anchor_feedback_source = :pilots_only
        idx_frozen, tgt_frozen, count_frozen =
            FBJuna._frame_anchor_plan(frame, flayout, metrics, 1)
        @test count_frozen == 0
        @test idx_frozen == flayout.pilot_idx
        @test tgt_frozen == flayout.pilot_syms

        # no posterior was already equivalent to pilots only; the setting agrees
        idx_none, tgt_none, count_none =
            FBJuna._frame_anchor_plan(frame, flayout, nothing, 1)
        @test (idx_none, tgt_none, count_none) == (idx_frozen, tgt_frozen, count_frozen)

        frame.anchor_feedback_source = :transmitted_symbols
        truth = ComplexF64[t <= length(flayout.data_idx) ?
                           FB_QPSK[1 + (t % 4)] : one(ComplexF64)
                           for t in 1:length(flayout.data_idx)]
        frame.transmitted_symbols = reshape(truth, :, 1)
        idx_genie, tgt_genie, count_genie =
            FBJuna._frame_anchor_plan(frame, flayout, metrics, 1)
        @test count_genie > 0
        @test length(idx_genie) == length(flayout.pilot_idx) + count_genie
        @test tgt_genie[length(flayout.pilot_idx)+1:end] == truth[1:count_genie]

        corrupted = FBJuna.corrupt_feedback_symbols(
            truth, 1.0, MersenneTwister(29), FB_QPSK)
        frame.anchor_feedback_source = :corrupted_transmitted_symbols
        frame.transmitted_symbols = reshape(corrupted, :, 1)
        _, tgt_graded, count_graded =
            FBJuna._frame_anchor_plan(frame, flayout, metrics, 1)
        @test count_graded == count_genie
        @test tgt_graded[length(flayout.pilot_idx)+1:end] ==
              corrupted[1:count_graded]

        frame.transmitted_symbols = nothing
        @test_throws ArgumentError FBJuna._frame_anchor_plan(
            frame, flayout, metrics, 1)
    end

    @testset "feedback settings produce distinct receiver refits" begin
        # If a refactor collapses the settings into the same computation, the
        # mechanism comparison would return a misleading null result.
        #
        # Divergence needs estimation to be imperfect. Under a noiseless,
        # fully-resolved observation the pilots alone recover everything and all
        # three settings agree exactly -- which is itself worth pinning, because
        # they differ only where feedback could matter.
        function distorted(mode; snr_db = 18.0, seed = 11)
            fx = fb_fixture(anchor_feedback_source = mode)
            fft_length = Int(fx.m.fft_length)
            grid = zeros(ComplexF64, fft_length)
            grid[fx.layout.pilot_idx] .= fx.layout.pilot_syms
            for t in 1:length(fx.layout.data_idx)
                grid[fx.layout.data_idx[t]] = fx.truth[t]
            end
            rng = MersenneTwister(seed)
            # frequency-selective response the sparse pilot comb cannot resolve
            h = [(1.0 + 0.9 * sin(2pi * 4.5 * k / fft_length)) *
                 cis(2.2 * cos(2pi * 3.1 * k / fft_length))
                 for k in 1:fft_length]
            grid .*= h
            power = mean(abs2, grid)
            sigma = sqrt(power / 10^(snr_db / 10) / 2)
            grid .+= sigma .* (randn(rng, fft_length) .+
                               im .* randn(rng, fft_length))
            yparts = zeros(ComplexF64, 1, fft_length)
            yparts[1, :] .= grid
            fx.m.transmitted_symbols = fx.truth
            soft = Float64[bit ? 3.0 : -3.0 for bit in fx.codeword]
            initial_candidate = (
                posterior_metric=soft, ldpc_valid=false, syndrome_weight=88,
                mean_absolute_posterior_metric=mean(abs, soft), pilot_mse=0.4,
                tie_mse=0.8, selection_score=0.9)
            (; fx, step = FBJuna._lite_refinement_step(
                fx.m, fx.code, fx.layout, yparts, initial_candidate))
        end

        pilots_only_setting = distorted(:pilots_only)
        decoder_posterior_setting = distorted(:decoder_posterior)
        transmitted_symbol_setting = distorted(:transmitted_symbols)

        @test pilots_only_setting.step.posterior_metric !=
              decoder_posterior_setting.step.posterior_metric
        @test pilots_only_setting.step.posterior_metric !=
              transmitted_symbol_setting.step.posterior_metric
        @test decoder_posterior_setting.step.posterior_metric !=
              transmitted_symbol_setting.step.posterior_metric

        # :pilots_only is idempotent -- with no data anchor the re-fit reaches a fixed
        # point immediately, so the refinement loop's early exit costs nothing.
        # This is why the control setting may report fewer iterations than
        # :decoder_posterior
        # without that being a confound.
        fx = fb_fixture(anchor_feedback_source = :pilots_only)
        yparts = zeros(ComplexF64, 1, Int(fx.m.fft_length))
        yparts[1, fx.layout.pilot_idx] .= fx.layout.pilot_syms
        for t in 1:length(fx.layout.data_idx)
            yparts[1, fx.layout.data_idx[t]] = fx.truth[t]
        end
        initial_candidate = (
            posterior_metric=fx.metrics, ldpc_valid=false, syndrome_weight=88,
            mean_absolute_posterior_metric=mean(abs, fx.metrics), pilot_mse=0.4,
            tie_mse=0.8, selection_score=0.9)
        one_step = FBJuna._lite_refinement_step(
            fx.m, fx.code, fx.layout, yparts, initial_candidate)
        two_step = FBJuna._lite_refinement_step(
            fx.m, fx.code, fx.layout, yparts, one_step)
        @test one_step.posterior_metric == two_step.posterior_metric
        @test one_step.selection_score == two_step.selection_score
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("feedback-mode arm checks passed")
end
