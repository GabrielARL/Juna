# JUNA-lite: seed from the Partial-FFT combiner (so JUNA starts where Partial
# FFT+FEC ends), then re-fit the combiner toward BP posterior means as soft data
# anchors and keep the best re-decode.
function _juna_lite(m::Modulation, code::_Code, layout::_Layout, yparts, seed=nothing)
  _payload_from_metrics(m, code, _juna_lite_candidate(m, code, layout, yparts, seed).lpost_metric)
end

function _juna_lite_candidate(m::Modulation, code::_Code, layout::_Layout, yparts, seed=nothing)
  seed = seed === nothing ? _seed_candidate(m, code, layout, yparts) : seed
  seed.valid && return seed

  current = seed
  best = seed
  for _ in 1:_JUNA_ITERS
    candidate = _juna_step(m, code, layout, yparts, current)
    _juna_better(best, candidate) && (best = candidate)
    step_improves = _juna_better(current, candidate)
    current = candidate
    candidate.valid && break
    step_improves || break
  end

  best
end

# Ground-truth anchors are supplied one column per codeword block; a
# single-block receiver reads column 1. Anything other than a matching shape is
# an error rather than a silent fall-through, so a mis-shaped genie grid cannot
# quietly degrade an oracle arm into the deployed one.
_genie_block(::Nothing, ::Integer) = nothing
_genie_block(truth::AbstractMatrix, block::Integer) =
  1 <= block <= size(truth, 2) ? view(truth, :, block) :
  throw(DimensionMismatch(
    "genie symbols cover $(size(truth, 2)) blocks; block $block was requested"))
_genie_block(truth::AbstractVector, block::Integer) =
  block == 1 ? truth :
  throw(DimensionMismatch(
    "genie symbols cover one block; block $block was requested"))

function _juna_anchor_targets(m::Modulation,
                              layout::_Layout,
                              lpost_metric;
                              confidence_min::Real = _JUNA_CONFIDENCE_MIN,
                              max_data_anchors::Integer = _JUNA_MAX_DATA_ANCHORS,
                              truth = nothing)
  isfinite(confidence_min) && confidence_min >= 0 ||
    throw(ArgumentError("confidence_min must be finite and nonnegative"))
  max_data_anchors >= 0 ||
    throw(ArgumentError("max_data_anchors must be nonnegative"))

  anchors = _posterior_symbols(m, lpost_metric)
  confidence = _posterior_confidence(m, lpost_metric)
  n = min(length(anchors), length(layout.data_idx))
  mode = m.feedback_mode

  # Control arm: the coupled machinery runs unchanged, but no data decision ever
  # anchors the re-fit.  This is the baseline for mechanism claims -- comparing
  # against the separate receiver instead would confound the feedback path with
  # every other difference between the two receivers.
  if mode === _FEEDBACK_FROZEN
    return (; target_idx = copy(layout.pilot_idx),
            targets = copy(layout.pilot_syms),
            target_weights = ones(Float64, length(layout.pilot_idx)),
            selected = Int[], confidence)
  end

  # Oracle arms: the anchors carry the transmitted symbols instead of posterior
  # decisions.  :graded receives truth that the caller has already corrupted at
  # a known rate, so the receiver stays deterministic and both oracle arms share
  # one path.  Anchors are weighted 1.0 because a genie is certain; that makes
  # this an upper bound on what feedback can contribute, so a null result here
  # is strong evidence that no recoverable channel information exists.
  if mode in _FEEDBACK_ORACLE_MODES
    truth === nothing && throw(ArgumentError(
      "feedback_mode $mode requires transmitted symbols; none were supplied"))
    length(truth) >= n || throw(DimensionMismatch(
      "genie symbols cover $(length(truth)) tones but $n data tones are in play"))
    selected = collect(1:n)
    if length(selected) > max_data_anchors
      # Same top-k rule as :real, so the arms differ in anchor VALUES rather
      # than in how many anchors the least-squares fit sees.
      order = sortperm(confidence[selected]; rev=true)
      selected = selected[order[1:max_data_anchors]]
    end
    target_idx = vcat(layout.pilot_idx, layout.data_idx[selected])
    targets = vcat(layout.pilot_syms, ComplexF64.(truth[selected]))
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
    corrupt_feedback_symbols(truth, p, rng, alphabet)

Replace each symbol independently with probability `p` by a different point of
`alphabet`. Used to build the `:graded` arm's anchors outside the receiver, so
that corruption is seeded and reproducible alongside the frame's payload/noise.

Note the idealization recorded in the pre-registration: real decision errors are
bursty and correlated with the channel state, whereas these are independent.
"""
function corrupt_feedback_symbols(truth::AbstractVector, p::Real, rng,
                                  alphabet::AbstractVector)
  isfinite(p) && 0 <= p <= 1 ||
    throw(ArgumentError("graded error rate must lie in [0, 1]"))
  length(alphabet) >= 2 ||
    throw(ArgumentError("need at least two constellation points to corrupt into"))
  out = ComplexF64.(truth)
  p == 0 && return out
  for i in eachindex(out)
    rand(rng) < p || continue
    wrong = filter(s -> !isapprox(s, out[i]; rtol=0, atol=1e-12), alphabet)
    isempty(wrong) && continue
    out[i] = ComplexF64(wrong[rand(rng, 1:length(wrong))])
  end
  out
end

function _juna_step(m::Modulation, code::_Code, layout::_Layout, yparts, current)
  anchors = _juna_anchor_targets(m, layout, current.lpost_metric;
                                 truth = _genie_block(m.genie_symbols, 1))
  equalized = _equalize_from_targets(
    m, yparts, layout, anchors.target_idx, anchors.targets;
    target_weights = anchors.target_weights,
  )
  _candidate_from_equalized(m, code, layout, equalized)
end
