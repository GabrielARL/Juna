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
const PC_PROFILED_CZ_KEY = "profiled_cz.compact"
const PC_PROFILED_CZ_READER_NAME = "Profiled C,z"
const PC_CONDITIONED_JOINT_KEY = "conditioned_joint_cwz.compact"
const PC_CONDITIONED_JOINT_READER_NAME = "Conditioned joint C,W,z"
const PC_RECEIVERS = (
    ("standard", JunaCore.Juna.StandardModulation),
    ("partial-fft", JunaCore.Juna.PartialFFTModulation),
    ("lite", JunaCore.Juna.LiteModulation),
)

function frame_refinement_parity_digest(label, modem; conditioned_joint=false)
    nbits = 2 * PC_Modulations.bitspersymbol(modem) - 3
    rng = MersenneTwister(20260730)
    bits = rand(rng, Bool, nbits)
    waveform = PC_Modulations.modulate(modem, bits, PC_FC, PC_FS)
    noise = 0.05 .* (
        randn(rng, length(waveform)) .+ 1im .* randn(rng, length(waveform)))
    metrics, _ = PC_Modulations.demodulate(
        modem, nbits, waveform .+ noise, PC_FC, PC_FS)
    trace = JunaCore.Juna._cz_gradient_last_trace(modem)
    trace.bp_checkpoints >= 2 || error(
        "$label parity case did not run refinement")
    trace.conditioned_joint == conditioned_joint || error(
        "$label parity case ran the wrong conditioned-joint branch")
    if conditioned_joint
        trace.conditioned_accepted_steps + trace.conditioned_rejected_steps > 0 ||
            error("$label parity case made no conditioned-joint proposal")
    end

    decisions = vcat(UInt8.(metrics .> 0), UInt8.(bits))
    println(stderr, "  $label compact case: ",
            sum((metrics .> 0) .== bits), "/", nbits,
            " bits correct; ", trace.bp_checkpoints, " BP checkpoints")
    bytes2hex(PC_SHA.sha256(decisions))
end

function profiled_cz_parity_digest()
    modem = JunaCore.JunaProfiledCzFrame.Modulation(
        nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
        refinement_steps=1, cz_gate_selection_only=true,
    )
    frame_refinement_parity_digest(PC_PROFILED_CZ_READER_NAME, modem)
end

function conditioned_joint_parity_digest()
    modem = JunaCore.JunaCrcConditionedJointCwzFrame.Modulation(
        nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
        refinement_steps=1, cz_gate_selection_only=true,
        cz_crc_gate=false, cz_gradient_only=true,
    )
    frame_refinement_parity_digest(
        PC_CONDITIONED_JOINT_READER_NAME, modem; conditioned_joint=true)
end

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
    results[PC_PROFILED_CZ_KEY] = profiled_cz_parity_digest()
    results[PC_CONDITIONED_JOINT_KEY] = conditioned_joint_parity_digest()
    results
end

function load_golden(path)
    text = read(path, String)
    Dict(m.captures[1] => m.captures[2]
         for m in eachmatch(r"\"([a-z_-]+\.[a-z_]+)\"\s*:\s*\"([0-9a-f]{64})\"",
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
    label = key == PC_PROFILED_CZ_KEY ?
        "$PC_PROFILED_CZ_READER_NAME compact case" :
        key == PC_CONDITIONED_JOINT_KEY ?
        "$PC_CONDITIONED_JOINT_READER_NAME compact case" : key
    println("parity $label: ", actual[key], " PASS")
end
summary_bytes = Vector{UInt8}(codeunits(join(
    ["$key=$(actual[key])" for key in sort(collect(keys(actual)))], "\n")))
println("parity digest: ", bytes2hex(PC_SHA.sha256(summary_bytes)),
        " (aggregate of keyed receiver/scenario digests)")
println("per-receiver parity: PASS (", length(actual), " keyed digests)")
