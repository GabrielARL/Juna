#!/usr/bin/env julia
#
# Export the authoritative SUITES registry (test/runtests.jl) as JSON for the
# explorer. The registry is the single source of truth: this exporter reads
# it by including the (side-effect-guarded) runner, so the explorer can never
# drift from what Pkg.test actually runs.
#
# Usage: julia tools/explorer/export_suites.jl [output.json]
# Default output: tools/explorer/suites.json.
#
# No JSON package dependency on the Julia side; the explorer contract
# re-parses the output with Python's json module, which keeps the hand
# emitter honest.

const EXPORT_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const _REGISTRY_ONLY_KEY = "JUNA_SUITE_REGISTRY_ONLY"
const _REGISTRY_ONLY_PRIOR = get(ENV, _REGISTRY_ONLY_KEY, nothing)
ENV[_REGISTRY_ONLY_KEY] = "1"
try
    include(joinpath(EXPORT_ROOT, "test", "runtests.jl"))
finally
    if _REGISTRY_ONLY_PRIOR === nothing
        delete!(ENV, _REGISTRY_ONLY_KEY)
    else
        ENV[_REGISTRY_ONLY_KEY] = _REGISTRY_ONLY_PRIOR
    end
end

function _json_escape(s::AbstractString)
    io = IOBuffer()
    for char in s
        if char == '"'
            print(io, "\\\"")
        elseif char == '\\'
            print(io, "\\\\")
        elseif char == '\b'
            print(io, "\\b")
        elseif char == '\f'
            print(io, "\\f")
        elseif char == '\n'
            print(io, "\\n")
        elseif char == '\r'
            print(io, "\\r")
        elseif char == '\t'
            print(io, "\\t")
        elseif Int(char) < 0x20
            print(io, "\\u", lpad(string(Int(char), base=16), 4, '0'))
        else
            print(io, char)
        end
    end
    String(take!(io))
end

function _emit(io, suites)
    println(io, "{")
    println(io, "  \"generated_from\": \"test/runtests.jl\",")
    println(io, "  \"suites\": [")
    for (i, s) in enumerate(suites)
        print(io, "    {\"key\": \"", _json_escape(s.key), "\", ",
              "\"file\": \"", _json_escape(s.file), "\", ",
              "\"tier\": \"", _json_escape(s.tier), "\", ",
              "\"receivers\": \"", _json_escape(s.receivers), "\", ",
              "\"title\": \"", _json_escape(s.title), "\", ",
              "\"claim\": \"", _json_escape(s.claim), "\", ",
              "\"origin\": \"", _json_escape(s.origin), "\", ",
              "\"reader_title\": \"", _json_escape(s.reader_title), "\", ",
              "\"reader_summary\": \"", _json_escape(s.reader_summary), "\", ",
              "\"method\": \"", _json_escape(s.method), "\", ",
              "\"reader_origin\": \"", _json_escape(s.reader_origin), "\"}")
        println(io, i < length(suites) ? "," : "")
    end
    println(io, "  ]")
    println(io, "}")
end

function main()
    out = isempty(ARGS) ? joinpath(@__DIR__, "suites.json") : ARGS[1]
    open(io -> _emit(io, SUITES), out, "w")
    println("wrote ", out, " (", length(SUITES), " suites)")
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
