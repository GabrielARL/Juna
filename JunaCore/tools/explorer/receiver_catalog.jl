# Authoritative catalog for the package's public receiver facades.
#
# This stays in Julia because the factories and modes are Julia behavior.
# export_receivers.jl emits the explorer's receivers.json; the explorer
# contract byte-compares that generated file so the browser cannot drift.

using JunaCore

const RECEIVERS = [
    (id = "ofdm_fec",
     display_name = "OFDM+FEC",
     facade = "JunaOFDMFEC",
     mode = "ofdm_fec",
     profile = "ofdm_fec",
     frame_receiver = "",
     objective = "none",
     variant_facades = String[],
     chain_path = ["acquisition", "ofdm_fec"],
     role = "baseline",
     specific_suite_exemption =
        "OFDM+FEC behavior is covered by the shared baseline suite",
     purpose = "One-tap pilot-interpolated OFDM equalization followed by FEC."),
    (id = "partial-fft",
     display_name = "Partial-FFT + FEC",
     facade = "JunaPartialFFT",
     mode = "pfft",
     profile = "pfft",
     frame_receiver = "",
     objective = "pilot_band_ls",
     variant_facades = String[],
     chain_path = ["acquisition", "seed"],
     role = "baseline",
     specific_suite_exemption =
        "partial-FFT-specific behavior is covered by the shared baseline suite",
     purpose = "Pilot-trained partial-FFT combining followed by FEC."),
    (id = "lite",
     display_name = "JUNA-Lite",
     facade = "JunaLite",
     mode = "lite",
     profile = "lite",
     frame_receiver = "",
     objective = "posterior_anchor_ls",
     variant_facades = String[],
     chain_path = ["acquisition", "seed", "posterior", "anchors", "refit",
                   "redecode", "keep-best"],
     role = "proposed",
     specific_suite_exemption = "",
     purpose = "Partial-FFT seed plus decoder-guided combiner refinement."),
    (id = "profiled_cz",
     display_name = "Profiled C,z",
     facade = "JunaProfiledCzFrame",
     mode = "frame_wide_ldpc",
     profile = "frame_wide_ldpc",
     frame_receiver = "profiled_cz",
     objective = "profiled_cz_frame",
     variant_facades = ["JunaCrcProfiledCzFrame",
                        "JunaCrcConditionedJointCwzFrame"],
     chain_path = ["acquisition", "frame", "profiled_cz"],
     role = "proposed",
     specific_suite_exemption = "",
     purpose = "Frame-wide variable projection over physical response C and relaxed codeword z, with CRC, turbo, and conditioned forms."),
]

function assert_receiver_catalog()
    @assert length(unique(r.id for r in RECEIVERS)) == length(RECEIVERS)
    all_facades = [facade for receiver in RECEIVERS
                   for facade in [receiver.facade;
                                  receiver.variant_facades]]
    @assert length(unique(all_facades)) == length(all_facades)
    @assert Set(all_facades) == Set([
        "JunaOFDMFEC", "JunaPartialFFT", "JunaLite",
        "JunaProfiledCzFrame", "JunaCrcProfiledCzFrame",
        "JunaCrcConditionedJointCwzFrame",
    ])
    for receiver in RECEIVERS
        facade = getfield(JunaCore, Symbol(receiver.facade))
        modem = facade.Modulation()
        @assert string(modem.mode) == receiver.mode
        @assert string(JunaCore.Juna.receiver_profile(modem)) == receiver.profile
        @assert string(JunaCore.Modulations.refinement_objective(modem)) ==
                receiver.objective
        isempty(receiver.frame_receiver) ||
            @assert string(modem.frame_receiver) == receiver.frame_receiver
        for variant_name in receiver.variant_facades
            variant = getfield(JunaCore, Symbol(variant_name)).Modulation()
            @assert string(JunaCore.Juna.receiver_profile(variant)) ==
                    receiver.profile
            @assert string(JunaCore.Modulations.refinement_objective(variant)) ==
                    receiver.objective
            isempty(receiver.frame_receiver) ||
                @assert string(variant.frame_receiver) == receiver.frame_receiver
        end
    end
    true
end
