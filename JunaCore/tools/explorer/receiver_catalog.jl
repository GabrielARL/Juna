# Authoritative catalog for the package's public receiver facades.
#
# This stays in Julia because the factories and modes are Julia behavior.
# export_receivers.jl emits the explorer's receivers.json; the explorer
# contract byte-compares that generated file so the browser cannot drift.

using JunaCore

const RECEIVERS = [
    (id = "standard",
     display_name = "Standard OFDM + FEC",
     facade = "JunaStandard",
     mode = "standard",
     profile = "standard",
     frame_receiver = "",
     objective = "none",
     conditioned_joint = false,
     variant_facades = String[],
     chain_path = ["acquisition", "standard"],
     role = "baseline",
     specific_suite_exemption =
        "standard-specific behavior is covered by the shared baseline suite",
     purpose = "One-tap pilot-interpolated OFDM equalization followed by FEC."),
    (id = "partial-fft",
     display_name = "Partial-FFT + FEC",
     facade = "JunaPartialFFT",
     mode = "pfft",
     profile = "pfft",
     frame_receiver = "",
     objective = "pilot_band_ls",
     conditioned_joint = false,
     variant_facades = String[],
     chain_path = ["acquisition", "initial-candidate"],
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
     conditioned_joint = false,
     variant_facades = String[],
     chain_path = ["acquisition", "initial-candidate", "posterior", "anchors", "refit",
                   "redecode", "keep-best"],
     role = "proposed",
     specific_suite_exemption = "",
     purpose = "Partial-FFT initial candidate plus decoder-guided combiner refinement."),
    (id = "profiled_cz",
     display_name = "Profiled C,z",
     facade = "JunaProfiledCzFrame",
     mode = "frame_wide_ldpc",
     profile = "frame_wide_ldpc",
     frame_receiver = "profiled_cz",
     objective = "profiled_cz_frame",
     conditioned_joint = false,
     variant_facades = ["JunaCrcProfiledCzFrame"],
     chain_path = ["acquisition", "frame", "profiled_cz"],
     role = "proposed",
     specific_suite_exemption = "",
     purpose = "Frame-wide C,z refinement; solves C conditional on z and derives W from C."),
    (id = "conditioned_joint_cwz",
     display_name = "Conditioned joint C,W,z",
     facade = "JunaCrcConditionedJointCwzFrame",
     mode = "crc_profiled_cz_frame",
     profile = "frame_wide_ldpc",
     frame_receiver = "profiled_cz",
     objective = "profiled_cz_frame",
     conditioned_joint = true,
     variant_facades = String[],
     chain_path = ["acquisition", "frame", "profiled_cz",
                   "conditioned_joint_cwz"],
     role = "proposed",
     specific_suite_exemption = "",
     purpose = "Profiled C,z frame receiver with guarded simultaneous C,W,z proposals."),
    (id = "direct_cz",
     display_name = "Direct C,z",
     facade = "JunaDirectCzFrame",
     mode = "frame_wide_ldpc",
     profile = "frame_wide_ldpc",
     frame_receiver = "profiled_cz",
     objective = "direct_cz_frame",
     conditioned_joint = false,
     variant_facades = String[],
     chain_path = ["acquisition", "frame", "direct_cz"],
     role = "proposed",
     specific_suite_exemption = "",
     purpose = "Direct simultaneous descent on C and z with CRC no-harm selection."),
]

function assert_receiver_catalog()
    @assert length(unique(r.id for r in RECEIVERS)) == length(RECEIVERS)
    all_facades = [facade for receiver in RECEIVERS
                   for facade in [receiver.facade;
                                  receiver.variant_facades]]
    @assert length(unique(all_facades)) == length(all_facades)
    @assert Set(all_facades) == Set([
        "JunaStandard", "JunaPartialFFT", "JunaLite",
        "JunaProfiledCzFrame", "JunaCrcProfiledCzFrame",
        "JunaCrcConditionedJointCwzFrame",
        "JunaDirectCzFrame",
    ])
    for receiver in RECEIVERS
        facade = getfield(JunaCore, Symbol(receiver.facade))
        modem = facade.Modulation()
        base = receiver.id == "direct_cz" ? modem.base : modem
        @assert string(base.mode) == receiver.mode
        @assert string(JunaCore.Juna.receiver_profile(base)) == receiver.profile
        @assert string(JunaCore.Modulations.refinement_objective(modem)) ==
                receiver.objective
        @assert base.cz_conditioned_joint == receiver.conditioned_joint
        isempty(receiver.frame_receiver) ||
            @assert string(base.frame_receiver) == receiver.frame_receiver
        for variant_name in receiver.variant_facades
            variant = getfield(JunaCore, Symbol(variant_name)).Modulation()
            @assert string(JunaCore.Juna.receiver_profile(variant)) ==
                    receiver.profile
            @assert string(JunaCore.Modulations.refinement_objective(variant)) ==
                    receiver.objective
            @assert variant.cz_conditioned_joint == receiver.conditioned_joint
            isempty(receiver.frame_receiver) ||
                @assert string(variant.frame_receiver) == receiver.frame_receiver
        end
    end
    true
end
