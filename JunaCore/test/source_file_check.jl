# Source file check: selected Juna algorithm files and LDPC helper binaries
# have stored SHA-256 values so an unreviewed edit is detected without another
# repository checkout.
#
# Historical source: sonique research/JunaCore @
# d49fff0127732af4fad3862628fd93a96e2e75e9. Juna is a separate entity and
# does not have to remain byte-identical to that source. A reviewed Juna change
# may update an affected stored value in the same change after user approval.

using Test
using SHA

const PROV_ROOT = get(ENV, "JUNA_CORE_ROOT",
                      normpath(joinpath(@__DIR__, "..")))

const PROV_PINNED = [
    ("src/Modulations.jl",
     "6561e6bb79886fdc2f4397c592a3e3a96291e4cfca72ffb4b3af3f40e6a2d6ee"),
    ("src/LDPC.jl",
     "32d4c087c6b4fb93b40acbeb5e17eee2b47f88e709dfc8bb65cbb5039614f6b9"),
    ("src/JunaCore.jl",   # diverged: Profiled C,z public facades
     "8ec319b99474a8626bcfd7834190e4c92c99045279ac0b8ccdc6e53abf3735b3"),
    ("src/Juna.jl",   # diverged: Profiled C,z implementation closure
     "45634f3933f9fff511dde63f4990c52372430a4c51d244325fed72f5472434b0"),
    ("src/juna/common.jl",   # approved receiver catalog, feedback, compatibility, and terminology
     "b43a5e3810e41212bb2daf8234935692b821c3e73200350fda643b3f9f4ff285"),
    ("src/juna/frame_wide_ldpc.jl",   # approved receiver catalog and feedback validation
     "057b68b49d7a34fb912cc0c1fff9a148997fcc88bebca4c2ec552d25633b41e2"),
    ("src/juna/lite.jl",
     "bd16396b93a571ea08360f0972feec937d50bd43867821b488eba498a09f8b2c"),
    ("src/juna/full.jl",   # restored Profiled C,z dependency
     "b00886626f375c9fdd339072e13b62ac21bb17572a553ff9ad51b893ddcbc732"),
    ("src/juna/coupled.jl",   # restored Profiled C,z dependency
     "1ffc47c3772872d10a2f8147104bd070996204dc19285f029ae640e4ab4e0b81"),
    ("src/juna/profiled_cz_frame.jl",   # approved Profiled C,z family
     "aa893f68f2f53fa2b9626a9cfe7b2ce32f8d1271e63c8232c4afdb08fc4c94ff"),
    ("tools/ldpc/make-ldpc",
     "fa8b613a7297977858bdeaf44cc9c3fa9f49d90ed7c294b23330b36041716a23"),
    ("tools/ldpc/make-gen",
     "5af29a291985b334ac312a2b3314d02d3538e2de438b077ccf26858da4c78fa8"),
    ("tools/ldpc/print-pchk",
     "1f573dab0d4de11ca77054700b32943ec389806929305836b223457620919d53"),
]

@testset "Source file check" begin
    for (rel, pinned) in PROV_PINNED
        path = joinpath(PROV_ROOT, rel)
        @test isfile(path)
        isfile(path) || continue
        actual = bytes2hex(SHA.sha256(read(path)))
        if actual != pinned
            println("=" ^ 72)
            println("JUNA SOURCE FILE CHANGED: ", rel)
            println("  stored : ", pinned)
            println("  current: ", actual)
            println("  Review this Juna change with the user.")
            println("  If approved, update the stored value in the same change.")
            println("  No corresponding Sonique change is required.")
            println("=" ^ 72)
        end
        @test actual == pinned
    end
end
