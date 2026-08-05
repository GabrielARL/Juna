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
    ("src/juna/common.jl",   # diverged: rpchan removal (CL-1/2/3); adaptive-lite removal; seed-to-initial-candidate rename (register CL-13, CL-15)
     "93ed0078b9ca7be430bce1460dd4139d17cd508e7d7ac80292fe5a808a2afa75"),
    ("src/juna/frame_wide_ldpc.jl",   # diverged: rpchan removal (CL-1/2/3); adaptive-lite removal; seed-to-initial-candidate rename (register CL-13, CL-15)
     "ebb65dc4a960316ca7caeb8d03873b2f2121adb30e5a3b905e4ea93f479822d2"),
    ("src/juna/lite.jl",   # diverged: seed-to-initial-candidate rename (register CL-13, CL-15)
     "ac6bae2a1837ccd9d2f7a98942eecd96f72da90361d4fcd1f82a6ec3e84d8416"),
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
