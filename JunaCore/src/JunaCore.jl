# Migrated subset of sonique research/JunaCore @ d49fff0 (juna-dev):
# JUNA-Lite, Profiled C,z, and the two paper baselines. Facades for receiver
# files outside this closure remain deliberately absent.
module JunaCore

include(joinpath(@__DIR__, "Modulations.jl"))
include(joinpath(@__DIR__, "LDPC.jl"))
include(joinpath(@__DIR__, "Juna.jl"))

module JunaLite
  using ..Juna
  export Modulation
  const Modulation = Juna.LiteModulation
end

module JunaProfiledCzFrame
  # Frame-wide variable projection over physical response C and relaxed
  # codeword z. The partial-FFT combiner W is derived from C, not optimized.
  export Modulation
  const Modulation =
    getfield(parentmodule(@__MODULE__), :Juna).ProfiledCzFrameModulation
end

module JunaCrcProfiledCzFrame
  # CRC-bearing frame-wide C,z receiver. Lite is checkpoint zero and a
  # gradient checkpoint is accepted only as a CRC-certified rescue.
  export Modulation
  const Modulation =
    getfield(parentmodule(@__MODULE__), :Juna).CrcProfiledCzFrameModulation
end

module JunaCrcConditionedJointCwzFrame
  # CRC-bearing frame receiver with simultaneous, block-preconditioned
  # hand-gradient C,W,z proposals guarded by pilot and trust-region checks.
  export Modulation
  const Modulation =
    getfield(parentmodule(@__MODULE__), :Juna).
      CrcConditionedJointCwzFrameModulation
end

module JunaOFDMFEC
  # Paper baseline: one-tap pilot-interpolated OFDM equalization + FEC, no refinement.
  export Modulation
  const Modulation = getfield(parentmodule(@__MODULE__), :Juna).OFDMFECModulation
end

module JunaStandard
  # Compatibility facade preserving the former constructor and mode value.
  export Modulation
  const Modulation = getfield(parentmodule(@__MODULE__), :Juna).StandardModulation
end

module JunaPartialFFT
  # Paper baseline: pilot-trained per-band partial-FFT combining + FEC (the
  # pure partial column of demodulate_methods, no OFDM+FEC fallback, no
  # refinement).
  export Modulation
  const Modulation = getfield(parentmodule(@__MODULE__), :Juna).PartialFFTModulation
end

end # module JunaCore
