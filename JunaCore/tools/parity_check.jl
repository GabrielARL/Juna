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
const PC_SEED = 20260730
const PC_DIRECT_CZ_RESCUE_SEED = 5
const PC_DIRECT_CZ_RESCUE_SNR_DB = 4.0
const PC_SCENARIOS = (("clean", 0.0), ("mild_noise", 0.05))
const PC_PROFILED_CZ_KEY = "profiled_cz.compact"
const PC_PROFILED_CZ_READER_NAME = "Profiled C,z"
const PC_CONDITIONED_JOINT_KEY = "conditioned_joint_cwz.compact"
const PC_CONDITIONED_JOINT_READER_NAME = "Conditioned joint C,W,z"
const PC_DIRECT_CZ_KEY = "direct_cz.compact"
const PC_DIRECT_CZ_READER_NAME = "Direct C,z"
const PC_RECEIVERS = (
    ("standard", JunaCore.Juna.StandardModulation),
    ("partial-fft", JunaCore.Juna.PartialFFTModulation),
    ("lite", JunaCore.Juna.LiteModulation),
)

function frame_refinement_parity_digest(label, modem; conditioned_joint=false)
    nbits = 2 * PC_Modulations.bitspersymbol(modem) - 3
    rng = MersenneTwister(PC_SEED)
    bits = rand(rng, Bool, nbits)
    waveform = PC_Modulations.modulate(modem, bits, PC_FC, PC_FS)
    noise = 0.05 .* (
        randn(rng, length(waveform)) .+ 1im .* randn(rng, length(waveform)))
    metrics, _ = PC_Modulations.demodulate(
        modem, nbits, waveform .+ noise, PC_FC, PC_FS)
    clean_trace = JunaCore.Juna._cz_crc_no_harm_last_trace(modem)
    clean_trace.standard_crc_valid || error(
        "$label parity case did not certify Standard")
    clean_trace.selected_source === :standard || error(
        "$label parity case did not return Standard exactly")
    modem.cz_gradient_trace === nothing || error(
        "$label parity case ran refinement after Standard passed CRC")

    PC_Modulations.demodulate(
        modem, nbits, zeros(ComplexF64, length(waveform)), PC_FC, PC_FS)
    failed_trace = JunaCore.Juna._cz_crc_no_harm_last_trace(modem)
    failed_trace.rescue_executed || error(
        "$label parity case did not run refinement after Standard failed CRC")
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
        refinement_steps=1,
    )
    frame_refinement_parity_digest(PC_PROFILED_CZ_READER_NAME, modem)
end

function conditioned_joint_parity_digest()
    modem = JunaCore.JunaCrcConditionedJointCwzFrame.Modulation(
        nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
        refinement_steps=1,
    )
    frame_refinement_parity_digest(
        PC_CONDITIONED_JOINT_READER_NAME, modem; conditioned_joint=true)
end

function direct_cz_parity_digest()
    modem = JunaCore.JunaDirectCzFrame.Modulation(
        nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
        refinement_steps=1,
    )
    nbits = 2 * PC_Modulations.bitspersymbol(modem) - 3
    nbits == 37 || error(
        "$PC_DIRECT_CZ_READER_NAME compact fixture changed payload length")
    rng = MersenneTwister(PC_SEED)
    bits = rand(rng, Bool, nbits)
    waveform = PC_Modulations.modulate(modem, bits, PC_FC, PC_FS)
    noise = 0.05 .* (
        randn(rng, length(waveform)) .+ 1im .* randn(rng, length(waveform)))
    clean_metrics, _ = PC_Modulations.demodulate(
        modem, nbits, waveform .+ noise, PC_FC, PC_FS)
    clean_trace = JunaCore.Juna._direct_cz_last_trace(modem)
    clean_trace.standard_crc_valid || error(
        "$PC_DIRECT_CZ_READER_NAME parity case did not certify Standard")
    clean_trace.rescue_executed && error(
        "$PC_DIRECT_CZ_READER_NAME parity case refined after Standard passed CRC")
    clean_trace.selected_source === :standard || error(
        "$PC_DIRECT_CZ_READER_NAME parity case did not return Standard exactly")
    clean_trace.selection_reason === :standard_crc_valid || error(
        "$PC_DIRECT_CZ_READER_NAME parity case recorded the wrong clean selection")
    clean_trace.accepted_steps == 0 || error(
        "$PC_DIRECT_CZ_READER_NAME parity case accepted a clean-path step")
    clean_trace.rejected_steps == 0 || error(
        "$PC_DIRECT_CZ_READER_NAME parity case rejected a clean-path step")
    clean_trace.gradient_checkpoints == 0 || error(
        "$PC_DIRECT_CZ_READER_NAME parity case derived a clean-path gradient")
    all((clean_metrics .> 0) .== bits) || error(
        "$PC_DIRECT_CZ_READER_NAME parity case did not decode every payload bit")

    PC_Modulations.demodulate(
        modem, nbits, zeros(ComplexF64, length(waveform)), PC_FC, PC_FS)
    failed_trace = JunaCore.Juna._direct_cz_last_trace(modem)
    failed_trace.standard_crc_valid && error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case unexpectedly passed Standard CRC")
    failed_trace.rescue_executed || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case did not run rescue")
    failed_trace.scope === :frame || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case did not use frame descent")
    failed_trace.optimized_variables == (:C, :z) || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case optimized the wrong variables")
    failed_trace.independent_w_parameters == 0 || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case introduced independent W")
    failed_trace.requested_steps == 1 || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case requested the wrong step count")
    failed_trace.accepted_steps == 1 || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case did not accept one step")
    failed_trace.rejected_steps == 0 || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case rejected a step")
    failed_trace.gradient_checkpoints == 1 || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case recorded the wrong checkpoints")
    failed_trace.w_derivations == failed_trace.gradient_checkpoints || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case did not derive W per checkpoint")
    failed_trace.selected_source === :standard || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case violated no-harm fallback")
    failed_trace.selection_reason === :standard_fallback || error(
        "$PC_DIRECT_CZ_READER_NAME zero-input case recorded the wrong fallback")
    failed_trace.rescue_crc_valid && error(
        "$PC_DIRECT_CZ_READER_NAME zero-input rescue unexpectedly passed CRC")

    rescue_modem = JunaCore.JunaDirectCzFrame.Modulation(
        nc=64, np=16, ldpc_k=20, ldpc_n=40, ldpc_npc=2,
        partial_fft_parts=2, partial_fft_nbands=2,
        pilot_ratio=1/3, inner_pilot_ratio=0.0,
        refinement_steps=8,
    )
    rescue_bits = Bool[
        isodd(count_ones(37i + 5)) for i in 1:24
    ]
    rescue_waveform = PC_Modulations.modulate(
        rescue_modem, rescue_bits, PC_FC, PC_FS)
    signal_power = sum(abs2, rescue_waveform) / length(rescue_waveform)
    sigma = sqrt(signal_power /
                 (2 * 10.0^(PC_DIRECT_CZ_RESCUE_SNR_DB / 10.0)))
    rescue_rng = MersenneTwister(PC_DIRECT_CZ_RESCUE_SEED)
    rescue_received = rescue_waveform .+ sigma .* (
        randn(rescue_rng, length(rescue_waveform)) .+
        1im .* randn(rescue_rng, length(rescue_waveform)))
    rescue_metrics, _ = PC_Modulations.demodulate(
        rescue_modem, length(rescue_bits), rescue_received, PC_FC, PC_FS)
    rescue_trace = JunaCore.Juna._direct_cz_last_trace(rescue_modem)
    rescue_trace.standard_crc_valid && error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture unexpectedly passed Standard CRC")
    rescue_trace.rescue_executed || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture did not run refinement")
    rescue_trace.requested_steps == 8 || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture requested the wrong step count")
    rescue_trace.accepted_steps == 8 || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture did not accept eight steps")
    rescue_trace.rejected_steps == 0 || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture rejected a step")
    rescue_trace.gradient_checkpoints == 8 || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture recorded the wrong checkpoints")
    rescue_trace.w_derivations == 8 || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture derived W the wrong number of times")
    rescue_trace.rescue_crc_valid || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture did not certify Direct C,z")
    rescue_trace.selected_source === :direct_cz || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture did not select Direct C,z")
    rescue_trace.selection_reason === :crc_rescue || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture recorded the wrong selection")
    rescue_trace.selected_iteration == 1 || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture selected the wrong iteration")
    all((rescue_metrics .> 0) .== rescue_bits) || error(
        "$PC_DIRECT_CZ_READER_NAME rescue fixture did not decode every payload bit")

    decisions = vcat(
        UInt8.(clean_metrics .> 0), UInt8.(bits),
        UInt8.(rescue_metrics .> 0), UInt8.(rescue_bits))
    println(stderr, "  $PC_DIRECT_CZ_READER_NAME compact cases: ",
            sum((clean_metrics .> 0) .== bits), "/", nbits,
            " clean bits and ",
            sum((rescue_metrics .> 0) .== rescue_bits), "/",
            length(rescue_bits), " rescued bits correct; ",
            failed_trace.accepted_steps, " zero-input step and ",
            rescue_trace.accepted_steps, " rescue steps accepted")
    bytes2hex(PC_SHA.sha256(decisions))
end

function parity_digests()
    results = Dict{String,String}()
    for (label, factory) in PC_RECEIVERS
        for (scenario, noise_scale) in PC_SCENARIOS
            decisions = UInt8[]
            modem = factory()
            nbits = PC_Modulations.bitspersymbol(modem)
            rng = MersenneTwister(PC_SEED)
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
    results[PC_DIRECT_CZ_KEY] = direct_cz_parity_digest()
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
    println("  \"seed\": ", PC_SEED, ",")
    println("  \"direct_cz_rescue\": {\"seed\": ",
            PC_DIRECT_CZ_RESCUE_SEED, ", \"snr_db\": ",
            PC_DIRECT_CZ_RESCUE_SNR_DB, "},")
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
        "$PC_CONDITIONED_JOINT_READER_NAME compact case" :
        key == PC_DIRECT_CZ_KEY ?
        "$PC_DIRECT_CZ_READER_NAME compact case" : key
    println("parity $label: ", actual[key], " PASS")
end
summary_bytes = Vector{UInt8}(codeunits(join(
    ["$key=$(actual[key])" for key in sort(collect(keys(actual)))], "\n")))
println("parity digest: ", bytes2hex(PC_SHA.sha256(summary_bytes)),
        " (aggregate of keyed receiver/scenario digests)")
println("per-receiver parity: PASS (", length(actual), " keyed digests)")
