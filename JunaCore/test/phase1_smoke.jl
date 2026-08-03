# Phase-1 migration smoke gate: each migrated public facade recovers a
# clean-channel payload bit-exactly using only the migrated closure
# (Modulations + LDPC + juna/common.jl + juna/lite.jl, with the LDPC helper
# binaries under tools/ldpc). Mirrors the noiseless-loopback rule of the
# source repo's interface contract: payload-exact acceptance, alternating
# bit pattern so polarity/ordering bugs cannot hide.
#
# Provenance: migrated from sonique research/JunaCore @ d49fff0 (juna-dev).

using Test
using JunaCore

const Modulations = JunaCore.Modulations
const FC = 24_000.0
const FS = 24_000.0

@testset "phase-1 migration smoke: clean-channel roundtrip" begin
  for (name, provider) in (
      ("OFDM+FEC", () -> JunaCore.JunaOFDMFEC.Modulation()),
      ("PartialFFT", () -> JunaCore.JunaPartialFFT.Modulation()),
      ("Lite", () -> JunaCore.JunaLite.Modulation()),
  )
    @testset "$name" begin
      m = provider()
      nbits = Modulations.bitspersymbol(m)
      @test nbits > 0
      bits = Vector{Bool}(isodd.(1:nbits))
      waveform = Modulations.modulate(m, bits, FC, FS)
      @test waveform isa Vector{ComplexF64}
      @test length(waveform) == Modulations.signallength(m, nbits, FC, FS)
      metrics, cfo = Modulations.demodulate(m, nbits, waveform, FC, FS)
      @test metrics isa Vector{Float64}
      @test length(metrics) == nbits
      @test all(isfinite, metrics)
      @test (metrics .> 0) == bits   # payload-exact recovery
      @test cfo isa Float64
    end
  end

  # The migrated Lite facade must still declare its refinement objective, so
  # a facade wired to the wrong provider cannot pass as Lite.
  @test Modulations.refinement_objective(JunaCore.JunaLite.Modulation()) ==
        :posterior_anchor_ls
end
