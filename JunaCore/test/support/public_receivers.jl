# Shared descriptors for cross-cutting public-boundary tests.
#
# The catalog has one entry for each reader-selectable receiver family. The
# C,z refinement entry uses the base facade; its CRC and joint C,W,z public
# facades are covered by the receiver-specific family tests.

const PUBLIC_RECEIVER_DESCRIPTORS = (
    (name = "OFDM+FEC", mode = :ofdm_fec,
     profile = :ofdm_fec, factory = JunaCore.Juna.OFDMFECModulation,
     supports_bpsk = true, supports_shifted_band = true),
    (name = "Partial-FFT", mode = :pfft,
     profile = :pfft, factory = JunaCore.Juna.PartialFFTModulation,
     supports_bpsk = true, supports_shifted_band = true),
    (name = "JUNA-Lite", mode = :lite,
     profile = :lite, factory = JunaCore.Juna.LiteModulation,
     supports_bpsk = true, supports_shifted_band = true),
    (name = "C,z refinement", mode = :frame_wide_ldpc,
     profile = :frame_wide_ldpc,
     factory = JunaCore.JunaCzRefinement.Modulation,
     supports_bpsk = false, supports_shifted_band = true),
)

public_receiver_descriptors() = PUBLIC_RECEIVER_DESCRIPTORS
public_receiver(descriptor; kwargs...) = descriptor.factory(; kwargs...)

function assert_public_receiver_catalog()
    runtime_modes = JunaCore.Juna._PUBLIC_RECEIVER_MODES
    descriptor_modes = Tuple(descriptor.mode for descriptor in
                                public_receiver_descriptors())

    @test length(unique(descriptor_modes)) == length(descriptor_modes)
    @test descriptor_modes == (:ofdm_fec, :pfft, :lite, :frame_wide_ldpc)
    @test runtime_modes == descriptor_modes
    for descriptor in public_receiver_descriptors()
        receiver = public_receiver(descriptor)
        @test receiver.mode === descriptor.mode
        @test JunaCore.Juna.receiver_profile(receiver) === descriptor.profile
        @test (Int(receiver.bits_per_data_carrier) == 1 &&
               descriptor.supports_bpsk) ||
              Int(receiver.bits_per_data_carrier) == 2
    end
end
