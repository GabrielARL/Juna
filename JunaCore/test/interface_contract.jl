#!/usr/bin/env julia
#
# Interface contract — the end-to-end executable contract for every receiver path.
#
# Paper claims protected (reference papers/gab/joe.tex):
#   sec:method                       OFDM+FEC, Partial-FFT+FEC, and JUNA share one
#                                    transmitted frame and one public boundary; only
#                                    receiver processing differs. Here: the OFDM+FEC,
#                                    Partial-FFT, Lite, and Profiled C,z modulations
#                                    satisfy the same public contract.
#   tab:hyperparams                  Acceptance is payload-exact recovery. The
#                                    noiseless loopback below applies exactly that
#                                    rule: every payload bit recovered, bit for bit.
#   eq:goodput                       payload_rate(128 bits) == 128*24000/1280 == 2400 bit/s.
#   sec:solver; ssec:junalite        :lite runs JUNA-lite. The
#                                    internal :full and :coupled implementations supply
#                                    the Profiled C,z closure and remain without separate
#                                    public facades.
#
# The noiseless loopback runs UNCONDITIONALLY (it is deterministic and cheap).
# Set JUNA_INTERFACE_ROUNDTRIP=1 (or `test/runtests.jl roundtrip`) to additionally
# run the extended multi-block loopback on every receiver.
#
# If this fails: a receiver path crashed, produced non-finite metrics, or can no
# longer decode its own clean transmission — nothing downstream is trustworthy.
#
# Run alone:  julia --project=. test/interface_contract.jl
# Strict:     JUNA_INTERFACE_ROUNDTRIP=1 julia --project=. test/interface_contract.jl
# Via runner: julia --project=. test/runtests.jl contract   (or: roundtrip)

using Test
using JunaCore

if !isdefined(@__MODULE__, :PUBLIC_RECEIVER_DESCRIPTORS)
    include(joinpath(@__DIR__, "support", "public_receivers.jl"))
end

const Modulations = JunaCore.Modulations
const Juna = JunaCore.Juna

const ROOT = get(ENV, "JUNA_CORE_ROOT",
    normpath(joinpath(dirname(pathof(JunaCore)), "..")))
const FC = 24_000.0
const FS = 24_000.0

# A non-JUNA modem proves that refinement is an optional capability of the
# shared interface, not a requirement silently imposed on every modulation.
struct InterfaceOnlyModulation <: Modulations.Modulation end
Modulations.init(::InterfaceOnlyModulation, fc, fs) = nothing
Modulations.bitspersymbol(::InterfaceOnlyModulation) = 1
Modulations.signallength(::InterfaceOnlyModulation, nbits, fc, fs) = Int(nbits)
Modulations.modulate(::InterfaceOnlyModulation, bits, fc, fs) =
    ComplexF64[bit ? -1.0 : 1.0 for bit in bits]
Modulations.demodulate(::InterfaceOnlyModulation, nbits, x, fc, fs) =
    (Float64[real(x[i]) < 0 ? 1.0 : -1.0 for i in 1:Int(nbits)], 0.0)
Base.isvalid(::InterfaceOnlyModulation, fc, fs) = true

function assert_ldpc_tools_present()
    # LDPC.build shells out to these vendored binaries; _tool() would silently fall
    # back to bare names on PATH, so their presence must be pinned here.
    for tool in ("make-ldpc", "make-gen", "print-pchk")
        path = joinpath(ROOT, "tools", "ldpc", tool)
        @test isfile(path)
    end
end

function assert_ldpc_create_input_contract()
    for (k, n) in ((0, 40), (40, 40), (41, 40), (-1, 40))
        @test_throws ArgumentError JunaCore.LDPC.create(k, n, "1 evenboth 2")
    end
    @test_throws ArgumentError JunaCore.LDPC.create(true, 40, "1 evenboth 2")
    @test_throws ArgumentError JunaCore.LDPC.create(20.0, 40, "1 evenboth 2")
    @test_throws ArgumentError JunaCore.LDPC.create(20, 40, "1 evenboth")
    @test_throws ArgumentError JunaCore.LDPC.create(20, 40, "1 unknown 2")
    @test_throws ArgumentError JunaCore.LDPC.create(
        20, 40, "1 evenboth 2 cycle")
    @test_throws ArgumentError JunaCore.LDPC.create(
        20, 40, "1 evenboth 2 unexpected")
    @test_throws ArgumentError JunaCore.LDPC.create(
        20, 40, "1 evenboth 2 no4cycle extra")
end

function assert_ofdm_fec_compatibility()
    compact = (
        nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1 / 3, inner_pilot_ratio=0.0,
        refinement_steps=0,
    )
    canonical = Juna.OFDMFECModulation(; compact...)
    legacy = Juna.StandardModulation(; compact...)
    payload = Bool[isodd(i) for i in 1:17]
    waveform = Modulations.modulate(canonical, payload, FC, FS)
    canonical_metrics, _ = Modulations.demodulate(
        canonical, length(payload), waveform, FC, FS)
    legacy_metrics, _ = Modulations.demodulate(
        legacy, length(payload), waveform, FC, FS)
    @test legacy_metrics == canonical_metrics

    canonical_methods = Juna.demodulate_methods(
        canonical, length(payload), waveform, FC, FS)
    legacy_methods = Juna.demodulate_methods(
        legacy, length(payload), waveform, FC, FS)
    @test canonical_methods.provenance === :ofdm_fec
    @test legacy_methods.provenance === :standard
    @test legacy_methods.ofdm_fec == canonical_methods.ofdm_fec
    @test legacy_methods.standard === legacy_methods.ofdm_fec

    code = Juna._code(canonical)
    layout = Juna._layout(canonical, FS)
    observations = Juna._branch_observations(canonical, waveform)
    @test Juna._standard_candidate(canonical, code, layout, observations) ==
          Juna._ofdm_fec_candidate(canonical, code, layout, observations)

    frame_canonical = Juna.FrameWideLDPCModulation(
        ; compact..., frame_receiver=:ofdm_fec)
    frame_legacy = Juna.FrameWideLDPCModulation(
        ; compact..., frame_receiver=:standard)
    frame_payload = Bool[true, false, true]
    frame_waveform = Modulations.modulate(
        frame_canonical, frame_payload, FC, FS)
    frame_canonical_metrics, _ = Modulations.demodulate(
        frame_canonical, length(frame_payload), frame_waveform, FC, FS)
    frame_legacy_metrics, _ = Modulations.demodulate(
        frame_legacy, length(frame_payload), frame_waveform, FC, FS)
    @test frame_legacy_metrics == frame_canonical_metrics
    @test Juna._frame_receiver_profile(frame_canonical) === :ofdm_fec
    @test Juna._frame_receiver_profile(frame_legacy) === :ofdm_fec
    frame_methods = Juna.demodulate_methods(
        frame_legacy, length(frame_payload), frame_waveform, FC, FS)
    @test frame_methods.provenance === :frame_wide_ldpc
    @test frame_methods.standard === frame_methods.ofdm_fec
end

# The Profiled C,z family is public. Its internal :full and :coupled
# dependencies remain implementation profiles rather than separate facades.
function assert_receiver_profiles()
    ofdm_fec = Juna.OFDMFECModulation()
    legacy_standard = Juna.StandardModulation()
    pfft = Juna.PartialFFTModulation()
    lite = Juna.LiteModulation()
    full = Juna.FullModulation()
    coupled = Juna.CoupledModulation()
    profiled_cz = Juna.ProfiledCzFrameModulation()
    crc_profiled_cz = Juna.CrcProfiledCzFrameModulation()
    turbo_cwz = Juna.CrcTurboCwzFrameModulation()
    conditioned_cwz = Juna.CrcConditionedCwzFrameModulation()
    conditioned_joint = Juna.CrcConditionedJointCwzFrameModulation()
    legacy_full = Juna.Modulation(mode = :robust)

    @test ofdm_fec.mode === :ofdm_fec
    @test legacy_standard.mode === :standard
    @test pfft.mode === :pfft
    @test lite.mode === :lite
    @test full.mode === :full
    @test coupled.mode === :coupled
    @test profiled_cz.frame_receiver === :profiled_cz
    @test crc_profiled_cz.mode === :crc_profiled_cz_frame
    @test turbo_cwz.cz_independent_w
    @test conditioned_cwz.cz_vp_gradient
    @test conditioned_joint.cz_conditioned_joint
    @test legacy_full.mode === :robust
    @test JunaCore.JunaOFDMFEC.Modulation().mode === :ofdm_fec
    @test JunaCore.JunaStandard.Modulation().mode === :standard
    @test JunaCore.JunaPartialFFT.Modulation().mode === :pfft
    @test JunaCore.JunaLite.Modulation().mode === :lite
    @test JunaCore.JunaProfiledCzFrame.Modulation().frame_receiver ===
          :profiled_cz
    @test JunaCore.JunaCrcProfiledCzFrame.Modulation().frame_crc_bits == 16
    @test JunaCore.JunaCrcConditionedJointCwzFrame.Modulation().
          cz_conditioned_joint
    @test Juna.receiver_profile(ofdm_fec) === :ofdm_fec
    @test Juna.receiver_profile(:standard) === :ofdm_fec
    @test Juna.receiver_profile(legacy_standard) === :ofdm_fec
    @test Juna.receiver_profile(pfft) === :pfft
    @test Juna.receiver_profile(lite) === :lite
    @test Juna.receiver_profile(full) === :full
    @test Juna.receiver_profile(coupled) === :coupled
    @test Juna.receiver_profile(profiled_cz) === :frame_wide_ldpc
    @test Juna.receiver_profile(crc_profiled_cz) === :frame_wide_ldpc
    @test Juna.receiver_profile(legacy_full) === :full
    # the baselines never refine, so BPSK stays legal for them (like Lite)
    @test isvalid(Juna.OFDMFECModulation(bpc = 1, ldpc_k = 170, ldpc_n = 680), FC, FS)
    @test isvalid(Juna.StandardModulation(bpc = 1, ldpc_k = 170, ldpc_n = 680), FC, FS)
    @test isvalid(Juna.PartialFFTModulation(bpc = 1, ldpc_k = 170, ldpc_n = 680), FC, FS)
    @test !isvalid(Juna.Modulation(mode = :unknown), FC, FS)
end

# :pilot_band_ls is the ONLY objective the Partial-FFT baseline solves: the
# pilot-trained per-band ridge LS of eq:pfft-ls. Executable contract: the
# fitted combiner weights must satisfy the ridge normal equations against an
# INDEPENDENT recomputation, and the resulting initial candidate must decode a
# clean OFDM-symbol payload exactly.
function assert_pilot_band_ls_objective_contract(m)
    @test Juna.receiver_profile(m) === :pfft
    @test isvalid(m, FC, FS)

    layout = Juna._layout(m, FS)
    code = Juna._code(m)
    bits = Bool[isodd(count_ones(31i + 5)) for i in 1:Modulations.bitspersymbol(m)]
    message = Juna._build_message(m, code, bits)
    codeword = Juna._encode(code, message)
    waveform = Juna._modulate_block(m, layout, codeword)
    yparts = Juna._branch_observations(m, waveform)

    P = Int(m.partial_fft_parts)
    weights = zeros(ComplexF64, P)
    A = zeros(ComplexF64, P, P)
    b = zeros(ComplexF64, P)
    positions = collect(eachindex(layout.pilot_idx))
    Juna._fit_branch_weights!(
        weights, A, b, m, yparts, layout.pilot_idx, layout.pilot_syms, positions)

    gram = zeros(ComplexF64, P, P)
    rhs = zeros(ComplexF64, P)
    for (row, k) in enumerate(layout.pilot_idx), p in 1:P
        rhs[p] += conj(yparts[p, k]) * layout.pilot_syms[row]
        for q in 1:P
            gram[p, q] += conj(yparts[p, k]) * yparts[q, k]
        end
    end
    for p in 1:P
        gram[p, p] += Juna._RIDGE
    end
    residual = gram * weights - rhs
    @test maximum(abs, residual) < 1e-8 * max(maximum(abs, rhs), 1.0)

    initial_candidate = Juna._initial_candidate(m, code, layout, yparts)
    @test initial_candidate.valid
    @test Juna._payload_from_metrics(
        m, code, initial_candidate.lpost_metric) == bits
end

# The declared-refinement dispatch table covers every reader-selectable
# receiver family. Receiver-specific suites execute the complete C,z receiver.
function assert_declared_refinement_contract(m)
    capability = Modulations.refinement_objective(m)
    contracts = Dict{Symbol,Function}(
        :none => _ -> (@test true),
        :pilot_band_ls => assert_pilot_band_ls_objective_contract,
        :posterior_anchor_ls => receiver -> begin
            @test Juna.receiver_profile(receiver) === :lite
            @test isdefined(Juna, :_juna_step)
        end,
        :profiled_cz_frame => receiver -> begin
            @test Juna.receiver_profile(receiver) === :frame_wide_ldpc
            @test receiver.frame_receiver === :profiled_cz
            @test isdefined(Juna, :_frame_profiled_cz_refine)
            @test isdefined(Juna, :_CoupledProblem)
        end,
    )

    @test capability isa Symbol
    @test haskey(contracts, capability)
    contracts[capability](m)
end

function assert_modulation_contract(m)
    @test m isa Modulations.Modulation
    @test hasmethod(Modulations.init, Tuple{typeof(m), Float64, Float64})
    @test hasmethod(Modulations.modulate, Tuple{typeof(m), Vector{Bool}, Float64, Float64})
    @test hasmethod(Modulations.demodulate, Tuple{typeof(m), Int, Vector{ComplexF64}, Float64, Float64})
    @test hasmethod(Modulations.bitspersymbol, Tuple{typeof(m)})
    @test hasmethod(Modulations.signallength, Tuple{typeof(m), Int, Float64, Float64})
    @test hasmethod(Base.isvalid, Tuple{typeof(m), Float64, Float64})
    @test hasmethod(Modulations.refinement_objective, Tuple{typeof(m)})

    @test Modulations.init(m, FC, FS) === nothing
    @test isvalid(m, FC, FS)

    payload_capacity = Modulations.bitspersymbol(m)
    @test payload_capacity isa Int
    @test payload_capacity > 0

    nbits = min(128, payload_capacity)                 # sub-block payload, zero-padded
    nsamples = Modulations.signallength(m, nbits, FC, FS)
    @test nsamples isa Int
    @test nsamples > 0
    @test Modulations.payload_rate(m, nbits, FC, FS) == nbits * FS / nsamples

    # Noiseless loopback with a non-trivial pattern; payload-exact acceptance, the
    # paper's PSR rule. An all-zeros payload would hide polarity/ordering bugs.
    bits = Vector{Bool}(isodd.(1:nbits))
    waveform = Modulations.modulate(m, bits, FC, FS)
    @test waveform isa Vector{ComplexF64}
    @test length(waveform) == nsamples

    metrics, cfo = Modulations.demodulate(m, nbits, waveform, FC, FS)
    @test metrics isa Vector{Float64}
    @test length(metrics) == nbits
    @test all(isfinite, metrics)
    @test (metrics .> 0) == bits                       # payload-exact recovery
    @test cfo isa Float64
    @test cfo == 0.0                                   # sync disabled -> no CFO estimate
end

# Extended roundtrip: multiple blocks with an aperiodic pattern (Thue-Morse:
# parity of the bit count of the index), so the three blocks carry three DIFFERENT
# payloads — a receiver that swapped or repeated blocks would fail here.
function assert_extended_roundtrip(m)
    payload_capacity = Modulations.bitspersymbol(m)
    nbits = 2 * payload_capacity + min(17, payload_capacity)
    bits = Vector{Bool}([isodd(count_ones(p)) for p in 1:nbits])
    waveform = Modulations.modulate(m, bits, FC, FS)
    @test length(waveform) == Modulations.signallength(m, nbits, FC, FS)
    metrics, cfo = Modulations.demodulate(m, nbits, waveform, FC, FS)
    @test (metrics .> 0) == bits
    @test cfo == 0.0
end

@testset verbose = true "Checks shared by all receivers" begin
    @testset "LDPC helper binaries are vendored" begin
        assert_ldpc_tools_present()
    end

    @testset "LDPC.create rejects invalid dimensions and option strings" begin
        assert_ldpc_create_input_contract()
    end

    @testset "Receiver mode names map to their expected profiles" begin
        assert_receiver_profiles()
    end

    @testset "OFDM+FEC canonical and compatibility names give the same result" begin
        assert_ofdm_fec_compatibility()
    end

    @testset "shared receiver catalog covers the four reader-selectable families" begin
        assert_public_receiver_catalog()
        # FrameRLS remains outside this package's public facade set.
    end

    @testset "declared refinement identifies the required implementation" begin
        providers = (
            ("unrelated interface implementation", InterfaceOnlyModulation()),
            ("OFDM+FEC baseline", Juna.OFDMFECModulation()),
            ("JunaOFDMFEC module", JunaCore.JunaOFDMFEC.Modulation()),
            ("Partial-FFT baseline", Juna.PartialFFTModulation()),
            ("JunaPartialFFT module", JunaCore.JunaPartialFFT.Modulation()),
            ("default JUNA-lite", Juna.Modulation()),
            ("JunaLite module", JunaCore.JunaLite.Modulation()),
            ("Profiled C,z", JunaCore.JunaProfiledCzFrame.Modulation()),
            ("Profiled C,z", JunaCore.JunaCrcProfiledCzFrame.Modulation()),
            ("Profiled C,z", JunaCore.JunaCrcConditionedJointCwzFrame.Modulation()),
        )
        expected = (:none, :none, :none, :pilot_band_ls, :pilot_band_ls,
                    :posterior_anchor_ls, :posterior_anchor_ls,
                    :profiled_cz_frame, :profiled_cz_frame,
                    :profiled_cz_frame)

        for ((name, provider), objective) in zip(providers, expected)
            @testset "$name declares $objective" begin
                @test Modulations.refinement_objective(provider) === objective
                assert_declared_refinement_contract(provider)
            end
        end
    end

    @testset "The default receiver is JUNA-Lite" begin
        @test Juna.receiver_profile(Juna.Modulation()) === :lite
        assert_modulation_contract(Juna.Modulation())
    end

    for descriptor in public_receiver_descriptors()
        @testset "$(descriptor.name) recovers all 128 test bits from its own clean waveform" begin
            assert_modulation_contract(public_receiver(descriptor))
        end
    end

    if get(ENV, "JUNA_INTERFACE_ROUNDTRIP", "0") == "1"
        for descriptor in public_receiver_descriptors()
            @testset "$(descriptor.name): extended three-block loopback" begin
                assert_extended_roundtrip(public_receiver(descriptor))
            end
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    println("Checks shared by all receivers passed")
end
