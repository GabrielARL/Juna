# Frame-wide constrained variable-projection receiver.
#
# C is the physical partial-FFT response and z is the relaxed global LDPC
# codeword. C is solved exactly conditional on z. The combiner is never an
# independent optimization block: its MRC/MMSE form is derived from the
# desired (zero-offset) column of C after every C solve.

const _CZ_COMBINER_RIDGE = 1e-3

function _cz_mmse_weights!(W::AbstractMatrix, C::AbstractArray{<:Number,4};
                           ridge::Real=_CZ_COMBINER_RIDGE)
  size(C, 1) == size(W, 1) || throw(DimensionMismatch(
    "C and W must have the same number of partial-FFT views"))
  size(C, 3) == size(W, 2) || throw(DimensionMismatch(
    "C response groups must match W combiner groups"))
  isodd(size(C, 2)) || throw(ArgumentError(
    "C must have an odd number of ICI offsets"))
  ridge >= 0 || throw(ArgumentError("combiner ridge must be nonnegative"))
  center = cld(size(C, 2), 2)
  @inbounds for group in axes(W, 2)
    h = @view C[:, center, group, 1]
    denominator = sum(abs2, h) + Float64(ridge)
    @views W[:, group] .= h ./ denominator
  end
  W
end

function _cz_derive_weights!(state::_CoupledState)
  _cz_mmse_weights!(state.W, state.C)
  state
end

function _cz_profile_C!(m::Modulation,
                        problem::_CoupledProblem,
                        state::_CoupledState,
                        scratch::_CoupledScratch,
                        anchor,
                        weights::_CoupledWeights;
                        damping::Real=m.cz_em_damping)
  if m.cz_em_enabled
    _coupled_em_C!(
      problem, state;
      weights, scratch, anchor,
      trust=m.cz_em_trust, damping=damping)
  else
    _coupled_exact_C!(problem, state; weights, scratch)
  end
end

function _cz_pilot_anchor_C(problem::_CoupledProblem,
                            state::_CoupledState,
                            scratch::_CoupledScratch,
                            weights::_CoupledWeights)
  bootstrap = _copy_coupled_state(state)
  # Unknown coded bits carry no sign information at bootstrap. Outer pilots
  # remain fixed symbols, inner-pilot bits remain hard clamps, and the
  # posterior-moment Gram retains unit-energy uncertainty for everything else.
  fill!(bootstrap.z, 0.0)
  fill!(bootstrap.C, 0.0 + 0.0im)
  _coupled_em_C!(
    problem, bootstrap;
    weights, scratch, anchor=nothing, trust=0.0, damping=1.0)
  copy(bootstrap.C)
end

function _cz_update_W!(m::Modulation,
                       problem::_CoupledProblem,
                       state::_CoupledState,
                       scratch::_CoupledScratch,
                       weights::_CoupledWeights)
  m.cz_independent_w ?
    _coupled_posterior_W!(problem, state; weights, scratch) :
    _cz_derive_weights!(state)
end

function _cz_bp_feedback!(z, posterior_metrics, inner_mask, inner_bits,
                          feedback::Real, clip::Real)
  length(posterior_metrics) == length(z) ||
    throw(DimensionMismatch("BP posterior must cover every frame logit"))
  length(inner_mask) == length(z) && length(inner_bits) == length(z) ||
    throw(DimensionMismatch("inner-pilot masks must cover every frame logit"))
  isfinite(feedback) && 0 <= feedback <= 1 ||
    throw(ArgumentError("BP feedback must lie in [0,1]"))
  @inbounds for bit in eachindex(z)
    if inner_mask[bit]
      z[bit] = inner_bits[bit] ? -Float64(clip) : Float64(clip)
    else
      target = clamp(
        -Float64(posterior_metrics[bit]), -Float64(clip), Float64(clip))
      z[bit] = (1.0 - feedback) * z[bit] + feedback * target
    end
  end
  z
end

function _cz_genie_logits(m::Modulation, nblocks::Integer,
                          block_n::Integer, clip::Real)
  truth = m.genie_symbols
  truth === nothing && throw(ArgumentError(
    "cz_feedback_source=:genie requires transmitted symbols"))
  blocks = Int(nblocks)
  bits_per_block = Int(block_n)
  blocks > 0 && bits_per_block > 0 ||
    throw(ArgumentError("C,z genie feedback needs positive frame dimensions"))
  ntones = cld(bits_per_block, 2)
  logits = Vector{Float64}(undef, blocks * bits_per_block)
  @inbounds for block in 1:blocks
    symbols = _genie_block(truth, block)
    length(symbols) >= ntones || throw(DimensionMismatch(
      "genie symbols cover $(length(symbols)) tones in block $block; " *
      "$ntones coded tones are required"))
    for local_bit in 1:bits_per_block
      tone = cld(local_bit, 2)
      component = isodd(local_bit) ?
        real(symbols[tone]) : imag(symbols[tone])
      abs(component) > eps(Float64) || throw(ArgumentError(
        "genie symbol component for block $block bit $local_bit is zero"))
      logits[(block - 1) * bits_per_block + local_bit] =
        copysign(Float64(clip), component)
    end
  end
  logits
end

"""
Build one source-only C,z feedback checkpoint.

Experiment-B fixes the supported logit indices and their blend weights before
looking at the information source. The arms therefore differ only in `values`:
the trajectory's initial logits, current BP posteriors, or transmitted symbols.
"""
function _cz_feedback_plan(m::Modulation, initial_z, posterior_metrics,
                           inner_mask, inner_bits, nblocks::Integer,
                           block_n::Integer, clip::Real)
  length(initial_z) == length(posterior_metrics) ==
    length(inner_mask) == length(inner_bits) ||
    throw(DimensionMismatch(
      "C,z feedback vectors must cover the same global codeword"))
  length(initial_z) == Int(nblocks) * Int(block_n) ||
    throw(DimensionMismatch(
      "C,z feedback dimensions must match blocks times block length"))
  source = m.cz_feedback_source
  source in (:frozen, :real, :genie) || throw(ArgumentError(
    "C,z source-only feedback requires :frozen, :real, or :genie"))
  support = findall(!, inner_mask)
  weights = fill(Float64(m.cz_bp_feedback), length(support))
  values = if source === :frozen
    clamp.(Float64.(initial_z[support]), -Float64(clip), Float64(clip))
  elseif source === :real
    clamp.(
      -Float64.(posterior_metrics[support]),
      -Float64(clip), Float64(clip))
  else
    truth_logits = _cz_genie_logits(m, nblocks, block_n, clip)
    truth_logits[support]
  end
  (; source, support, weights, values)
end

function _cz_apply_feedback!(z, plan, inner_mask, inner_bits, clip::Real)
  length(z) == length(inner_mask) == length(inner_bits) ||
    throw(DimensionMismatch(
      "C,z feedback and inner-pilot vectors must share one length"))
  length(plan.support) == length(plan.weights) == length(plan.values) ||
    throw(DimensionMismatch(
      "C,z feedback support, weights, and values must match"))
  @inbounds for index in eachindex(plan.support)
    bit = plan.support[index]
    1 <= bit <= length(z) || throw(BoundsError(z, bit))
    weight = plan.weights[index]
    isfinite(weight) && 0 <= weight <= 1 || throw(ArgumentError(
      "C,z feedback weights must lie in [0,1]"))
    z[bit] = (1.0 - weight) * z[bit] + weight * plan.values[index]
  end
  @inbounds for bit in eachindex(z)
    inner_mask[bit] || continue
    z[bit] = inner_bits[bit] ? -Float64(clip) : Float64(clip)
  end
  z
end

function _cz_conditioned_direction(x::AbstractArray{<:Complex},
                                   gradient::AbstractArray{<:Complex},
                                   radius::Real)
  axes(x) == axes(gradient) ||
    throw(DimensionMismatch("state and gradient shapes must match"))
  isfinite(radius) && radius > 0 ||
    throw(ArgumentError("conditioned trust radius must be positive"))
  isempty(x) && return similar(x)
  rms = sqrt(sum(abs2, gradient) / length(gradient))
  (!isfinite(rms) || rms <= eps(Float64)) && return zero.(x)
  direction = -gradient ./ rms
  limit = Float64(radius) * max(norm(x), sqrt(Float64(length(x))))
  magnitude = norm(direction)
  magnitude > limit && (direction .*= limit / magnitude)
  direction
end

function _cz_conditioned_direction(x::AbstractArray{<:Real},
                                   gradient::AbstractArray{<:Real},
                                   radius::Real)
  axes(x) == axes(gradient) ||
    throw(DimensionMismatch("state and gradient shapes must match"))
  isfinite(radius) && radius > 0 ||
    throw(ArgumentError("conditioned trust radius must be positive"))
  isempty(x) && return similar(x, Float64)
  rms = sqrt(sum(abs2, gradient) / length(gradient))
  (!isfinite(rms) || rms <= eps(Float64)) &&
    return zeros(Float64, size(x))
  direction = -Float64.(gradient) ./ rms
  magnitude = maximum(abs, direction)
  magnitude > radius && (direction .*= Float64(radius) / magnitude)
  direction
end

function _cz_conditioned_accept(old_loss::Real, new_loss::Real,
                                old_pilot::Real, new_pilot::Real,
                                pilot_tolerance::Real)
  all(isfinite, (old_loss, new_loss, old_pilot, new_pilot, pilot_tolerance)) ||
    return false
  pilot_tolerance >= 0 || return false
  new_loss <= old_loss + 64eps(max(abs(Float64(old_loss)), 1.0)) &&
    new_pilot <= old_pilot * (1.0 + pilot_tolerance) +
                 64eps(max(abs(Float64(old_pilot)), 1.0))
end

function _cz_conditioned_penalty!(gradients, states, c_anchors, w_anchors,
                                  c_weight::Real, w_weight::Real)
  nblocks = length(states)
  inverse_blocks = inv(Float64(nblocks))
  penalty = 0.0
  @inbounds for block in eachindex(states)
    state = states[block]
    gradient = gradients[block]
    cscale = inverse_blocks * Float64(c_weight) / length(state.C)
    wscale = inverse_blocks * Float64(w_weight) / length(state.W)
    for index in eachindex(state.C)
      difference = state.C[index] - c_anchors[block][index]
      penalty += cscale * abs2(difference)
      gradient.C[index] += cscale * difference
    end
    for index in eachindex(state.W)
      difference = state.W[index] - w_anchors[block][index]
      penalty += wscale * abs2(difference)
      gradient.W[index] += wscale * difference
    end
  end
  penalty
end

function _cz_temporal_c_penalty!(gradients, states, weight::Real)
  nblocks = length(states)
  (nblocks <= 1 || weight <= 0) && return 0.0
  ncoefficients = length(first(states).C)
  scale = Float64(weight) / ((nblocks - 1) * ncoefficients)
  penalty = 0.0
  @inbounds for block in 2:nblocks
    previous = states[block - 1]
    current = states[block]
    previous_gradient = gradients[block - 1]
    current_gradient = gradients[block]
    for index in eachindex(current.C)
      difference = current.C[index] - previous.C[index]
      penalty += scale * abs2(difference)
      current_gradient.C[index] += scale * difference
      previous_gradient.C[index] -= scale * difference
    end
  end
  penalty
end

function _cz_conditioned_loss_and_grad!(
    m::Modulation, code::_Code, problems, states, gradients, scratches,
    gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
    parity_prefix, parity_clamped, c_anchors, w_anchors,
    weights::_CoupledWeights)
  loss = _frame_coupled_loss_and_grad!(
    m, code, problems, states, gradients, scratches,
    gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
    parity_prefix, parity_clamped;
    weights, expected_variance=true)
  loss += _cz_conditioned_penalty!(
    gradients, states, c_anchors, w_anchors,
    m.cz_em_trust, weights.combiner_regularization)
  loss + _cz_temporal_c_penalty!(
    gradients, states, m.cz_temporal_c_smoothness)
end

function _cz_conditioned_pilot_loss(problems, states, scratches,
                                    weights::_CoupledWeights)
  inverse_blocks = inv(Float64(length(problems)))
  sum(eachindex(problems); init=0.0) do block
    inverse_blocks * _coupled_objective(
      problems[block], states[block];
      weights, scratch=scratches[block], expected_variance=true).pilot
  end
end

function _cz_conditioned_joint_step!(
    m::Modulation, code::_Code, problems, states, gradients, scratches,
    gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
    parity_prefix, parity_clamped, c_anchors, w_anchors,
    weights::_CoupledWeights, iteration::Integer, logit_clip::Real)
  _cz_sync_logits!(states, z, Int(m.ldpc_n))
  old_loss = _cz_conditioned_loss_and_grad!(
    m, code, problems, states, gradients, scratches,
    gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
    parity_prefix, parity_clamped, c_anchors, w_anchors, weights)
  old_pilot = _cz_conditioned_pilot_loss(
    problems, states, scratches, weights)
  isfinite(old_loss) && isfinite(old_pilot) ||
    return (accepted=false, loss=old_loss, pilot=old_pilot, step_scale=0.0)

  c_directions = [
    _cz_conditioned_direction(
      states[block].C, gradients[block].C, m.cz_joint_c_radius)
    for block in eachindex(states)
  ]
  w_directions = if iteration >= m.cz_joint_w_start
    [
      _cz_conditioned_direction(
        states[block].W, gradients[block].W, m.cz_joint_w_radius)
      for block in eachindex(states)
    ]
  else
    [zero.(state.W) for state in states]
  end
  z_direction = _cz_conditioned_direction(z, gz, m.cz_joint_z_radius)

  candidate_states = [_copy_coupled_state(state) for state in states]
  candidate_z = similar(z)
  trial_gz = similar(gz)
  for backtrack in 0:6
    scale = 0.5^backtrack
    @inbounds for block in eachindex(states)
      candidate_states[block].C .=
        states[block].C .+ scale .* c_directions[block]
      candidate_states[block].W .=
        states[block].W .+ scale .* w_directions[block]
    end
    candidate_z .= clamp.(
      z .+ scale .* z_direction, -Float64(logit_clip), Float64(logit_clip))
    @inbounds for bit in eachindex(candidate_z)
      inner_mask[bit] || continue
      candidate_z[bit] =
        inner_bits[bit] ? -Float64(logit_clip) : Float64(logit_clip)
    end
    _cz_sync_logits!(candidate_states, candidate_z, Int(m.ldpc_n))
    new_loss = _cz_conditioned_loss_and_grad!(
      m, code, problems, candidate_states, gradients, scratches,
      trial_gz, candidate_z, inner_mask, inner_bits,
      parity_relaxed, parity_grad, parity_prefix, parity_clamped,
      c_anchors, w_anchors, weights)
    new_pilot = _cz_conditioned_pilot_loss(
      problems, candidate_states, scratches, weights)
    _cz_conditioned_accept(
      old_loss, new_loss, old_pilot, new_pilot,
      m.cz_joint_pilot_tolerance) || continue
    @inbounds for block in eachindex(states)
      states[block].C .= candidate_states[block].C
      states[block].W .= candidate_states[block].W
      states[block].z .= candidate_states[block].z
    end
    z .= candidate_z
    return (accepted=true, loss=new_loss, pilot=new_pilot, step_scale=scale)
  end
  _cz_sync_logits!(states, z, Int(m.ldpc_n))
  (accepted=false, loss=old_loss, pilot=old_pilot, step_scale=0.0)
end

function _cz_runtime_weights(m::Modulation)
  base = _COUPLED_RUNTIME_WEIGHTS
  _CoupledWeights(
    observation=base.observation,
    pilot=base.pilot,
    tie=base.tie,
    response_regularization=base.response_regularization,
    combiner_regularization=base.combiner_regularization,
    smoothness=base.smoothness,
    parity=m.cz_parity_weight,
  )
end

function _cz_sync_logits!(states, z, block_n::Int)
  @inbounds for block in eachindex(states)
    lo = 1 + (block - 1) * block_n
    copyto!(states[block].z, @view z[lo:lo + block_n - 1])
  end
  states
end

_cz_crc_choose_gradient(lite_crc_valid::Bool,
                        gradient_crc_valid::Bool) =
  gradient_crc_valid && !lite_crc_valid

function _cz_candidate_crc_valid(m::Modulation, code::_Code, candidate,
                                 nblocks::Integer, payload_nbits)
  m.frame_crc_bits == 0 && return candidate.valid
  payload_nbits === nothing && throw(ArgumentError(
    "CRC-gated C,z selection requires the user payload length"))
  total = Int(payload_nbits) + m.frame_crc_bits
  metrics = _frame_payload_metrics(
    m, code, candidate.lpost_metric, nblocks, total)
  _frame_crc_valid(metrics .> 0, m.frame_crc_bits)
end

function _cz_candidate_payload(m::Modulation, code::_Code, candidate,
                               nblocks::Integer, payload_nbits)
  payload_nbits === nothing && throw(ArgumentError(
    "C,z candidate recording requires the user payload length"))
  metrics = _frame_payload_metrics(
    m, code, candidate.lpost_metric, nblocks, Int(payload_nbits))
  BitVector(metrics .> 0)
end

function _cz_restart_logits(base, restart::Integer, seed::Integer,
                            inner_mask, inner_bits, clip::Real)
  index = Int(restart)
  1 <= index <= 5 || throw(ArgumentError(
    "C,z restart index must be in 1:5"))
  z = clamp.(Float64.(base), -Float64(clip), Float64(clip))
  unknown = findall(!, inner_mask)
  if index > 1
    rng = MersenneTwister(Int(seed) + 104_729index)
    selected = if index in (2, 3)
      unknown
    else
      fraction = index == 4 ? 0.05 : 0.10
      count = max(1, ceil(Int, fraction * length(unknown)))
      sort(unknown; by=bit -> abs(z[bit]))[1:count]
    end
    sigma = index == 2 ? 0.5 : 1.0
    @inbounds for bit in selected
      uncertainty = 1 / (1 + abs(z[bit]))
      z[bit] = clamp(
        z[bit] + sigma * uncertainty * randn(rng),
        -Float64(clip), Float64(clip))
    end
  end
  @inbounds for bit in eachindex(z)
    inner_mask[bit] || continue
    z[bit] = inner_bits[bit] ? -Float64(clip) : Float64(clip)
  end
  z
end

function _frame_profiled_cz_refine(m::Modulation, code::_Code,
                                   layout::_Layout, observations;
                                   payload_nbits=nothing)
  _bpc(m) == 2 || throw(ArgumentError(
    "frame C,z profiled gradient implements QPSK only"))
  standard = _frame_static_trace(
    m, code, layout, observations, _MODE_STANDARD)
  lite = _frame_lite_refine(m, code, layout, observations)
  config = _wcz_optimizer_config(m)
  nblocks = size(observations, 3)
  crc_enabled = m.frame_crc_bits > 0 && m.cz_crc_gate
  lite_crc_valid = _cz_candidate_crc_valid(
    m, code, lite.best, nblocks, payload_nbits)
  legacy_early_skip = crc_enabled ?
    lite_crc_valid : (standard.best.valid || lite.best.valid)
  # cz_gradient_only measures the gradient alone, so it must never take the
  # early exit that returns Lite before the gradient has run.
  early_skip = config.steps == 0 ||
    (!m.cz_gate_selection_only && !m.cz_gradient_only && legacy_early_skip)
  if early_skip
    baseline = (crc_enabled || m.cz_gate_selection_only) ? lite :
      (standard.best.valid ? standard : lite)
    reason = m.cz_gate_selection_only ?
      (config.steps == 0 ? :zero_steps : :lite_fallback) :
      crc_enabled ?
      (config.steps == 0 ? :zero_steps : :lite_crc_valid_skip) :
      (standard.best.valid ? :standard_valid_skip :
       config.steps == 0 ? :zero_steps : :lite_valid_skip)
    m.cz_gradient_trace = (
      scope=:frame,
      optimized_variables=(m.cz_independent_w || m.cz_conditioned_joint) ?
        (:C, :W, :z) : (:C, :z),
      independent_w_parameters=0, bp_checkpoints=1,
      selection_reason=reason, selected_gradient=false,
      selected_iteration=0,
      selected_restart=0,
      restart_count=0,
      requested_restarts=m.cz_restarts,
      candidates=NamedTuple[],
      crc_bits=m.frame_crc_bits,
      selection_gate=crc_enabled ? :crc : :score,
      feedback_source=m.cz_feedback_source,
      feedback_support=Int[],
      feedback_weights=Float64[],
      feedback_value_history=NamedTuple[],
      c_estimator=m.cz_em_enabled ? :posterior_moment_em : :mean_only_ridge,
      c_anchor=m.cz_em_enabled ? :pilots_and_unknown_energy : :legacy_initial,
      c_em_trust=m.cz_em_trust,
      c_em_damping=m.cz_em_damping,
      bp_feedback=m.cz_bp_feedback,
      conditioned_joint=m.cz_conditioned_joint,
      conditioned_accepted_steps=0,
      conditioned_rejected_steps=0,
      conditioned_step_scales=Float64[],
      lite_crc_valid,
      gradient_crc_valid=lite_crc_valid,
      lite=(valid=lite.best.valid, syndrome=lite.best.syndrome,
            score=lite.best.score),
      gradient=(valid=baseline.best.valid, syndrome=baseline.best.syndrome,
                score=baseline.best.score),
    )
    return merge(baseline, (profile=_MODE_PROFILED_CZ,))
  end

  block_n = Int(m.ldpc_n)
  inner_pairs = _frame_global_inner_pairs(m, code)
  inner_mask = falses(code.n)
  inner_bits = falses(code.n)
  @inbounds for (position, bit) in inner_pairs
    inner_mask[position] = true
    inner_bits[position] = bit
  end
  problems = [_frame_coupled_problem(
    m, code, layout, observations, block, inner_pairs)
    for block in 1:nblocks]
  scratches = [_CoupledScratch(problem) for problem in problems]

  base_z = clamp.(-Float64.(lite.best.lpost_metric),
                  -_GRAD_CLIP_Z, _GRAD_CLIP_Z)
  parity_relaxed = zeros(Float64, code.n)
  parity_grad = zeros(Float64, code.n)
  max_degree = maximum((length(check) for check in code.check_vars); init=0)
  parity_prefix = zeros(Float64, max_degree)
  parity_clamped = zeros(Float64, max_degree)

  best_gradient = lite.best
  best_gradient_equalized = lite.best_equalized
  best_crc_gradient = nothing
  best_crc_gradient_equalized = nothing
  best_crc_iteration = 0
  best_crc_restart = 0
  selected_iteration = 0
  selected_restart = 0
  bp_checkpoints = 1
  recorded_candidates = NamedTuple[]
  feedback_support = findall(!, inner_mask)
  feedback_weights = fill(Float64(m.cz_bp_feedback), length(feedback_support))
  feedback_value_history = NamedTuple[]
  conditioned_accepted_steps = 0
  conditioned_rejected_steps = 0
  conditioned_step_scales = Float64[]
  runtime_weights = _cz_runtime_weights(m)
  for restart in 1:m.cz_restarts
    states = [_frame_initial_coupled_state(
      m, layout, problems[block],
      @view(lite.best.lpost_metric[
        1 + (block - 1) * block_n:block * block_n]))
      for block in 1:nblocks]
    c_anchors = if m.cz_em_enabled
      [
        _cz_pilot_anchor_C(
          problems[block], states[block], scratches[block], runtime_weights)
        for block in 1:nblocks
      ]
    else
      [copy(state.C) for state in states]
    end
    if m.cz_em_enabled
      @inbounds for block in 1:nblocks
        states[block].C .= c_anchors[block]
        m.cz_conditioned_joint && _cz_derive_weights!(states[block])
      end
    end
    w_anchors = [copy(state.W) for state in states]
    gradients = [_CoupledGradient(problem) for problem in problems]
    z = _cz_restart_logits(
      base_z, restart, m.cz_restart_seed,
      inner_mask, inner_bits, config.logit_clip)
    feedback_initial = copy(z)
    gz = zeros(Float64, length(z))
    mz = zeros(Float64, length(z))
    vz = zeros(Float64, length(z))

    for iteration in 1:config.steps
      loss = if m.cz_conditioned_joint
        proposal = _cz_conditioned_joint_step!(
          m, code, problems, states, gradients, scratches,
          gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
          parity_prefix, parity_clamped, c_anchors, w_anchors,
          runtime_weights, iteration, config.logit_clip)
        if proposal.accepted
          conditioned_accepted_steps += 1
          push!(conditioned_step_scales, proposal.step_scale)
        else
          conditioned_rejected_steps += 1
        end
        proposal.loss
      else
        _cz_sync_logits!(states, z, block_n)
        @inbounds for block in 1:nblocks
          # Variable-projection gradient wants C/W at the exact (undamped)
          # block minimizer so the profiled z-gradient is the total derivative.
          _cz_profile_C!(
            m, problems[block], states[block], scratches[block],
            c_anchors[block], runtime_weights;
            damping=m.cz_vp_gradient ? 1.0 : m.cz_em_damping)
          _cz_update_W!(
            m, problems[block], states[block], scratches[block],
            runtime_weights)
        end
        _frame_coupled_loss_and_grad!(
          m, code, problems, states, gradients, scratches,
          gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
          parity_prefix, parity_clamped;
          weights=runtime_weights,
          expected_variance=m.cz_vp_gradient)
        _adam_step_real!(
          z, mz, vz, gz, iteration,
          config.alpha_z, config.beta1, config.beta2, config.epsilon,
          config.gradient_clip, config.logit_clip)
        @inbounds for bit in eachindex(z)
          inner_mask[bit] || continue
          z[bit] = inner_bits[bit] ? -config.logit_clip : config.logit_clip
        end

        # Re-profile C and derive W at the updated z before the BP checkpoint.
        _cz_sync_logits!(states, z, block_n)
        @inbounds for block in 1:nblocks
          _cz_profile_C!(
            m, problems[block], states[block], scratches[block],
            c_anchors[block], runtime_weights)
          _cz_update_W!(
            m, problems[block], states[block], scratches[block],
            runtime_weights)
        end
        _frame_coupled_loss_and_grad!(
          m, code, problems, states, gradients, scratches,
          gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
          parity_prefix, parity_clamped;
          weights=runtime_weights)
      end
      isfinite(loss) || break
      candidate = _frame_wcz_candidate(
        m, code, layout, problems, states, z)
      bp_checkpoints += 1
      candidate_crc_valid = _cz_candidate_crc_valid(
        m, code, candidate, nblocks, payload_nbits)
      if crc_enabled || m.cz_gate_selection_only
        push!(recorded_candidates, (
          restart,
          iteration,
          payload=_cz_candidate_payload(
            m, code, candidate, nblocks, payload_nbits),
          crc_valid=candidate_crc_valid,
          ldpc_valid=candidate.valid,
          syndrome=candidate.syndrome,
        ))
      end
      if crc_enabled && candidate_crc_valid &&
          (best_crc_gradient === nothing ||
           _juna_better(best_crc_gradient, candidate))
        best_crc_gradient = candidate
        best_crc_gradient_equalized = _frame_coupled_equalized(
          m, layout, problems, states)
        best_crc_iteration = iteration
        best_crc_restart = restart
      end
      if _juna_better(best_gradient, candidate)
        best_gradient = candidate
        best_gradient_equalized = _frame_coupled_equalized(
          m, layout, problems, states)
        selected_iteration = iteration
        selected_restart = restart
      end
      if m.cz_bp_feedback > 0
        if m.cz_feedback_source === :legacy
          feedback_values = clamp.(
            -Float64.(candidate.lpost_metric[feedback_support]),
            -Float64(config.logit_clip), Float64(config.logit_clip))
          push!(feedback_value_history, (
            restart,
            iteration,
            values=feedback_values,
          ))
          _cz_bp_feedback!(
            z, candidate.lpost_metric, inner_mask, inner_bits,
            m.cz_bp_feedback, config.logit_clip)
        else
          feedback_plan = _cz_feedback_plan(
            m, feedback_initial, candidate.lpost_metric,
            inner_mask, inner_bits, nblocks, block_n, config.logit_clip)
          push!(feedback_value_history, (
            restart,
            iteration,
            values=copy(feedback_plan.values),
          ))
          _cz_apply_feedback!(
            z, feedback_plan, inner_mask, inner_bits, config.logit_clip)
        end
      end
      if m.cz_conditioned_joint
        # The next joint step sees a frozen, physically meaningful W reference.
        # Refreshing only between BP checkpoints avoids an unaccounted dWref/dC
        # term inside the simultaneous analytical gradient.
        @inbounds for block in eachindex(states)
          reference = _copy_coupled_state(states[block])
          _cz_derive_weights!(reference)
          w_anchors[block] .= reference.W
        end
      end
    end
  end

  gradient_crc_valid = crc_enabled ?
    best_crc_gradient !== nothing :
    _cz_candidate_crc_valid(
      m, code, best_gradient, nblocks, payload_nbits)
  # Under cz_gradient_only the gradient's own decode is reported whether or
  # not it beats Lite: the arm is being measured, not protected.
  choose_gradient = m.cz_gradient_only ? true :
    crc_enabled ?
    _cz_crc_choose_gradient(lite_crc_valid, gradient_crc_valid) :
    _juna_selection_reason(lite.best, best_gradient) !== :lite_fallback
  # The CRC-certified candidate may be `nothing` when no iterate passed CRC,
  # so the standalone arm keeps the raw gradient rather than swapping it in.
  if crc_enabled && choose_gradient && !m.cz_gradient_only
    best_gradient = best_crc_gradient
    best_gradient_equalized = best_crc_gradient_equalized
    selected_iteration = best_crc_iteration
    selected_restart = best_crc_restart
  end
  reason = m.cz_gradient_only ? :gradient_only :
    crc_enabled ?
    (choose_gradient ? :crc_rescue :
     lite_crc_valid ? :lite_crc_valid : :crc_fallback) :
    _juna_selection_reason(lite.best, best_gradient)
  m.cz_gradient_trace = (
    scope=:frame,
    optimized_variables=(m.cz_independent_w || m.cz_conditioned_joint) ?
      (:C, :W, :z) : (:C, :z),
    independent_w_parameters=(m.cz_independent_w || m.cz_conditioned_joint) ?
      nblocks * Int(m.partial_fft_parts) * Int(m.partial_fft_nbands) : 0,
    bp_checkpoints,
    selection_reason=reason, selected_gradient=choose_gradient,
    selected_iteration=choose_gradient ? selected_iteration : 0,
    selected_restart=choose_gradient ? selected_restart : 0,
    restart_count=m.cz_restarts,
    requested_restarts=m.cz_restarts,
    candidates=recorded_candidates,
    crc_bits=m.frame_crc_bits,
    selection_gate=crc_enabled ? :crc : :score,
    feedback_source=m.cz_feedback_source,
    feedback_support,
    feedback_weights,
    feedback_value_history,
    c_estimator=m.cz_em_enabled ? :posterior_moment_em : :mean_only_ridge,
    c_anchor=m.cz_em_enabled ? :pilots_and_unknown_energy : :legacy_initial,
    c_em_trust=m.cz_em_trust,
    c_em_damping=m.cz_em_damping,
    bp_feedback=m.cz_bp_feedback,
    conditioned_joint=m.cz_conditioned_joint,
    conditioned_accepted_steps,
    conditioned_rejected_steps,
    conditioned_step_scales,
    lite_crc_valid,
    gradient_crc_valid,
    lite=(valid=lite.best.valid, syndrome=lite.best.syndrome,
          score=lite.best.score),
    gradient=(valid=best_gradient.valid, syndrome=best_gradient.syndrome,
              score=best_gradient.score),
  )
  (
    profile=_MODE_PROFILED_CZ,
    initial_candidate=lite.best,
    best=choose_gradient ? best_gradient : lite.best,
    initial_candidate_equalized=lite.best_equalized,
    best_equalized=choose_gradient ? best_gradient_equalized : lite.best_equalized,
    selected_iteration=choose_gradient ? selected_iteration : 0,
    data_anchor_counts=Int[],
  )
end

function _cz_gradient_last_trace(m::Modulation)
  m.cz_gradient_trace === nothing && throw(ArgumentError(
    "no C,z frame gradient trace is available; run demodulation first"))
  m.cz_gradient_trace
end
