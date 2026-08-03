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
