# Shared descriptors for cross-cutting public-boundary tests.
#
# Migrated subset: this catalog covers exactly the three public facades of
# this package (OFDM+FEC, Partial-FFT, JUNA-Lite). The runtime constant
# Juna._PUBLIC_RECEIVER_MODES still enumerates the earlier full nine-receiver
# family. The catalog therefore asserts subset membership in the runtime list
# plus an exact match against this package's three facades.

const PUBLIC_RECEIVER_DESCRIPTORS = (
    (name = "OFDM+FEC", key = :ofdm_fec, mode = :ofdm_fec,
     profile = :ofdm_fec, factory = JunaCore.Juna.OFDMFECModulation,
     supports_bpsk = true, supports_lfm = true, supports_shifted_band = true,
     supports_synthetic_uwa = true),
    (name = "Partial-FFT", key = :pfft, mode = :pfft,
     profile = :pfft, factory = JunaCore.Juna.PartialFFTModulation,
     supports_bpsk = true, supports_lfm = true, supports_shifted_band = true,
     supports_synthetic_uwa = true),
    (name = "JUNA-Lite", key = :lite, mode = :lite,
     profile = :lite, factory = JunaCore.Juna.LiteModulation,
     supports_bpsk = true, supports_lfm = true, supports_shifted_band = true,
     supports_synthetic_uwa = true),
)

public_receiver_descriptors() = PUBLIC_RECEIVER_DESCRIPTORS
public_receiver(descriptor; kwargs...) = descriptor.factory(; kwargs...)

function assert_public_receiver_catalog()
    runtime_modes = JunaCore.Juna._PUBLIC_RECEIVER_MODES
    descriptor_modes = Tuple(descriptor.mode for descriptor in
                                public_receiver_descriptors())

    @test length(unique(descriptor_modes)) == length(descriptor_modes)
    # common.jl still lists the whole family; this package exposes three
    # facades. Every catalog mode must be a runtime mode, and the catalog must
    # match this package's facades exactly.
    @test all(mode -> mode in runtime_modes, descriptor_modes)
    @test descriptor_modes == (:ofdm_fec, :pfft, :lite)
    for descriptor in public_receiver_descriptors()
        receiver = public_receiver(descriptor)
        @test receiver.mode === descriptor.mode
        @test JunaCore.Juna.receiver_profile(receiver) === descriptor.profile
        @test (Int(receiver.bpc) == 1 && descriptor.supports_bpsk) ||
              Int(receiver.bpc) == 2
    end
end
