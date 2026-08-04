#!/usr/bin/env julia
#
# JUNA-WCz end-to-end evidence on clean multi-block data, fixed residual ICI and
# AWGN, coupled dispatch, and warmed execution.
#
# The impairment is a residual frequency offset of 0.08 subcarrier spacings:
# x[n] * exp(j*2*pi*0.08*n/N). It creates inter-carrier interference without
# invoking the optional sync/CFO correction, so the coupled receiver must work
# through its ordinary Partial-FFT, pilot, C/W/z, BP path.
#
# Run alone: julia --project=. test/juna_coupled_end_to_end.jl
# Via runner: julia --project=. test/runtests.jl coupled-e2e

using Test
using JunaCore

const CoupledE2EJuna = JunaCore.Juna
const CoupledE2EModulations = JunaCore.Modulations
const COUPLED_E2E_FC = 24_000.0
const COUPLED_E2E_FS = 24_000.0
const COUPLED_E2E_SEED = 7
const COUPLED_E2E_CFO_BINS = 0.08

coupled_e2e_payload(n::Integer) =
    Bool[isodd(count_ones(41i + 9)) for i in 1:Int(n)]

function coupled_e2e_stable_normal(n::Integer, seed::Integer)
    state = UInt64(seed)
    samples = Vector{Float64}(undef, Int(n))
    for i in eachindex(samples)
        total = 0
        for _ in 1:12
            state = state * UInt64(6_364_136_223_846_793_005) +
                    UInt64(1_442_695_040_888_963_407)
            total += Int(state >> 48)
        end
        # Twelve U(0, 65535) draws have mean 393210 and variance nearly 65536^2.
        samples[i] = (total - 393_210) / 65_536.0
    end
    samples
end

function coupled_e2e_impaired_waveform(m, bits, snr_db::Real)
    waveform = CoupledE2EModulations.modulate(
        m, bits, COUPLED_E2E_FC, COUPLED_E2E_FS,
    )
    sample = collect(0:length(waveform)-1)
    rotated = waveform .* exp.(
        2im * pi * COUPLED_E2E_CFO_BINS .* sample ./ Int(m.fft_length),
    )
    sigma = sqrt(10.0^(-Float64(snr_db) / 10) / 2)
    noise = coupled_e2e_stable_normal(2 * length(rotated), COUPLED_E2E_SEED)
    rotated .+ sigma .* (
        noise[1:length(rotated)] .+ im .* noise[length(rotated)+1:end]
    )
end

function coupled_e2e_errors(m, bits, snr_db::Real)
    impaired = coupled_e2e_impaired_waveform(m, bits, snr_db)
    metrics, cfo = CoupledE2EModulations.demodulate(
        m, length(bits), impaired, COUPLED_E2E_FC, COUPLED_E2E_FS,
    )
    (; errors = count((metrics .> 0) .!= bits), metrics, cfo)
end

function coupled_e2e_candidates(m, bits, snr_db::Real)
    impaired = coupled_e2e_impaired_waveform(m, bits, snr_db)
    code = CoupledE2EJuna._code(m)
    layout = CoupledE2EJuna._layout(m, COUPLED_E2E_FS)
    yparts = CoupledE2EJuna._branch_observations(m, impaired)
    initial_candidate = CoupledE2EJuna._initial_candidate(
        m, code, layout, yparts)
    direct = CoupledE2EJuna._coupled_candidate(
        m, code, layout, yparts, initial_candidate)
    dispatched = CoupledE2EJuna._juna_candidate(
        m, code, layout, yparts, initial_candidate)
    (; impaired, code, layout, initial_candidate, direct, dispatched)
end

function coupled_e2e_candidate_errors(m, code, candidate, bits)
    decoded = CoupledE2EJuna._payload_from_metrics(
        m, code, candidate.posterior_metric)
    count(decoded .!= bits)
end

@testset verbose = true "Coupled receiver on clean and impaired signals" begin
    @testset "seeded noise is stable across Julia versions" begin
        @test coupled_e2e_stable_normal(6, COUPLED_E2E_SEED) == [
            0.4285736083984375,
            -0.6252593994140625,
            -0.103546142578125,
            -0.25347900390625,
            -1.189239501953125,
            -1.18536376953125,
        ]
        @test coupled_e2e_stable_normal(6, COUPLED_E2E_SEED) !=
              coupled_e2e_stable_normal(6, COUPLED_E2E_SEED + 1)
    end

    @testset "clean three-block payload roundtrips exactly" begin
        m = CoupledE2EJuna.CoupledModulation()
        bits = coupled_e2e_payload(2 * 170 + 17)
        waveform = CoupledE2EModulations.modulate(
            m, bits, COUPLED_E2E_FC, COUPLED_E2E_FS,
        )
        metrics, cfo = CoupledE2EModulations.demodulate(
            m, length(bits), waveform, COUPLED_E2E_FC, COUPLED_E2E_FS,
        )

        @test length(waveform) == 3 * (1024 + 256)
        @test length(metrics) == length(bits)
        @test all(isfinite, metrics)
        @test (metrics .> 0) == bits
        @test cfo == 0.0
    end

    @testset "fixed residual ICI and AWGN produce more errors at lower SNR" begin
        m = CoupledE2EJuna.CoupledModulation()
        bits = coupled_e2e_payload(CoupledE2EModulations.bitspersymbol(m))
        high = coupled_e2e_errors(m, bits, 12.0)
        edge = coupled_e2e_errors(m, bits, 1.5)
        floor = coupled_e2e_errors(m, bits, 0.0)

        @test high.errors == 0
        @test edge.errors < length(bits) ÷ 2
        @test floor.errors >= edge.errors
        @test all(isfinite, high.metrics)
        @test high.cfo == edge.cfo == floor.cfo == 0.0
    end

    @testset "internal coupled dispatch wins on the mismatched 0 dB channel" begin
        m = CoupledE2EJuna.CoupledModulation()
        lite = CoupledE2EJuna.LiteModulation()
        bits = coupled_e2e_payload(CoupledE2EModulations.bitspersymbol(m))
        f = coupled_e2e_candidates(m, bits, 0.0)

        public_metrics, cfo = CoupledE2EModulations.demodulate(
            m, length(bits), f.impaired, COUPLED_E2E_FC, COUPLED_E2E_FS,
        )
        lite_metrics, _ = CoupledE2EModulations.demodulate(
            lite, length(bits), f.impaired, COUPLED_E2E_FC, COUPLED_E2E_FS,
        )
        initial_errors = coupled_e2e_candidate_errors(
            m, f.code, f.initial_candidate, bits)
        direct_errors = coupled_e2e_candidate_errors(m, f.code, f.direct, bits)
        dispatched_errors = coupled_e2e_candidate_errors(
            m, f.code, f.dispatched, bits,
        )
        public_errors = count((public_metrics .> 0) .!= bits)
        lite_errors = count((lite_metrics .> 0) .!= bits)

        @test CoupledE2EJuna._candidate_is_better(
            f.initial_candidate, f.direct)
        @test f.dispatched.posterior_metric == f.direct.posterior_metric
        @test f.dispatched.syndrome_weight <
              f.initial_candidate.syndrome_weight
        @test (f.initial_candidate.syndrome_weight,
               f.direct.syndrome_weight,
               initial_errors, direct_errors) == (130, 99, 22, 17)
        @test direct_errors < initial_errors
        @test dispatched_errors == direct_errors
        @test public_errors == dispatched_errors
        @test public_errors < lite_errors
        @test public_metrics != lite_metrics
        @test cfo == 0.0
    end

    @testset "proxy-selected candidate has a bounded truth-error tradeoff" begin
        m = CoupledE2EJuna.CoupledModulation()
        bits = coupled_e2e_payload(CoupledE2EModulations.bitspersymbol(m))
        f = coupled_e2e_candidates(m, bits, 1.5)
        initial_errors = coupled_e2e_candidate_errors(
            m, f.code, f.initial_candidate, bits)
        selected_errors = coupled_e2e_candidate_errors(
            m, f.code, f.dispatched, bits,
        )

        @test CoupledE2EJuna._candidate_is_better(
            f.initial_candidate, f.direct)
        @test f.dispatched.syndrome_weight <
              f.initial_candidate.syndrome_weight
        @test (f.initial_candidate.syndrome_weight,
               f.dispatched.syndrome_weight,
               initial_errors, selected_errors) == (16, 0, 1, 0)
        @test selected_errors <= initial_errors + 4
        @test selected_errors < length(bits) ÷ 2
        initial_syndrome_weight = f.initial_candidate.syndrome_weight
        selected_syndrome_weight = f.dispatched.syndrome_weight
        @info "C,z refinement proxy/truth tradeoff" initial_syndrome_weight selected_syndrome_weight initial_errors selected_errors
    end

    @testset "valid 3 dB initial candidate is retained" begin
        m = CoupledE2EJuna.CoupledModulation()
        bits = coupled_e2e_payload(CoupledE2EModulations.bitspersymbol(m))
        f = coupled_e2e_candidates(m, bits, 3.0)

        @test f.initial_candidate.ldpc_valid
        @test f.initial_candidate.syndrome_weight == 0
        @test coupled_e2e_candidate_errors(
            m, f.code, f.initial_candidate, bits) == 0
        @test f.dispatched.posterior_metric ==
              f.initial_candidate.posterior_metric
    end

    @testset "warmed one-block decode remains correct" begin
        m = CoupledE2EJuna.CoupledModulation()
        bits = coupled_e2e_payload(CoupledE2EModulations.bitspersymbol(m))
        impaired = coupled_e2e_impaired_waveform(m, bits, 12.0)

        # Warm compilation and LDPC/layout caches before measuring runtime.
        CoupledE2EModulations.demodulate(
            m, length(bits), impaired, COUPLED_E2E_FC, COUPLED_E2E_FS,
        )
        elapsed = @elapsed metrics, _ = CoupledE2EModulations.demodulate(
            m, length(bits), impaired, COUPLED_E2E_FC, COUPLED_E2E_FS,
        )

        @test (metrics .> 0) == bits
        @info "C,z refinement warmed one-block decode" seconds = elapsed
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("C,z refinement checks passed")
end
