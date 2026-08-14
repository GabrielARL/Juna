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
  # Standard is returned when its frame passes CRC. Otherwise frame-wide C,z
  # refinement runs, and replaces Standard only when its own output passes CRC.
  export Modulation
  const Modulation =
    getfield(parentmodule(@__MODULE__), :Juna).
      CrcNoHarmProfiledCzFrameModulation
end

module JunaCrcProfiledCzFrame
  # CRC-bearing frame-wide C,z receiver. Lite is checkpoint zero and a
  # gradient checkpoint is accepted only as a CRC-certified rescue.
  export Modulation
  const Modulation =
    getfield(parentmodule(@__MODULE__), :Juna).CrcProfiledCzFrameModulation
end

module JunaCrcConditionedJointCwzFrame
  # Standard is returned when its frame passes CRC. Otherwise simultaneous
  # C,W,z refinement runs, and replaces Standard only when its output passes CRC.
  export Modulation
  const Modulation =
    getfield(parentmodule(@__MODULE__), :Juna).
      CrcNoHarmConditionedJointCwzFrameModulation
end

module JunaDirectCzFrame
  # Separate direct C,z descent with CRC no-harm selection.
  export Modulation
  const Modulation =
    getfield(parentmodule(@__MODULE__), :Juna).DirectCzFrameModulation
end

module JunaStandard
  # Paper baseline: one-tap pilot-interpolated equalization + FEC, no refinement.
  export Modulation
  const Modulation = getfield(parentmodule(@__MODULE__), :Juna).StandardModulation
end

module JunaPartialFFT
  # Paper baseline: pilot-trained per-band partial-FFT combining + FEC (the
  # pure partial column of demodulate_methods, no standard fallback, no
  # refinement).
  export Modulation
  const Modulation = getfield(parentmodule(@__MODULE__), :Juna).PartialFFTModulation
end

end # module JunaCore
