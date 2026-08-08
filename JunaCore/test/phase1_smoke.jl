# Package smoke gate: each reader-selectable receiver recovers a
# clean-channel payload bit-exactly using only the package closure. Mirrors
# the noiseless-loopback rule of the
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
      ("Standard", () -> JunaCore.JunaStandard.Modulation()),
      ("PartialFFT", () -> JunaCore.JunaPartialFFT.Modulation()),
      ("Lite", () -> JunaCore.JunaLite.Modulation()),
      ("Profiled C,z", () -> JunaCore.JunaProfiledCzFrame.Modulation(
          nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
          partial_fft_parts=2, partial_fft_nbands=2,
          pilot_ratio=1 / 3, inner_pilot_ratio=0.0,
          refinement_steps=0)),
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
