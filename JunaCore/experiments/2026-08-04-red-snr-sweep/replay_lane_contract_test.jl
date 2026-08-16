#!/usr/bin/env julia

# Focused contract for the UACR phase/delay replay semantics used by the Blue
# campaign. The registered package replay wrapper includes this file as
# mandatory package evidence.

using Test

const HELPER_ROOT = @__DIR__

include(joinpath(HELPER_ROOT, "replay_lane.jl"))
using .ReplayLane

@testset "MAT loads only for capture files" begin
    @test !isdefined(ReplayLane, :MAT)
end

function fixture_capture(; tracking::Symbol=:theta_hat,
                         phase=zeros(24), step::Integer=3,
                         snapshots::Integer=12)
    h = ones(ComplexF64, 1, snapshots)
    ReplayCapture(h, Float64.(phase), 8.0, 2.0, step, 1, "fixture";
                  tracking)
end

@testset "UACR replay tracking contract" begin
    @testset "tracking identity survives MAT-like loading" begin
        params = Dict("fs_delay" => 8.0, "fc" => 2.0, "fs_time" => 2.0)
        h = reshape(ComplexF64.(1:16), 2, 2, 4)
        phi = reshape(collect(0.0:0.1:1.5), 2, 8)
        theta = phi .+ 10

        phi_capture = capture_from_dict(Dict(
            "h_hat" => h, "params" => params, "phi_hat" => phi,
        ); receiver=2, name="phi")
        theta_capture = capture_from_dict(Dict(
            "h_hat" => h, "params" => params, "theta_hat" => theta,
        ); receiver=1, name="theta")

        @test phi_capture.tracking === :phi_hat
        @test theta_capture.tracking === :theta_hat
        @test_throws UndefKeywordError ReplayCapture(
            ones(ComplexF64, 1, 2), zeros(4), 8.0, 2.0, 2, 1,
            "ambiguous")
        copied = ReplayCapture(
            copy(phi_capture.h), copy(phi_capture.phase), phi_capture.fs,
            phi_capture.fc, phi_capture.step, phi_capture.receiver,
            phi_capture.name; tracking=phi_capture.tracking)
        @test copied.tracking === :phi_hat
    end

    @testset "snapshot one maps to phase offset zero" begin
        phase = collect(0.0:0.1:2.3)
        capture = fixture_capture(; phase, step=3)
        input = ComplexF64[1 + 0im, 2 - 0.5im]
        first = apply_capture(capture, input; snapshot=1)
        second = apply_capture(capture, input; snapshot=2)
        @test first ≈ input .* cis.(phase[1:2]) atol=1e-14 rtol=0
        @test second ≈ input .* cis.(phase[4:5]) atol=1e-14 rtol=0
        support = replay_support(capture, length(input); snapshot=2)
        @test support.q0 == 3
        @test support.phase_start_index == 4
        @test support.phase_stop_index == 5
    end

    @testset "theta is phase only" begin
        phase = fill(pi / 3, 24)
        capture = fixture_capture(; tracking=:theta_hat, phase)
        input = ComplexF64[1, 2, -1, 0.5]
        result = apply_capture(capture, input; snapshot=2,
                               return_support=true)
        @test result.waveform ≈ input .* cis(pi / 3) atol=1e-14 rtol=0
        @test result.replay_support.left_guard == 0
        @test result.replay_support.right_guard == 0
        @test result.replay_support.relative_indices == 0:3
        @test result.replay_support.nominal_samples == 4
    end

    @testset "h_hat uses official not-a-knot time interpolation" begin
        taps = reshape(ComplexF64[
            0.2 + 0.1im, 1.1 - 0.4im, -0.3 + 0.8im,
            0.7 + 0.2im, -0.9 - 0.5im, 0.4 + 1.2im,
        ], 1, :)
        capture = ReplayCapture(
            taps, zeros(40), 8.0, 2.0, 4, 1, "h-spline";
            tracking=:theta_hat)
        expected = ComplexF64[
            1.1 - 0.4im,
            0.6536458333333334 - 0.07057291666666665im,
            0.18833333333333335 + 0.2895833333333334im,
            -0.17114583333333333 + 0.6049479166666668im,
            -0.3 + 0.8im,
            -0.12479166666666663 + 0.8200520833333335im,
            0.22250000000000003 + 0.6937500000000001im,
            0.5585416666666668 + 0.4705729166666668im,
            0.7 + 0.2im,
        ]
        @test apply_capture(capture, ones(ComplexF64, 9); snapshot=2) ≈
            expected atol=2e-13 rtol=2e-13
    end

    @testset "phi uses official not-a-knot cubic delay warp" begin
        # Fixed SciPy CubicSpline (default not-a-knot) golden fixture. The
        # phase values encode delay in samples through delta=phi*fs/(2*pi*fc).
        delta = [0.0, 0.1, -0.1, 0.05, 0.2, -0.15, 0.3, -0.25,
                 0.1, -0.05, 0.0, 0.0, 0.0, 0.0, 0.0]
        phase = delta .* (pi / 2)
        capture = fixture_capture(
            ; tracking=:phi_hat, phase, step=4, snapshots=8)
        input = ComplexF64[
            1 + 0.2im, -0.3 + 0.7im, 0.5 - 0.4im,
            1.2 + 0.1im, -0.8 - 0.6im, 0.2 + 1.1im,
        ]
        result = apply_capture(capture, input; snapshot=2,
                               return_support=true)
        expected = ComplexF64[
            0.0 + 0.0im,
            0.48206415595024 + 0.7743461120407386im,
            -0.12017687204049338 + 0.8534841326926429im,
            0.987387342187282 - 0.22344352916940227im,
            1.2782945110961055 - 0.28081407228375654im,
            -0.7434979897876673 - 0.6147464462362374im,
            0.20764847247541973 + 0.9991634058044243im,
            0.0 + 0.0im,
        ]
        @test result.waveform ≈ expected atol=2e-13 rtol=2e-13
        support = result.replay_support
        @test support.q0 == 4
        @test support.left_guard == 1
        @test support.right_guard == 1
        @test support.relative_indices == -1:6
        @test support.nominal_indices == 2:7
        @test support.nominal_samples == 6
        @test support.output_samples == 8
        @test support.map_is_strictly_increasing
    end

    @testset "guards reach a fixed point" begin
        delta = zeros(18)
        # q0=5. The nominal interval first asks for one left guard; that new
        # point asks for two, after which the interval is stable.
        delta[4] = 1.5
        delta[5] = 1.2
        delta[6:9] .= 0.5
        phase = delta .* (2pi * 2.0 / 8.0)
        capture = fixture_capture(
            ; tracking=:phi_hat, phase, step=5, snapshots=8)
        support = replay_support(capture, 4; snapshot=2)
        @test support.left_guard == 2
        @test support.right_guard == 0
        @test support.relative_indices == -2:3
    end

    @testset "support is strict and never clamped" begin
        positive_delay = fill(2pi * 2.0 / 8.0 * 2, 16)
        left = fixture_capture(
            ; tracking=:phi_hat, phase=positive_delay, step=1,
            snapshots=16)
        left_error = try
            replay_support(left, 4; snapshot=1)
            nothing
        catch error
            error
        end
        @test left_error isa ArgumentError
        @test occursin("left phase support", sprint(showerror, left_error))

        negative_delay = fill(-2pi * 2.0 / 8.0 * 3, 8)
        right = fixture_capture(
            ; tracking=:phi_hat, phase=negative_delay, step=2,
            snapshots=12)
        right_error = try
            replay_support(right, 4; snapshot=3)
            nothing
        catch error
            error
        end
        @test right_error isa ArgumentError
        @test occursin("right phase support", sprint(showerror, right_error))

        tap_limited = ReplayCapture(
            ones(ComplexF64, 1, 4), zeros(20), 8.0, 2.0, 2, 1,
            "tap-limited"; tracking=:theta_hat)
        tap_error = try
            replay_support(tap_limited, 5; snapshot=2)
            nothing
        catch error
            error
        end
        @test tap_error isa ArgumentError
        @test occursin("tap snapshot support", sprint(showerror, tap_error))
    end

    @testset "non-monotone phi map is rejected" begin
        delta = zeros(20)
        delta[5:8] .= [0.0, 2.0, -1.0, 0.0]
        capture = fixture_capture(
            ; tracking=:phi_hat,
            phase=delta .* (2pi * 2.0 / 8.0), step=4, snapshots=8)
        error = try
            replay_support(capture, 4; snapshot=2)
            nothing
        catch exception
            exception
        end
        @test error isa ArgumentError
        @test occursin("strictly increasing", sprint(showerror, error))
    end

    @testset "safe snapshot bounds account for phi guards" begin
        phase = fill(2pi * 2.0 / 8.0 * 2, 40)
        capture = fixture_capture(
            ; tracking=:phi_hat, phase, step=4, snapshots=10)
        bounds = replay_snapshot_bounds(capture, 4)
        @test bounds.first == 2
        @test bounds.last >= bounds.first
        @test replay_support(capture, 4; snapshot=bounds.first).q0 == 4
    end
end

@testset "phi guard retains a boundary impulse" begin
    one_sample_phase = 2pi * 2.0 / 8.0
    capture = fixture_capture(
        ; tracking=:phi_hat, phase=fill(one_sample_phase, 24),
        step=1, snapshots=12)
    result = apply_capture(
        capture, ComplexF64[1, 0, 0, 0]; snapshot=2,
        return_support=true)

    @test result.replay_support.left_guard == 1
    @test result.replay_support.right_guard == 0
    @test result.replay_support.nominal_indices == 2:5
    @test result.waveform ≈ ComplexF64[im, 0, 0, 0, 0] atol=1e-14 rtol=0
end

@testset "negative phi guard retains the right boundary impulse" begin
    one_sample_phase = 2pi * 2.0 / 8.0
    capture = fixture_capture(
        ; tracking=:phi_hat, phase=fill(-one_sample_phase, 24),
        step=1, snapshots=12)
    result = apply_capture(
        capture, ComplexF64[0, 0, 0, 1]; snapshot=2,
        return_support=true)

    @test result.replay_support.left_guard == 0
    @test result.replay_support.right_guard == 1
    @test result.replay_support.nominal_indices == 1:4
    @test result.waveform ≈ ComplexF64[0, 0, 0, 0, -im] atol=1e-14 rtol=0
end

include(joinpath(HELPER_ROOT, "benchmark_port.jl"))
using .BenchmarkPort

@testset "benchmark consumes replay support" begin
    phase = fill(2pi * 2.0 / 8.0 * 2, 80)
    capture = BenchmarkPort.ReplayLane.ReplayCapture(
        ones(ComplexF64, 1, 20), phase, 8.0, 2.0, 4, 1, "power";
        tracking=:phi_hat)
    result = BenchmarkPort.replay_at_modem_rate(
        capture, ComplexF64[1, 2, 3, 4]; snapshot=2, modem_fs=8.0,
        return_support=true)
    @test result.replay_support.nominal_output_samples == 4
    @test length(result.waveform) == 6
    @test BenchmarkPort._nominal_replay_power(result) ≈
        sum(abs2, result.waveform) / 4 atol=1e-14 rtol=0

    theta = BenchmarkPort.ReplayLane.ReplayCapture(
        copy(capture.h), copy(capture.phase), capture.fs, capture.fc,
        capture.step, capture.receiver, capture.name; tracking=:theta_hat)
    @test BenchmarkPort._compact_capture_digest(capture) !=
          BenchmarkPort._compact_capture_digest(theta)
end

println("UACR_REPLAY_CONTRACT_PASS")
