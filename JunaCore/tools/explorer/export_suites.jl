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
include(joinpath(EXPORT_ROOT, "test", "runtests.jl"))  # loads SUITES; runs nothing

_json_escape(s::AbstractString) =
    replace(replace(replace(s, "\\" => "\\\\"), "\"" => "\\\""), "\n" => "\\n")

function _emit(io, suites)
    println(io, "{")
    println(io, "  \"generated_from\": \"test/runtests.jl\",")
    println(io, "  \"suites\": [")
    for (i, s) in enumerate(suites)
        print(io, "    {\"key\": \"", _json_escape(s.key), "\", ",
              "\"file\": \"", _json_escape(s.file), "\", ",
              "\"title\": \"", _json_escape(s.title), "\", ",
              "\"claim\": \"", _json_escape(s.claim), "\", ",
              "\"provenance\": \"", _json_escape(s.provenance), "\"}")
        println(io, i < length(suites) ? "," : "")
    end
    println(io, "  ]")
    println(io, "}")
end

out = isempty(ARGS) ? joinpath(@__DIR__, "suites.json") : ARGS[1]
open(io -> _emit(io, SUITES), out, "w")
println("wrote ", out, " (", length(SUITES), " suites)")
