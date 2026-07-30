module Juna

using FFTW
using LinearAlgebra
using Random
using Statistics
using ..LDPC
using ..Modulations

# Migrated Lite closure only: every helper the Lite receiver calls lives in
# common.jl, so the other variant files (full, coupled, profiled, fully
# coupled, guarded, turbo MAP, frame-wide) stay in the source repository.
# ForwardDiff and FixedPathChannel served only those pruned variants.
include(joinpath(@__DIR__, "juna", "common.jl"))
include(joinpath(@__DIR__, "juna", "lite.jl"))

end # module Juna
