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
     chain_path = ["acquisition", "seed", "posterior", "anchors", "refit",
                   "redecode", "keep-best"],
     role = "proposed",
     specific_suite_exemption = "",
     purpose = "Partial-FFT seed plus decoder-guided combiner refinement."),
]

function assert_receiver_catalog()
    @assert length(unique(r.id for r in RECEIVERS)) == length(RECEIVERS)
    @assert length(unique(r.facade for r in RECEIVERS)) == length(RECEIVERS)
    @assert Set(r.facade for r in RECEIVERS) ==
            Set(["JunaOFDMFEC", "JunaPartialFFT", "JunaLite"])
    for receiver in RECEIVERS
        facade = getfield(JunaCore, Symbol(receiver.facade))
        modem = facade.Modulation()
        @assert string(modem.mode) == receiver.mode
        @assert string(JunaCore.Juna.receiver_profile(modem)) == receiver.profile
    end
    true
end
