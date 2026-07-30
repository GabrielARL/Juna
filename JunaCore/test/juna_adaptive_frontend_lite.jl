using Test
using JunaCore

const AdaptiveJuna = JunaCore.Juna

@testset "pilot-conditioned P=1/P=4 Lite front end" begin
    m = AdaptiveJuna.AdaptiveLiteModulation(
        nc=128, np=16, partial_fft_parts=4,
        pilot_ratio=1 / 3, inner_pilot_ratio=1 / 2,
        frontend_guard_min_relative_gain=0.02)
    layout = AdaptiveJuna._layout(m, 9_600.0)
    pilots = layout.pilot_idx

    @testset "no validated multi-part gain collapses to P=1" begin
        yparts = zeros(ComplexF64, 4, Int(m.nc))
        gains = ComplexF64[0.2 + 0.1im, 0.3 - 0.1im, 0.1, 0.4]
        for (position, carrier) in pairs(pilots), part in 1:4
            yparts[part, carrier] =
                gains[part] * layout.pilot_syms[position]
        end
        choice = AdaptiveJuna._pilot_guarded_front_end_choice(
            m, layout, yparts)
        @test choice.selected_parts == 1
        @test choice.p1_loss - choice.partial_loss <
              AdaptiveJuna._FRONTEND_GUARD_MIN_ABSOLUTE_GAIN
    end

    @testset "held-out pilots retain a genuinely useful multi-part model" begin
        yparts = zeros(ComplexF64, 4, Int(m.nc))
        for (position, carrier) in pairs(pilots)
            symbol = layout.pilot_syms[position]
            a = 0.25 + 0.5 * sin(0.31 * position)
            b = (1 - 0.7a) / 0.3
            yparts[1, carrier] = a * symbol
            yparts[2, carrier] = b * symbol
        end
        choice = AdaptiveJuna._pilot_guarded_front_end_choice(
            m, layout, yparts)
        @test choice.selected_parts == 4
        @test choice.partial_loss <
              (1 - m.frontend_guard_min_relative_gain) * choice.p1_loss
    end

    @testset "constructor and objective identify the guarded receiver" begin
        @test AdaptiveJuna.receiver_profile(m) === :adaptive_lite
        @test JunaCore.Modulations.refinement_objective(m) ===
              :pilot_guarded_posterior_anchor_ls
        @test_throws ArgumentError AdaptiveJuna.AdaptiveLiteModulation(
            frontend_guard_min_relative_gain=-0.1)
    end

    @testset "frame-wide seed applies the same guard independently per block" begin
        frame = AdaptiveJuna.FrameWideLDPCModulation(
            nc=128, np=16, partial_fft_parts=4,
            pilot_ratio=1 / 3, inner_pilot_ratio=1 / 2,
            frame_receiver=:adaptive_lite,
            frontend_guard_min_relative_gain=0.02)
        @test frame.frame_receiver === :adaptive_lite

        frame_layout = AdaptiveJuna._layout(frame, 9_600.0)
        observations = zeros(ComplexF64, 4, Int(frame.nc), 2)
        gains = ComplexF64[0.2 + 0.1im, 0.3 - 0.1im, 0.1, 0.4]
        for (position, carrier) in pairs(frame_layout.pilot_idx), part in 1:4
            observations[part, carrier, 1] =
                gains[part] * frame_layout.pilot_syms[position]
        end
        for (position, carrier) in pairs(frame_layout.pilot_idx)
            symbol = frame_layout.pilot_syms[position]
            a = 0.25 + 0.5 * sin(0.31 * position)
            b = (1 - 0.7a) / 0.3
            observations[1, carrier, 2] = a * symbol
            observations[2, carrier, 2] = b * symbol
        end

        seed = AdaptiveJuna._frame_adaptive_seed_equalized(
            frame, frame_layout, observations)
        @test seed.selected_parts == [1, 4]
        @test size(seed.equalized) == (Int(frame.nc), 2)
    end
end
