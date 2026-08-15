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

@testset "UACR phi_hat applies phase and delay while theta_hat is phase-only" begin
    fs = 10.0
    fc = 10.0
    step = 1
    taps = ones(ComplexF64, 1, 8)
    one_sample_phase = 2pi * fc / fs
    phase = fill(one_sample_phase, 16)
    input = zeros(ComplexF64, 6)
    input[3] = 1

    phase_only = ReplayCapture(
        taps, phase, fs, fc, step, 1, "theta"; tracking=:phase)
    delay_phase = ReplayCapture(
        taps, phase, fs, fc, step, 1, "phi"; tracking=:delay_phase)
    theta_output = apply_capture(phase_only, input)
    phi_output = apply_capture(delay_phase, input)

    @test argmax(abs.(theta_output)) == 3
    @test argmax(abs.(phi_output)) == 2
    @test abs(phi_output[2]) ≈ 1.0 atol=1e-12
end

@testset "UACR phi_hat delay uses cubic interpolation" begin
    samples = ComplexF64[(index - 1)^3 for index in 1:8]
    offsets = fill(0.25, length(samples))
    warped = ReplayLane._cubic_time_warp(samples, offsets)

    @test warped[1:7] ≈ ComplexF64[(index - 0.75)^3 for index in 1:7] atol=1e-10
    @test warped[8] == 0
end

@testset "capture schema preserves theta_hat versus phi_hat semantics" begin
    params = Dict(
        "fs_delay" => 10.0,
        "fc" => 10.0,
        "fs_time" => 10.0,
    )
    h_hat = ones(ComplexF64, 1, 1, 4)
    phase = zeros(1, 16)

    theta = capture_from_dict(Dict(
        "h_hat" => h_hat, "theta_hat" => phase, "params" => params))
    phi = capture_from_dict(Dict(
        "h_hat" => h_hat, "phi_hat" => phase, "params" => params))

    @test theta.tracking === :phase
    @test phi.tracking === :delay_phase
end
