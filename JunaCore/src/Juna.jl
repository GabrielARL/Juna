module Juna

using FFTW
using LinearAlgebra
using Random
using Statistics
using ..LDPC
using ..Modulations

# Migrated Lite closure: every helper the Lite receiver calls lives in
# common.jl, and frame_wide_ldpc.jl carries the frame-stateful Lite paths
# (frame_receiver = :lite / :stateful_lite) that the mechanism suites
# exercise. The other variant files (full, coupled, profiled, fully coupled,
# guarded, turbo MAP) stay in the source repository; frame_wide_ldpc.jl's
# :turbo_map frame path is unreachable here and would error if requested.
# ForwardDiff and FixedPathChannel served only the pruned variants.
# Include order matches the source repository.
include(joinpath(@__DIR__, "juna", "common.jl"))
include(joinpath(@__DIR__, "juna", "frame_wide_ldpc.jl"))
include(joinpath(@__DIR__, "juna", "lite.jl"))

end # module Juna
