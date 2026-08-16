# Direct frame-wide descent on the pure J(C,z) objective.
#
# This receiver is deliberately separate from Profiled C,z.  Its optimizer
# moves the complex response C and real relaxed bits z together from one
# analytical gradient.  W is absent from the objective and is derived from an
# accepted C only when that state is presented to the decoder.

Base.@kwdef struct _DirectCzConfig
  steps::Int = 8
  alpha_C::Float64 = 0.004
  alpha_z::Float64 = 0.004
  shrink::Float64 = 0.5
  min_scale::Float64 = 2.0^-12
  gradient_clip::Float64 = 100.0
  complex_value_clip::Float64 = 25.0
  logit_clip::Float64 = 10.0
end

function _validate_direct_cz_config(config::_DirectCzConfig)
  config.steps >= 0 || throw(ArgumentError(
    "Direct C,z steps must be nonnegative"))
  isfinite(config.alpha_C) && config.alpha_C > 0 || throw(ArgumentError(
    "Direct C,z C step must be finite and positive"))
  isfinite(config.alpha_z) && config.alpha_z > 0 || throw(ArgumentError(
    "Direct C,z z step must be finite and positive"))
  isfinite(config.shrink) && 0 < config.shrink < 1 || throw(ArgumentError(
    "Direct C,z backtracking shrink must lie in (0,1)"))
  isfinite(config.min_scale) && 0 < config.min_scale <= 1 ||
    throw(ArgumentError(
      "Direct C,z minimum backtracking scale must lie in (0,1]"))
  isfinite(config.gradient_clip) && config.gradient_clip > 0 ||
    throw(ArgumentError(
      "Direct C,z gradient clip must be finite and positive"))
  isfinite(config.complex_value_clip) && config.complex_value_clip > 0 ||
    throw(ArgumentError(
      "Direct C,z complex-value clip must be finite and positive"))
  isfinite(config.logit_clip) && config.logit_clip > 0 ||
    throw(ArgumentError(
      "Direct C,z logit clip must be finite and positive"))
  config
end

# The wrapper preserves the established frame modem bytes and owns only the
# Direct C,z receive path and its trace.  Its base supplies all waveform,
# layout, code, and CRC settings.
mutable struct DirectCzFrameModulation <: Modulations.Modulation
  base::Modulation
  direct_cz_trace::Any
end

function DirectCzFrameModulation(; kwargs...)
  base = CrcNoHarmProfiledCzFrameModulation(; kwargs...)
  DirectCzFrameModulation(base, nothing)
end

Base.isvalid(m::DirectCzFrameModulation, fc, fs) =
  isvalid(m.base, fc, fs)
function Modulations.init(m::DirectCzFrameModulation, fc, fs)
  result = Modulations.init(m.base, fc, fs)
  m.direct_cz_trace = nothing
  result
end
Modulations.bitspersymbol(m::DirectCzFrameModulation) =
  Modulations.bitspersymbol(m.base)
Modulations.signallength(m::DirectCzFrameModulation, nbits, fc, fs) =
  Modulations.signallength(m.base, nbits, fc, fs)
Modulations.frameblockcount(m::DirectCzFrameModulation, fs) =
  Modulations.frameblockcount(m.base, fs)
Modulations.framepayloadbits(m::DirectCzFrameModulation, fs) =
  Modulations.framepayloadbits(m.base, fs)
Modulations.modulate(m::DirectCzFrameModulation, bits, fc, fs) =
  Modulations.modulate(m.base, bits, fc, fs)
Modulations.refinement_objective(::DirectCzFrameModulation) =
  :direct_cz_frame

function _direct_cz_config(m::DirectCzFrameModulation)
  steps = m.base.refinement_steps < 0 ? 8 : m.base.refinement_steps
  _validate_direct_cz_config(_DirectCzConfig(; steps))
end

function _direct_cz_runtime_weights(m::DirectCzFrameModulation)
  _CoupledWeights(
    observation=1.0,
    pilot=0.0,
    tie=0.0,
    response_regularization=0.002,
    combiner_regularization=0.0,
    smoothness=0.0,
    parity=m.base.cz_parity_weight,
  )
end

function _direct_cz_objective(problem::_CoupledProblem,
                              state::_CoupledState;
                              weights::_CoupledWeights)
  _coupled_objective(problem, state; weights)
end

function _direct_cz_objective_and_gradient!(
    gradient::_CoupledGradient,
    problem::_CoupledProblem,
    state::_CoupledState;
    weights::_CoupledWeights)
  terms = _coupled_objective_and_gradient!(
    gradient, problem, state; weights)
  # W is not an optimization variable in J(C,z).  Keeping this explicit
  # protects the boundary even if the shared objective grows another term.
  fill!(gradient.W, 0.0 + 0.0im)
  terms
end

@inline function _direct_cz_clip_complex_gradient(
    value::ComplexF64, limit::Float64)
  magnitude = abs(value)
  magnitude > limit ? value * (limit / magnitude) : value
end

function _direct_cz_trial(problem::_CoupledProblem,
                          state::_CoupledState,
                          gradient::_CoupledGradient,
                          config::_DirectCzConfig,
                          scale::Float64)
  trial = _copy_coupled_state(state)
  @inbounds for index in eachindex(trial.C)
    direction = _direct_cz_clip_complex_gradient(
      gradient.C[index], config.gradient_clip)
    trial.C[index] = _clip_complex(
      state.C[index] - scale * config.alpha_C * direction,
      config.complex_value_clip,
    )
  end
  @inbounds for index in eachindex(trial.z)
    if problem.inner_pilot_mask[index]
      trial.z[index] = state.z[index]
    else
      direction = clamp(
        gradient.z[index], -config.gradient_clip, config.gradient_clip)
      trial.z[index] = clamp(
        state.z[index] - scale * config.alpha_z * direction,
        -config.logit_clip, config.logit_clip,
      )
    end
  end
  trial
end

function _direct_cz_accept(old_loss::Real, new_loss::Real)
  isfinite(old_loss) && isfinite(new_loss) || return false
  new_loss <= old_loss + 64eps(max(abs(Float64(old_loss)), 1.0))
end

function _direct_cz_solve(problem::_CoupledProblem,
                          initial::_CoupledState;
                          weights::_CoupledWeights,
                          config::_DirectCzConfig=_DirectCzConfig())
  _validate_direct_cz_config(config)
  current = _copy_coupled_state(initial)
  gradient = _CoupledGradient(problem)
  initial_terms = _direct_cz_objective_and_gradient!(
    gradient, problem, current; weights)
  isfinite(initial_terms.total) || throw(ArgumentError(
    "Direct C,z requires a finite initial objective"))

  initial_loss = initial_terms.total
  loss = initial_loss
  best_loss = initial_loss
  best_state = _copy_coupled_state(current)
  selected_iter = 0
  accepted_steps = 0
  rejected_steps = 0
  loss_history = Float64[initial_loss]
  step_scales = Float64[]

  for iteration in 1:config.steps
    terms = _direct_cz_objective_and_gradient!(
      gradient, problem, current; weights)
    loss = terms.total
    scale = 1.0
    accepted = false
    while scale >= config.min_scale
      trial = _direct_cz_trial(
        problem, current, gradient, config, scale)
      trial_loss = _direct_cz_objective(problem, trial; weights).total
      if _direct_cz_accept(loss, trial_loss)
        current = trial
        loss = trial_loss
        accepted = true
        break
      end
      scale *= config.shrink
    end

    if accepted
      accepted_steps += 1
      push!(step_scales, scale)
      if loss < best_loss
        best_loss = loss
        best_state = _copy_coupled_state(current)
        selected_iter = iteration
      end
    else
      rejected_steps += 1
      push!(step_scales, 0.0)
    end
    push!(loss_history, loss)
  end

  (
    state=best_state,
    initial_loss,
    best_loss,
    final_loss=loss,
    loss_history,
    step_scales,
    selected_iter,
    accepted_steps,
    rejected_steps,
  )
end

_direct_cz_keep_best(::Nothing, candidate) = candidate
_direct_cz_keep_best(base, candidate) =
  _juna_better(base, candidate) ? candidate : base

function _direct_cz_crc_select(standard, standard_crc_valid::Bool,
                               rescue, rescue_crc_valid::Bool)
  standard_crc_valid && return (
    selected=standard,
    selected_source=:standard,
    selection_reason=:standard_crc_valid,
  )
  rescue_crc_valid && return (
    selected=rescue,
    selected_source=:direct_cz,
    selection_reason=:crc_rescue,
  )
  (
    selected=standard,
    selected_source=:standard,
    selection_reason=:standard_fallback,
  )
end

function _direct_cz_frame_trial(states, z, gradients, gz,
                                inner_mask, config::_DirectCzConfig,
                                scale::Float64)
  trial_states = [_copy_coupled_state(state) for state in states]
  @inbounds for block in eachindex(states)
    state = states[block]
    gradient = gradients[block]
    trial = trial_states[block]
    for index in eachindex(trial.C)
      direction = _direct_cz_clip_complex_gradient(
        gradient.C[index], config.gradient_clip)
      trial.C[index] = _clip_complex(
        state.C[index] - scale * config.alpha_C * direction,
        config.complex_value_clip,
      )
    end
  end
  trial_z = copy(z)
  @inbounds for bit in eachindex(trial_z)
    inner_mask[bit] && continue
    direction = clamp(gz[bit], -config.gradient_clip, config.gradient_clip)
    trial_z[bit] = clamp(
      z[bit] - scale * config.alpha_z * direction,
      -config.logit_clip, config.logit_clip,
    )
  end
  trial_states, trial_z
end

function _direct_cz_frame_trace(; standard_crc_valid::Bool,
                                rescue_executed::Bool,
                                accepted_steps::Int,
                                rejected_steps::Int,
                                step_scales,
                                loss_history,
                                selected_source::Symbol,
                                selection_reason::Symbol,
                                rescue_crc_valid::Bool,
                                selected_iteration::Int,
                                requested_steps::Int)
  (
    scope=:frame,
    optimized_variables=(:C, :z),
    independent_w_parameters=0,
    standard_crc_valid,
    rescue_executed,
    accepted_steps,
    rejected_steps,
    requested_steps,
    step_scales,
    loss_history,
    gradient_checkpoints=accepted_steps,
    w_derivations=accepted_steps,
    selected_source,
    selection_reason,
    rescue_crc_valid,
    selected_iteration,
  )
end

function _frame_direct_cz_refine(
    m::DirectCzFrameModulation,
    code::_Code,
    layout::_Layout,
    observations;
    payload_nbits=nothing)
  base = m.base
  _bpc(base) == 2 || throw(ArgumentError(
    "Direct C,z frame descent implements QPSK only"))
  payload_nbits === nothing && throw(ArgumentError(
    "Direct C,z CRC selection requires the user payload length"))

  nblocks = size(observations, 3)
  standard = _frame_static_trace(
    base, code, layout, observations, _MODE_STANDARD)
  standard_crc_valid = _cz_candidate_crc_valid(
    base, code, standard.best, nblocks, payload_nbits)
  if standard_crc_valid
    decision = _direct_cz_crc_select(standard, true, nothing, false)
    m.direct_cz_trace = _direct_cz_frame_trace(
      standard_crc_valid=true,
      rescue_executed=false,
      accepted_steps=0,
      rejected_steps=0,
      step_scales=Float64[],
      loss_history=Float64[],
      selected_source=decision.selected_source,
      selection_reason=decision.selection_reason,
      rescue_crc_valid=false,
      selected_iteration=0,
      requested_steps=0,
    )
    return merge(decision.selected, (profile=:direct_cz,))
  end

  config = _direct_cz_config(m)
  weights = _direct_cz_runtime_weights(m)
  block_n = Int(base.ldpc_n)
  inner_pairs = _frame_global_inner_pairs(base, code)
  inner_mask = falses(code.n)
  inner_bits = falses(code.n)
  @inbounds for (position, bit) in inner_pairs
    inner_mask[position] = true
    inner_bits[position] = bit
  end
  problems = [
    _frame_coupled_problem(
      base, code, layout, observations, block, inner_pairs)
    for block in 1:nblocks
  ]
  z = clamp.(
    -Float64.(standard.best.lpost_metric),
    -config.logit_clip, config.logit_clip,
  )
  @inbounds for bit in eachindex(z)
    inner_mask[bit] || continue
    z[bit] = inner_bits[bit] ? -config.logit_clip : config.logit_clip
  end
  states = [
    _frame_initial_coupled_state(
      base, layout, problems[block],
      @view(z[1 + (block - 1) * block_n:block * block_n]) .* -1.0)
    for block in 1:nblocks
  ]
  # _frame_initial_coupled_state consumes posterior metrics, so restore the
  # exact global direct logits after its physical-response bootstrap.
  _cz_sync_logits!(states, z, block_n)

  gradients = [_CoupledGradient(problem) for problem in problems]
  trial_gradients = [_CoupledGradient(problem) for problem in problems]
  scratches = [_CoupledScratch(problem) for problem in problems]
  gz = zeros(Float64, code.n)
  trial_gz = similar(gz)
  parity_relaxed = zeros(Float64, code.n)
  parity_grad = zeros(Float64, code.n)
  max_degree = maximum((length(check) for check in code.check_vars); init=0)
  parity_prefix = zeros(Float64, max_degree)
  parity_clamped = zeros(Float64, max_degree)

  loss = _frame_coupled_loss_and_grad!(
    base, code, problems, states, gradients, scratches,
    gz, z, inner_mask, inner_bits,
    parity_relaxed, parity_grad, parity_prefix, parity_clamped;
    weights,
  )
  isfinite(loss) || throw(ArgumentError(
    "Direct C,z requires a finite initial frame objective"))
  loss_history = Float64[loss]
  step_scales = Float64[]
  accepted_steps = 0
  rejected_steps = 0
  best_candidate = nothing
  best_equalized = nothing
  best_iteration = 0
  best_crc_candidate = nothing
  best_crc_equalized = nothing
  best_crc_iteration = 0

  for iteration in 1:config.steps
    loss = _frame_coupled_loss_and_grad!(
      base, code, problems, states, gradients, scratches,
      gz, z, inner_mask, inner_bits,
      parity_relaxed, parity_grad, parity_prefix, parity_clamped;
      weights,
    )
    scale = 1.0
    accepted = false
    candidate_states = states
    candidate_z = z
    candidate_loss = loss
    while scale >= config.min_scale
      candidate_states, candidate_z = _direct_cz_frame_trial(
        states, z, gradients, gz, inner_mask, config, scale)
      _cz_sync_logits!(candidate_states, candidate_z, block_n)
      candidate_loss = _frame_coupled_loss_and_grad!(
        base, code, problems, candidate_states, trial_gradients, scratches,
        trial_gz, candidate_z, inner_mask, inner_bits,
        parity_relaxed, parity_grad, parity_prefix, parity_clamped;
        weights,
      )
      if _direct_cz_accept(loss, candidate_loss)
        accepted = true
        break
      end
      scale *= config.shrink
    end

    if accepted
      states = candidate_states
      z = candidate_z
      loss = candidate_loss
      accepted_steps += 1
      push!(step_scales, scale)

      checkpoint_states = [_copy_coupled_state(state) for state in states]
      foreach(_cz_derive_weights!, checkpoint_states)
      candidate = _frame_wcz_candidate(
        base, code, layout, problems, checkpoint_states, z)
      equalized = _frame_coupled_equalized(
        base, layout, problems, checkpoint_states)
      retained = _direct_cz_keep_best(best_candidate, candidate)
      if retained === candidate
        best_candidate = candidate
        best_equalized = equalized
        best_iteration = iteration
      end
      candidate_crc_valid = _cz_candidate_crc_valid(
        base, code, candidate, nblocks, payload_nbits)
      if candidate_crc_valid
        retained_crc = _direct_cz_keep_best(best_crc_candidate, candidate)
        if retained_crc === candidate
          best_crc_candidate = candidate
          best_crc_equalized = equalized
          best_crc_iteration = iteration
        end
      end
    else
      rejected_steps += 1
      push!(step_scales, 0.0)
    end
    push!(loss_history, loss)
  end

  rescue_crc_valid = best_crc_candidate !== nothing
  rescue_candidate = rescue_crc_valid ? best_crc_candidate :
    (best_candidate === nothing ? standard.best : best_candidate)
  rescue_equalized = rescue_crc_valid ? best_crc_equalized :
    (best_equalized === nothing ? standard.best_equalized : best_equalized)
  rescue_iteration = rescue_crc_valid ? best_crc_iteration : best_iteration
  rescue = (
    profile=:direct_cz,
    initial_candidate=standard.best,
    best=rescue_candidate,
    initial_candidate_equalized=standard.best_equalized,
    best_equalized=rescue_equalized,
    selected_iteration=rescue_iteration,
    data_anchor_counts=Int[],
  )
  decision = _direct_cz_crc_select(
    standard, false, rescue, rescue_crc_valid)
  m.direct_cz_trace = _direct_cz_frame_trace(
    standard_crc_valid=false,
    rescue_executed=true,
    accepted_steps=accepted_steps,
    rejected_steps=rejected_steps,
    step_scales=step_scales,
    loss_history=loss_history,
    selected_source=decision.selected_source,
    selection_reason=decision.selection_reason,
    rescue_crc_valid=rescue_crc_valid,
    selected_iteration=decision.selected_source === :direct_cz ?
      best_crc_iteration : 0,
    requested_steps=config.steps,
  )
  merge(decision.selected, (profile=:direct_cz,))
end

function Modulations.demodulate(
    m::DirectCzFrameModulation, nbits, x, fc, fs)
  nbits2, code, layout, nblocks, observations, cfo =
    _prepare_frame_observations(m.base, nbits, x, fc, fs)
  trace = _frame_direct_cz_refine(
    m, code, layout, observations; payload_nbits=nbits2)
  metrics = _frame_payload_metrics(
    m.base, code, trace.best.lpost_metric, nblocks, nbits2)
  metrics, cfo
end

function _direct_cz_last_trace(m::DirectCzFrameModulation)
  m.direct_cz_trace === nothing && throw(ArgumentError(
    "no Direct C,z frame trace is available; run demodulation first"))
  m.direct_cz_trace
end
