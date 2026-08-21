#!/usr/bin/env julia

# Parameterized local-only entry point for the validated native-Blue runner.
const BLUE_NFFT = parse(Int, get(ENV, "JUNA_BLUE_NATIVE_NFFT", "0"))
BLUE_NFFT in (512, 1024, 1152, 1200, 1280, 1344, 1408, 1536, 2048) || error(
    "JUNA_BLUE_NATIVE_NFFT must be one of 512, 1024, 2048")
const BASE = joinpath(
    @__DIR__, "run_blue_native_awgn_n1536_p6_8_crc_no_harm.jl")
isfile(BASE) || error("missing native-Blue runner at $BASE")
source = replace(read(BASE, String), "1536" => string(BLUE_NFFT))
include_string(Main, source, BASE * "#n$(BLUE_NFFT)")
