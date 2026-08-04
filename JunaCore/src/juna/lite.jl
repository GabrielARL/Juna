# JUNA-lite starts from the Partial-FFT candidate, then re-fits the combiner
# toward BP posterior means as soft data anchors and keeps the best re-decode.
function _juna_lite(m::Modulation, code::_Code, layout::_Layout, yparts,
                    initial_candidate=nothing)
  _payload_from_metrics(
    m, code,
    _juna_lite_candidate(
      m, code, layout, yparts, initial_candidate).posterior_metric)
end

function _juna_lite_candidate(m::Modulation, code::_Code, layout::_Layout,
                              yparts, initial_candidate=nothing)
  _required_transmitted_symbols(m, layout, code.n, 1)
  initial_candidate = initial_candidate === nothing ?
    _initial_candidate(m, code, layout, yparts) : initial_candidate
  initial_candidate.ldpc_valid && return initial_candidate

  current = initial_candidate
  best = initial_candidate
  for _ in 1:_JUNA_ITERS
    candidate = _lite_refinement_step(m, code, layout, yparts, current)
    _candidate_is_better(best, candidate) && (best = candidate)
    step_improves = _candidate_is_better(current, candidate)
    current = candidate
    candidate.ldpc_valid && break
    step_improves || break
  end

  best
end

# Transmitted-symbol anchors are supplied one column per codeword block; a
# single-block receiver reads column 1. Anything other than a matching shape is
# an error rather than a silent fall-through, so a mis-shaped grid cannot
# quietly degrade an experiment setting into the deployed one.
_transmitted_symbol_block(::Nothing, ::Integer) = nothing
_transmitted_symbol_block(transmitted_symbols::AbstractMatrix, block::Integer) =
  1 <= block <= size(transmitted_symbols, 2) ? view(transmitted_symbols, :, block) :
  throw(DimensionMismatch(
    "transmitted symbols cover $(size(transmitted_symbols, 2)) blocks; block $block was requested"))
_transmitted_symbol_block(transmitted_symbols::AbstractVector, block::Integer) =
  block == 1 ? transmitted_symbols :
  throw(DimensionMismatch(
    "transmitted symbols cover one block; block $block was requested"))

function _required_transmitted_symbols(m::Modulation, layout::_Layout,
                                       ncoded::Integer, block::Integer)
  m.anchor_feedback_source in _FEEDBACK_TRANSMITTED_SYMBOL_MODES || return nothing
  transmitted_symbols = _transmitted_symbol_block(m.transmitted_symbols, block)
  transmitted_symbols === nothing && throw(ArgumentError(
    "anchor_feedback_source $(m.anchor_feedback_source) requires transmitted symbols; " *
    "none were supplied"))
  count_data = min(length(layout.data_idx), _ndata_tones(m, ncoded))
  length(transmitted_symbols) >= count_data || throw(DimensionMismatch(
    "transmitted symbols cover $(length(transmitted_symbols)) carriers but $count_data are in play"))
  transmitted_symbols
end

function _lite_anchor_targets(m::Modulation,
                              layout::_Layout,
                              posterior_metric;
                              confidence_min::Real = _JUNA_CONFIDENCE_MIN,
                              max_data_anchors::Integer = _JUNA_MAX_DATA_ANCHORS,
                              transmitted_symbols = nothing)
  isfinite(confidence_min) && confidence_min >= 0 ||
    throw(ArgumentError("confidence_min must be finite and nonnegative"))
  max_data_anchors >= 0 ||
    throw(ArgumentError("max_data_anchors must be nonnegative"))

  anchors = _posterior_symbols(m, posterior_metric)
  confidence = _posterior_confidence(m, posterior_metric)
  n = min(length(anchors), length(layout.data_idx))
  mode = m.anchor_feedback_source

  # Control arm: the coupled machinery runs unchanged, but no data decision ever
  # anchors the re-fit.  This is the baseline for mechanism claims -- comparing
  # against the separate receiver instead would confound the feedback path with
  # every other difference between the two receivers.
  if mode === _FEEDBACK_PILOTS_ONLY
    return (; target_idx = copy(layout.pilot_idx),
            targets = copy(layout.pilot_syms),
            target_weights = ones(Float64, length(layout.pilot_idx)),
            selected = Int[], confidence)
  end

  # These arms replace posterior decisions with transmitted symbols. A null
  # result shows only that this receiver's refit did not improve with those
  # anchors. :corrupted_transmitted_symbols receives symbols that the caller
  # has already corrupted, so the receiver stays deterministic and both
  # settings share one path.
  if mode in _FEEDBACK_TRANSMITTED_SYMBOL_MODES
    transmitted_symbols === nothing && throw(ArgumentError(
      "anchor_feedback_source $mode requires transmitted symbols; none were supplied"))
    length(transmitted_symbols) >= n || throw(DimensionMismatch(
      "transmitted symbols cover $(length(transmitted_symbols)) carriers but $n data carriers are in play"))
    selected = collect(1:n)
    if length(selected) > max_data_anchors
      # The same top-k rule as :decoder_posterior keeps the anchor count fixed.
      order = sortperm(confidence[selected]; rev=true)
      selected = selected[order[1:max_data_anchors]]
    end
    target_idx = vcat(layout.pilot_idx, layout.data_idx[selected])
    targets = vcat(layout.pilot_syms, ComplexF64.(transmitted_symbols[selected]))
    target_weights = ones(Float64, length(target_idx))
    return (; target_idx, targets, target_weights, selected, confidence)
  end

  selected = [i for i in 1:n if confidence[i] >= confidence_min]

  if length(selected) > max_data_anchors
    order = sortperm(confidence[selected]; rev=true)
    selected = selected[order[1:max_data_anchors]]
  end

  target_idx = vcat(layout.pilot_idx, layout.data_idx[selected])
  targets = vcat(layout.pilot_syms, ComplexF64.(anchors[selected]))
  target_weights = vcat(ones(Float64, length(layout.pilot_idx)), confidence[selected])
  (; target_idx, targets, target_weights, selected, confidence)
end

"""
    corrupt_feedback_symbols(transmitted_symbols, p, rng, alphabet)

Replace each symbol independently with probability `p` by a different point of
`alphabet`. Used to build `:corrupted_transmitted_symbols` anchors outside the
receiver, so corruption is seeded and reproducible alongside the frame payload
and noise.

Note the idealization recorded in the pre-registration: real decision errors are
bursty and correlated with the channel state, whereas these are independent.
"""
function corrupt_feedback_symbols(transmitted_symbols::AbstractVector, p::Real, rng,
                                  alphabet::AbstractVector)
  isfinite(p) && 0 <= p <= 1 ||
    throw(ArgumentError("corruption probability must lie in [0, 1]"))
  length(alphabet) >= 2 ||
    throw(ArgumentError("need at least two constellation points to corrupt into"))
  out = ComplexF64.(transmitted_symbols)
  p == 0 && return out
  for i in eachindex(out)
    rand(rng) < p || continue
    wrong = filter(s -> !isapprox(s, out[i]; rtol=0, atol=1e-12), alphabet)
    isempty(wrong) && continue
    out[i] = ComplexF64(wrong[rand(rng, 1:length(wrong))])
  end
  out
end

function _lite_refinement_step(m::Modulation, code::_Code, layout::_Layout, yparts, current)
  anchors = _lite_anchor_targets(m, layout, current.posterior_metric;
                                 transmitted_symbols = _required_transmitted_symbols(
                                   m, layout, code.n, 1))
  equalized = _equalize_from_targets(
    m, yparts, layout, anchors.target_idx, anchors.targets;
    target_weights = anchors.target_weights,
  )
  _candidate_from_equalized(m, code, layout, equalized)
end
