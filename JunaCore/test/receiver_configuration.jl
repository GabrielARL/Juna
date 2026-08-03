#!/usr/bin/env julia
#
# Receiver configuration — retained public modes plus internal solver profiles.
#
# Paper claims protected (reference papers/gab/joe.tex):
#   sec:solver                    The paper implements exactly two receivers:
#                                 JUNA-lite (ssec:junalite) and JUNA-Wz
#                                 (ssec:gradient-juna). Here: mode :lite / :full.
#   sec:method                    The benchmark geometry n1024_cp256_sym1_p3_r0p25_dc4_sig1_ip2:
#                                 N=1024, CP=256, outer pilot every 3rd active carrier,
#                                  LDPC rate 0.25 (k=340, n=1360), inner pilot every
#                                  2nd message bit. init() must reset a modulation to
#                                  this geometry so every experiment measures the
#                                  receiver, not a drifted configuration. Known
#                                  divergence: the paper string carries dc4 (sparsity
#                                  setting d_cfg=4); the package pins
#                                  ldpc_npc=3, the make-ldpc per-column check count —
#                                  a related but differently parameterized setting.
#   tab:hyperparams                4 Partial-FFT temporal views (partial_fft_parts = 4).
#
# :coupled and :full remain internal implementation profiles used by the
# Profiled C,z receiver and numerical audits. :robust is a legacy alias for
# :full. Their optimizer configuration is part of the restored closure.
#
# If this fails: experiments could silently run the wrong receiver or a non-paper
# frame geometry, invalidating any comparison against the paper's tables.
#
# Run alone:  julia --project=. test/receiver_configuration.jl
# Via runner: julia --project=. test/runtests.jl config

using Test
using JunaCore

const ReceiverConfigJuna = JunaCore.Juna
const ReceiverConfigModulations = JunaCore.Modulations

const RECEIVER_CONFIG_FC = 24_000.0
const RECEIVER_CONFIG_FS = 24_000.0

@testset verbose = true "JUNA receiver configuration" begin
    default = ReceiverConfigJuna.Modulation()
    lite = ReceiverConfigJuna.LiteModulation(mode = :full)
    full = ReceiverConfigJuna.FullModulation(mode = :lite)
    coupled = ReceiverConfigJuna.CoupledModulation(mode = :lite)
    profiled_cz = ReceiverConfigJuna.ProfiledCzFrameModulation()
    crc_profiled_cz = ReceiverConfigJuna.CrcProfiledCzFrameModulation()
    conditioned_cwz =
        ReceiverConfigJuna.CrcConditionedJointCwzFrameModulation()
    legacy = ReceiverConfigJuna.Modulation(mode = :robust)

    @testset "constructors force their public or internal implementation profile" begin
        @test default isa ReceiverConfigModulations.Modulation
        @test default.mode === :lite                 # package default receiver is JUNA-lite
        @test lite.mode === :lite                    # LiteModulation wins over mode kwarg
        @test full.mode === :full                    # FullModulation wins over mode kwarg
        @test coupled.mode === :coupled              # CoupledModulation wins over mode kwarg
        @test legacy.mode === :robust                # legacy spelling preserved on the struct
        @test JunaCore.JunaLite.Modulation(mode = :full).mode === :lite
        @test JunaCore.Juna.FullModulation(mode = :lite).mode === :full
        @test JunaCore.Juna.CoupledModulation(mode = :lite).mode === :coupled
        @test profiled_cz.frame_receiver === :profiled_cz
        @test crc_profiled_cz.mode === :crc_profiled_cz_frame
        @test crc_profiled_cz.frame_crc_bits == 16
        @test conditioned_cwz.cz_conditioned_joint
        @test JunaCore.JunaProfiledCzFrame.Modulation().frame_receiver ===
              :profiled_cz
        @test JunaCore.JunaCrcProfiledCzFrame.Modulation().frame_crc_bits == 16
        @test JunaCore.JunaCrcConditionedJointCwzFrame.Modulation().
              cz_conditioned_joint
    end

    @testset "receiver_profile distinguishes public and internal solver profiles" begin
        @test ReceiverConfigJuna.receiver_profile(:lite) === :lite
        @test ReceiverConfigJuna.receiver_profile(:full) === :full
        @test ReceiverConfigJuna.receiver_profile(:robust) === :full
        @test ReceiverConfigJuna.receiver_profile(:coupled) === :coupled
        @test ReceiverConfigJuna.receiver_profile(default) === :lite
        @test ReceiverConfigJuna.receiver_profile(lite) === :lite
        @test ReceiverConfigJuna.receiver_profile(full) === :full
        @test ReceiverConfigJuna.receiver_profile(legacy) === :full
        @test ReceiverConfigJuna.receiver_profile(coupled) === :coupled
        @test ReceiverConfigJuna.receiver_profile(profiled_cz) ===
              :frame_wide_ldpc
        @test ReceiverConfigJuna.receiver_profile(crc_profiled_cz) ===
              :frame_wide_ldpc
    end

    @testset "isvalid accepts only the known receiver modes" begin
        @test isvalid(default, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(lite, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(full, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(coupled, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(legacy, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(profiled_cz, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(crc_profiled_cz, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(conditioned_cwz, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test !isvalid(ReceiverConfigJuna.Modulation(mode = :unknown),
                       RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test !isvalid(ReceiverConfigJuna.CoupledModulation(
                           bpc = 1, ldpc_k = 170, ldpc_n = 680,
                       ), RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
    end

    @testset "every accepted receiver setting executes and unavailable settings are rejected" begin
        compact = (
            nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
            partial_fft_parts=2, partial_fft_nbands=2,
            pilot_ratio=1 / 3, inner_pilot_ratio=0.0,
            refinement_steps=0,
        )
        unavailable = (
            :fully_coupled, :turbo_map, :guarded_physical,
            :gradient_guarded, :profiled_gradient,
        )
        for mode in unavailable
            @test !(mode in ReceiverConfigJuna._RECEIVER_PROFILES)
            @test !isvalid(
                ReceiverConfigJuna.Modulation(; compact..., mode),
                RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        end

        for mode in ReceiverConfigJuna._RECEIVER_PROFILES
            receiver = ReceiverConfigJuna.Modulation(; compact..., mode)
            @test isvalid(receiver, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
            nbits = min(17, ReceiverConfigModulations.bitspersymbol(receiver))
            payload = Bool[isodd(i) for i in 1:nbits]
            waveform = ReceiverConfigModulations.modulate(
                receiver, payload, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
            metrics, _ = ReceiverConfigModulations.demodulate(
                receiver, nbits, waveform,
                RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
            @test (metrics .> 0) == payload
        end

        @test !(:fully_coupled in ReceiverConfigJuna._FRAME_RECEIVER_PROFILES)
        @test !isvalid(
            ReceiverConfigJuna.FrameWideLDPCModulation(
                ; compact..., frame_receiver=:fully_coupled),
            RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        for frame_receiver in ReceiverConfigJuna._FRAME_RECEIVER_PROFILES
            receiver = ReceiverConfigJuna.FrameWideLDPCModulation(
                ; compact..., frame_receiver)
            @test isvalid(receiver, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
            payload = Bool[true, false, true]
            waveform = ReceiverConfigModulations.modulate(
                receiver, payload, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
            metrics, _ = ReceiverConfigModulations.demodulate(
                receiver, length(payload), waveform,
                RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
            @test (metrics .> 0) == payload
        end
    end

    @testset "refinement-step ablations preserve deployed defaults" begin
        wz_default = ReceiverConfigJuna.FullModulation()
        wz_eight = ReceiverConfigJuna.FullModulation(refinement_steps = 8)
        wcz_default = ReceiverConfigJuna.CoupledModulation()
        wcz_twenty = ReceiverConfigJuna.CoupledModulation(refinement_steps = 20)

        @test wz_default.refinement_steps == -1
        @test ReceiverConfigJuna._wz_refinement_steps(wz_default) == 20
        @test ReceiverConfigJuna._wz_refinement_steps(wz_eight) == 8
        @test wcz_default.refinement_steps == -1
        @test ReceiverConfigJuna._wcz_optimizer_config(wcz_default).steps == 8
        @test ReceiverConfigJuna._wcz_optimizer_config(wcz_twenty).steps == 20
        @test ReceiverConfigJuna._wcz_optimizer_config(wcz_twenty).alpha_z ==
              ReceiverConfigJuna._COUPLED_PUBLIC_CONFIG.alpha_z
        @test isvalid(wz_eight, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test isvalid(wcz_twenty, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test !isvalid(ReceiverConfigJuna.FullModulation(refinement_steps = -2),
                       RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)

        ReceiverConfigModulations.init(
            wcz_twenty, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
        @test wcz_twenty.refinement_steps == 20
    end

    # Poison every geometry field and all caches, then check init() restores the
    # paper benchmark geometry exactly, clears the caches, and preserves only the
    # operator's choices: mode and sync.
    @testset "init() resets to the paper geometry and keeps mode and synchronization" begin
        configured = ReceiverConfigJuna.Modulation(
            mode = :full,
            sync = true,
            nc = UInt16(64),
            np = UInt16(16),
            bpc = 1,
            bw = 0.5,
            dc0 = Int16(1),
            pilot_ratio = 0.9,
            inner_pilot_ratio = 0.9,
            ldpc_k = 10,
            ldpc_n = 20,
            ldpc_npc = 7,
            partial_fft_parts = 9,
            partial_fft_nbands = 9,
        )
        configured.code = :stale_code_cache
        configured.layout = :stale_layout_cache
        configured.bp_scratch = :stale_bp_cache

        @test ReceiverConfigModulations.init(configured, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS) === nothing

        @test configured.mode === :full              # operator choice preserved
        @test configured.sync === true               # operator choice preserved

        @test configured.nc == UInt16(1024)          # N = 1024
        @test configured.np == UInt16(256)           # CP length = 256
        @test configured.bpc == 2                    # QPSK
        @test configured.bw == 1.0
        @test configured.dc0 == Int16(0)
        @test configured.pilot_ratio == 1 / 3        # outer pilot every 3rd active carrier (p3)
        @test configured.inner_pilot_ratio == 1 / 2  # inner pilot every 2nd message bit (ip2)
        @test configured.ldpc_k == 340               # rate 340/1360 = 0.25   (r0p25)
        @test configured.ldpc_n == 1360
        @test configured.ldpc_npc == 3               # package setting; paper string says dc4 (see header)
        @test configured.partial_fft_parts == 4      # 4 Partial-FFT views
        @test configured.partial_fft_nbands == 16    # package-default ridge bands

        @test configured.code === nothing            # stale caches cleared
        @test configured.layout === nothing
        @test configured.bp_scratch === nothing
        @test isvalid(configured, RECEIVER_CONFIG_FC, RECEIVER_CONFIG_FS)
    end

    @testset "init derives channel centre offset and fixed-reference bandwidth" begin
        red = ReceiverConfigJuna.LiteModulation()
        @test ReceiverConfigModulations.init(red, 25_000.0, 9_600.0) === nothing
        @test red.dc0 == Int16(1)
        @test red.bw == 0.4
        @test ReceiverConfigJuna._rf_center_hz(red) == 25_000.0
        @test ReceiverConfigJuna._occupied_bandwidth_hz(red) == 9_600.0
        @test ReceiverConfigJuna._rf_band_edges(red) == (20_200.0, 29_800.0)
        @test isvalid(red, 25_000.0, 9_600.0)
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA receiver configuration checks passed")
end
