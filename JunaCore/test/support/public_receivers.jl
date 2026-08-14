# Shared descriptors for cross-cutting public-boundary tests.
#
# The shared catalog has one entry for each public runtime mode exercised by
# the cross-cutting boundary tests. The CRC, conditioned C,W,z, and Direct C,z
# wrapper facades are covered by receiver-specific suites.

const PUBLIC_RECEIVER_DESCRIPTORS = (
    (name = "Standard OFDM", key = :standard, mode = :standard,
     profile = :standard, factory = JunaCore.Juna.StandardModulation,
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
    (name = "Profiled C,z", key = :profiled_cz,
     mode = :frame_wide_ldpc, profile = :frame_wide_ldpc,
     factory = JunaCore.JunaProfiledCzFrame.Modulation,
     supports_bpsk = false, supports_lfm = true,
     supports_shifted_band = true, supports_synthetic_uwa = true),
)

public_receiver_descriptors() = PUBLIC_RECEIVER_DESCRIPTORS
public_receiver(descriptor; kwargs...) = descriptor.factory(; kwargs...)

function assert_public_receiver_catalog()
    runtime_modes = JunaCore.Juna._PUBLIC_RECEIVER_MODES
    descriptor_modes = Tuple(descriptor.mode for descriptor in
                                public_receiver_descriptors())

    @test length(unique(descriptor_modes)) == length(descriptor_modes)
    # Every catalog mode must be a runtime mode. Variant facades share the
    # Profiled C,z family's frame-wide mode and are checked in its own suites.
    @test all(mode -> mode in runtime_modes, descriptor_modes)
    @test descriptor_modes == (:standard, :pfft, :lite, :frame_wide_ldpc)
    for descriptor in public_receiver_descriptors()
        receiver = public_receiver(descriptor)
        @test receiver.mode === descriptor.mode
        @test JunaCore.Juna.receiver_profile(receiver) === descriptor.profile
        @test (Int(receiver.bpc) == 1 && descriptor.supports_bpsk) ||
              Int(receiver.bpc) == 2
    end
end
