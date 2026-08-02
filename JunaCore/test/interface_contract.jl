#!/usr/bin/env julia
#
# Interface contract — the end-to-end executable contract for every receiver path.
#
# Paper claims protected (papers/main.tex):
#   sec:method (lines 1919-1964)     OFDM+FEC, Partial-FFT+FEC, and JUNA share one
#                                    transmitted frame and one public boundary; only
#                                    receiver processing differs. Here: the Standard,
#                                    Partial-FFT, and Lite modulations all satisfy the
#                                    same contract on the same 170-bit / 1280-sample
#                                    frame.
#   acceptance rule (1928-1932,      Acceptance is payload-exact recovery. The
#   tab:hyperparams line 2029)       noiseless loopback below applies exactly that
#                                    rule: every payload bit recovered, bit for bit.
#   eq:goodput (1934-1939)           payload_rate(128 bits) == 128*24000/1280 == 2400 bit/s.
#   sec:solver (843)                 :lite runs JUNA-lite (ssec:junalite, 1522); it must
#                                    survive the full modulate->demodulate path. :full
#                                    (JUNA-Wz, ssec:gradient-juna, 1622) and :coupled
#                                    (JUNA-WCz) remain recognized internal mode tags, but
#                                    their solvers (juna/full.jl, juna/coupled.jl) are not
#                                    part of this migrated package's src/, so only their
#                                    mode/profile plumbing is checked here, not execution.
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

# FullyCoupled, TurboMAP, ProfiledGradient, ProfiledCz*, CrcConditioned*,
# GuardedPhysical, GradientGuarded, and FrameRLS are dropped below: their
# facades are absent from JunaCore.jl (scope narrowed to the migrated
# facades). :full and :coupled keep their mode/profile plumbing in common.jl
# but are not exercised beyond that, since their
# solvers (juna/full.jl, juna/coupled.jl) are not part of this package's src/.
function assert_receiver_profiles()
    standard = Juna.StandardModulation()
    pfft = Juna.PartialFFTModulation()
    lite = Juna.LiteModulation()
    full = Juna.FullModulation()
    coupled = Juna.CoupledModulation()
    legacy_full = Juna.Modulation(mode = :robust)

    @test standard.mode === :standard
    @test pfft.mode === :pfft
    @test lite.mode === :lite
    @test full.mode === :full
    @test coupled.mode === :coupled
    @test legacy_full.mode === :robust
    @test JunaCore.JunaStandard.Modulation().mode === :standard
    @test JunaCore.JunaPartialFFT.Modulation().mode === :pfft
    @test JunaCore.JunaLite.Modulation().mode === :lite
    @test Juna.receiver_profile(standard) === :standard
    @test Juna.receiver_profile(pfft) === :pfft
    @test Juna.receiver_profile(lite) === :lite
    @test Juna.receiver_profile(full) === :full
    @test Juna.receiver_profile(coupled) === :coupled
    @test Juna.receiver_profile(legacy_full) === :full
    # the baselines never refine, so BPSK stays legal for them (like Lite)
    @test isvalid(Juna.StandardModulation(bpc = 1, ldpc_k = 170, ldpc_n = 680), FC, FS)
    @test isvalid(Juna.PartialFFTModulation(bpc = 1, ldpc_k = 170, ldpc_n = 680), FC, FS)
    @test !isvalid(Juna.Modulation(mode = :unknown), FC, FS)
end

# :pilot_band_ls is the ONLY objective the Partial-FFT baseline solves: the
# pilot-trained per-band ridge LS of eq:pfft-ls. Executable contract: the
# fitted branch weights must satisfy the ridge normal equations against an
# INDEPENDENT recomputation, and the resulting seed candidate must decode a
# clean block payload-exactly.
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

    seed = Juna._seed_candidate(m, code, layout, yparts)
    @test seed.valid
    @test Juna._payload_from_metrics(m, code, seed.lpost_metric) == bits
end

# The declared-refinement dispatch table is intentionally restricted to the
# three migrated objectives (:none, :pilot_band_ls, :posterior_anchor_ls).
# :reduced_wz (:full) and :coupled_cwz (:coupled) are recognized Symbols that
# refinement_objective can still return, but executing either requires
# juna/full.jl / juna/coupled.jl, which are not part of this package's src/;
# scope narrowed to the migrated facades' objectives only.
function assert_declared_refinement_contract(m)
    capability = Modulations.refinement_objective(m)
    contracts = Dict{Symbol,Function}(
        :none => _ -> (@test true),
        :pilot_band_ls => assert_pilot_band_ls_objective_contract,
        :posterior_anchor_ls => receiver -> begin
            @test Juna.receiver_profile(receiver) === :lite
            @test isdefined(Juna, :_juna_step)
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

    @testset "Receiver mode names map to their expected profiles" begin
        assert_receiver_profiles()
    end

    @testset "shared receiver catalog covers every public runtime mode" begin
        assert_public_receiver_catalog()
        # The FrameRLS name-membership check is dropped: its facade is absent
        # from JunaCore.jl (scope narrowed to the migrated facades).
    end

    @testset "declared refinement capability matches an executable objective" begin
        providers = (
            ("unrelated interface implementation", InterfaceOnlyModulation()),
            ("Standard OFDM baseline", Juna.StandardModulation()),
            ("JunaStandard module", JunaCore.JunaStandard.Modulation()),
            ("Partial-FFT baseline", Juna.PartialFFTModulation()),
            ("JunaPartialFFT module", JunaCore.JunaPartialFFT.Modulation()),
            ("default JUNA-lite", Juna.Modulation()),
            ("JunaLite module", JunaCore.JunaLite.Modulation()),
        )
        expected = (:none, :none, :none, :pilot_band_ls, :pilot_band_ls,
                    :posterior_anchor_ls, :posterior_anchor_ls)

        for ((name, provider), objective) in zip(providers, expected)
            @testset "$name declares $objective" begin
                @test Modulations.refinement_objective(provider) === objective
                assert_declared_refinement_contract(provider)
            end
        end
        # FullyCoupled, TurboMAP, ProfiledGradient, ProfiledCz*, Crc*,
        # FrameWideLDPC, FrameRLS, :full ("JUNA-Wz"), :coupled ("JUNA-WCz"),
        # and the legacy :robust alias are dropped from this executable-
        # objective loop: their facades are absent, or (for :full/:coupled)
        # their solvers live in juna/full.jl / juna/coupled.jl, which are not
        # part of this migrated package's src/. Scope narrowed to the three
        # migrated facades' objectives: Standard -> :none,
        # Partial-FFT -> :pilot_band_ls, Lite -> :posterior_anchor_ls.
    end

    @testset "The default receiver is JUNA-Lite" begin
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
