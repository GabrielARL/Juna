#!/usr/bin/env julia
#
# Payload and block sizing — the frame arithmetic behind BER/PSR/goodput accounting.
#
# Paper claims protected (papers/main.tex):
#   sec:method (lines 1966-1971)      Benchmark geometry n1024_cp256_..._r0p25_..._ip2:
#                                     N=1024, CP=256, LDPC rate 0.25, inner pilot
#                                     every 2nd message bit.
#   fig:packet-tanner-example caption Message row k=340 splits into 170 known
#   (lines 670-679, esp. 674)         inner-pilot anchors + 170 unknown payload bits.
#   eq:goodput (lines 1934-1939)      k_payload excludes inner-pilot message bits —
#                                     so bitspersymbol must count ONLY the 170
#                                     unknown bits, never the full k=340 or n=1360.
#
# Every expected value below is a hard literal derived from the paper constants,
# NOT recomputed from the modulation's own fields — so a drifted default (e.g.
# ldpc_k != 340) or a wrong formula fails loudly instead of cancelling out.
#
# If this fails: the denominators behind payload BER, PSR, and goodput are wrong,
# and every measured-channel table becomes unverifiable.
#
# Run alone:  julia --project=. test/payload_block_sizing.jl
# Via runner: julia --project=. test/runtests.jl sizing

using Test
using JunaCore

const PayloadSizingModulations = JunaCore.Modulations
const PayloadSizingJuna = JunaCore.Juna

const PAYLOAD_SIZING_FC = 24_000.0
const PAYLOAD_SIZING_FS = 24_000.0

@testset verbose = true "JUNA payload and block sizing" begin
    m = PayloadSizingJuna.LiteModulation()
    @test PayloadSizingModulations.init(m, PAYLOAD_SIZING_FC, PAYLOAD_SIZING_FS) === nothing

    @testset "defaults are the paper benchmark geometry (main.tex:1966-1971)" begin
        @test Int(m.nc) == 1024        # N
        @test Int(m.np) == 256         # CP length
        @test Int(m.ldpc_k) == 340
        @test Int(m.ldpc_n) == 1360
        @test m.ldpc_k / m.ldpc_n == 0.25  # r0p25
    end

    @testset "block = 1280 samples; payload = 170 of k=340 bits (main.tex:674)" begin
        @test PayloadSizingJuna._blocklen(m) == 1280           # 1024 + 256
        # ip2: 170 inner-pilot anchors leave 170 unknown payload bits per block.
        @test PayloadSizingModulations.bitspersymbol(m) == 170
    end

    @testset "positive block count = ceil(nbits / 170); zero is rejected" begin
        @test_throws ArgumentError PayloadSizingJuna._nblocks(m, 0)
        @test PayloadSizingJuna._nblocks(m, 1) == 1
        @test PayloadSizingJuna._nblocks(m, 170) == 1
        @test PayloadSizingJuna._nblocks(m, 171) == 2
        @test PayloadSizingJuna._nblocks(m, 340) == 2
        @test PayloadSizingJuna._nblocks(m, 341) == 3
    end

    @testset "signallength counts whole 1280-sample blocks" begin
        @test_throws ArgumentError PayloadSizingModulations.signallength(
            m, 0, PAYLOAD_SIZING_FC, PAYLOAD_SIZING_FS)
        @test PayloadSizingModulations.signallength(
            m, 170, PAYLOAD_SIZING_FC, PAYLOAD_SIZING_FS) == 1280
        @test PayloadSizingModulations.signallength(
            m, 171, PAYLOAD_SIZING_FC, PAYLOAD_SIZING_FS) == 2560
    end

    @testset "inner-pilot density sets the payload share (ip-off: 340, ip3: 226)" begin
        no_inner = PayloadSizingJuna.LiteModulation(inner_pilot_ratio = 0.0)
        @test PayloadSizingModulations.bitspersymbol(no_inner) == 340  # whole message row
        @test PayloadSizingJuna._nblocks(no_inner, 341) == 2

        # Every 3rd message position pinned: ceil(340/3) = 114 anchors, 226 payload.
        every_third_inner = PayloadSizingJuna.LiteModulation(inner_pilot_ratio = 1 / 3)
        @test PayloadSizingModulations.bitspersymbol(every_third_inner) == 226
    end

    # The paper's packets carry a known sync preamble (main.tex:1953); the LFM
    # length 2048 is a package constant (_SYNC_LEN, src/juna/common.jl:62), not a
    # paper number — this pins the pre+postamble overhead at 2*2048 = 4096 samples.
    @testset "sync adds exactly 4096 samples regardless of block count" begin
        sync_enabled = PayloadSizingJuna.LiteModulation(sync = true)
        @test PayloadSizingModulations.signallength(
            sync_enabled, 170, PAYLOAD_SIZING_FC, PAYLOAD_SIZING_FS) == 1280 + 4096
        @test PayloadSizingModulations.signallength(
            sync_enabled, 171, PAYLOAD_SIZING_FC, PAYLOAD_SIZING_FS) == 2560 + 4096
    end

    @testset "all-inner-pilot config has no payload and is invalid" begin
        no_payload = PayloadSizingJuna.LiteModulation(inner_pilot_ratio = 1.0)
        @test PayloadSizingModulations.bitspersymbol(no_payload) == 0
        @test !isvalid(no_payload, PAYLOAD_SIZING_FC, PAYLOAD_SIZING_FS)
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA payload and block sizing checks passed")
end
