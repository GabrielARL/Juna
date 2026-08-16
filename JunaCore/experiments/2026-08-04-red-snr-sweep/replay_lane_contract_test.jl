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

@testset "UACR tap evolution uses not-a-knot cubic interpolation" begin
    step = 4
    snapshot_values = ComplexF64[(index - 1)^3 for index in 1:6]
    taps = reshape(snapshot_values, 1, :)
    phase = zeros(Float64, 64)
    capture = ReplayCapture(taps, phase, 16.0, 100.0, step, 1, "cubic")
    output = apply_capture(capture, ones(ComplexF64, 9); snapshot=2)

    positions = 1 .+ (0:8) ./ step
    @test output[1:9] ≈
        ComplexF64[position^3 for position in positions] atol=1e-10
    @test output[end] == 0
end

@testset "UACR support is zero-filled and phase bounds are strict" begin
    taps = ComplexF64[1 2]
    phase = zeros(Float64, 16)
    capture = ReplayCapture(taps, phase, 10.0, 100.0, 1, 1, "support")
    output = apply_capture(capture, ones(ComplexF64, 4); snapshot=2)

    @test output[1] ≈ 2.0 + 0im
    @test output[2:end] == zeros(ComplexF64, length(output) - 1)

    short_phase = ReplayCapture(
        ones(ComplexF64, 1, 8), zeros(Float64, 2),
        10.0, 100.0, 1, 1, "short-phase")
    @test_throws ArgumentError apply_capture(
        short_phase, ones(ComplexF64, 3))
end

@testset "tracking-specific packet guards retain complete UACR support" begin
    taps = ones(ComplexF64, 2, 10)
    phase = zeros(Float64, 9)
    theta = ReplayCapture(
        taps, phase, 10.0, 100.0, 2, 1, "theta"; tracking=:phase)
    phi = ReplayCapture(
        taps, phase, 10.0, 100.0, 2, 1, "phi"; tracking=:delay_phase)

    @test capture_snapshot_limit(theta, 4) == 3
    @test capture_snapshot_limit(phi, 4) == 2
    @test length(apply_capture(theta, ones(ComplexF64, 4))) == 6
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
