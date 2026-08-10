#!/usr/bin/env julia

module Awgn024Sweep

using JunaCore
using SHA

const SHARED_REPOSITORY = get(
    ENV, "JUNA_AWGN024_SHARED_REPOSITORY",
    "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-results")
const RECEIVER_REPOSITORY = get(
    ENV, "JUNA_AWGN024_RECEIVER_REPOSITORY",
    "/home/gabiel/Documents/GitHub/Juna-worktrees/crc-no-harm-gradients")
const SHARED_EXPERIMENTS = joinpath(SHARED_REPOSITORY, "JunaCore", "experiments")
const FIRST4_HARNESS = joinpath(
    SHARED_EXPERIMENTS,
    "2026-08-08-red-awgn-first4s-frames4-snr-sweep",
    "first4s_sweep.jl")
include(FIRST4_HARNESS)
using .AwgnFirst4SecondsSweep
const F = AwgnFirst4SecondsSweep
const A = F.A
const B = F.B
const Juna = JunaCore.Juna
const Modulations = JunaCore.Modulations

const DECISION = "AWGN-024"
const FAMILY = "2026-08-10-red-awgn-first32s-frames32-rate05-crc-no-harm"
const CONFIGURATIONS = [(
    id="$FAMILY-n1024-cp64-rate05-p5-5-dc14-kfill-pfft4",
    config=(nfft=1024, cp=64, code_rate=0.5,
            outer_spacing=5, inner_spacing=5,
            check_degree=14, horizon=0),
)]
const PATHS = [
    (Symbol("red$(channel)"), hydrophone)
    for channel in 1:4 for hydrophone in 1:3
]
const SNR_DB = 0:2:30
const FRAMES = 32
const CAPTURE_SECONDS = 32.0
const SEED = 4
const PARTIAL_FFT_PARTS = 4
const EXPECTED_PAYLOAD_BITS_PER_FRAME = 3_248
const EXPECTED_PAYLOAD_BITS_PER_POINT =
    EXPECTED_PAYLOAD_BITS_PER_FRAME * FRAMES
const AWGN022_SNAPSHOT_INDICES = [1, 96, 190, 285, 385, 480, 574, 669, 769, 864, 958, 1053, 1153, 1248, 1342, 1437, 1537, 1632, 1726, 1821, 1921, 2016, 2110, 2205, 2305, 2400, 2494, 2589, 2689, 2784, 2878, 2973]
const SNAPSHOT_INDICES = copy(AWGN022_SNAPSHOT_INDICES)
const GENERIC_THIRTYTWO_SNAPSHOT_INDICES = [1, 97, 193, 289, 384, 480, 576, 672, 768, 864, 960, 1056, 1151, 1247, 1343, 1439, 1535, 1631, 1727, 1823, 1918, 2014, 2110, 2206, 2302, 2398, 2494, 2590, 2685, 2781, 2877, 2973]
const GENERIC_APPENDED_SIXTEEN_SNAPSHOT_INDICES = [1537, 1633, 1728, 1824, 1920, 2016, 2111, 2207, 2303, 2399, 2494, 2590, 2686, 2782, 2877, 2973]
const DATA_DIR = get(
    ENV, "JUNA_RED_DATA_DIR",
    joinpath(SHARED_EXPERIMENTS, "2026-08-01-red-lite-search", "data"))
const EXPECTED_ACTIVE_PROJECT = joinpath(
    SHARED_EXPERIMENTS, "2026-08-04-red-snr-sweep", "Project.toml")
const AWGN022_HARNESS_DIR = get(
    ENV, "JUNA_AWGN024_AWGN022_HARNESS_DIR",
    "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-022-first32s/JunaCore/experiments/2026-08-10-red-awgn-first32s-frames32-crc-no-harm-sweep")
const AWGN022_SCHEDULE_SOURCE =
    joinpath(AWGN022_HARNESS_DIR, "awgn022_sweep.jl")
const AWGN022_SOURCE_CONTRACT =
    joinpath(AWGN022_HARNESS_DIR, "source_contract.json")
const EXPECTED_AWGN022_SCHEDULE_SOURCE_SHA256 =
    "6da387b2571f847bcc49770233acbe06b638f6954be76ed6c2799ab39e5a6010"
const EXPECTED_AWGN022_SOURCE_CONTRACT_SHA256 =
    "4959c4bb447306c73fea56e08c64e442c277eb4ec492c147fffa2c2f766f38db"
const EXPECTED_SOURCE_HEAD = "7fbdec9dd93e7ed5caade4bae4a73ccd030a7d3f"
const EXPECTED_SOURCE_DIFF_SHA256 =
    "4e19b15bea8fd9c96c2721691629ae35deb3538e43b92ccc1ec9a7fe8cdf8821"
const EXPECTED_SOURCE_STATUS = join((
    " M JunaCore/src/JunaCore.jl",
    " M JunaCore/src/juna/common.jl",
    " M JunaCore/src/juna/frame_wide_ldpc.jl",
    " M JunaCore/src/juna/profiled_cz_frame.jl",
), '\n')
const EXPECTED_CHANGED_SOURCE_SHA256 = Dict(
    "JunaCore/src/JunaCore.jl" =>
        "1666665f7a2728033d8f3645afa308fa8605d238dc534d038f4a611b0f419932",
    "JunaCore/src/juna/common.jl" =>
        "447bada2fb97bcff256f0d5acf6b9e6b867f1d852f0b3e24a9c8344eabb906ff",
    "JunaCore/src/juna/frame_wide_ldpc.jl" =>
        "f220e44dd80b5332ece6c140fdd8ac75e31ce8849bb2584de16e2cf561a12ab2",
    "JunaCore/src/juna/profiled_cz_frame.jl" =>
        "46c2e77080a6161c356acfe1691f9139ef0102ee5fa1696cd317ece426b4feb4",
)
const EXPECTED_HARNESS_SHA256 = Dict(
    "2026-08-07-red-awgn-snr-sweep/awgn_snr_sweep.jl" =>
        "29551eefadda77eb9709a3caf5c9887e99c40a0c0e58eb071b4c3fe65475f8e9",
    "2026-08-08-red-awgn-first4s-frames4-snr-sweep/first4s_sweep.jl" =>
        "667593f13bff1f8be70ba09f70eac2c1bb9631e011acabe68b33ac52589575f4",
    "2026-08-04-red-snr-sweep/benchmark_port.jl" =>
        "c683529ca32220f563163570294ce372114c4c1994e19a8cd3621c0615caffbe",
    "2026-08-04-red-snr-sweep/replay_lane.jl" =>
        "e4e00b84e96abc863c42d76a8494c3cefc9d81cf3dbb2354be08ceba3cfae6f3",
    "2026-08-04-red-snr-sweep/Project.toml" =>
        "09dd9b79369735576e21c210c969e16dbf77cc1ea333aecb2e4ee9d3b13a0ef0",
    "2026-08-04-red-snr-sweep/Manifest.toml" =>
        "ab8752e8e162a64bcf22441d1b4906dd30ef7c40447b7d8abe5bc22a93226b90",
)
const EXPECTED_DATA_SHA256 = Dict(
    "red_1.mat" => "09556b49e453a351f72b5c71435aab0048f68a80ab3b926ca4353dab47e89c45",
    "red_2.mat" => "0e42027cd51137e0c4519c7a9c109568ab513a5eece1abfc60b0073fe605f6eb",
    "red_3.mat" => "e3e4e53e96ec361e3df492616ae3f024727f039b5e5b1405dd709c8265798179",
    "red_4.mat" => "115ac3d1ae8b067858192f32a3fcfd073ee0220b3e2d0f5a6dc1dc7460bd27aa",
)

const ALGORITHMS = (
    (id=:ofdm_fec, name="OFDM + FEC", profile=:standard,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    (id=:pfft, name="Partial-FFT + FEC", profile=:pfft,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    (id=:lite, name="JUNA-Lite", profile=:lite,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    # The two protected descriptors intentionally use the historical Lite
    # profile. The decode boundary below replaces only their receiver object.
    (id=:profiled_cz, name="JUNA (C,z) Joint gradient", profile=:lite,
     partial_fft_parts=PARTIAL_FFT_PARTS),
    (id=:cwz_joint, name="Juna joint (C,W,z)", profile=:lite,
     partial_fft_parts=PARTIAL_FFT_PARTS),
)
const RECEIVER_IDS = ("ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint")
const PROTECTED_RECEIVER_IDS = ("profiled_cz", "cwz_joint")
const ALLOWED_SELECTION_REASONS =
    ("standard_crc_valid", "crc_rescue", "standard_fallback")

const AGGREGATE_HEADER = (
    "channel", "lane", "snr_db", "algorithm_id", "seed", "frames",
    "objective", "noise_model", "nfft", "cp", "code_rate",
    "outer_spacing", "inner_spacing", "check_degree", "horizon",
    "partial_fft_parts", "partial_fft_bands", "payload_bits_per_frame",
    "successful_frames", "psr", "payload_bits", "bit_errors", "ber",
    "decode_failures", "decode_seconds", "effective_rate_bps",
    "capture_start_seconds", "capture_stop_seconds",
    "capture_tap_snapshots", "capture_phase_samples",
)
const FRAME_TRACE_HEADER = (
    "workload_id", "snr_db", "frame", "algorithm_id", "noise_model",
    "capture_start_seconds", "capture_stop_seconds", "snapshot_index",
    "snapshot_seconds", "replay_support_end_seconds",
    "frame_duration_seconds", "frame_samples", "payload_bits",
    "payload_seed", "noise_seed", "replay_seed", "optimizer_seed",
    "bit_errors", "success", "decode_failure", "partial_fft_parts",
    "partial_fft_bands",
)
const PROTECTED_TRACE_HEADER = (
    "workload_id", "snr_db", "frame", "algorithm_id", "noise_model",
    "capture_start_seconds", "capture_stop_seconds", "snapshot_index",
    "snapshot_seconds", "replay_support_end_seconds",
    "frame_duration_seconds", "bit_errors", "success", "decode_failure",
    "selected_source", "selection_reason", "standard_crc_valid",
    "rescue_executed", "rescue_is_gradient", "rescue_crc_valid",
    "gradient_checkpoints", "selected_iteration", "optimized_variables",
    "partial_fft_parts", "partial_fft_bands",
)
const AGGREGATE_BASENAME =
    "red_snr_sweep_awgn_first32s_frames32_configuration.csv"
const FRAME_TRACE_BASENAME_SUFFIX = "_frame_trace.csv"
const PROTECTED_TRACE_BASENAME_SUFFIX = "_selection_trace.csv"
const _CAPTURE_CACHE = Dict{Tuple{String,Symbol,Int},Any}()

# Repeat the approved four-frame placement in each four-second block. The
# first sixteen positions remain the complete AWGN-021 workload schedule.
@eval B begin
    function _snapshot_positions(capture::ReplayCapture, packets::Integer,
                                 waveform_length::Integer, modem_fs::Real)
        count = Int(packets)
        count > 0 || throw(ArgumentError("packets must be positive"))
        waveform_length > 0 || throw(ArgumentError(
            "waveform length must be positive"))
        rate = Float64(modem_fs)
        isfinite(rate) && rate > 0 || throw(ArgumentError(
            "modem fs must be positive"))
        planning_length = Int(waveform_length) + 22
        _channel_samples, stop = _capture_position_limit(
            capture, planning_length, rate)
        if count == 32
            positions = [1, 96, 190, 285, 385, 480, 574, 669, 769, 864, 958, 1053, 1153, 1248, 1342, 1437, 1537, 1632, 1726, 1821, 1921, 2016, 2110, 2205, 2305, 2400, 2494, 2589, 2689, 2784, 2878, 2973]
            last(positions) <= stop || throw(ArgumentError(
                "capture supports positions through $stop, needs 2973"))
            return positions
        end
        count <= stop || throw(ArgumentError(
            "capture has only $stop distinct packet positions, requested $count"))
        count == 1 && return [1]
        positions = round.(Int, range(1, stop; length=count))
        allunique(positions) || throw(ArgumentError(
            "packet positions are not distinct"))
        positions
    end
end

file_sha256(path::AbstractString) = open(path) do io
    bytes2hex(sha256(io))
end

function _require_file_hash(path, expected, description)
    isfile(path) || error("AWGN-024 missing $description: $path")
    islink(path) && error("AWGN-024 refuses symlinked $description: $path")
    actual = file_sha256(path)
    actual == expected || error(
        "AWGN-024 $description content differs: expected $expected, got $actual")
end

function require_source_contract()
    package_root = realpath(dirname(dirname(pathof(JunaCore))))
    package_root == realpath(joinpath(RECEIVER_REPOSITORY, "JunaCore")) ||
        error("AWGN-024 loaded JunaCore from $package_root")
    git_root = readchomp(`git -C $package_root rev-parse --show-toplevel`)
    readchomp(`git -C $git_root rev-parse HEAD`) == EXPECTED_SOURCE_HEAD ||
        error("AWGN-024 receiver base commit differs")
    status = chomp(read(
        `git -C $git_root status --porcelain=v1 --untracked-files=all -- JunaCore/src`,
        String))
    status == EXPECTED_SOURCE_STATUS || error(
        "AWGN-024 receiver source status differs:\n$status")
    bytes2hex(sha256(read(`git -C $git_root diff --binary -- JunaCore/src`))) ==
        EXPECTED_SOURCE_DIFF_SHA256 || error(
            "AWGN-024 receiver source diff differs")
    for (relative, expected) in EXPECTED_CHANGED_SOURCE_SHA256
        _require_file_hash(joinpath(git_root, relative), expected,
                           "receiver source $relative")
    end
    nothing
end

function require_public_receiver_contract()
    lite = Juna.FrameWideLDPCModulation(
        frame_receiver=:lite, frame_crc_bits=16)
    cz = JunaCore.JunaProfiledCzFrame.Modulation()
    cwz = JunaCore.JunaCrcConditionedJointCwzFrame.Modulation()
    JunaCore.JunaProfiledCzFrame.Modulation ===
        Juna.CrcNoHarmProfiledCzFrameModulation || error(
            "AWGN-024 C,z public module alias differs")
    JunaCore.JunaCrcConditionedJointCwzFrame.Modulation ===
        Juna.CrcNoHarmConditionedJointCwzFrameModulation || error(
            "AWGN-024 C,W,z public module alias differs")
    !lite.cz_crc_no_harm && lite.frame_receiver === :lite || error(
        "AWGN-024 Lite was changed")
    for (receiver, conditioned, mode) in (
            (cz, false, :frame_wide_ldpc),
            (cwz, true, :crc_profiled_cz_frame))
        receiver.mode === mode || error("AWGN-024 protected mode differs")
        receiver.frame_receiver === :profiled_cz || error(
            "AWGN-024 protected frame receiver differs")
        receiver.frame_crc_bits == 16 && receiver.cz_crc_no_harm || error(
            "AWGN-024 protected CRC no-harm contract differs")
        !receiver.cz_crc_gate && !receiver.cz_gate_selection_only &&
            receiver.cz_gradient_only || error(
                "AWGN-024 protected gradient contract differs")
        receiver.cz_conditioned_joint == conditioned || error(
            "AWGN-024 conditioned-joint setting differs")
    end
    !cz.cz_em_enabled && !cz.cz_independent_w && cz.cz_bp_feedback == 0.0 &&
        !cz.cz_vp_gradient || error("AWGN-024 C,z fixed settings differ")
    cwz.cz_em_enabled && !cwz.cz_independent_w &&
        cwz.cz_bp_feedback == 0.5 && cwz.cz_vp_gradient || error(
            "AWGN-024 C,W,z fixed settings differ")
    nothing
end

function require_harness_contract()
    active_project = Base.active_project()
    active_project === nothing && error("AWGN-024 has no active Julia project")
    realpath(active_project) == realpath(EXPECTED_ACTIVE_PROJECT) || error(
        "AWGN-024 active Julia project differs: $active_project")
    for (relative, expected) in EXPECTED_HARNESS_SHA256
        _require_file_hash(joinpath(SHARED_EXPERIMENTS, relative), expected,
                           "shared harness $relative")
    end
    _require_file_hash(
        AWGN022_SCHEDULE_SOURCE, EXPECTED_AWGN022_SCHEDULE_SOURCE_SHA256,
        "AWGN-022 schedule source")
    _require_file_hash(
        AWGN022_SOURCE_CONTRACT, EXPECTED_AWGN022_SOURCE_CONTRACT_SHA256,
        "AWGN-022 source contract")
    nothing
end

function require_contract(; verify_data::Bool=true)
    length(CONFIGURATIONS) == 1 || error("AWGN-024 configuration count differs")
    only(CONFIGURATIONS).config == (
        nfft=1024, cp=64, code_rate=0.5,
        outer_spacing=5, inner_spacing=5,
        check_degree=14, horizon=0,
    ) || error("AWGN-024 configuration differs")
    EXPECTED_PAYLOAD_BITS_PER_FRAME == 3_248 &&
        EXPECTED_PAYLOAD_BITS_PER_POINT == 103_936 || error(
            "AWGN-024 payload contract differs")
    length(PATHS) == 12 || error("AWGN-024 path count differs")
    collect(SNR_DB) == collect(0:2:30) || error("AWGN-024 SNR grid differs")
    FRAMES == 32 && CAPTURE_SECONDS == 32.0 && SEED == 4 || error(
        "AWGN-024 capture, frame, or seed contract differs")
    SNAPSHOT_INDICES == AWGN022_SNAPSHOT_INDICES || error(
        "AWGN-024 AWGN-022 replay schedule differs")
    SNAPSHOT_INDICES == [1, 96, 190, 285, 385, 480, 574, 669, 769, 864, 958, 1053, 1153, 1248, 1342, 1437, 1537, 1632, 1726, 1821, 1921, 2016, 2110, 2205, 2305, 2400, 2494, 2589, 2689, 2784, 2878, 2973] || error(
        "AWGN-024 nested replay positions differ")
    require_source_contract()
    require_harness_contract()
    require_public_receiver_contract()
    if verify_data
        for (filename, expected) in EXPECTED_DATA_SHA256
            _require_file_hash(joinpath(DATA_DIR, filename), expected,
                               "measured capture $filename")
        end
    end
    nothing
end

function _populate_capture_cache!(channel::Symbol, data_dir::AbstractString)
    filename = getproperty(F.CHANNEL_FILES, channel)
    file = joinpath(data_dir, filename)
    isfile(file) || error("AWGN-024 missing measured capture: $file")
    islink(file) && error("AWGN-024 refuses symlinked measured capture: $file")
    data = F.MAT.matread(file)
    for lane in 1:3
        full = B.capture_from_dict(data; receiver=lane, name=splitext(filename)[1])
        cropped = F.crop_first_seconds(full, CAPTURE_SECONDS)
        _CAPTURE_CACHE[(String(data_dir), channel, lane)] = B.ReplayLane.ReplayCapture(
            cropped.h, cropped.phase, cropped.fs, cropped.fc, cropped.step,
            cropped.receiver, replace(cropped.name, "first4s" => "first32s"))
    end
    empty!(data)
    GC.gc()
end

function load_first32s_capture(channel::Symbol, lane::Integer;
                              data_dir::AbstractString=DATA_DIR)
    rx = Int(lane)
    1 <= rx <= 3 || error("hydrophone must be in 1:3")
    key = (String(data_dir), channel, rx)
    haskey(_CAPTURE_CACHE, key) || _populate_capture_cache!(channel, data_dir)
    _CAPTURE_CACHE[key]
end

snapshot_seconds(capture, snapshot::Integer) =
    (Int(snapshot) - 1) * capture.step / capture.fs

function replay_support_end_seconds(capture, snapshot::Integer,
                                    frame_samples::Integer)
    passband_samples = Int(frame_samples) + F.PASSBAND_MODEM_PADDING_SAMPLES
    channel_samples = ceil(Int, passband_samples * capture.fs / A.MODEM_FS)
    last_offset = channel_samples + size(capture.h, 1) - 2
    snapshot_seconds(capture, snapshot) + last_offset / capture.fs
end

function require_snapshot_contract(capture, config)
    config == only(CONFIGURATIONS).config || error(
        "AWGN-024 snapshot contract received another configuration")
    size(capture.h) == (768, 3_073) || error(
        "AWGN-024 cropped tap geometry differs")
    length(capture.phase) == 614_600 || error(
        "AWGN-024 cropped phase geometry differs")
    frame_samples = 9_536
    _, stop = B._capture_position_limit(
        capture, frame_samples + F.PASSBAND_MODEM_PADDING_SAMPLES, A.MODEM_FS)
    stop == 2_973 || error("AWGN-024 capture position stop differs: $stop")
    ends = [replay_support_end_seconds(capture, snapshot, frame_samples)
            for snapshot in SNAPSHOT_INDICES]
    maximum(ends) <= CAPTURE_SECONDS || error(
        "AWGN-024 replay support exceeds the first thirty-two seconds")
    (
        snapshot_indices=copy(SNAPSHOT_INDICES),
        position_stop=stop,
        frame_samples,
        payload_bits_per_frame=EXPECTED_PAYLOAD_BITS_PER_FRAME,
        support_end_seconds=ends,
        payload_seeds=collect(SEED:(SEED + FRAMES - 1)),
        noise_seeds=collect(SEED:(SEED + FRAMES - 1)),
        replay_seeds=collect(SEED:(SEED + FRAMES - 1)),
        optimizer_seeds=fill(SEED, FRAMES),
    )
end

function _configure_protected_receiver(id::Symbol, capture, config)
    constructor = id === :profiled_cz ?
        JunaCore.JunaProfiledCzFrame.Modulation : id === :cwz_joint ?
        JunaCore.JunaCrcConditionedJointCwzFrame.Modulation :
        error("AWGN-024 unknown protected receiver: $id")
    receiver = constructor(frame_duration_s=A.FRAME_DURATION_S)
    bandwidth = B._effective_bandwidth_geometry(capture, A.MODEM_FS, 1.0)
    B._configure_modem!(
        receiver, capture.fc, A.MODEM_FS, :passband_replay;
        nfft=config.nfft, cp=config.cp,
        partial_fft_parts=PARTIAL_FFT_PARTS,
        code_rate=config.code_rate, check_degree=config.check_degree,
        ldpc_method=:auto, ldpc_seed=51_001, ldpc_no4cycle=true,
        sync_profile=:lfm, frame_duration_s=A.FRAME_DURATION_S,
        outer_pilot_ratio=1 / config.outer_spacing,
        inner_pilot_ratio=1 / config.inner_spacing,
        bw=bandwidth.normalized_bw)
    Modulations.isvalid(receiver, capture.fc, A.MODEM_FS) || error(
        "AWGN-024 public receiver $id is invalid after configuration")
    receiver
end

function _protected_receivers(capture, config)
    receivers = Dict(id => _configure_protected_receiver(id, capture, config)
                     for id in (:profiled_cz, :cwz_joint))
    blocks = unique(Juna.frameblockcount(receiver, A.MODEM_FS)
                    for receiver in values(receivers))
    length(blocks) == 1 || error(
        "AWGN-024 protected receivers disagree on frame blocks")
    payloads = unique(Juna._frame_payload_capacity(receiver, only(blocks))
                      for receiver in values(receivers))
    only(payloads) == EXPECTED_PAYLOAD_BITS_PER_FRAME || error(
        "AWGN-024 protected payload capacity differs")
    receivers
end

function _frame_trace_row(row, id::Symbol, capture)
    (
        workload_id=row.workload_id, snr_db=row.snr_db, frame=row.frame,
        algorithm_id=String(id), noise_model="awgn",
        capture_start_seconds=0.0, capture_stop_seconds=CAPTURE_SECONDS,
        snapshot_index=row.snapshot_index,
        snapshot_seconds=snapshot_seconds(capture, row.snapshot_index),
        replay_support_end_seconds=replay_support_end_seconds(
            capture, row.snapshot_index, row.frame_samples),
        frame_duration_seconds=row.frame_duration_seconds,
        frame_samples=row.frame_samples, payload_bits=row.payload_bits,
        payload_seed=row.payload_seed, noise_seed=row.noise_seed,
        replay_seed=row.replay_seed, optimizer_seed=row.optimizer_seed,
        bit_errors=row.bit_errors, success=row.success,
        decode_failure=row.decode_failure,
        partial_fft_parts=row.partial_fft_parts,
        partial_fft_bands=row.partial_fft_bands,
    )
end

function _protected_trace_row(row, id::Symbol, capture, trace_bundle)
    no_harm = trace_bundle.no_harm
    gradient = trace_bundle.gradient
    selected_iteration = gradient === nothing ? 0 : Int(gradient.selected_iteration)
    (
        workload_id=row.workload_id, snr_db=row.snr_db, frame=row.frame,
        algorithm_id=String(id), noise_model="awgn",
        capture_start_seconds=0.0, capture_stop_seconds=CAPTURE_SECONDS,
        snapshot_index=row.snapshot_index,
        snapshot_seconds=snapshot_seconds(capture, row.snapshot_index),
        replay_support_end_seconds=replay_support_end_seconds(
            capture, row.snapshot_index, row.frame_samples),
        frame_duration_seconds=row.frame_duration_seconds,
        bit_errors=row.bit_errors, success=row.success,
        decode_failure=row.decode_failure,
        selected_source=String(no_harm.selected_source),
        selection_reason=String(no_harm.selection_reason),
        standard_crc_valid=Bool(no_harm.standard_crc_valid),
        rescue_executed=Bool(no_harm.rescue_executed),
        rescue_is_gradient=Bool(no_harm.rescue_is_gradient),
        rescue_crc_valid=Bool(no_harm.rescue_crc_valid),
        gradient_checkpoints=Int(no_harm.gradient_checkpoints),
        selected_iteration,
        optimized_variables=id === :profiled_cz ? "C+z" : "C+W+z",
        partial_fft_parts=row.partial_fft_parts,
        partial_fft_bands=row.partial_fft_bands,
    )
end

function evaluate(capture, channel_id, lane, config, snr_db;
                  frame_sink::Function=_row -> nothing,
                  protected_sink::Function=_row -> nothing)
    B._noise_override() === nothing || error(
        "AWGN-024 refuses a non-AWGN noise override")
    require_snapshot_contract(capture, config)
    protected = _protected_receivers(capture, config)
    trace_bundles = Dict{Symbol,Any}()
    ids_by_name = Dict(algorithm.name => Symbol(algorithm.id)
                       for algorithm in ALGORITHMS)

    function decode(item, payload_bits, decoder_input, fc, fs)
        id = Symbol(item.descriptor.id)
        if id in (:ofdm_fec, :pfft, :lite)
            id === :lite && item.receiver.cz_crc_no_harm && error(
                "AWGN-024 Lite changed at decode boundary")
            return first(Modulations.demodulate(
                item.receiver, payload_bits, decoder_input, fc, fs))
        end
        receiver = protected[id]
        receiver.code = item.receiver.code
        receiver.layout = item.receiver.layout
        receiver.bp_scratch = nothing
        receiver.cz_restart_seed = item.receiver.cz_restart_seed
        receiver.cz_crc_no_harm_trace = nothing
        receiver.cz_gradient_trace = nothing
        metrics = first(Modulations.demodulate(
            receiver, payload_bits, decoder_input, fc, fs))
        no_harm = Juna._cz_crc_no_harm_last_trace(receiver)
        gradient = receiver.cz_gradient_trace === nothing ? nothing :
            Juna._cz_gradient_last_trace(receiver)
        trace_bundles[id] = (no_harm=no_harm, gradient=gradient)
        metrics
    end

    function benchmark_sink(row)
        id = ids_by_name[row.algorithm]
        frame_sink(_frame_trace_row(row, id, capture))
        if id in (:profiled_cz, :cwz_joint)
            haskey(trace_bundles, id) || error(
                "AWGN-024 protected decode produced no no-harm trace")
            protected_sink(_protected_trace_row(
                row, id, capture, pop!(trace_bundles, id)))
        end
        nothing
    end

    rows = B.benchmark_frame_capture(
        capture;
        channel_id=String(channel_id), frames=FRAMES,
        frame_blocks=config.horizon == 0 ? nothing : Int(config.horizon),
        frame_duration_s=A.FRAME_DURATION_S,
        frame_crc_bits=A.FRAME_CRC_BITS,
        algorithms=ALGORITHMS, snr_db=Float64(snr_db), seed=SEED,
        modem_fs=A.MODEM_FS, modem_profile=:passband_replay,
        sync_profile=:lfm, nfft=config.nfft, cp=config.cp,
        code_rate=config.code_rate, check_degree=config.check_degree,
        ldpc_method=:auto, ldpc_seed=51_001, ldpc_no4cycle=true,
        outer_pilot_ratio=1 / config.outer_spacing,
        inner_pilot_ratio=1 / config.inner_spacing,
        frame_decode_function=decode, frame_sink=benchmark_sink)
    isempty(trace_bundles) || error(
        "AWGN-024 did not consume every protected trace")
    [(
        channel=String(channel_id), lane=Int(lane),
        snr_db=Float64(snr_db), algorithm_id=String(ALGORITHMS[i].id),
        seed=SEED, frames=FRAMES, objective="configuration",
        noise_model="awgn", nfft=config.nfft, cp=config.cp,
        code_rate=config.code_rate, outer_spacing=config.outer_spacing,
        inner_spacing=config.inner_spacing,
        check_degree=config.check_degree, horizon=config.horizon,
        partial_fft_parts=Int(row.partial_fft_parts),
        partial_fft_bands=Int(row.partial_fft_bands),
        payload_bits_per_frame=Int(row.payload_bits_per_frame),
        successful_frames=Int(row.successful_frames), psr=Float64(row.psr),
        payload_bits=Int(row.payload_bits), bit_errors=Int(row.bit_errors),
        ber=Float64(row.ber), decode_failures=Int(row.decode_failures),
        decode_seconds=Float64(row.mean_decode_seconds_per_frame),
        effective_rate_bps=Float64(row.effective_rate_bps),
        capture_start_seconds=0.0, capture_stop_seconds=CAPTURE_SECONDS,
        capture_tap_snapshots=size(capture.h, 2),
        capture_phase_samples=length(capture.phase),
    ) for (i, row) in pairs(rows)]
end

expected_aggregate_rows() = length(ALGORITHMS) * length(SNR_DB)
expected_frame_trace_rows() = length(ALGORITHMS) * length(SNR_DB) * FRAMES
expected_protected_trace_rows() =
    length(PROTECTED_RECEIVER_IDS) * length(SNR_DB) * FRAMES

function validate_path_rows(rows, frame_traces, protected_traces;
                            snrs=collect(SNR_DB))
    expected_snrs = Float64.(collect(snrs))
    length(rows) == length(ALGORITHMS) * length(expected_snrs) || error(
        "AWGN-024 aggregate row count differs")
    length(frame_traces) == length(ALGORITHMS) * length(expected_snrs) * FRAMES ||
        error("AWGN-024 frame trace row count differs")
    length(protected_traces) ==
        length(PROTECTED_RECEIVER_IDS) * length(expected_snrs) * FRAMES ||
        error("AWGN-024 protected trace row count differs")
    keys(first(rows)) == Symbol.(AGGREGATE_HEADER) || error(
        "AWGN-024 aggregate schema differs")
    keys(first(frame_traces)) == Symbol.(FRAME_TRACE_HEADER) || error(
        "AWGN-024 frame trace schema differs")
    keys(first(protected_traces)) == Symbol.(PROTECTED_TRACE_HEADER) || error(
        "AWGN-024 protected trace schema differs")
    all(row.payload_bits_per_frame == EXPECTED_PAYLOAD_BITS_PER_FRAME
        for row in rows) || error(
            "AWGN-024 aggregate payload bits per frame differ")
    all(row.payload_bits == EXPECTED_PAYLOAD_BITS_PER_POINT
        for row in rows) || error(
            "AWGN-024 aggregate payload bits per point differ")
    all(row.payload_bits == EXPECTED_PAYLOAD_BITS_PER_FRAME
        for row in frame_traces) || error(
            "AWGN-024 frame payload bits differ")
    Set(row.algorithm_id for row in rows) == Set(RECEIVER_IDS) || error(
        "AWGN-024 aggregate receiver IDs differ")
    Set(row.algorithm_id for row in frame_traces) == Set(RECEIVER_IDS) || error(
        "AWGN-024 frame trace receiver IDs differ")
    Set(row.algorithm_id for row in protected_traces) ==
        Set(PROTECTED_RECEIVER_IDS) || error(
            "AWGN-024 protected receiver IDs differ")
    all(!row.decode_failure for row in frame_traces) || error(
        "AWGN-024 frame trace contains a decode failure")
    all(!row.decode_failure for row in protected_traces) || error(
        "AWGN-024 protected trace contains a decode failure")
    all(row.payload_seed == row.noise_seed == row.replay_seed
        for row in frame_traces) || error("AWGN-024 paired frame seeds differ")
    all(row.optimizer_seed == SEED for row in frame_traces) || error(
        "AWGN-024 optimizer seed differs")
    all(row.snapshot_index == SNAPSHOT_INDICES[row.frame]
        for row in frame_traces) || error(
            "AWGN-024 frame replay positions differ")
    all(row.frame in 1:FRAMES for row in frame_traces) || error(
        "AWGN-024 frame index differs")
    all(row.payload_seed == SEED + row.frame - 1 &&
        row.noise_seed == SEED + row.frame - 1 &&
        row.replay_seed == SEED + row.frame - 1
        for row in frame_traces) || error(
            "AWGN-024 per-frame seeds differ")
    all(row.replay_support_end_seconds <= CAPTURE_SECONDS
        for row in frame_traces) || error(
            "AWGN-024 frame replay support exceeds thirty-two seconds")
    length(Set((row.algorithm_id, row.snr_db) for row in rows)) == length(rows) ||
        error("AWGN-024 aggregate keys are not unique")
    length(Set((row.algorithm_id, row.snr_db, row.frame)
               for row in frame_traces)) == length(frame_traces) || error(
        "AWGN-024 frame trace keys are not unique")
    length(Set((row.algorithm_id, row.snr_db, row.frame)
               for row in protected_traces)) == length(protected_traces) || error(
        "AWGN-024 protected trace keys are not unique")
    for snr in expected_snrs, frame in 1:FRAMES
        paired = [row for row in frame_traces
                  if row.snr_db == snr && row.frame == frame]
        length(paired) == length(ALGORITHMS) || error(
            "AWGN-024 paired workload receiver count differs")
        length(Set((row.workload_id, row.snapshot_index, row.payload_seed,
                    row.noise_seed, row.replay_seed, row.optimizer_seed)
                   for row in paired)) == 1 || error(
            "AWGN-024 receivers do not share one paired workload")
    end
    for receiver in RECEIVER_IDS, snr in expected_snrs
        aggregate = only(row for row in rows
                         if row.algorithm_id == receiver && row.snr_db == snr)
        frames = [row for row in frame_traces
                  if row.algorithm_id == receiver && row.snr_db == snr]
        sum(row.bit_errors for row in frames) == aggregate.bit_errors || error(
            "AWGN-024 frame errors do not reconcile")
        count(row -> row.success, frames) == aggregate.successful_frames || error(
            "AWGN-024 frame successes do not reconcile")
    end
    for receiver in PROTECTED_RECEIVER_IDS, snr in expected_snrs
        aggregate = only(row for row in rows
                         if row.algorithm_id == receiver && row.snr_db == snr)
        frames = [row for row in protected_traces
                  if row.algorithm_id == receiver && row.snr_db == snr]
        sum(row.bit_errors for row in frames) == aggregate.bit_errors || error(
            "AWGN-024 protected errors do not reconcile")
        count(row -> row.success, frames) == aggregate.successful_frames || error(
            "AWGN-024 protected successes do not reconcile")
        all(row.selection_reason in ALLOWED_SELECTION_REASONS for row in frames) ||
            error("AWGN-024 protected selection reason differs")
    end
    all(row.optimized_variables ==
        (row.algorithm_id == "profiled_cz" ? "C+z" : "C+W+z")
        for row in protected_traces) || error(
            "AWGN-024 optimized-variable label differs")
    for row in protected_traces
        if row.selection_reason == "standard_crc_valid"
            row.selected_source == "standard" && row.standard_crc_valid &&
                !row.rescue_executed && !row.rescue_is_gradient &&
                !row.rescue_crc_valid && row.gradient_checkpoints == 0 &&
                row.selected_iteration == 0 || error(
                    "AWGN-024 Standard short-circuit trace is inconsistent")
        elseif row.selection_reason == "crc_rescue"
            row.selected_source == "gradient" && !row.standard_crc_valid &&
                row.rescue_executed && row.rescue_is_gradient &&
                row.rescue_crc_valid && row.gradient_checkpoints > 0 &&
                row.selected_iteration > 0 || error(
                    "AWGN-024 CRC rescue trace is inconsistent")
        else
            row.selected_source == "standard" && !row.standard_crc_valid &&
                row.rescue_executed && !row.rescue_crc_valid &&
                row.gradient_checkpoints > 0 &&
                row.selected_iteration >= 0 || error(
                    "AWGN-024 Standard fallback trace is inconsistent")
        end
    end
    true
end

function write_csv(destination::AbstractString, rows, expected_header)
    isempty(rows) && error("AWGN-024 refuses an empty CSV")
    keys(first(rows)) == Symbol.(expected_header) || error(
        "AWGN-024 CSV schema differs")
    mkpath(dirname(destination))
    open(destination, "w") do io
        println(io, join(expected_header, ','))
        for row in rows
            println(io, join((getproperty(row, name)
                              for name in Symbol.(expected_header)), ','))
        end
    end
    destination
end

function run_path(channel::Symbol, lane::Integer, config;
                  data_dir::AbstractString=DATA_DIR,
                  aggregate_destination::AbstractString,
                  frame_trace_destination::AbstractString,
                  protected_trace_destination::AbstractString,
                  snrs=collect(SNR_DB), validate_full::Bool=true)
    require_contract(; verify_data=false)
    capture = load_first32s_capture(channel, lane; data_dir)
    groups = max(1, min(Threads.nthreads(), length(snrs)))
    chunks = [collect(snrs)[i:groups:end] for i in 1:groups]
    rows_by_chunk = [NamedTuple[] for _ in 1:groups]
    frames_by_chunk = [NamedTuple[] for _ in 1:groups]
    protected_by_chunk = [NamedTuple[] for _ in 1:groups]
    println(channel, " hydrophone ", lane,
            " AWGN-024 N=1024 CP=64 rate=0.5 pilots=5/5 dc=14 ",
            "K=fill PFFT parts=4 capture=first 32.0 s frames=32 receivers=5")
    println("cropped capture loaded; sweeping ", length(snrs),
            " SNR points on ", groups, " threads")
    flush(stdout)
    Threads.@threads for index in 1:groups
        for snr in chunks[index]
            append!(rows_by_chunk[index], evaluate(
                capture, channel, lane, config, snr;
                frame_sink=row -> push!(frames_by_chunk[index], row),
                protected_sink=row -> push!(protected_by_chunk[index], row)))
            println("  ", channel, " hydrophone ", lane,
                    " AWGN-024 SNR ", snr, " done")
            flush(stdout)
        end
    end
    rows = sort(reduce(vcat, rows_by_chunk);
                by=row -> (row.snr_db, row.algorithm_id))
    frame_traces = sort(reduce(vcat, frames_by_chunk);
                        by=row -> (row.snr_db, row.algorithm_id, row.frame))
    protected_traces = sort(reduce(vcat, protected_by_chunk);
                            by=row -> (row.snr_db, row.algorithm_id, row.frame))
    validate_full && validate_path_rows(rows, frame_traces, protected_traces)
    write_csv(aggregate_destination, rows, AGGREGATE_HEADER)
    write_csv(frame_trace_destination, frame_traces, FRAME_TRACE_HEADER)
    write_csv(protected_trace_destination, protected_traces,
              PROTECTED_TRACE_HEADER)
    println("PATH_DONE ", channel, " hydrophone ", lane,
            " aggregate_rows=", length(rows),
            " frame_trace_rows=", length(frame_traces),
            " protected_trace_rows=", length(protected_traces))
    flush(stdout)
    rows, frame_traces, protected_traces
end

function probe_path(; channel::Symbol=:red1, lane::Integer=1,
                    spec=first(CONFIGURATIONS), snrs=collect(SNR_DB))
    capture = load_first32s_capture(channel, lane; data_dir=DATA_DIR)
    rows = NamedTuple[]
    frame_traces = NamedTuple[]
    protected_traces = NamedTuple[]
    for snr in snrs
        append!(rows, evaluate(
            capture, channel, lane, spec.config, snr;
            frame_sink=row -> push!(frame_traces, row),
            protected_sink=row -> push!(protected_traces, row)))
    end
    sort!(rows; by=row -> (row.snr_db, row.algorithm_id))
    sort!(frame_traces; by=row -> (row.snr_db, row.algorithm_id, row.frame))
    sort!(protected_traces; by=row -> (row.snr_db, row.algorithm_id, row.frame))
    rows, frame_traces, protected_traces
end

end # module
