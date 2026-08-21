#!/usr/bin/env julia

# Parameterize the validated native-Blue runner by N and balanced pilot
# density while retaining the same channel, AWGN, frame, and receiver policy.
const NFFT = parse(Int, ENV["JUNA_BLUE_NATIVE_NFFT"])
const REQUESTED_PERCENT = parse(
    Int, ENV["JUNA_BLUE_NATIVE_REQUESTED_PERCENT"])
const SPACING = parse(Int, ENV["JUNA_BLUE_NATIVE_SPACING"])
const FRAME_BUDGET = parse(
    Float64, ENV["JUNA_BLUE_NATIVE_FRAME_BUDGET"])
const EXPECTED_FRAME_BUDGET = NFFT == 4096 ? 1.28 : 1.0
# CL-273: the identifier carried no cyclic prefix, budget, seed or variant
# token, so any run that varied one of them would overwrite a finished
# experiment. Each token is suppressed at its default value, which leaves
# every existing directory name byte-identical.
const BLUE_CP = parse(Int, get(ENV, "JUNA_BLUE_NATIVE_CP", "64"))
const BLUE_SEED = parse(Int, get(ENV, "JUNA_BLUE_NATIVE_SEED", "4"))
const BLUE_VARIANT = get(ENV, "JUNA_BLUE_NATIVE_VARIANT", "")
occursin(r"^[a-z0-9]*$", BLUE_VARIANT) ||
    error("native-Blue variant tag must be lowercase alphanumeric")
const ID_SUFFIX = string(
    BLUE_CP == 64 ? "" : "-cp$(BLUE_CP)",
    FRAME_BUDGET == EXPECTED_FRAME_BUDGET ? "" :
        "-b" * replace(string(FRAME_BUDGET), "." => "p"),
    BLUE_SEED == 4 ? "" : "-s$(BLUE_SEED)",
    isempty(BLUE_VARIANT) ? "" : "-$(BLUE_VARIANT)")
FRAME_BUDGET == EXPECTED_FRAME_BUDGET || !isempty(ID_SUFFIX) ||
    error("native-Blue frame-duration budget does not match N")
const EXPECTED_EXPERIMENT_ID =
    "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-" *
    "n$(NFFT)-d$(REQUESTED_PERCENT)-p$(SPACING)" * ID_SUFFIX
NFFT in (512, 1024, 1152, 1200, 1280, 1344, 1408, 1536, 2048, 4096) ||
    error("unsupported native-Blue pilot-density N")
REQUESTED_PERCENT in (10, 14, 20, 30, 60) ||
    error("unsupported pilot density")

function nearest_spacing(requested_total_percent::Int)
    half_density = requested_total_percent / 200
    inverse = 1 / half_density
    lower = max(2, floor(Int, inverse))
    upper = lower + 1
    first(sort((lower, upper); by=s -> (abs(half_density - 1 / s), s)))
end

SPACING == nearest_spacing(REQUESTED_PERCENT) || error(
    "pilot-density spacing does not match the 50/50 nearest-spacing rule")

const BASE = joinpath(
    @__DIR__, "run_blue_native_awgn_n1536_p6_8_crc_no_harm.jl")
isfile(BASE) || error("missing validated native-Blue runner at $BASE")
source = read(BASE, String)
source = replace(source, "1536" => string(NFFT))
source = replace(source, "p6-8" =>
    "pct$(REQUESTED_PERCENT)-p$(SPACING)-$(SPACING)")
source = replace(source, "outer_spacing=6, inner_spacing=8" =>
    "outer_spacing=$(SPACING), inner_spacing=$(SPACING)")
source = replace(source,
    "n$(NFFT)-cp64-r025-pct$(REQUESTED_PERCENT)-p$(SPACING)-$(SPACING)-dc14-kfill-pfft4" =>
    "n$(NFFT)-d$(REQUESTED_PERCENT)-p$(SPACING)" * ID_SUFFIX)

occursin("2026-08-13-blue-awgn-native-f", source) ||
    error("native-Blue experiment-ID prefix transformation is missing")
occursin("n$(NFFT)-d$(REQUESTED_PERCENT)-p$(SPACING)", source) ||
    error("native-Blue experiment-ID suffix transformation is missing")
include_string(Main, source, BASE *
    "#n$(NFFT)-pct$(REQUESTED_PERCENT)-p$(SPACING)-$(SPACING)")
