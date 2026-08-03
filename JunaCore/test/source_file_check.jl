# Executable provenance gate: the migrated algorithm files and LDPC helper
# binaries are claimed byte-identical to sonique research/JunaCore @
# d49fff0127732af4fad3862628fd93a96e2e75e9 (README.md, AGENTS.md). This
# suite pins their sha256 digests so a fork is detected standalone - no
# checkout of the source repository required.
#
# FORK PROTOCOL: if a pin fails, do NOT update it silently. Either the edit
# should land in the source repository too, or the byte-identical claim is
# being retired deliberately - in that case update the pins, README.md, the
# AGENTS.md provenance gate, and the parity expectations in ONE reviewed
# change, with the user's explicit approval.

using Test
using SHA

const PROV_ROOT = get(ENV, "JUNA_CORE_ROOT",
                      normpath(joinpath(@__DIR__, "..")))

const PROV_SOURCE = "sonique research/JunaCore @ d49fff0127732af4fad3862628fd93a96e2e75e9"

const PROV_PINNED = [
    ("src/Modulations.jl",
     "031486c0d2a0fc3304a13b4d0df3c945867b2ce2994b4e503a50a615a00d3eeb"),
    ("src/LDPC.jl",
     "e7bd15a6f42f3319245c661a28b25a545071256c1f8d46263808f52b6da846d0"),
    ("src/juna/common.jl",
     "d9108ae96071e48dac4b8c6ea9b5d5fc0b61cc6725bf464e124d3ddb923ac378"),
    ("src/juna/frame_wide_ldpc.jl",
     "7ff43e77fdbaa5d7232e7ade676cc6d22c94cb470935037ad68bab805323ffca"),
    ("src/juna/lite.jl",
     "9ef4c670546a3f89ac928af3cfa1c4542ec7d58500f87a8d9e3c7c0eeefe3ed8"),
    ("tools/ldpc/make-ldpc",
     "fa8b613a7297977858bdeaf44cc9c3fa9f49d90ed7c294b23330b36041716a23"),
    ("tools/ldpc/make-gen",
     "5af29a291985b334ac312a2b3314d02d3538e2de438b077ccf26858da4c78fa8"),
    ("tools/ldpc/print-pchk",
     "1f573dab0d4de11ca77054700b32943ec389806929305836b223457620919d53"),
]

@testset "Provenance: byte-identical migrated files" begin
    for (rel, pinned) in PROV_PINNED
        path = joinpath(PROV_ROOT, rel)
        @test isfile(path)
        isfile(path) || continue
        actual = bytes2hex(SHA.sha256(read(path)))
        if actual != pinned
            println("=" ^ 72)
            println("PROVENANCE FORK DETECTED: ", rel)
            println("  pinned : ", pinned)
            println("  actual : ", actual)
            println("  This file is claimed byte-identical to ", PROV_SOURCE, ".")
            println("  Do NOT update the pin to make this pass. Ask the user:")
            println("  land the change in the source repository too, or retire the")
            println("  byte-identical claim (pins + README + AGENTS provenance gate")
            println("  + parity expectations, in one reviewed change).")
            println("=" ^ 72)
        end
        @test actual == pinned
    end
end
