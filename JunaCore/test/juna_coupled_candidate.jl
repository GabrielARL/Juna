#!/usr/bin/env julia
#
# Turn the bounded C/W/z solution into an LDPC candidate and
# expose it through the same public Modulations boundary as Lite and Full.
#
# Run alone: julia --project=. test/juna_coupled_candidate.jl
# Via runner: julia --project=. test/runtests.jl coupled-candidate

using Test
using JunaCore

const CoupledCandidateJuna = JunaCore.Juna
const CoupledCandidateModulations = JunaCore.Modulations
const COUPLED_FC = 24_000.0
const COUPLED_FS = 24_000.0

function coupled_candidate_fixture()
    m = CoupledCandidateJuna.LiteModulation()
    code = CoupledCandidateJuna._code(m)
    layout = CoupledCandidateJuna._layout(m, COUPLED_FS)
    payload = Bool[isodd(count_ones(37i + 11))
                   for i in 1:CoupledCandidateModulations.bitspersymbol(m)]
    message = CoupledCandidateJuna._build_message(m, code, payload)
    codeword = CoupledCandidateJuna._encode(code, message)
    waveform = CoupledCandidateJuna._modulate_block(m, layout, codeword)
    yparts = CoupledCandidateJuna._branch_observations(m, waveform)
    initial_candidate = CoupledCandidateJuna._initial_candidate(
        m, code, layout, yparts)
    (; m, code, layout, payload, yparts, initial_candidate)
end

@testset verbose = true "C,W,z candidate selection" begin
    @testset "optimized state becomes a finite decoder candidate" begin
        f = coupled_candidate_fixture()
        problem = CoupledCandidateJuna._coupled_problem_from_receiver(
            f.m, f.code, f.layout, f.yparts,
        )
        initial = CoupledCandidateJuna._initial_coupled_state(
            f.m, f.code, f.layout, problem, f.initial_candidate,
        )
        solved = CoupledCandidateJuna._coupled_wcz_solve(
            problem, initial;
            config = CoupledCandidateJuna._CoupledOptimizerConfig(steps = 2),
        )
        candidate = CoupledCandidateJuna._coupled_state_candidate(
            f.m, f.code, f.layout, problem, solved.state,
        )

        @test length(candidate.lpost_metric) == f.code.n
        @test all(isfinite, candidate.lpost_metric)
        @test isfinite(candidate.pilot_mse)
        @test isfinite(candidate.tie_mse)
        @test isfinite(candidate.score)
        @test CoupledCandidateJuna._payload_from_metrics(
            f.m, f.code, candidate.lpost_metric,
        ) == f.payload
    end

    @testset "coupled candidate selection cannot regress the initial candidate" begin
        f = coupled_candidate_fixture()
        config = CoupledCandidateJuna._CoupledOptimizerConfig(steps = 2)
        direct = CoupledCandidateJuna._coupled_candidate(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate;
            config = config,
        )
        selected = CoupledCandidateJuna._juna_wcz_candidate(
            f.m, f.code, f.layout, f.yparts, f.initial_candidate;
            config = config,
        )

        @test all(isfinite, direct.lpost_metric)
        @test !CoupledCandidateJuna._juna_better(
            f.initial_candidate, f.initial_candidate)
        @test !CoupledCandidateJuna._juna_better(
            selected, f.initial_candidate)
        @test CoupledCandidateJuna._payload_from_metrics(
            f.m, f.code, selected.lpost_metric,
        ) == f.payload
    end

    @testset "CoupledModulation declares and executes the coupled objective" begin
        m = CoupledCandidateJuna.CoupledModulation()
        alias = JunaCore.Juna.CoupledModulation()

        @test m.mode === :coupled
        @test alias.mode === :coupled
        @test CoupledCandidateJuna.receiver_profile(m) === :coupled
        @test CoupledCandidateModulations.refinement_objective(m) === :coupled_cwz
        @test isvalid(m, COUPLED_FC, COUPLED_FS)
        @test !isvalid(
            CoupledCandidateJuna.CoupledModulation(
                bpc = 1, ldpc_k = 170, ldpc_n = 680,
            ),
            COUPLED_FC,
            COUPLED_FS,
        )

        bits = Bool[isodd(count_ones(19i + 3)) for i in 1:128]
        waveform = CoupledCandidateModulations.modulate(m, bits, COUPLED_FC, COUPLED_FS)
        metrics, cfo = CoupledCandidateModulations.demodulate(
            m, length(bits), waveform, COUPLED_FC, COUPLED_FS,
        )

        @test metrics isa Vector{Float64}
        @test length(metrics) == length(bits)
        @test all(isfinite, metrics)
        @test (metrics .> 0) == bits
        @test cfo == 0.0
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Profiled C,z checks passed")
end
