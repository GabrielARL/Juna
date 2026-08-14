#!/usr/bin/env julia
#
# Public modem interface — the modulate/demodulate boundary every receiver shares.
#
# Paper claims protected (papers/main.tex):
#   sec:method (lines 1919-1964)   All receivers are compared on the same transmitted
#                                  frame through one public modulate/demodulate
#                                  boundary; only the receiver processing differs.
#   eq:goodput (lines 1934-1939)   Throughput accounting divides payload bits by the
#                                  full airtime (CP, pilots, FEC parity, sync all
#                                  included), so payload_rate must equal
#                                  nbits * fs / signallength with real numbers:
#                                  170 bits / 1280 samples, 171 bits / 2560 samples.
#   Modulations.demodulate         Metric sign convention (src/Modulations.jl):
#                                  positive metric = bit 1, negative = bit 0. The
#                                  noiseless loopback below fails on any polarity or
#                                  bit-order regression, which the old all-zeros
#                                  payload could not detect.
#
# If this fails: the public boundary the paper's experimental method depends on is
# broken — signal lengths, metric polarity, or throughput accounting are wrong.
#
# Run alone:  julia --project=. test/public_modem_interface.jl
# Via runner: julia --project=. test/runtests.jl interface

using Test
using JunaCore
using SignalAnalysis: mseq

if !isdefined(@__MODULE__, :PUBLIC_RECEIVER_DESCRIPTORS)
    include(joinpath(@__DIR__, "support", "public_receivers.jl"))
end

const PublicInterfaceModulations = JunaCore.Modulations
const PublicInterfaceJuna = JunaCore.Juna

const PUBLIC_INTERFACE_FC = 24_000.0
const PUBLIC_INTERFACE_FS = 24_000.0

function assert_interface_methods(m)
    @test m isa PublicInterfaceModulations.Modulation
    @test hasmethod(PublicInterfaceModulations.init, Tuple{typeof(m), Float64, Float64})
    @test hasmethod(PublicInterfaceModulations.modulate,
                    Tuple{typeof(m), Vector{Bool}, Float64, Float64})
    @test hasmethod(PublicInterfaceModulations.demodulate,
                    Tuple{typeof(m), Int, Vector{ComplexF64}, Float64, Float64})
    @test hasmethod(PublicInterfaceModulations.bitspersymbol, Tuple{typeof(m)})
    @test hasmethod(PublicInterfaceModulations.signallength,
                    Tuple{typeof(m), Int, Float64, Float64})
    @test hasmethod(Base.isvalid, Tuple{typeof(m), Float64, Float64})
end

# Modulate a deterministic non-trivial pattern, demodulate the clean waveform, and
# require bit-exact recovery. An alternating 1010... pattern (instead of all zeros)
# makes polarity flips and bit reordering visible.
function assert_payload_transfer_contract(m, nbits)
    bits = Vector{Bool}(isodd.(1:nbits))
    signal_len = PublicInterfaceModulations.signallength(
        m, nbits, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
    waveform = PublicInterfaceModulations.modulate(
        m, bits, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)

    @test signal_len isa Int
    @test waveform isa Vector{ComplexF64}
    @test length(waveform) == signal_len   # signallength arithmetic vs actual samples

    metrics, cfo = PublicInterfaceModulations.demodulate(
        m, nbits, waveform, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)

    @test metrics isa Vector{Float64}
    @test length(metrics) == nbits
    @test all(isfinite, metrics)
    @test (metrics .> 0) == bits           # noiseless loopback, positive = bit 1
    @test cfo isa Float64
    @test cfo == 0.0                       # sync disabled -> no CFO estimate
end

function direct_payload_metrics(m, code, candidate, nbits::Integer)
    metrics = Vector{Float64}(undef, Int(nbits))
    next = PublicInterfaceJuna._write_payload_metrics!(
        metrics, 1, m, code, candidate.lpost_metric, Int(nbits))
    @test next == Int(nbits) + 1
    metrics
end

function direct_frame_paths(m, waveform, nbits::Integer)
    _, code, layout, blocks, observations, _ =
        PublicInterfaceJuna._prepare_frame_observations(
            m, nbits, waveform, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
    standard = PublicInterfaceJuna._frame_static_trace(
        m, code, layout, observations, :standard).best
    partial = PublicInterfaceJuna._frame_static_trace(
        m, code, layout, observations, :pfft).best
    juna = PublicInterfaceJuna._frame_receiver_trace(
        m, code, layout, observations; payload_nbits=nbits).best
    payload(candidate) = PublicInterfaceJuna._frame_payload_metrics(
        m, code, candidate.lpost_metric, blocks, nbits)
    (
        standard=payload(standard),
        partial=payload(partial),
        juna=payload(juna),
    )
end

@testset verbose = true "JUNA public modem interface" begin
    m = PublicInterfaceJuna.LiteModulation()

    @testset "interface methods exist and init/isvalid behave" begin
        assert_interface_methods(m)
        @test PublicInterfaceModulations.init(m, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) === nothing
        @test isvalid(m, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
        @test PublicInterfaceModulations.bitspersymbol(m) == 170  # k=340 minus 170 ip2 anchors (main.tex:674)
    end

    @testset "payload transfer: exact block fill (170 bits) and padded (171 bits)" begin
        assert_payload_transfer_contract(m, 170)
        assert_payload_transfer_contract(m, 171)
    end

    @testset "SignalAnalysis m-sequence survives inner/outer-pilot framing" begin
        chips = mseq(8)                 # 2^8 - 1 deterministic +1/-1 chips
        payload = Vector{Bool}(chips .> 0)

        @test length(payload) == 255
        @test count(payload) == 128
        @test count(!, payload) == 127

        tx = PublicInterfaceJuna.LiteModulation()
        @test PublicInterfaceJuna._pilot_spacing(tx) == 3
        @test PublicInterfaceJuna._inner_pilot_spacing(tx) == 2
        @test PublicInterfaceJuna._n_inner(tx, tx.ldpc_k) == 170

        waveform = PublicInterfaceModulations.modulate(
            tx, payload, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
        @test waveform isa Vector{ComplexF64}
        @test length(waveform) == 2 * (Int(tx.nc) + Int(tx.np))

        for descriptor in public_receiver_descriptors()
            rx = public_receiver(descriptor)
            @test PublicInterfaceJuna._pilot_spacing(rx) >= 2
            @test PublicInterfaceJuna._inner_pilot_spacing(rx) >= 1

            receiver_waveform = descriptor.profile === :frame_wide_ldpc ?
                PublicInterfaceModulations.modulate(
                    rx, payload, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) : waveform
            metrics, cfo = PublicInterfaceModulations.demodulate(
                rx, length(payload), receiver_waveform,
                PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
            @test metrics isa Vector{Float64}
            @test length(metrics) == length(payload)
            @test all(isfinite, metrics)
            @test (metrics .> 0) == payload
            @test cfo == 0.0
        end
    end

    @testset "fc/fs sweep preserves every receiver's public roundtrip" begin
        payload = Vector{Bool}(mseq(7) .> 0)  # 127 bits: one non-trivial OFDM block
        carrier_frequencies = (12_000.0, 24_000.0, 48_000.0)
        sample_rates = (9_600.0, 12_000.0, 24_000.0)

        @test length(payload) == 127
        for descriptor in public_receiver_descriptors()
            for fc in carrier_frequencies, fs in sample_rates
                @testset "$(descriptor.name) at fc=$(Int(fc)) Hz, fs=$(Int(fs)) Hz" begin
                    swept = public_receiver(descriptor)
                    @test PublicInterfaceModulations.init(swept, fc, fs) === nothing
                    @test swept.bw == fs / 24_000.0
                    @test swept.dc0 == round(Int16, (fc - 24_000.0) / 1_000.0)
                    @test isvalid(swept, fc, fs)

                    waveform = PublicInterfaceModulations.modulate(
                        swept, payload, fc, fs)
                    @test waveform isa Vector{ComplexF64}
                    @test length(waveform) == PublicInterfaceModulations.signallength(
                        swept, length(payload), fc, fs)
                    @test PublicInterfaceModulations.payload_rate(
                        swept, length(payload), fc, fs) ==
                          length(payload) * fs / length(waveform)

                    metrics, cfo = PublicInterfaceModulations.demodulate(
                        swept, length(payload), waveform, fc, fs)
                    @test length(metrics) == length(payload)
                    @test all(isfinite, metrics)
                    @test (metrics .> 0) == payload
                    @test cfo == 0.0
                end
            end
        end
    end

    @testset "payload_rate matches eq:goodput accounting (main.tex:1934-1939)" begin
        # One 1280-sample block carries 170 payload bits at fs = 24 kHz:
        #   170 * 24000 / 1280 = 3187.5 bit/s.
        # 171 bits force a second block: 171 * 24000 / 2560 = 1603.125 bit/s.
        @test PublicInterfaceModulations.signallength(
            m, 170, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) == 1280
        @test PublicInterfaceModulations.signallength(
            m, 171, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) == 2560
        @test PublicInterfaceModulations.payload_rate(
            m, 170, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) == 3187.5
        @test PublicInterfaceModulations.payload_rate(
            m, 171, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) == 1603.125
        rate = PublicInterfaceModulations.payload_rate(
            m, 171, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
        @test 0 < rate <= PUBLIC_INTERFACE_FS  # payload rate can never exceed sample rate
    end

    @testset "error contract: short waveform and invalid config are rejected" begin
        waveform = PublicInterfaceModulations.modulate(
            m, falses(170), PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
        short_waveform = waveform[1:end - 1]
        for descriptor in public_receiver_descriptors()
            receiver = public_receiver(descriptor)
            @test_throws ArgumentError PublicInterfaceModulations.demodulate(
                receiver, 170, short_waveform,
                PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)

            invalid = public_receiver(descriptor; nc = 1001)  # asymmetric FFT grid
            @test !isvalid(invalid, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
            @test_throws ArgumentError PublicInterfaceModulations.modulate(
                invalid, falses(170), PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
            @test_throws ArgumentError PublicInterfaceModulations.demodulate(
                invalid, 170, waveform, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
        end
    end

    @testset "every receiver's three-path table matches its direct candidates" begin
        payload = Vector{Bool}(mseq(7) .> 0)
        tx = PublicInterfaceJuna.LiteModulation()
        waveform = PublicInterfaceModulations.modulate(
            tx, payload, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)

        # Four different gains within one OFDM symbol create the regime where
        # the partial-FFT combiner is supposed to differ from one standard FFT.
        distorted = copy(waveform)
        gains = ComplexF64[1.45 - 0.35im, 0.62 + 0.75im,
                           -0.35 + 1.2im, 1.05 + 0.18im]
        N = Int(tx.nc)
        L = Int(tx.np)
        for p in 1:Int(tx.partial_fft_parts)
            lo, hi = PublicInterfaceJuna._part_bounds(N, Int(tx.partial_fft_parts), p)
            @views distorted[L+lo:L+hi] .*= gains[p]
        end

        for descriptor in public_receiver_descriptors()
            @testset "$(descriptor.name)" begin
                compared = public_receiver(descriptor)
                tested_waveform = descriptor.profile === :frame_wide_ldpc ?
                    PublicInterfaceModulations.modulate(
                        compared, payload,
                        PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) :
                    waveform
                paths = PublicInterfaceJuna.demodulate_methods(
                    compared, length(payload), tested_waveform,
                    PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                @test keys(paths) == (:standard, :partial, :juna, :provenance)
                @test paths.provenance === descriptor.profile
                for metrics in (paths.standard, paths.partial, paths.juna)
                    @test metrics isa Vector{Float64}
                    @test length(metrics) == length(payload)
                    @test all(isfinite, metrics)
                    @test (metrics .> 0) == payload
                end
                @test paths.standard !== paths.partial
                @test paths.partial !== paths.juna

                public_metrics, _ = PublicInterfaceModulations.demodulate(
                    compared, length(payload), tested_waveform,
                    PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                @test paths.juna == public_metrics

                tested_distorted = if descriptor.profile === :frame_wide_ldpc
                    copy(tested_waveform)
                else
                    distorted
                end
                if descriptor.profile === :frame_wide_ldpc
                    payload_start = if !compared.sync
                        1
                    else
                        PublicInterfaceJuna._synclen(compared) + 1
                    end
                    for p in 1:Int(compared.partial_fft_parts)
                        lo, hi = PublicInterfaceJuna._part_bounds(
                            Int(compared.nc),
                            Int(compared.partial_fft_parts),
                            p,
                        )
                        first_sample = payload_start - 1 + Int(compared.np) + lo
                        last_sample = payload_start - 1 + Int(compared.np) + hi
                        @views tested_distorted[first_sample:last_sample] .*= gains[p]
                    end
                end
                distorted_paths = PublicInterfaceJuna.demodulate_methods(
                    compared, length(payload), tested_distorted,
                    PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                direct_paths = if descriptor.profile === :frame_wide_ldpc
                    direct_frame_paths(
                        compared, tested_distorted, length(payload))
                else
                    code = PublicInterfaceJuna._code(compared)
                    layout = PublicInterfaceJuna._layout(
                        compared, PUBLIC_INTERFACE_FS)
                    yparts = PublicInterfaceJuna._branch_observations(
                        compared, tested_distorted)
                    standard_candidate = PublicInterfaceJuna._standard_candidate(
                        compared, code, layout, yparts)
                    partial_candidate = PublicInterfaceJuna._initial_candidate(
                        compared, code, layout, yparts)
                    juna_candidate = PublicInterfaceJuna._juna_candidate(
                        compared, code, layout, yparts, partial_candidate)
                    (
                        standard=direct_payload_metrics(
                            compared, code, standard_candidate, length(payload)),
                        partial=direct_payload_metrics(
                            compared, code, partial_candidate, length(payload)),
                        juna=direct_payload_metrics(
                            compared, code, juna_candidate, length(payload)),
                    )
                end

                @test distorted_paths.standard == direct_paths.standard
                @test distorted_paths.partial == direct_paths.partial
                @test distorted_paths.juna == direct_paths.juna
                @test count((distorted_paths.standard .> 0) .!= payload) > 0
                @test (distorted_paths.partial .> 0) == payload
                if descriptor.profile === :standard
                    # The standard baseline's own column IS the one-tap
                    # branch: it must inherit that branch's failure here,
                    # not be rescued by another receiver's refinement.
                    @test distorted_paths.juna == distorted_paths.standard
                elseif descriptor.profile === :frame_wide_ldpc &&
                       compared.cz_crc_no_harm
                    # Standard fails CRC for this deterministic distortion, so
                    # no-harm C,z must select a certified gradient checkpoint.
                    no_harm = PublicInterfaceJuna._cz_crc_no_harm_last_trace(
                        compared)
                    @test no_harm.selected_source === :gradient
                    @test no_harm.selection_reason === :crc_rescue
                    @test !no_harm.standard_crc_valid
                    @test no_harm.rescue_is_gradient
                    @test no_harm.rescue_crc_valid
                    @test (distorted_paths.juna .> 0) == payload
                else
                    # JUNA-Lite remains unchanged and recovers this waveform.
                    @test (distorted_paths.juna .> 0) == payload
                end
                @test distorted_paths.standard != distorted_paths.partial
            end
        end
    end

    @testset "configuration controls are explicit across every receiver mode" begin
        configurations = (
            (name = "short CP", kwargs = (np = 64,), requires_bpsk = false,
             requires_shifted_band = false),
            (name = "large FFT", kwargs = (nc = 2048, np = 64),
             requires_bpsk = false, requires_shifted_band = false),
            (name = "compact BPSK code",
             kwargs = (bpc = 1, ldpc_k = 170, ldpc_n = 680),
             requires_bpsk = true, requires_shifted_band = false),
            (name = "rate-one-half code", kwargs = (ldpc_k = 340, ldpc_n = 680),
             requires_bpsk = false, requires_shifted_band = false),
            (name = "eight partial views", kwargs = (partial_fft_parts = 8,),
             requires_bpsk = false, requires_shifted_band = false),
            (name = "minimum trained p16 pilot comb", kwargs = (pilot_ratio = 1 / 16,),
             requires_bpsk = false, requires_shifted_band = false),
            (name = "maximum supported partial views", kwargs = (partial_fft_parts = 16,),
             requires_bpsk = false, requires_shifted_band = false),
            (name = "half-band large FFT",
             kwargs = (nc = 2048, np = 128, bw = 0.5),
             requires_bpsk = false, requires_shifted_band = true),
            (name = "three-quarter-reference-band large FFT",
             kwargs = (nc = 2048, np = 128, bw = 0.75),
             requires_bpsk = false, requires_shifted_band = true),
        )
        source_payload = Vector{Bool}(mseq(9) .> 0)

        for descriptor in public_receiver_descriptors(), config in configurations
            @testset "$(descriptor.name) / $(config.name)" begin
                configured = public_receiver(descriptor; config.kwargs...)
                supported = (!config.requires_bpsk || descriptor.supports_bpsk) &&
                    (!config.requires_shifted_band || descriptor.supports_shifted_band)
                @test isvalid(configured, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS) ==
                      supported

                if supported
                    bps = PublicInterfaceModulations.bitspersymbol(configured)
                    for nbits in (1, bps, bps + 1)
                        @testset "$nbits payload bits" begin
                            payload = Bool[
                                isodd(count_ones(37i + 11)) for i in 1:nbits
                            ]
                            waveform = PublicInterfaceModulations.modulate(
                                configured, payload,
                                PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                            metrics, cfo = PublicInterfaceModulations.demodulate(
                                configured, nbits, waveform,
                                PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)

                            @test length(waveform) ==
                                  PublicInterfaceModulations.signallength(
                                      configured, nbits,
                                      PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                            @test length(metrics) == nbits
                            @test all(isfinite, metrics)
                            @test (metrics .> 0) == payload
                            @test cfo == 0.0
                        end
                    end
                else
                    @test_throws ArgumentError PublicInterfaceModulations.modulate(
                        configured, source_payload[1:170],
                        PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                end
            end
        end
    end

    @testset "non-default rate and pilot geometry keeps the strongest clean front end" begin
        kwargs = (
            nc = 1024,
            bpc = 2,
            pilot_ratio = 0.76,
            inner_pilot_ratio = 0.17,
            ldpc_k = 261,
            ldpc_n = 522,
        )
        payload = Vector{Bool}(isodd.(1:217))

        for descriptor in public_receiver_descriptors()
            @testset "$(descriptor.name)" begin
                m = public_receiver(descriptor; kwargs...)
                @test isvalid(m, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                @test PublicInterfaceModulations.bitspersymbol(m) == length(payload)

                waveform = PublicInterfaceModulations.modulate(
                    m, payload, PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                paths = PublicInterfaceJuna.demodulate_methods(
                    m, length(payload), waveform,
                    PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)
                metrics, cfo = PublicInterfaceModulations.demodulate(
                    m, length(payload), waveform,
                    PUBLIC_INTERFACE_FC, PUBLIC_INTERFACE_FS)

                @test (paths.standard .> 0) == payload
                @test (paths.juna .> 0) == payload
                if descriptor.profile === :pfft
                    # The pure partial combiner is exactly the weak front
                    # end this pilot geometry exposes: its public failure
                    # here is WHY every refined receiver must select the
                    # stronger standard initial candidate above. No fallback may hide it.
                    @test metrics == paths.partial
                    @test count((metrics .> 0) .!= payload) > 0
                else
                    @test (metrics .> 0) == payload
                end
                @test all(isfinite, metrics)
                @test cfo == 0.0
            end
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("JUNA public modem interface checks passed")
end
