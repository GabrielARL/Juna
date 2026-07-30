# Cross-repo parity check for the JUNA-Lite migration.
#
# Run this file under BOTH projects on the same machine and Julia binary:
#   julia --project=/home/gabiel/Documents/GitHub/Juna/JunaCore              tools/parity_check.jl
#   julia --project=/home/gabiel/Documents/GitHub/BP/sonique/research/JunaCore tools/parity_check.jl
# The printed digest must match: byte-identical algorithm files must produce
# bit-identical decisions on seeded frames (clean + mild-noise) for all three
# migrated facades. Decisions (metric signs), not raw metrics, are hashed so
# the check is robust by construction; a digest mismatch means the migration
# changed behavior and must be investigated, not papered over.
#
# The digest is SHA-256 (archival interchange format, stable across Julia
# versions) - Julia's general-purpose hash() carries no such guarantee. The
# SHA stdlib is loaded by UUID via Base.require because this script must run
# under BOTH projects and the source repository's Project.toml does not
# declare SHA (and is not edited from here).

using JunaCore
using Random

const PC_SHA = Base.require(Base.PkgId(
    Base.UUID("ea8e919c-243c-51af-8825-aaa63cd721ce"), "SHA"))

const PC_Modulations = JunaCore.Modulations
const PC_FC = 24_000.0
const PC_FS = 24_000.0

decisions = UInt8[]
for (label, factory) in (
    ("standard", JunaCore.Juna.StandardModulation),
    ("pfft", JunaCore.Juna.PartialFFTModulation),
    ("lite", JunaCore.Juna.LiteModulation),
)
  m = factory()
  nbits = PC_Modulations.bitspersymbol(m)
  rng = MersenneTwister(20260730)
  for trial in 1:5
    bits = rand(rng, Bool, nbits)
    x = PC_Modulations.modulate(m, bits, PC_FC, PC_FS)
    noise = 0.05 .* (randn(rng, length(x)) .+ 1im .* randn(rng, length(x)))
    metrics, _ = PC_Modulations.demodulate(m, nbits, x .+ noise, PC_FC, PC_FS)
    append!(decisions, UInt8.(metrics .> 0))
    append!(decisions, UInt8.(bits))
    println(stderr, "  $label trial $trial: ",
            sum((metrics .> 0) .== bits), "/", nbits, " bits correct")
  end
end
println("parity digest: ", bytes2hex(PC_SHA.sha256(decisions)),
        " (", length(decisions), " decision bytes; sha256)")
