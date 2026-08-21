#!/usr/bin/env julia

# Local-only Blue native-bandwidth specialization of the validated Red AWGN
# runner.  Keeping the transformation here makes the experiment inherit the
# exact CRC-gated no-harm receiver policy and trace contract from the Red
# baseline while documenting every deliberate Blue-specific change.

const BASE = joinpath(@__DIR__, "run_awgn_n512_crc_no_harm.jl")
isfile(BASE) || error("missing validated Red AWGN runner at $BASE")
const BLUE_FRAME_DURATION_BUDGET = parse(
    Float64, get(ENV, "JUNA_BLUE_NATIVE_FRAME_BUDGET", "1.0"))
BLUE_FRAME_DURATION_BUDGET in (0.7, 0.8, 1.0, 1.1, 1.28, 1.3) ||
    error("unsupported native-Blue frame-duration budget")
# CL-286: cyclic prefix, seed and budget are substituted here in the Blue
# runner, leaving run_awgn_n512_crc_no_harm.jl byte-identical (CL-278). The
# baseline identifier already carries the cyclic prefix; seed and budget,
# which it does not, are appended as tokens suppressed at their defaults so
# every existing 6/8 directory name is unchanged.
const BLUE_CP = parse(Int, get(ENV, "JUNA_BLUE_NATIVE_CP", "64"))
const BLUE_SEED = parse(Int, get(ENV, "JUNA_BLUE_NATIVE_SEED", "4"))
const BLUE_ID_SUFFIX = string(
    BLUE_SEED == 4 ? "" : "-s$(BLUE_SEED)",
    BLUE_FRAME_DURATION_BUDGET == 1.0 ? "" :
        "-b" * replace(string(BLUE_FRAME_DURATION_BUDGET), "." => "p"))

source = read(BASE, String)
source = replace(source, "seed=4," => "seed=$(BLUE_SEED),")

function replace_required(text, old, new)
    occursin(old, text) || error("Blue runner transform no longer matches: $old")
    replace(text, old => new)
end

# The retained Red runner uses the historical frame-profile spelling. Keep
# the published algorithm id/name while targeting the current canonical
# receiver symbol in JunaCore.
source = replace_required(source, "profile=:ofdm_fec", "profile=:standard")

source = replace_required(source, "frame_duration_s=1.0",
    "frame_duration_s=$(BLUE_FRAME_DURATION_BUDGET)")

source = replace(source, "N512" => "N1536", "n512" => "n1536")
source = replace_required(source,
    "2026-08-10-red-awgn-first\$(CAPTURE_LABEL)s-frames32-crc-gated-no-harm-",
    "2026-08-13-blue-awgn-native-f\$(CAPTURE_LABEL)s-f1s-frames32-crc-no-harm-")
source = replace_required(source,
    "n1536-cp64-rate025-p5-5-dc14-kfill-pfft4",
    "n1536-cp$(BLUE_CP)-r025-p6-8-dc14-kfill-pfft4$(BLUE_ID_SUFFIX)")
source = replace_required(source,
    "red_snr_sweep_awgn_first\$(CAPTURE_LABEL)s_frames32_configuration.csv",
    "blue_snr_sweep_awgn_native_first\$(CAPTURE_LABEL)s_frames32_configuration.csv")
source = replace_required(source,
    "const PATHS = [(Symbol(\"red\$channel\"), lane)",
    "const PATHS = [(Symbol(\"blue\$channel\"), lane)")
source = replace_required(source,
    "nfft=512, cp=64, code_rate=0.25,\n    outer_spacing=5, inner_spacing=5,",
    "nfft=1536, cp=$(BLUE_CP), code_rate=0.25,\n    outer_spacing=6, inner_spacing=8,")
source = replace_required(source,
    "nfft=512, cp=64, code_rate=0.25,\n        outer_spacing=5, inner_spacing=5,",
    "nfft=1536, cp=$(BLUE_CP), code_rate=0.25,\n        outer_spacing=6, inner_spacing=8,")
source = replace_required(source, "JUNA_RED_DATA_DIR", "JUNA_BLUE_DATA_DIR")
source = replace_required(source,
    "campaign=N1536-CRC-GATED-NO-HARM-FIRST\$(CAPTURE_LABEL)S",
    "campaign=BLUE-NATIVE-AWGN-N1536-CRC-GATED-NO-HARM-FIRST\$(CAPTURE_LABEL)S")

const BLUE_INSERT = raw"""

const BLUE_CHANNEL_FILES = Dict(
    :blue1 => "blue_1.mat", :blue2 => "blue_2.mat",
    :blue3 => "blue_3.mat", :blue4 => "blue_4.mat",
)
const BLUE_NATIVE_MODEM_FS = 4_882.8125
const BLUE_NATIVE_CAPTURE_FS = 9_765.625
const BLUE_NATIVE_FC = 13_000.0
# Red uses 2048 samples/burst at 9600 Hz.  1042 at the Blue modem rate
# preserves the physical burst duration (0.2133 s) to sub-sample precision.
const BLUE_NATIVE_SYNC_SAMPLES = 1_042

function load_blue_capture(path::AbstractString; receiver::Integer=1)
    isfile(path) || error("missing Blue replay capture: $path")
    filesize(path) > 1_000_000 || error("Blue replay capture is truncated: $path")
    data = B.ReplayLane.MAT.matopen(path) do file
        Dict(
            "h_hat" => read(file, "h_hat"),
            "phi_hat" => read(file, "phi_hat"),
            "params" => read(file, "params"),
        )
    end
    capture = B.ReplayLane.capture_from_dict(
        data; receiver=receiver, name=first(splitext(basename(path))))
    capture.fs == BLUE_NATIVE_CAPTURE_FS || error("Blue capture fs differs")
    capture.fc == BLUE_NATIVE_FC || error("Blue capture fc differs")
    capture.step == 200 || error("Blue capture snapshot step differs")
    capture
end

@eval Juna begin
    _synclen(m::Modulation) = m.sync ? $BLUE_NATIVE_SYNC_SAMPLES : 0
    _sync_overhead(m::Modulation, fs) =
        m.sync ? $(2 * BLUE_NATIVE_SYNC_SAMPLES) : 0
end
"""
source = replace_required(source, "const Modulations = B.Modulations\n",
                          "const Modulations = B.Modulations\n" * BLUE_INSERT)
source = replace_required(source,
    "getproperty(A.CHANNEL_FILES, channel)", "BLUE_CHANNEL_FILES[channel]")
source = replace_required(source,
    "full = B.load_capture(file; receiver=Int(lane))",
    "full = load_blue_capture(file; receiver=Int(lane))")
source = replace(source, "CAPTURE_SECONDS * 96" =>
                          "CAPTURE_SECONDS * 48.828125")
source = replace(source, "CAPTURE_SECONDS * 19_200" =>
                          "CAPTURE_SECONDS * 9_765.625")
source = replace(source, "9_600.0" => "BLUE_NATIVE_MODEM_FS")
source = replace(source, "(768, expected_taps)" => "(320, expected_taps)")
source = replace(source, ":red1" => ":blue1")

# Add an explicit ungated C,z arm alongside the five established receivers.
# The protected C,z and C,W,z arms retain their CRC no-harm policy and traces.
function add_direct_cz(text)
    direct_anchor =
        "    (id=:profiled_cz, name=\"JUNA (C,z) CRC no-harm\", profile=:profiled_cz,\n"
    text = replace_required(text, direct_anchor,
        "    (id=:direct_cz, name=\"JUNA (C,z) direct\", profile=:profiled_cz,\n" *
        "     cz_crc_gate=false, cz_gradient_only=true, partial_fft_parts=4),\n" *
        direct_anchor)
    for (old, new) in (
        ("csv_shape(paths.aggregate, AGGREGATE_HEADER, 80)",
         "csv_shape(paths.aggregate, AGGREGATE_HEADER, 96)"),
        ("csv_shape(paths.frame_trace, FRAME_TRACE_HEADER, 2_560)",
         "csv_shape(paths.frame_trace, FRAME_TRACE_HEADER, 3_072)"),
        ("\"aggregate_rows=80\"", "\"aggregate_rows=96\""),
        ("\"frame_trace_rows=2560\"", "\"frame_trace_rows=3072\""),
        ("length(rows) == 5 * length(expected_snrs)",
         "length(rows) == 6 * length(expected_snrs)"),
        ("length(frames) == 5 * length(expected_snrs) * expected_frames",
         "length(frames) == 6 * length(expected_snrs) * expected_frames"),
        ("CONTRACT_PASS receivers=5", "CONTRACT_PASS receivers=6"),
    )
        text = replace_required(text, old, new)
    end
    text
end
source = add_direct_cz(source)

include_string(Main, source, BASE * "#blue-native")
