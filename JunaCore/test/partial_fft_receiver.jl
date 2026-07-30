#!/usr/bin/env julia
#
# Baseline receivers — the paper's OFDM+FEC (:standard) and Partial FFT+FEC
# (:pfft) benchmark branches as first-class public modes.
#
# Paper claims protected (papers/main.tex):
#   sec:method            "We evaluate three receivers on the same transmitted
#                          schedule": the two baselines must be REAL public
#                          receivers, not just columns of an internal table.
#   eq:pfft-ls             :pfft is the pilot-trained per-band ridge LS combiner
#                          and nothing more (no standard fallback, no refinement).
#   eq:ofdm5-band-index    the band partition drives the combiner :pfft uses.
#
# The dispatch pins are the load-bearing tests: each public mode must equal its
# demodulate_methods column on a waveform where the columns provably differ, so
# a mode silently rerouted to another receiver path cannot pass.
#
# Run alone:  julia --project=. test/partial_fft_receiver.jl
# Via runner: julia --project=. test/runtests.jl pfft

using Random
using Test
using JunaCore
using FFTW

const PfftJuna = JunaCore.Juna
const PfftModulations = JunaCore.Modulations
const PFFT_FC = 24_000.0
const PFFT_FS = 24_000.0

pfft_payload(n::Integer) = Bool[isodd(count_ones(23i + 11)) for i in 1:Int(n)]

# The equalization suite's piecewise fixture through the PUBLIC waveform: a
# distinct complex gain per partial-FFT window, i.e. a channel that changes
# within one OFDM symbol. One-tap equalization provably fails here while the
# per-band branch combiner succeeds — the discrimination the paper claims.
function pfft_piecewise_waveform(m, bits)
    waveform = collect(PfftModulations.modulate(m, bits, PFFT_FC, PFFT_FS))
    gains = ComplexF64[1.45 - 0.35im, 0.62 + 0.75im, -0.35 + 1.2im, 1.05 + 0.18im]
    N = Int(m.nc)
    L = Int(m.np)
    for p in 1:Int(m.partial_fft_parts)
        lo, hi = PfftJuna._part_bounds(N, Int(m.partial_fft_parts), p)
        @views waveform[L+lo:L+hi] .*= gains[mod1(p, length(gains))]
    end
    waveform
end

@testset verbose = true "Partial-FFT and standard baseline receivers" begin
    @testset "one partial-FFT view is the full useful-symbol FFT" begin
        m = PfftJuna.PartialFFTModulation(
            nc=1024, np=256, bpc=1, partial_fft_parts=1)
        rng = Xoshiro(20_260_725)
        useful = randn(rng, ComplexF64, Int(m.nc))
        block = vcat(useful[end-Int(m.np)+1:end], useful)
        observation = PfftJuna._branch_observations(m, block)
        @test size(observation) == (1, Int(m.nc))
        @test vec(observation) ≈ fft(useful) rtol=2e-14 atol=2e-12
    end

    @testset "public :standard and :pfft equal their three-path columns" begin
        pfft = PfftJuna.PartialFFTModulation()
        standard = PfftJuna.StandardModulation()
        bits = pfft_payload(PfftModulations.bitspersymbol(pfft))
        distorted = pfft_piecewise_waveform(pfft, bits)

        paths = PfftJuna.demodulate_methods(
            standard, length(bits), distorted, PFFT_FC, PFFT_FS)
        standard_metrics, standard_cfo = PfftModulations.demodulate(
            standard, length(bits), distorted, PFFT_FC, PFFT_FS)
        pfft_metrics, pfft_cfo = PfftModulations.demodulate(
            pfft, length(bits), distorted, PFFT_FC, PFFT_FS)

        # the fixture must genuinely separate the columns, or the pins prove nothing
        @test paths.standard != paths.partial
        @test standard_metrics == paths.standard
        @test pfft_metrics == paths.partial
        @test standard_cfo == pfft_cfo == 0.0
    end

    @testset "per-band combining survives the channel one-tap cannot" begin
        pfft = PfftJuna.PartialFFTModulation()
        standard = PfftJuna.StandardModulation()
        bits = pfft_payload(PfftModulations.bitspersymbol(pfft))
        distorted = pfft_piecewise_waveform(pfft, bits)

        pfft_metrics, _ = PfftModulations.demodulate(
            pfft, length(bits), distorted, PFFT_FC, PFFT_FS)
        standard_metrics, _ = PfftModulations.demodulate(
            standard, length(bits), distorted, PFFT_FC, PFFT_FS)

        @test (pfft_metrics .> 0) == bits
        @test count((standard_metrics .> 0) .!= bits) > 0
    end

    @testset "lite refinement builds on the pfft seed and never falls behind it" begin
        pfft = PfftJuna.PartialFFTModulation()
        lite = PfftJuna.LiteModulation()
        bits = pfft_payload(PfftModulations.bitspersymbol(pfft))

        # clean channel: the seed is already valid, refinement keeps it, and the
        # two public receivers emit IDENTICAL metrics
        clean = PfftModulations.modulate(pfft, bits, PFFT_FC, PFFT_FS)
        clean_pfft, _ = PfftModulations.demodulate(
            pfft, length(bits), clean, PFFT_FC, PFFT_FS)
        clean_lite, _ = PfftModulations.demodulate(
            lite, length(bits), clean, PFFT_FC, PFFT_FS)
        @test clean_lite == clean_pfft
        @test (clean_pfft .> 0) == bits

        # seeded waterfall edge: posterior-anchor refinement must not lose to
        # its own seed in aggregate on the shared fixture
        rng = Xoshiro(20_260_401)
        sigma = sqrt(10.0^(-1.5 / 10) / 2)
        pfft_errors = 0
        lite_errors = 0
        for _ in 1:6
            packet = rand(rng, Bool, length(bits))
            wf = PfftModulations.modulate(pfft, packet, PFFT_FC, PFFT_FS)
            noisy = wf .+ sigma .* (randn(rng, length(wf)) .+ im .* randn(rng, length(wf)))
            mp, _ = PfftModulations.demodulate(pfft, length(packet), noisy, PFFT_FC, PFFT_FS)
            ml, _ = PfftModulations.demodulate(lite, length(packet), noisy, PFFT_FC, PFFT_FS)
            pfft_errors += count((mp .> 0) .!= packet)
            lite_errors += count((ml .> 0) .!= packet)
        end
        @test pfft_errors > 0            # the edge fixture is genuinely noisy
        @test lite_errors <= pfft_errors # refinement never loses to its seed here
    end

    @testset "both baselines roundtrip the compact BPSK code" begin
        for factory in (PfftJuna.StandardModulation, PfftJuna.PartialFFTModulation)
            m = factory(bpc = 1, ldpc_k = 170, ldpc_n = 680)
            @test isvalid(m, PFFT_FC, PFFT_FS)
            bits = pfft_payload(PfftModulations.bitspersymbol(m))
            wf = PfftModulations.modulate(m, bits, PFFT_FC, PFFT_FS)
            metrics, cfo = PfftModulations.demodulate(
                m, length(bits), wf, PFFT_FC, PFFT_FS)
            @test (metrics .> 0) == bits
            @test cfo == 0.0
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Partial-FFT and standard baseline receiver checks passed")
end
