module Juna

using FFTW
using LinearAlgebra
using Random
using Statistics
using ..LDPC
using ..Modulations

# Migrated Lite and Profiled C,z closure. The Profiled C,z receiver uses the
# shared W,z and C,W,z types and conditional solves from full.jl and coupled.jl.
# Other variant files (fully coupled, guarded, turbo MAP, and profiled
# gradient) stay in the source repository. ForwardDiff and FixedPathChannel
# serve only those pruned variants. Include order matches the source repository.
include(joinpath(@__DIR__, "juna", "common.jl"))
include(joinpath(@__DIR__, "juna", "frame_wide_ldpc.jl"))
include(joinpath(@__DIR__, "juna", "lite.jl"))
include(joinpath(@__DIR__, "juna", "full.jl"))
include(joinpath(@__DIR__, "juna", "coupled.jl"))
include(joinpath(@__DIR__, "juna", "profiled_cz_frame.jl"))

end # module Juna
