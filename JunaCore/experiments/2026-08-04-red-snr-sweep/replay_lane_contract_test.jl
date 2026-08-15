#!/usr/bin/env julia

using Test

include(joinpath(@__DIR__, "replay_lane.jl"))
using .ReplayLane

@testset "replay phase starts with the selected channel snapshot" begin
    step = 2
    taps = ones(ComplexF64, 1, 3)
    phase = collect(0.0:0.1:1.0)
    capture = ReplayCapture(taps, phase, 10.0, 100.0, step, 1, "fixture")
    output = apply_capture(capture, ones(ComplexF64, 2); snapshot=2)

    @test output[1] ≈ cis(phase[(2 - 1) * step + 1])
    @test output[2] ≈ cis(phase[(2 - 1) * step + 2])
end
