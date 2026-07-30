# Migrated subset of sonique research/JunaCore @ d49fff0 (juna-dev): the
# JUNA-Lite receiver and the two paper baselines it is measured against.
# Facades whose implementation files are not migrated are deliberately absent.
module JunaCore

include(joinpath(@__DIR__, "Modulations.jl"))
include(joinpath(@__DIR__, "LDPC.jl"))
include(joinpath(@__DIR__, "Juna.jl"))

module JunaLite
  using ..Juna
  export Modulation
  const Modulation = Juna.LiteModulation
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
