#!/usr/bin/env julia
#
# Source layout and public facades — src/ contains the Lite closure
# plus the approved C,z refinement closure. The complete C,z receiver uses the
# shared W,z and C,W,z implementation files, while unrelated receiver files
# and facades remain absent. JunaStandard remains a compatibility alias.
#
# If this fails: package composition drifted — a migrated file went missing,
# the Juna.jl include order/count changed, a pruned receiver file
# reappeared, or a foreign facade leaked back into JunaCore.jl.
#
# Run alone:  julia --project=. test/source_layout.jl
# Via runner: julia --project=. test/runtests.jl packaging

using Test
using JunaCore

const SOURCE_LAYOUT_ROOT = get(ENV, "JUNA_CORE_ROOT",
    normpath(joinpath(dirname(pathof(JunaCore)), "..")))
const SOURCE_LAYOUT_SRC = joinpath(SOURCE_LAYOUT_ROOT, "src")

@testset verbose = true "Source layout and public facades" begin
    junacore = joinpath(SOURCE_LAYOUT_SRC, "JunaCore.jl")
    wrapper = joinpath(SOURCE_LAYOUT_SRC, "Juna.jl")
    modulations = joinpath(SOURCE_LAYOUT_SRC, "Modulations.jl")
    ldpc = joinpath(SOURCE_LAYOUT_SRC, "LDPC.jl")
    common = joinpath(SOURCE_LAYOUT_SRC, "juna", "common.jl")
    frame_wide_ldpc = joinpath(SOURCE_LAYOUT_SRC, "juna", "frame_wide_ldpc.jl")
    lite = joinpath(SOURCE_LAYOUT_SRC, "juna", "lite.jl")
    full = joinpath(SOURCE_LAYOUT_SRC, "juna", "full.jl")
    coupled = joinpath(SOURCE_LAYOUT_SRC, "juna", "coupled.jl")
    cz_refinement = joinpath(SOURCE_LAYOUT_SRC, "juna", "cz_refinement.jl")

    @testset "required files are present" begin
        @test isfile(junacore)
        @test isfile(wrapper)
        @test isfile(modulations)
        @test isfile(ldpc)
        @test isfile(common)
        @test isfile(frame_wide_ldpc)
        @test isfile(lite)
        @test isfile(full)
        @test isfile(coupled)
        @test isfile(cz_refinement)
    end

    @testset "wrapper wires the complete approved closure in source order" begin
        wrapper_text = read(wrapper, String)
        include_common = "include(joinpath(@__DIR__, \"juna\", \"common.jl\"))"
        include_frame_wide = "include(joinpath(@__DIR__, \"juna\", \"frame_wide_ldpc.jl\"))"
        include_lite = "include(joinpath(@__DIR__, \"juna\", \"lite.jl\"))"
        include_full = "include(joinpath(@__DIR__, \"juna\", \"full.jl\"))"
        include_coupled = "include(joinpath(@__DIR__, \"juna\", \"coupled.jl\"))"
        include_cz_refinement =
            "include(joinpath(@__DIR__, \"juna\", \"cz_refinement.jl\"))"

        @test occursin(include_common, wrapper_text)
        @test occursin(include_frame_wide, wrapper_text)
        @test occursin(include_lite, wrapper_text)
        @test occursin(include_full, wrapper_text)
        @test occursin(include_coupled, wrapper_text)
        @test occursin(include_cz_refinement, wrapper_text)

        @test count("include(joinpath(@__DIR__, \"juna\"", wrapper_text) == 6

        common_at = findfirst(include_common, wrapper_text)
        frame_wide_at = findfirst(include_frame_wide, wrapper_text)
        lite_at = findfirst(include_lite, wrapper_text)
        full_at = findfirst(include_full, wrapper_text)
        coupled_at = findfirst(include_coupled, wrapper_text)
        cz_refinement_at = findfirst(include_cz_refinement, wrapper_text)
        @test common_at !== nothing
        @test frame_wide_at !== nothing
        @test lite_at !== nothing
        @test full_at !== nothing
        @test coupled_at !== nothing
        @test cz_refinement_at !== nothing
        @test first(common_at) < first(frame_wide_at) < first(lite_at) <
              first(full_at) < first(coupled_at) < first(cz_refinement_at)
    end

    @testset "unrelated receiver files are absent from src/" begin
        @test !isfile(joinpath(SOURCE_LAYOUT_SRC, "FixedPathChannel.jl"))
        for name in ("fully_coupled", "turbo_map", "guarded_physical",
                     "gradient_guarded", "profiled_gradient")
            @test !isfile(joinpath(SOURCE_LAYOUT_SRC, "juna", "$(name).jl"))
        end
    end

    @testset "approved facades and the compatibility alias are exposed" begin
        @test isdefined(JunaCore, :JunaLite)
        @test isdefined(JunaCore, :JunaOFDMFEC)
        @test isdefined(JunaCore, :JunaStandard)
        @test isdefined(JunaCore, :JunaPartialFFT)
        @test JunaCore.JunaOFDMFEC.Modulation().mode === :ofdm_fec
        @test JunaCore.JunaStandard.Modulation().mode === :standard
        @test JunaCore.Juna.receiver_profile(
                  JunaCore.JunaStandard.Modulation()) === :ofdm_fec
        @test isdefined(JunaCore, :JunaCzRefinement)
        @test isdefined(JunaCore, :JunaCrcCzRefinement)
        @test isdefined(JunaCore, :JunaCrcJointCwz)
        @test JunaCore.JunaCzRefinement.Modulation().frame_receiver ===
              :cz_refinement
        @test JunaCore.JunaCrcCzRefinement.Modulation().mode ===
              :crc_cz_refinement
        @test JunaCore.JunaCrcJointCwz.Modulation().
              joint_cwz_enabled

        for facade in (:JunaFullyCoupled, :JunaTurboMAP,
                       :JunaProfiledGradient, :JunaFrameWideLDPC,
                       :JunaFrameRLS)
            @test !isdefined(JunaCore, facade)
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA source layout checks passed")
end
