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
    ("src/JunaCore.jl",   # SRC-001a: approved Profiled C,z public facades
     "486b4ecc918c0b851d98900cc365904b1caca0b74efdcd3b6e60d5c5882a6255"),
    ("src/Juna.jl",   # SRC-001a: approved Profiled C,z implementation closure
     "45634f3933f9fff511dde63f4990c52372430a4c51d244325fed72f5472434b0"),
    ("src/juna/common.jl",   # SRC-001a closure; phase-balanced residual carrier and duration acquisition
     "e650f3d13dc0af44e47497eaba48252744349d060e4bead73ae2e24408db1836"),
    ("src/juna/frame_wide_ldpc.jl",   # diverged: rpchan removal (CL-1/2/3); adaptive-lite removal; seed-to-initial-candidate rename (register CL-13, CL-15)
     "ebb65dc4a960316ca7caeb8d03873b2f2121adb30e5a3b905e4ea93f479822d2"),
    ("src/juna/lite.jl",   # diverged: seed-to-initial-candidate rename (register CL-13, CL-15)
     "ac6bae2a1837ccd9d2f7a98942eecd96f72da90361d4fcd1f82a6ec3e84d8416"),
    ("src/juna/full.jl",   # SRC-001a: restored Profiled C,z dependency
     "58358829aea2a1cfce3d8e05801e58267d1b9cc19d4b897baab70fa93e007120"),
    ("src/juna/coupled.jl",   # SRC-001a: restored Profiled C,z dependency
     "6f2eaa31a680ac341d597fda0287547d940d9a91f8c25b80aadfc795ebc03836"),
    ("src/juna/profiled_cz_frame.jl",   # SRC-001a: approved receiver family
     "9e4f8d960cf3c90cd1ea1a3324f3612474f469d52afacb0d44e7b0271b1a3726"),
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
