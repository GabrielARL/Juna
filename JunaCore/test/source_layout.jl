#!/usr/bin/env julia
#
# Migrated source layout and facade pruning — src/ contains exactly the
# migrated subset (JunaCore.jl, Juna.jl, Modulations.jl, LDPC.jl, and the
# three juna/ receiver files this package retains: common.jl,
# frame_wide_ldpc.jl, lite.jl), and only three public facades are exposed:
# JunaStandard, JunaPartialFFT, JunaLite. The nine-receiver source
# repository's other receiver implementation files and facades
# (FullyCoupled, TurboMAP, ProfiledGradient, ProfiledCzFrame,
# CrcProfiledCzFrame, CrcConditionedJointCwzFrame, FrameWideLDPC, FrameRLS)
# are deliberately absent from this package.
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

@testset verbose = true "Migrated source layout and facade pruning" begin
    junacore = joinpath(SOURCE_LAYOUT_SRC, "JunaCore.jl")
    wrapper = joinpath(SOURCE_LAYOUT_SRC, "Juna.jl")
    modulations = joinpath(SOURCE_LAYOUT_SRC, "Modulations.jl")
    ldpc = joinpath(SOURCE_LAYOUT_SRC, "LDPC.jl")
    common = joinpath(SOURCE_LAYOUT_SRC, "juna", "common.jl")
    frame_wide_ldpc = joinpath(SOURCE_LAYOUT_SRC, "juna", "frame_wide_ldpc.jl")
    lite = joinpath(SOURCE_LAYOUT_SRC, "juna", "lite.jl")

    @testset "migrated files are present" begin
        @test isfile(junacore)
        @test isfile(wrapper)
        @test isfile(modulations)
        @test isfile(ldpc)
        @test isfile(common)
        @test isfile(frame_wide_ldpc)
        @test isfile(lite)
    end

    @testset "wrapper wires exactly common/frame_wide_ldpc/lite, in that order" begin
        wrapper_text = read(wrapper, String)
        include_common = "include(joinpath(@__DIR__, \"juna\", \"common.jl\"))"
        include_frame_wide = "include(joinpath(@__DIR__, \"juna\", \"frame_wide_ldpc.jl\"))"
        include_lite = "include(joinpath(@__DIR__, \"juna\", \"lite.jl\"))"

        @test occursin(include_common, wrapper_text)
        @test occursin(include_frame_wide, wrapper_text)
        @test occursin(include_lite, wrapper_text)

        # "exactly" also means no other juna/*.jl include crept back in.
        @test count("include(joinpath(@__DIR__, \"juna\"", wrapper_text) == 3

        common_at = findfirst(include_common, wrapper_text)
        frame_wide_at = findfirst(include_frame_wide, wrapper_text)
        lite_at = findfirst(include_lite, wrapper_text)
        @test common_at !== nothing
        @test frame_wide_at !== nothing
        @test lite_at !== nothing
        @test first(common_at) < first(frame_wide_at) < first(lite_at)
    end

    @testset "pruned receiver files are absent from src/" begin
        @test !isfile(joinpath(SOURCE_LAYOUT_SRC, "FixedPathChannel.jl"))
        for name in ("full", "coupled", "fully_coupled", "turbo_map",
                     "guarded_physical", "gradient_guarded",
                     "profiled_gradient", "profiled_cz_frame")
            @test !isfile(joinpath(SOURCE_LAYOUT_SRC, "juna", "$(name).jl"))
        end
    end

    @testset "only the three migrated facades are exposed" begin
        @test isdefined(JunaCore, :JunaLite)
        @test isdefined(JunaCore, :JunaStandard)
        @test isdefined(JunaCore, :JunaPartialFFT)

        for facade in (:JunaFullyCoupled, :JunaTurboMAP, :JunaProfiledGradient,
                       :JunaProfiledCzFrame, :JunaCrcProfiledCzFrame,
                       :JunaCrcConditionedJointCwzFrame, :JunaFrameWideLDPC,
                       :JunaFrameRLS)
            @test !isdefined(JunaCore, facade)
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA source layout checks passed")
end
