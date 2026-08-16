# Mandatory package wrapper for the measured-channel replay contract. The
# contract itself lives beside the replay helper so the same file can also run
# under the frozen experiment environment.

using Test

const REPLAY_EXPERIMENT_ROOT = normpath(joinpath(
    @__DIR__, "..", "experiments", "2026-08-04-red-snr-sweep"))

@testset "Measured-channel replay contract files" begin
    for name in (
        "Project.toml",
        "Manifest.toml",
        "replay_lane.jl",
        "benchmark_port.jl",
        "replay_lane_contract_test.jl",
    )
        @test isfile(joinpath(REPLAY_EXPERIMENT_ROOT, name))
    end
end

include(joinpath(REPLAY_EXPERIMENT_ROOT, "replay_lane_contract_test.jl"))
