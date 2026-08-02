# Fixed Juna receiver decisions, keyed by receiver and scenario.
#
# The committed results were first recorded during migration from the Sonique
# source commit named in parity_golden.json. This script now checks Juna against
# results stored in this repository. A reviewed Juna behavior change may update
# those results without a corresponding Sonique change.

using JunaCore
using Random

const PC_SHA = Base.require(Base.PkgId(
    Base.UUID("ea8e919c-243c-51af-8825-aaa63cd721ce"), "SHA"))
const PC_Modulations = JunaCore.Modulations
const PC_FC = 24_000.0
const PC_FS = 24_000.0
const PC_SCENARIOS = (("clean", 0.0), ("mild_noise", 0.05))
const PC_RECEIVERS = (
    ("standard", JunaCore.Juna.StandardModulation),
    ("partial-fft", JunaCore.Juna.PartialFFTModulation),
    ("lite", JunaCore.Juna.LiteModulation),
)

function parity_digests()
    results = Dict{String,String}()
    for (label, factory) in PC_RECEIVERS
        for (scenario, noise_scale) in PC_SCENARIOS
            decisions = UInt8[]
            modem = factory()
            nbits = PC_Modulations.bitspersymbol(modem)
            rng = MersenneTwister(20260730)
            for trial in 1:5
                bits = rand(rng, Bool, nbits)
                x = PC_Modulations.modulate(modem, bits, PC_FC, PC_FS)
                noise = noise_scale .* (
                    randn(rng, length(x)) .+ 1im .* randn(rng, length(x)))
                metrics, _ = PC_Modulations.demodulate(
                    modem, nbits, x .+ noise, PC_FC, PC_FS)
                append!(decisions, UInt8.(metrics .> 0))
                append!(decisions, UInt8.(bits))
                println(stderr, "  $label/$scenario trial $trial: ",
                        sum((metrics .> 0) .== bits), "/", nbits,
                        " bits correct")
            end
            results["$label.$scenario"] =
                bytes2hex(PC_SHA.sha256(decisions))
        end
    end
    results
end

function load_golden(path)
    text = read(path, String)
    Dict(m.captures[1] => m.captures[2]
         for m in eachmatch(r"\"([a-z-]+\.[a-z_]+)\"\s*:\s*\"([0-9a-f]{64})\"",
                            text))
end

function emit_json(results)
    println("{")
    println("  \"source_repository\": \"sonique/research/JunaCore\",")
    println("  \"source_commit\": \"d49fff0127732af4fad3862628fd93a96e2e75e9\",")
    println("  \"julia_version\": \"", VERSION, "\",")
    println("  \"seed\": 20260730,")
    println("  \"scenarios\": {\"clean\": 0.0, \"mild_noise\": 0.05},")
    println("  \"digests\": {")
    pairs = sort(collect(results))
    for (i, (key, digest)) in enumerate(pairs)
        println("    \"", key, "\": \"", digest, "\"",
                i < length(pairs) ? "," : "")
    end
    println("  }")
    println("}")
end

actual = parity_digests()
if get(ENV, "JUNA_PARITY_RECORD", "") == "1"
    emit_json(actual)
    exit()
end

golden_path = joinpath(@__DIR__, "parity_golden.json")
expected = load_golden(golden_path)
missing = setdiff(keys(actual), keys(expected))
extra = setdiff(keys(expected), keys(actual))
isempty(missing) || error("golden parity keys missing: $(sort(collect(missing)))")
isempty(extra) || error("golden parity has obsolete keys: $(sort(collect(extra)))")
for key in sort(collect(keys(actual)))
    actual[key] == expected[key] ||
        error("parity mismatch for $key: expected $(expected[key]), " *
              "got $(actual[key])")
    println("parity $key: ", actual[key], " PASS")
end
summary_bytes = Vector{UInt8}(codeunits(join(
    ["$key=$(actual[key])" for key in sort(collect(keys(actual)))], "\n")))
println("parity digest: ", bytes2hex(PC_SHA.sha256(summary_bytes)),
        " (aggregate of keyed receiver/scenario digests)")
println("per-receiver parity: PASS (", length(actual), " keyed digests)")
