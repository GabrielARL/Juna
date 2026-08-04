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
     "908f581f44ce0c96cc72e5816387850ad4ce9c54fb64c4f13d27bfe6245e6933"),
    ("src/JunaCore.jl",   # diverged: C,z refinement public facades
     "912a1e01aa26191d345df6d45ea9a9044c304c7f1ea1c7d8d5a3966d829d91a1"),
    ("src/Juna.jl",   # diverged: C,z refinement implementation closure
     "8fc3008c91c1c5e04388f50d0c790f6e9ed227567fb0dfd85fe4568e34176c7f"),
    ("src/juna/common.jl",   # approved receiver catalog, feedback, compatibility, and terminology
     "de895ec895011252bcbc51aae5f8e3d8002b4f7e03dc296e315f85fc596d522e"),
    ("src/juna/frame_wide_ldpc.jl",   # approved receiver catalog and feedback validation
     "e6884e65d4e2e372591c4fb9593e70f751f64f154866da7be183552b1ee9ab4e"),
    ("src/juna/lite.jl",
     "964913dbb263281814ad45ed8bebfbe1ef724a4eef95f7eaf9233157b2f68fc7"),
    ("src/juna/full.jl",   # restored C,z refinement dependency
     "57f6e7082c7da1552be16014219ea93386d26d3b69d4c583cee945fa8bc3360b"),
    ("src/juna/coupled.jl",   # restored C,z refinement dependency
     "8f1cb9d73154ba64f3da4a5b0be6a8aff3c69e3b60f750e61986c484d23733e8"),
    ("src/juna/cz_refinement.jl",   # approved C,z refinement family
     "55d4ca07c9d72df659d75c3606e47e9ed242cd9adaa465034d49592911f6da30"),
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
