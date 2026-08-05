#!/usr/bin/env julia
#
# Export receiver_catalog.jl to deterministic JSON for the explorer.
# Usage: julia --project=. tools/explorer/export_receivers.jl [output.json]

include(joinpath(@__DIR__, "receiver_catalog.jl"))
assert_receiver_catalog()

_json_escape(s::AbstractString) =
    replace(replace(replace(s, "\\" => "\\\\"), "\"" => "\\\""), "\n" => "\\n")

function _strings(io, values)
    print(io, "[", join(["\"" * _json_escape(v) * "\"" for v in values], ", "),
          "]")
end

function _emit(io, receivers)
    println(io, "{")
    println(io, "  \"generated_from\": \"tools/explorer/receiver_catalog.jl\",")
    println(io, "  \"receivers\": [")
    for (i, r) in enumerate(receivers)
        print(io, "    {\"id\": \"", _json_escape(r.id), "\", ",
              "\"display_name\": \"", _json_escape(r.display_name), "\", ",
              "\"facade\": \"", _json_escape(r.facade), "\", ",
              "\"mode\": \"", _json_escape(r.mode), "\", ",
              "\"profile\": \"", _json_escape(r.profile), "\", ",
              "\"chain_path\": ")
        _strings(io, r.chain_path)
        print(io, ", \"role\": \"", _json_escape(r.role), "\", ",
              "\"specific_suite_exemption\": \"",
              _json_escape(r.specific_suite_exemption), "\", ",
              "\"purpose\": \"", _json_escape(r.purpose), "\"}")
        println(io, i < length(receivers) ? "," : "")
    end
    println(io, "  ]")
    println(io, "}")
end

out = isempty(ARGS) ? joinpath(@__DIR__, "receivers.json") : ARGS[1]
open(io -> _emit(io, RECEIVERS), out, "w")
println("wrote ", out, " (", length(RECEIVERS), " receivers)")
