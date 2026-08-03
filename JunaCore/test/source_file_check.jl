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
     "031486c0d2a0fc3304a13b4d0df3c945867b2ce2994b4e503a50a615a00d3eeb"),
    ("src/LDPC.jl",
     "e7bd15a6f42f3319245c661a28b25a545071256c1f8d46263808f52b6da846d0"),
    ("src/JunaCore.jl",   # diverged: Profiled C,z public facades
     "8ec319b99474a8626bcfd7834190e4c92c99045279ac0b8ccdc6e53abf3735b3"),
    ("src/Juna.jl",   # diverged: Profiled C,z implementation closure
     "45634f3933f9fff511dde63f4990c52372430a4c51d244325fed72f5472434b0"),
    ("src/juna/common.jl",   # diverged: Rpchan/adaptive-lite removal; OFDM+FEC rename
     "b86b82ff17e52f52de66f2a58882d8f0373043dee589dd99a426cb2110719469"),
    ("src/juna/frame_wide_ldpc.jl",   # diverged: Rpchan/adaptive-lite removal; OFDM+FEC rename
     "e24f27f50589cdd387366e0417e95f0173003723117ffad8eebd6316ae0e78cc"),
    ("src/juna/lite.jl",
     "9ef4c670546a3f89ac928af3cfa1c4542ec7d58500f87a8d9e3c7c0eeefe3ed8"),
    ("src/juna/full.jl",   # restored Profiled C,z dependency
     "bf44e6065ce81197ecee10ee44b5a07fca3543495ff5651addf2d29b4797776f"),
    ("src/juna/coupled.jl",   # restored Profiled C,z dependency
     "e6e1da89ad988e8c31a7d3ff9c2801e3e403c00e66db6b2546017886d3d5a5ea"),
    ("src/juna/profiled_cz_frame.jl",   # approved Profiled C,z family
     "c9e74bb82a720eaf226123a8f5cf1b34ad9cc9394cea4e32c27ab6baf75f2f13"),
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
