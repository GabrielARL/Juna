#!/usr/bin/env julia
#
# OFDM layout — carrier plan: DC null, outer pilot comb, data carriers, band partition.
#
# Paper claims protected (reference papers/gab/joe.tex):
#   fig:packet-tanner-example           The package reference geometry has 1023
#                                       active carriers: 341 outer comb pilots and
#                                       682 data carriers, of which 680 carry the
#                                       QPSK codeword.
#   ssec:packet-tanner-example          Outer pilots are frequency-domain comb
#                                       pilots on known subcarriers.
#   eq:ofdm5-band-index                 Bandwise processing partitions the bins into
#                                       contiguous frequency bands.
#
# IMPLEMENTATION/PROFILE BOUNDARY:
#   * JunaCore and the corrected packet figure agree on 1023 active, 341 pilot,
#     682 data, and n=1360 coded bits with two deterministic filler carriers.
#   * The package fixes 16 ridge-LS bands (_PARTIAL_FFT_NBANDS); the separately
#     labeled paper benchmark uses 4. This suite pins the package default and
#     checks the four-band benchmark configuration separately.
#   * bw is a fraction of the fixed 24 kHz reference width; fs determines the
#     fraction of the complex-baseband FFT needed to realize that width.
#   * dc0 tunes the RF centre in kHz and does not shift baseband carrier bins.
# If one of these asserts changes intentionally, update the literal, package
# default table, paper benchmark, and walkthrough contract together.
#
# If this fails: transmitter and receiver disagree about which carrier carries what —
# pilots train on data, data lands on pilots, or the band partition shifts.
#
# Run alone:  julia --project=. test/ofdm_layout.jl
# Via runner: julia --project=. test/runtests.jl layout

using Test
using JunaCore

const OfdmLayoutJuna = JunaCore.Juna

const OFDM_LAYOUT_FC = 24_000.0
const OFDM_LAYOUT_FS = 24_000.0

@testset verbose = true "JUNA OFDM layout" begin
    m = OfdmLayoutJuna.LiteModulation()
    layout = OfdmLayoutJuna._layout(m, OFDM_LAYOUT_FS)

    @testset "layout shapes and dimensions" begin
        @test layout.active isa Vector{Int}
        @test layout.pilot_idx isa Vector{Int}
        @test layout.data_idx isa Vector{Int}
        @test layout.pilot_syms isa Vector{ComplexF64}
        @test layout.bands isa Vector{Vector{Int}}
        @test layout.band_ids isa Vector{Int}
        @test length(layout.band_ids) == 1024                    # one id per FFT bin
        @test length(layout.pilot_syms) == length(layout.pilot_idx)
    end

    @testset "active set: DC nulled, in range, sorted, unique" begin
        @test !(1 in layout.active)                              # FFT bin 1 = DC, never used
        @test all(1 .<= layout.active .<= 1024)
        @test allunique(layout.active)
        @test issorted(layout.active)
    end

    @testset "carrier counts: 1023 active = 341 pilots + 682 data" begin
        @test length(layout.active) == 1023
        @test length(layout.pilot_idx) == 341
        @test length(layout.data_idx) == 682
    end

    @testset "outer comb: pilot every 3rd active bin starting at bin 2 (p3)" begin
        @test all(k -> (k - 2) % 3 == 0, layout.pilot_idx)
        @test all(k -> (k - 2) % 3 != 0, layout.data_idx)
        @test layout.pilot_idx[1:8] == [2, 5, 8, 11, 14, 17, 20, 23]
    end

    @testset "pilots and data carriers partition the active set" begin
        @test isempty(intersect(layout.pilot_idx, layout.data_idx))
        @test sort(union(layout.pilot_idx, layout.data_idx)) == layout.active
    end

    # Both transmitter and receiver must regenerate this exact sign pattern; a
    # changed PRBS breaks over-the-air compatibility while every count test passes.
    @testset "pilot symbols: deterministic BPSK +/-1 with a pinned prefix" begin
        @test all(s -> s == ComplexF64(1.0, 0.0) || s == ComplexF64(-1.0, 0.0),
                  layout.pilot_syms)
        @test real.(layout.pilot_syms[1:8]) == [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0]
    end

    @testset "16 contiguous near-even bands cover exactly the active set" begin
        @test length(layout.bands) == 16                         # package default
        @test all(!isempty, layout.bands)
        @test reduce(vcat, layout.bands) == layout.active        # ordered partition
        band_sizes = length.(layout.bands)
        @test maximum(band_sizes) - minimum(band_sizes) <= 1     # near-even split
        @test all(k -> layout.band_ids[k] > 0, layout.active)
        inactive = setdiff(1:1024, layout.active)
        @test all(k -> layout.band_ids[k] == 0, inactive)
    end

    @testset "four-band benchmark configuration uses contiguous receiver bands" begin
        benchmark = OfdmLayoutJuna.LiteModulation(partial_fft_nbands = 4)
        benchmark_layout = OfdmLayoutJuna._layout(benchmark, OFDM_LAYOUT_FS)
        @test length(benchmark_layout.bands) == 4
        @test reduce(vcat, benchmark_layout.bands) == benchmark_layout.active
        @test maximum(length.(benchmark_layout.bands)) -
              minimum(length.(benchmark_layout.bands)) <= 1
        @test all(k -> benchmark_layout.band_ids[k] > 0,
                  benchmark_layout.active)
    end

    @testset "QPSK capacity: 1360 coded bits use 680 of the 682 data carriers" begin
        @test OfdmLayoutJuna._ndata_tones(m, 1360) == 680
        @test 680 <= length(layout.data_idx)                     # 2 filler carriers remain
        @test Int(m.ldpc_n) <= 2 * length(layout.data_idx)       # isvalid capacity rule
    end

    @testset "layout cache: reused until the pilot comb changes" begin
        cached = OfdmLayoutJuna._layout(m, OFDM_LAYOUT_FS)
        @test cached === layout                                  # identical signature -> same object

        m.pilot_ratio = 1 / 4
        changed = OfdmLayoutJuna._layout(m, OFDM_LAYOUT_FS)
        @test changed !== layout                                 # signature changed -> rebuilt
        @test OfdmLayoutJuna._pilot_spacing(m) == 4
        @test all(k -> (k - 2) % 4 == 0, changed.pilot_idx)
        @test sort(union(changed.pilot_idx, changed.data_idx)) == changed.active
    end

    @testset "fixed 24 kHz bw reference and RF-only dc0 tuning" begin
        half_band = OfdmLayoutJuna.LiteModulation(bw = 0.5)
        base = OfdmLayoutJuna._layout(half_band, OFDM_LAYOUT_FS)
        shifted = OfdmLayoutJuna.LiteModulation(bw = 0.5, dc0 = Int16(1))
        shifted_layout = OfdmLayoutJuna._layout(shifted, OFDM_LAYOUT_FS)

        @test shifted_layout.active == base.active
        @test length(base.active) == 511
        @test !(1 in shifted_layout.active)
        @test allunique(shifted_layout.active)
        @test sort(union(shifted_layout.pilot_idx, shifted_layout.data_idx)) ==
              shifted_layout.active

        rf_edges(layout, centre) = begin
            signed_bins = [(bin - 1) <= 1024 ÷ 2 ? bin - 1 : bin - 1 - 1024
                           for bin in layout.active]
            frequencies = centre .+ signed_bins .* (OFDM_LAYOUT_FS / 1024)
            extrema(frequencies)
        end
        bin_width = OFDM_LAYOUT_FS / 1024
        base_edges = rf_edges(base, 24_000.0)
        shifted_edges = rf_edges(shifted_layout, 25_000.0)
        @test isapprox(base_edges[1], 18_000.0; atol=bin_width)
        @test isapprox(base_edges[2], 30_000.0; atol=bin_width)
        @test isapprox(shifted_edges[1], 19_000.0; atol=bin_width)
        @test isapprox(shifted_edges[2], 31_000.0; atol=bin_width)

        red = OfdmLayoutJuna.LiteModulation(bw=0.4, dc0=Int16(1))
        red_layout = OfdmLayoutJuna._layout(red, 9_600.0)
        @test length(red_layout.active) == 1023
        @test OfdmLayoutJuna._occupied_bandwidth_hz(red) == 9_600.0
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA OFDM layout checks passed")
end
