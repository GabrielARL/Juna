# Frame-wide FEC receiver. OFDM carrier mapping remains one block at a time,
# while a single LDPC codeword and BP graph span all blocks in the frame.

const _FRAME_RLS_FORGETTING = 0.98
const _FRAME_RLS_DELTA = 1e-2
const _FRAME_JUNA_ITERS = 4
const _FRAME_JUNA_CONFIDENCE_MIN = 0.0
const _FRAME_JUNA_MAX_DATA_ANCHORS = 1024
const _FRAME_BP_ITERS = 8
const _FRAME_LLR_CLIP = 50.0
const _FRAME_INNER_LLR = 50.0
const _FRAME_BIN_SIGMA2_SCALE = 4.0
const _FRAME_BIN_SIGMA2_MIN_BLOCKS = 8
const _FRAME_CRC16_POLY = UInt16(0x1021)
const _FRAME_CRC16_INIT = UInt16(0xffff)

function _frame_crc16_ccitt(bits::AbstractVector{Bool})
  crc = _FRAME_CRC16_INIT
  @inbounds for bit in bits
    feedback = xor(((crc >> 15) & 0x0001) == 0x0001, bit)
    crc <<= 1
    feedback && (crc ⊻= _FRAME_CRC16_POLY)
  end
  crc
end

function _frame_crc_append(payload::AbstractVector{Bool}, crc_bits::Integer)
  width = Int(crc_bits)
  width == 0 && return copy(payload)
  width == 16 || throw(ArgumentError(
    "frame CRC width must be 0 or 16 bits"))
  checksum = _frame_crc16_ccitt(payload)
  framed = Vector{Bool}(undef, length(payload) + width)
  copyto!(framed, payload)
  @inbounds for offset in 1:width
    framed[length(payload) + offset] =
      ((checksum >> (width - offset)) & 0x0001) == 0x0001
  end
  framed
end

function _frame_crc_valid(framed::AbstractVector{Bool}, crc_bits::Integer)
  width = Int(crc_bits)
  width == 0 && return true
  width == 16 || throw(ArgumentError(
    "frame CRC width must be 0 or 16 bits"))
  length(framed) >= width || return false
  payload_length = length(framed) - width
  checksum = _frame_crc16_ccitt(@view framed[1:payload_length])
  @inbounds for offset in 1:width
    expected = ((checksum >> (width - offset)) & 0x0001) == 0x0001
    framed[payload_length + offset] == expected || return false
  end
  true
end

function _frame_code_horizon(m::Modulation, nblocks::Integer)
  blocks = Int(nblocks)
  blocks > 0 || throw(ArgumentError("frame-wide LDPC needs at least one block"))
  requested = Int(m.frame_code_component_block_count)
  requested >= 0 || throw(ArgumentError(
    "frame code horizon must be nonnegative"))
  requested == 0 && return blocks
  requested <= blocks || throw(ArgumentError(
    "frame code horizon $requested exceeds the $blocks physical OFDM symbols"))
  blocks % requested == 0 || throw(ArgumentError(
    "frame code horizon $requested must divide the $blocks physical OFDM symbols"))
  requested
end

function _frame_base_code_method(m::Modulation)
  m.ldpc_method === :auto ? "frame_sparse" : _code_method(m)
end

function _frame_component_code_seed(m::Modulation, nblocks::Integer)
  blocks = Int(nblocks)
  horizon = _frame_code_horizon(m, blocks)
  component_k = horizon * Int(m.ldpc_k)
  component_n = horizon * Int(m.ldpc_n)
  _code_seed(m, component_k, component_n, m.ldpc_checks_per_column)
end

_frame_block_diagonal_method(base_method::AbstractString,
                             horizon::Integer) =
  "frame_blockdiag_h$(Int(horizon))_$(base_method)"

function _create_frame_block_diagonal_code(
    m::Modulation, blocks::Integer, horizon::Integer,
    method::AbstractString, seed::Integer)
  block_count = Int(blocks)
  component_blocks = Int(horizon)
  component_count = div(block_count, component_blocks)
  component_k = component_blocks * Int(m.ldpc_k)
  component_n = component_blocks * Int(m.ldpc_n)
  component_m = component_n - component_k
  total_k = block_count * Int(m.ldpc_k)
  total_n = block_count * Int(m.ldpc_n)
  total_m = total_n - total_k
  base_method = _frame_base_code_method(m)
  component_seed = _frame_component_code_seed(m, block_count)
  component = _create_code(
    component_k, component_n, m.ldpc_checks_per_column, base_method,
    component_seed, m.ldpc_eliminate_length_4_cycles)

  generator = falses(total_m, total_k)
  H = falses(total_m, total_n)
  icols = Vector{Int}(undef, total_n)
  @inbounds for component_index in 1:component_count
    check_offset = (component_index - 1) * component_m
    message_offset = (component_index - 1) * component_k
    variable_offset = (component_index - 1) * component_n
    generator[
      check_offset + 1:check_offset + component_m,
      message_offset + 1:message_offset + component_k,
    ] .= component.gen
    H[
      check_offset + 1:check_offset + component_m,
      variable_offset + 1:variable_offset + component_n,
    ] .= component.H
    for local_variable in 1:component_n
      source = component.icols[local_variable]
      icols[variable_offset + local_variable] =
        source <= component_m ?
          check_offset + source :
          total_m + message_offset + source - component_m
    end
  end
  check_vars, var_edges = _build_graph(H)
  _Code(total_k, total_n, m.ldpc_checks_per_column, String(method), Int(seed),
        m.ldpc_eliminate_length_4_cycles, icols, generator, H, check_vars, var_edges,
        invperm(icols))
end

function _frame_code(m::Modulation, nblocks::Integer)
  blocks = Int(nblocks)
  horizon = _frame_code_horizon(m, blocks)
  k = blocks * Int(m.ldpc_k)
  n = blocks * Int(m.ldpc_n)
  base_method = _frame_base_code_method(m)
  method = horizon == blocks ?
    base_method : _frame_block_diagonal_method(base_method, horizon)
  seed = _code_seed(m, k, n, m.ldpc_checks_per_column)
  if m.code === nothing ||
      m.code.k != k ||
      m.code.n != n ||
      m.code.npc != m.ldpc_checks_per_column ||
      m.code.method != method ||
      m.code.seed != seed ||
      m.code.no4cycle != m.ldpc_eliminate_length_4_cycles
    m.code = if horizon == blocks
      _create_code(
        k, n, m.ldpc_checks_per_column, method, seed, m.ldpc_eliminate_length_4_cycles)
    else
      _create_frame_block_diagonal_code(
        m, blocks, horizon, method, seed)
    end
    m.bp_scratch = nothing
  end
  m.code::_Code
end

_frame_message_payload_capacity(m::Modulation, nblocks::Integer) = begin
  k = Int(nblocks) * Int(m.ldpc_k)
  k - _n_inner(m, k)
end

_frame_payload_capacity(m::Modulation, nblocks::Integer) =
  _frame_message_payload_capacity(m, nblocks) - m.frame_crc_bits

function _frame_nblocks(m::Modulation, nbits::Integer)
  required = _positive_nbits(nbits)
  blocks = max(1, cld(required, Modulations.bitspersymbol(m)))
  while blocks > 1 && _frame_payload_capacity(m, blocks - 1) >= required
    blocks -= 1
  end
  while _frame_payload_capacity(m, blocks) < required
    blocks += 1
  end
  blocks
end

_frame_inner_bit(m::Modulation, message_position::Integer) =
  _known_inner_bit(m, message_position)

function _build_frame_message(m::Modulation, code::_Code,
                              payload::AbstractVector{Bool}, nblocks::Integer)
  blocks = Int(nblocks)
  block_k = Int(m.ldpc_k)
  code.k == blocks * block_k ||
    throw(ArgumentError("frame LDPC message length does not match its OFDM symbol count"))
  capacity = _frame_message_payload_capacity(m, blocks)
  length(payload) <= capacity ||
    throw(ArgumentError("frame holds $capacity payload bits, got $(length(payload))"))

  message = falses(code.k)
  isp = _inner_pilot_spacing(m)
  payload_pos = 1
  @inbounds for p in 1:code.k
    if isp >= 1 && (p - 1) % isp == 0
      message[p] = _frame_inner_bit(m, p)
    elseif payload_pos <= length(payload)
      message[p] = payload[payload_pos]
      payload_pos += 1
    end
  end
  message
end

function _frame_payload_metrics(m::Modulation, code::_Code, metrics,
                                nblocks::Integer, nbits::Integer)
  blocks = Int(nblocks)
  block_k = Int(m.ldpc_k)
  code.k == blocks * block_k ||
    throw(ArgumentError("frame LDPC message length does not match its OFDM symbol count"))
  output = Vector{Float64}(undef, Int(nbits))
  mparity = code.n - code.k
  isp = _inner_pilot_spacing(m)
  output_pos = 1
  @inbounds for p in 1:code.k
    isp >= 1 && (p - 1) % isp == 0 && continue
    output_pos > nbits && break
    output[output_pos] = metrics[code.invperm[mparity + p]] > 0 ? 1.0 : -1.0
    output_pos += 1
  end
  output_pos == nbits + 1 ||
    throw(ArgumentError("frame LDPC did not expose the requested payload length"))
  output
end

function _modulate_frame_wide_ldpc(m::Modulation, payload::AbstractVector{Bool}, fs)
  nblocks = _frame_nblocks(m, length(payload))
  capacity = _frame_message_payload_capacity(m, nblocks)
  padded = _frame_crc_append(payload, m.frame_crc_bits)
  append!(padded, falses(capacity - length(padded)))

  code = _frame_code(m, nblocks)
  layout = _layout(m, fs)
  message = _build_frame_message(m, code, padded, nblocks)
  codeword = _encode(code, message)
  coded_bits_per_block = Int(m.ldpc_n)
  out = Vector{ComplexF64}(undef, nblocks * _blocklen(m))
  for block in 1:nblocks
    coded_lo = 1 + (block - 1) * coded_bits_per_block
    coded_hi = block * coded_bits_per_block
    samples = _modulate_block(m, layout, @view codeword[coded_lo:coded_hi])
    copyto!(out, 1 + (block - 1) * _blocklen(m), samples, 1, _blocklen(m))
  end

  m.synchronization_enabled || return out
  sync = _sync_waveform(m, fs)
  vcat(sync, out, sync)
end

function _frame_rls_update!(weights, inverse_covariance, xraw, target;
                            forgetting::Real=_FRAME_RLS_FORGETTING,
                            scratch_x=similar(weights),
                            scratch_px=similar(weights),
                            scratch_gain=similar(weights),
                            scratch_row=similar(weights))
  lambda = Float64(forgetting)
  0 < lambda <= 1 || throw(ArgumentError(
    "frame RLS forgetting factor must satisfy 0 < lambda <= 1"))
  pcount = length(weights)
  length(xraw) == pcount || throw(DimensionMismatch(
    "frame RLS observation length must match its weights"))
  size(inverse_covariance) == (pcount, pcount) || throw(DimensionMismatch(
    "frame RLS inverse covariance must be square and match its weights"))

  @inbounds for i in 1:pcount
    scratch_x[i] = ComplexF64(xraw[i])
  end
  @inbounds for i in 1:pcount
    acc = 0.0 + 0.0im
    for j in 1:pcount
      acc += inverse_covariance[i, j] * scratch_x[j]
    end
    scratch_px[i] = acc
  end
  denominator = ComplexF64(lambda, 0.0)
  @inbounds for i in 1:pcount
    denominator += conj(scratch_x[i]) * scratch_px[i]
  end
  @inbounds for i in 1:pcount
    scratch_gain[i] = scratch_px[i] / denominator
  end

  predicted = 0.0 + 0.0im
  @inbounds for i in 1:pcount
    predicted += conj(weights[i]) * scratch_x[i]
  end
  residual = ComplexF64(target) - predicted
  @inbounds for i in 1:pcount
    weights[i] += scratch_gain[i] * conj(residual)
  end

  @inbounds for j in 1:pcount
    acc = 0.0 + 0.0im
    for i in 1:pcount
      acc += conj(scratch_x[i]) * inverse_covariance[i, j]
    end
    scratch_row[j] = acc
  end
  inv_lambda = inv(lambda)
  @inbounds for j in 1:pcount
    row = scratch_row[j]
    for i in 1:pcount
      inverse_covariance[i, j] =
        (inverse_covariance[i, j] - scratch_gain[i] * row) * inv_lambda
    end
  end
  weights
end

function _frame_nearest_valid_band(valid, band_id::Int)
  valid[band_id] && return band_id
  best = 0
  distance = typemax(Int)
  @inbounds for candidate in eachindex(valid)
    valid[candidate] || continue
    candidate_distance = abs(candidate - band_id)
    if candidate_distance < distance
      best = candidate
      distance = candidate_distance
    end
  end
  best > 0 || throw(ArgumentError("frame RLS has no trained pilot band"))
  best
end

function _frame_rls_band_ids(layout::_Layout, nbands::Int, nfft::Int)
  nbands > 0 || throw(ArgumentError("frame RLS needs at least one band"))
  nactive = length(layout.active)
  band_ids = zeros(Int, nfft)
  @inbounds for band_id in 1:min(nbands, nactive)
    lo = floor(Int, (band_id - 1) * nactive / nbands) + 1
    hi = floor(Int, band_id * nactive / nbands)
    for rank in lo:hi
      band_ids[layout.active[rank]] = band_id
    end
  end
  band_ids
end

function _frame_anchor_plan(m::Modulation, layout::_Layout, posterior_metrics,
                            block::Int)
  target_idx = copy(layout.pilot_idx)
  targets = copy(layout.pilot_syms)
  posterior_metrics === nothing && return target_idx, targets, 0
  # Mechanism arms; see _lite_anchor_targets for the rationale. The pilots-only
  # return above already provides the control path.
  m.anchor_feedback_source === _FEEDBACK_PILOTS_ONLY && return target_idx, targets, 0

  coded_bits_per_block = Int(m.ldpc_n)
  lo = 1 + (block - 1) * coded_bits_per_block
  hi = block * coded_bits_per_block
  hi <= length(posterior_metrics) || throw(DimensionMismatch(
    "frame posterior does not cover OFDM symbol $block"))
  block_metrics = @view posterior_metrics[lo:hi]
  soft_symbols = _posterior_symbols(m, block_metrics)
  confidence = _posterior_confidence(m, block_metrics)
  count_data = min(length(layout.data_idx), length(soft_symbols), length(confidence))
  uses_transmitted_symbols =
    m.anchor_feedback_source in _FEEDBACK_TRANSMITTED_SYMBOL_MODES
  transmitted_symbols = _required_transmitted_symbols(m, layout, coded_bits_per_block, block)
  if uses_transmitted_symbols
    length(transmitted_symbols) >= count_data || throw(DimensionMismatch(
      "transmitted symbols cover $(length(transmitted_symbols)) carriers but $count_data are in play"))
  end
  candidates = Tuple{Int,Float64,ComplexF64}[]
  sizehint!(candidates, count_data)
  @inbounds for data_position in 1:count_data
    c = confidence[data_position]
    # Transmitted-symbol anchors skip the confidence floor because that floor
    # suppresses unreliable decisions. This arm only tests whether this
    # receiver's refit improves with those anchors.
    uses_transmitted_symbols || c >= _FRAME_JUNA_CONFIDENCE_MIN || continue
    push!(candidates, (
      layout.data_idx[data_position], c,
      uses_transmitted_symbols ?
        ComplexF64(transmitted_symbols[data_position]) :
        soft_symbols[data_position]))
  end
  if length(candidates) > _FRAME_JUNA_MAX_DATA_ANCHORS
    sort!(candidates; by=item -> item[2], rev=true)
    resize!(candidates, _FRAME_JUNA_MAX_DATA_ANCHORS)
  end
  for (carrier, _, target) in candidates
    push!(target_idx, carrier)
    push!(targets, target)
  end
  target_idx, targets, length(candidates)
end

function _frame_stateful_band_rls(m::Modulation, layout::_Layout, observations;
                                  posterior_metrics=nothing)
  ndims(observations) == 3 || throw(DimensionMismatch(
    "frame observations must have partial-FFT, carrier, and block axes"))
  pcount, nfft, nblocks = size(observations)
  pcount == m.partial_fft_parts || throw(DimensionMismatch(
    "frame observation branches do not match partial_fft_parts"))
  nfft == Int(m.fft_length) || throw(DimensionMismatch(
    "frame observation carriers do not match nc"))
  nblocks > 0 || throw(ArgumentError("frame RLS needs at least one OFDM symbol"))
  posterior_metrics === nothing ||
    length(posterior_metrics) == nblocks * Int(m.ldpc_n) ||
    throw(DimensionMismatch("frame posterior length does not match its OFDM symbols"))

  nbands = min(Int(m.partial_fft_nbands), length(layout.active))
  band_ids = _frame_rls_band_ids(layout, nbands, nfft)
  running_weights = zeros(ComplexF64, pcount, nbands)
  inverse_covariances = [
    Matrix{ComplexF64}(I, pcount, pcount) ./ _FRAME_RLS_DELTA
    for _ in 1:nbands
  ]
  valid = falses(nbands)
  combined = zeros(ComplexF64, nfft, nblocks)
  equalized = zeros(ComplexF64, nfft, nblocks)
  weight_history = Array{ComplexF64}(undef, pcount, nbands, nblocks)
  data_anchor_counts = zeros(Int, nblocks)
  scaled_x = Vector{ComplexF64}(undef, pcount)
  scratch_px = similar(scaled_x)
  scratch_gain = similar(scaled_x)
  scratch_row = similar(scaled_x)
  observation_scale = inv(sqrt(nfft))

  for block in 1:nblocks
    target_idx, targets, data_anchor_count =
      _frame_anchor_plan(m, layout, posterior_metrics, block)
    data_anchor_counts[block] = data_anchor_count
    @inbounds for (target_position, carrier) in pairs(target_idx)
      band_id = band_ids[carrier]
      band_id > 0 || continue
      for part in 1:pcount
        scaled_x[part] = observation_scale * observations[part, carrier, block]
      end
      _frame_rls_update!(
        @view(running_weights[:, band_id]),
        inverse_covariances[band_id],
        scaled_x,
        targets[target_position];
        scratch_x=scaled_x,
        scratch_px,
        scratch_gain,
        scratch_row,
      )
      valid[band_id] = true
    end

    applied_weights = copy(running_weights)
    for band_id in 1:nbands
      valid[band_id] && continue
      nearest = _frame_nearest_valid_band(valid, band_id)
      copyto!(@view(applied_weights[:, band_id]),
              @view(running_weights[:, nearest]))
    end
    weight_history[:, :, block] .= applied_weights
    @inbounds for carrier in layout.active
      band_id = band_ids[carrier]
      acc = 0.0 + 0.0im
      for part in 1:pcount
        acc += conj(applied_weights[part, band_id]) *
               (observation_scale * observations[part, carrier, block])
      end
      combined[carrier, block] = acc
    end
    equalized[:, block] .= _residual_pilot_equalize(
      m, layout, @view combined[:, block])
  end
  (
    equalized,
    combined,
    weights=weight_history,
    data_anchor_counts,
  )
end

_frame_sigma2_floor(::Modulation) = _BETA_FLOOR

function _frame_channel_metrics(m::Modulation, layout::_Layout, equalized)
  nblocks = size(equalized, 2)
  pilot_total = 0.0
  pilot_count = 0
  @inbounds for block in 1:nblocks
    for index in eachindex(layout.pilot_idx)
      carrier = layout.pilot_idx[index]
      pilot_total += abs2(equalized[carrier, block] - layout.pilot_syms[index])
      pilot_count += 1
    end
  end
  pilot_mse = pilot_total / max(pilot_count, 1)
  packet_sigma2 = max(pilot_mse, _frame_sigma2_floor(m))
  sigma2_by_carrier = fill(packet_sigma2, Int(m.fft_length))
  if _bpc(m) == 2 && nblocks >= _FRAME_BIN_SIGMA2_MIN_BLOCKS
    @inbounds for carrier in layout.data_idx
      residual = 0.0
      for block in 1:nblocks
        symbol = equalized[carrier, block]
        sliced = ComplexF64(real(symbol) >= 0 ? 1.0 : -1.0,
                            imag(symbol) >= 0 ? 1.0 : -1.0) / sqrt(2)
        residual += abs2(symbol - sliced)
      end
      sigma2_by_carrier[carrier] = max(
        _FRAME_BIN_SIGMA2_SCALE * residual / nblocks, packet_sigma2)
    end
  end

  coded_bits_per_block = Int(m.ldpc_n)
  metrics = Vector{Float64}(undef, nblocks * coded_bits_per_block)
  if _bpc(m) == 1
    @inbounds for block in 1:nblocks
      offset = (block - 1) * coded_bits_per_block
      for bit in 1:coded_bits_per_block
        carrier = layout.data_idx[bit]
        metrics[offset + bit] = clamp(
          -2real(equalized[carrier, block]) / sigma2_by_carrier[carrier],
          -_FRAME_LLR_CLIP, _FRAME_LLR_CLIP)
      end
    end
  else
    tones = cld(coded_bits_per_block, 2)
    @inbounds for block in 1:nblocks
      offset = (block - 1) * coded_bits_per_block
      for tone in 1:tones
        carrier = layout.data_idx[tone]
        symbol = equalized[carrier, block]
        denominator = sigma2_by_carrier[carrier]
        metrics[offset + 2tone - 1] = clamp(
          -2real(symbol) / denominator, -_FRAME_LLR_CLIP, _FRAME_LLR_CLIP)
        2tone <= coded_bits_per_block && (metrics[offset + 2tone] = clamp(
          -2imag(symbol) / denominator, -_FRAME_LLR_CLIP, _FRAME_LLR_CLIP))
      end
    end
  end
  metrics, pilot_mse
end

function _frame_pilot_mse(layout::_Layout, equalized)
  nblocks = size(equalized, 2)
  total = 0.0
  count = 0
  @inbounds for block in 1:nblocks
    for index in eachindex(layout.pilot_idx)
      carrier = layout.pilot_idx[index]
      total += abs2(equalized[carrier, block] - layout.pilot_syms[index])
      count += 1
    end
  end
  total / max(count, 1)
end

function _frame_apply_inner_clamps!(m::Modulation, code::_Code, lch)
  spacing = _inner_pilot_spacing(m)
  spacing < 1 && return lch
  parity = code.n - code.k
  clamp_abs = min(_FRAME_INNER_LLR, _FRAME_LLR_CLIP)
  @inbounds for position in 1:spacing:code.k
    variable = code.invperm[parity + position]
    lch[variable] = _frame_inner_bit(m, position) ? -clamp_abs : clamp_abs
  end
  lch
end

function _frame_bp_decode(m::Modulation, code::_Code, metrics)
  length(metrics) == code.n || throw(DimensionMismatch(
    "frame BP metrics must match the global LDPC code"))
  bp = _bp_scratch(m, code)
  lch, lpost, bits, q, r = bp.lch, bp.lpost, bp.bits, bp.q, bp.r
  @inbounds for variable in 1:code.n
    lch[variable] = -Float64(metrics[variable])
    lpost[variable] = lch[variable]
    bits[variable] = lch[variable] < 0
  end
  _frame_apply_inner_clamps!(m, code, lch)
  @inbounds for variable in 1:code.n
    lpost[variable] = lch[variable]
    bits[variable] = lch[variable] < 0
  end
  syndrome_weight = _syndrome_weight(code, bits)
  if syndrome_weight != 0
    @inbounds for check in eachindex(code.check_vars)
      for edge in eachindex(q[check])
        q[check][edge] = lch[code.check_vars[check][edge]]
      end
    end
    for _ in 1:_FRAME_BP_ITERS
      for check in eachindex(code.check_vars)
        _bp_check_normalized_min_sum!(r[check], q[check])
      end
      @inbounds for variable in 1:code.n
        total = lch[variable]
        for (check, edge) in code.var_edges[variable]
          total += r[check][edge]
        end
        lpost[variable] = total
        bits[variable] = total < 0
        for (check, edge) in code.var_edges[variable]
          q[check][edge] = total - r[check][edge]
        end
      end
      syndrome_weight = _syndrome_weight(code, bits)
      syndrome_weight == 0 && break
    end
  end
  posterior_metric = Vector{Float64}(undef, code.n)
  @inbounds for variable in 1:code.n
    posterior_metric[variable] = -lpost[variable]
  end
  (
    posterior_metric,
    bits=copy(bits),
    ldpc_valid=syndrome_weight == 0,
    syndrome_weight,
  )
end

function _frame_tie_mse(m::Modulation, layout::_Layout, equalized, posterior_metric)
  nblocks = size(equalized, 2)
  coded_bits_per_block = Int(m.ldpc_n)
  total = 0.0
  weight_sum = 0.0
  for block in 1:nblocks
    lo = 1 + (block - 1) * coded_bits_per_block
    hi = block * coded_bits_per_block
    soft = _posterior_symbols(m, @view posterior_metric[lo:hi])
    confidence = _posterior_confidence(m, @view posterior_metric[lo:hi])
    count_data = min(length(layout.data_idx), length(soft), length(confidence))
    @inbounds for position in 1:count_data
      weight = max(confidence[position], 1e-3)
      total += weight * abs2(
        equalized[layout.data_idx[position], block] - soft[position])
      weight_sum += weight
    end
  end
  total / max(weight_sum, eps(Float64))
end

function _frame_candidate(m::Modulation, code::_Code, layout::_Layout,
                          equalized, metrics=nothing)
  if metrics === nothing
    metrics, pilot_mse = _frame_channel_metrics(m, layout, equalized)
  else
    length(metrics) == code.n || throw(DimensionMismatch(
      "frame candidate metrics must match the global LDPC code"))
    pilot_mse = _frame_pilot_mse(layout, equalized)
  end
  bp = _frame_bp_decode(m, code, metrics)
  tie_mse = _frame_tie_mse(m, layout, equalized, bp.posterior_metric)
  mean_absolute_posterior_metric = mean(abs, bp.posterior_metric)
  normalized_syndrome_weight =
    bp.syndrome_weight / max(size(code.H, 1), 1)
  (
    posterior_metric=bp.posterior_metric,
    ldpc_valid=bp.ldpc_valid,
    syndrome_weight=bp.syndrome_weight,
    mean_absolute_posterior_metric,
    pilot_mse,
    tie_mse,
    selection_score=pilot_mse + 0.25tie_mse +
      0.05normalized_syndrome_weight -
      1e-4mean_absolute_posterior_metric,
  )
end

function _frame_independent_equalized(m::Modulation,
                                      layout::_Layout,
                                      observations,
                                      profile::Symbol)
  profile = receiver_profile(profile)
  profile in (_MODE_OFDM_FEC, _MODE_PFFT) ||
    throw(ArgumentError("independent frame equalization needs OFDM+FEC or pfft"))
  nblocks = size(observations, 3)
  equalized = zeros(ComplexF64, Int(m.fft_length), nblocks)
  @inbounds for block in 1:nblocks
    yparts = @view observations[:, :, block]
    equalized[:, block] .= if profile === _MODE_OFDM_FEC
      _residual_pilot_equalize(m, layout, _sum_branches(yparts))
    else
      _equalize_from_targets(
        m, yparts, layout, layout.pilot_idx, layout.pilot_syms)
    end
  end
  equalized
end

function _frame_static_trace(m::Modulation, code::_Code, layout::_Layout,
                             observations, profile::Symbol)
  profile = receiver_profile(profile)
  equalized = _frame_independent_equalized(
    m, layout, observations, profile)
  candidate = _frame_candidate(m, code, layout, equalized)
  (
    profile=profile,
    initial_candidate=candidate,
    best=candidate,
    initial_equalized=equalized,
    best_equalized=equalized,
    selected_iteration=0,
    data_anchor_counts=Int[],
  )
end

function _frame_lite_refine(m::Modulation, code::_Code, layout::_Layout,
                            observations)
  nblocks = size(observations, 3)
  coded_bits_per_block = Int(m.ldpc_n)
  for block in 1:nblocks
    _required_transmitted_symbols(m, layout, coded_bits_per_block, block)
  end
  initial_equalized = _frame_independent_equalized(
    m, layout, observations, _MODE_PFFT)
  initial_candidate = _frame_candidate(m, code, layout, initial_equalized)
  initial_candidate.ldpc_valid && return (
    profile=_MODE_LITE,
    initial_candidate,
    best=initial_candidate,
    initial_equalized,
    best_equalized=initial_equalized,
    selected_iteration=0,
    data_anchor_counts=Int[],
  )

  current = initial_candidate
  best = initial_candidate
  best_equalized = initial_equalized
  selected_iteration = 0
  all_anchor_counts = Int[]
  for iteration in 1:_JUNA_ITERS
    equalized = zeros(ComplexF64, Int(m.fft_length), nblocks)
    for block in 1:nblocks
      lo = 1 + (block - 1) * coded_bits_per_block
      hi = block * coded_bits_per_block
      anchors = _lite_anchor_targets(
        m, layout, @view current.posterior_metric[lo:hi];
        transmitted_symbols = _transmitted_symbol_block(m.transmitted_symbols, block))
      push!(all_anchor_counts, length(anchors.selected))
      equalized[:, block] .= _equalize_from_targets(
        m,
        @view(observations[:, :, block]),
        layout,
        anchors.target_idx,
        anchors.targets;
        target_weights=anchors.target_weights,
      )
    end
    candidate = _frame_candidate(m, code, layout, equalized)
    if _candidate_is_better(best, candidate)
      best = candidate
      best_equalized = equalized
      selected_iteration = iteration
    end
    step_improves = _candidate_is_better(current, candidate)
    current = candidate
    candidate.ldpc_valid && break
    step_improves || break
  end
  (
    profile=_MODE_LITE,
    initial_candidate,
    best,
    initial_equalized,
    best_equalized,
    selected_iteration,
    data_anchor_counts=all_anchor_counts,
  )
end

function _frame_wz_equalized(m::Modulation, layout::_Layout, observations, W)
  nblocks = size(observations, 3)
  size(W) == (Int(m.partial_fft_parts), length(layout.bands), nblocks) ||
    throw(DimensionMismatch("frame Wz combiner shape does not match observations"))
  equalized = zeros(ComplexF64, Int(m.fft_length), nblocks)
  @inbounds for block in 1:nblocks
    for (band_id, band) in enumerate(layout.bands)
      for carrier in band
        acc = 0.0 + 0.0im
        for part in 1:Int(m.partial_fft_parts)
          acc += conj(W[part, band_id, block]) *
                 observations[part, carrier, block]
        end
        equalized[carrier, block] = acc
      end
    end
  end
  equalized
end

function _frame_wz_candidate(m::Modulation, code::_Code, layout::_Layout,
                             observations, W, z)
  equalized = _frame_wz_equalized(m, layout, observations, W)
  metrics = clamp.(-z, -_LLR_CLIP, _LLR_CLIP)
  _frame_candidate(m, code, layout, equalized, metrics)
end

function _frame_wz_loss_and_gradient!(m::Modulation,
                                  code::_Code,
                                  layout::_Layout,
                                  gW,
                                  gz,
                                  W,
                                  z,
                                  W0,
                                  z0,
                                  observations,
                                  confidence,
                                  scratch)
  _bpc(m) == 2 || throw(ArgumentError(
    "frame JUNA-Wz implements QPSK only"))
  nblocks = size(observations, 3)
  expected_W = (
    Int(m.partial_fft_parts), length(layout.bands), nblocks)
  size(W) == expected_W || throw(DimensionMismatch(
    "frame Wz state must have shape $expected_W"))
  size(gW) == expected_W || throw(DimensionMismatch(
    "frame Wz gradient must have shape $expected_W"))
  length(z) == code.n == length(gz) ||
    throw(DimensionMismatch("frame Wz logits must match the global code"))

  fill!(gW, 0.0 + 0.0im)
  fill!(gz, 0.0)
  fill!(scratch.symbol_gradient, 0.0 + 0.0im)
  fill!(scratch.bit_gradient, 0.0)
  _wz_symbol_grid!(m, scratch.symbols, scratch.relaxed_bits, z)

  coded_bits_per_block = Int(m.ldpc_n)
  tones_per_block = cld(coded_bits_per_block, 2)
  total_tones = nblocks * tones_per_block
  length(scratch.symbols) == total_tones ||
    throw(DimensionMismatch("frame Wz symbol grid does not match its blocks"))
  length(confidence) == total_tones ||
    throw(DimensionMismatch("frame Wz confidence does not match its symbols"))

  loss = 0.0
  tie_scale = _GRAD_TIE_WEIGHT / max(total_tones, 1)
  @inbounds for block in 1:nblocks
    tone_offset = (block - 1) * tones_per_block
    for tone in 1:tones_per_block
      carrier = layout.data_idx[tone]
      band_id = layout.band_ids[carrier]
      symbol_index = tone_offset + tone
      combined = 0.0 + 0.0im
      for part in 1:Int(m.partial_fft_parts)
        combined += conj(W[part, band_id, block]) *
                    observations[part, carrier, block]
      end
      local_scale = tie_scale * confidence[symbol_index]
      local_scale <= 0.0 && continue
      residual = combined - scratch.symbols[symbol_index]
      loss += local_scale * abs2(residual)
      for part in 1:Int(m.partial_fft_parts)
        gW[part, band_id, block] +=
          local_scale * observations[part, carrier, block] * conj(residual)
      end
      scratch.symbol_gradient[symbol_index] -= local_scale * residual
    end
  end

  pilot_count = nblocks * length(layout.pilot_idx)
  pilot_scale = _GRAD_PILOT_WEIGHT / max(pilot_count, 1)
  @inbounds for block in 1:nblocks
    for (pilot_position, carrier) in enumerate(layout.pilot_idx)
      band_id = layout.band_ids[carrier]
      combined = 0.0 + 0.0im
      for part in 1:Int(m.partial_fft_parts)
        combined += conj(W[part, band_id, block]) *
                    observations[part, carrier, block]
      end
      residual = combined - layout.pilot_syms[pilot_position]
      loss += pilot_scale * abs2(residual)
      for part in 1:Int(m.partial_fft_parts)
        gW[part, band_id, block] +=
          pilot_scale * observations[part, carrier, block] * conj(residual)
      end
    end
  end

  invsqrt2 = inv(sqrt(2.0))
  @inbounds for tone in eachindex(scratch.symbols)
    bit_i = 2tone - 1
    bit_q = bit_i + 1
    relaxed_i = scratch.relaxed_bits[bit_i]
    gz[bit_i] += 2.0 * real(scratch.symbol_gradient[tone]) *
                 (0.5 * (1.0 - relaxed_i * relaxed_i) * invsqrt2)
    if bit_q <= length(z)
      relaxed_q = scratch.relaxed_bits[bit_q]
      gz[bit_q] += 2.0 * imag(scratch.symbol_gradient[tone]) *
                   (0.5 * (1.0 - relaxed_q * relaxed_q) * invsqrt2)
    end
  end

  if _GRAD_LAMBDA_CODE > 0.0 && !isempty(code.check_vars)
    lambda = _GRAD_LAMBDA_CODE / length(code.check_vars)
    loss += _parity_penalty_and_bit_gradient!(
      scratch.bit_gradient,
      scratch.relaxed_bits,
      code.check_vars,
      lambda,
      scratch.prefix,
      scratch.clamped,
    )
    @inbounds for bit in eachindex(z)
      derivative = 0.5 * (1.0 - scratch.relaxed_bits[bit] * scratch.relaxed_bits[bit])
      gz[bit] += scratch.bit_gradient[bit] * derivative
    end
  end

  if _GRAD_ETA_W > 0.0
    scale = _GRAD_ETA_W / max(length(W), 1)
    @inbounds for index in eachindex(W)
      difference = W[index] - W0[index]
      loss += scale * abs2(difference)
      gW[index] += scale * difference
    end
  end
  if _GRAD_GAMMA_Z > 0.0
    scale = _GRAD_GAMMA_Z / max(length(z), 1)
    @inbounds for index in eachindex(z)
      loss += scale * z[index] * z[index]
      gz[index] += 2.0 * scale * z[index]
    end
  end
  if _GRAD_TRUST_MU > 0.0
    scale = _GRAD_TRUST_MU / max(length(z), 1)
    @inbounds for index in eachindex(z)
      difference = z[index] - z0[index]
      loss += 0.5 * scale * difference * difference
      gz[index] += scale * difference
    end
  end
  loss
end

function _frame_wz_refine(m::Modulation, code::_Code, layout::_Layout,
                          observations)
  nblocks = size(observations, 3)
  initial_equalized = _frame_independent_equalized(
    m, layout, observations, _MODE_PFFT)
  initial_candidate = _frame_candidate(
    m, code, layout, initial_equalized)

  W = Array{ComplexF64}(undef,
    Int(m.partial_fft_parts), length(layout.bands), nblocks)
  @inbounds for block in 1:nblocks
    W[:, :, block] .= _initial_pilot_W(
      m, @view(observations[:, :, block]), layout)
  end
  W0 = copy(W)
  z = clamp.(-Float64.(initial_candidate.posterior_metric),
             -_GRAD_CLIP_Z, _GRAD_CLIP_Z)
  z0 = copy(z)
  confidence = _posterior_confidence(m, z0)

  gW = similar(W)
  gz = zeros(Float64, length(z))
  mW = zero(W)
  mz = zeros(Float64, length(z))
  vW = zeros(Float64, size(W))
  vz = zeros(Float64, length(z))
  scratch = _WzGradientScratch(m, code)

  best = initial_candidate
  best_equalized = initial_equalized
  selected_iteration = 0
  best_loss = _frame_wz_loss_and_gradient!(
    m, code, layout, gW, gz, W, z, W0, z0,
    observations, confidence, scratch)
  best_W = copy(W)
  best_z = copy(z)

  for iteration in 1:_wz_refinement_steps(m)
    _adam_step_complex!(
      W, mW, vW, gW, iteration, _GRAD_ALPHA_W,
      _GRAD_BETA1, _GRAD_BETA2, _GRAD_EPS_ADAM,
      _GRAD_CLIP, _GRAD_CLIP_W)
    _adam_step_real!(
      z, mz, vz, gz, iteration, _GRAD_ALPHA_Z,
      _GRAD_BETA1, _GRAD_BETA2, _GRAD_EPS_ADAM,
      _GRAD_CLIP, _GRAD_CLIP_Z)
    loss = _frame_wz_loss_and_gradient!(
      m, code, layout, gW, gz, W, z, W0, z0,
      observations, confidence, scratch)
    if isfinite(loss) && loss < best_loss
      best_loss = loss
      copyto!(best_W, W)
      copyto!(best_z, z)
    end
    candidate = _frame_wz_candidate(
      m, code, layout, observations, W, z)
    if _candidate_is_better(best, candidate)
      best = candidate
      best_equalized = _frame_wz_equalized(
        m, layout, observations, W)
      selected_iteration = iteration
    end
  end

  candidate = _frame_wz_candidate(
    m, code, layout, observations, best_W, best_z)
  if _candidate_is_better(best, candidate)
    best = candidate
    best_equalized = _frame_wz_equalized(
      m, layout, observations, best_W)
  end
  (
    profile=_MODE_FULL,
    initial_candidate,
    best,
    initial_equalized,
    best_equalized,
    selected_iteration,
    data_anchor_counts=Int[],
  )
end

function _frame_global_inner_pairs(m::Modulation, code::_Code)
  pairs = Tuple{Int,Bool}[]
  spacing = _inner_pilot_spacing(m)
  spacing < 1 && return pairs
  parity = code.n - code.k
  @inbounds for message_position in 1:code.k
    (message_position - 1) % spacing == 0 || continue
    push!(pairs, (
      code.invperm[parity + message_position],
      _frame_inner_bit(m, message_position),
    ))
  end
  sort!(pairs; by=first)
  pairs
end

function _frame_coupled_problem(m::Modulation,
                                code::_Code,
                                layout::_Layout,
                                observations,
                                block::Int,
                                inner_pairs)
  coded_bits_per_block = Int(m.ldpc_n)
  lo = 1 + (block - 1) * coded_bits_per_block
  hi = block * coded_bits_per_block
  local_pairs = [
    (position - lo + 1, bit)
    for (position, bit) in inner_pairs
    if lo <= position <= hi
  ]
  _CoupledProblem(
    @view(observations[:, :, block]);
    active=layout.active,
    dc_index=1,
    pilot_idx=layout.pilot_idx,
    pilot_syms=layout.pilot_syms,
    data_idx=layout.data_idx,
    bands=layout.bands,
    nbits=coded_bits_per_block,
    inner_pilot_idx=first.(local_pairs),
    inner_pilot_bits=last.(local_pairs),
    parity_sets=Vector{Vector{Int}}(),
  )
end

function _frame_initial_coupled_state(m::Modulation,
                                      layout::_Layout,
                                      problem,
                                      initial_metrics)
  length(initial_metrics) == problem.nbits || throw(DimensionMismatch(
    "frame WCz initial metrics must match one OFDM symbol"))
  W = _initial_pilot_W(m, problem.observations, layout)
  z = clamp.(-Float64.(initial_metrics), -_GRAD_CLIP_Z, _GRAD_CLIP_Z)
  @inbounds for bit in eachindex(z)
    problem.inner_pilot_mask[bit] || continue
    z[bit] = problem.inner_pilot_bits[bit] ?
             -_GRAD_CLIP_Z : _GRAD_CLIP_Z
  end
  state = _CoupledState(problem; W=W, z=z)
  scratch = _CoupledScratch(problem)
  _coupled_symbols!(problem, state, scratch)
  _cwz_initial_C_ridge_solve!(state.C, problem, scratch.symbols)
  state
end

function _frame_coupled_equalized(m::Modulation,
                                  layout::_Layout,
                                  problems,
                                  states)
  nblocks = length(problems)
  length(states) == nblocks || throw(DimensionMismatch(
    "frame WCz state count must match its block count"))
  equalized = zeros(ComplexF64, Int(m.fft_length), nblocks)
  @inbounds for block in 1:nblocks
    problem = problems[block]
    state = states[block]
    for carrier in problem.active
      group = _coupled_combiner_group(problem, carrier)
      for branch in axes(problem.observations, 1)
        equalized[carrier, block] +=
          conj(state.W[branch, group]) *
          problem.observations[branch, carrier]
      end
    end
  end
  equalized
end

function _frame_wcz_candidate(m::Modulation,
                              code::_Code,
                              layout::_Layout,
                              problems,
                              states,
                              z)
  equalized = _frame_coupled_equalized(
    m, layout, problems, states)
  metrics = clamp.(-z, -_LLR_CLIP, _LLR_CLIP)
  _frame_candidate(m, code, layout, equalized, metrics)
end

function _frame_coupled_loss_and_gradient!(m::Modulation,
                                       code::_Code,
                                       problems,
                                       states,
                                       gradients,
                                       scratches,
                                       gz,
                                       z,
                                       inner_mask,
                                       inner_bits,
                                       parity_relaxed,
                                       parity_grad,
                                       parity_prefix,
                                       parity_clamped;
                                       weights=_COUPLED_RUNTIME_WEIGHTS,
                                       expected_variance::Bool=false)
  nblocks = length(problems)
  length(states) == nblocks == length(gradients) == length(scratches) ||
    throw(DimensionMismatch("frame WCz workspaces must share one block count"))
  length(z) == code.n == length(gz) ||
    throw(DimensionMismatch("frame WCz logits must match the global code"))
  coded_bits_per_block = Int(m.ldpc_n)
  fill!(gz, 0.0)

  local_weights = _CoupledWeights(
    observation=weights.observation,
    pilot=weights.pilot,
    tie=weights.tie,
    response_regularization=weights.response_regularization,
    combiner_regularization=weights.combiner_regularization,
    smoothness=weights.smoothness,
    parity=0.0,
  )
  inverse_blocks = inv(Float64(nblocks))
  loss = 0.0
  @inbounds for block in 1:nblocks
    lo = 1 + (block - 1) * coded_bits_per_block
    hi = block * coded_bits_per_block
    copyto!(states[block].z, @view z[lo:hi])
    terms = _coupled_objective_and_gradient!(
      gradients[block],
      problems[block],
      states[block];
      weights=local_weights,
      scratch=scratches[block],
      expected_variance=expected_variance,
    )
    loss += inverse_blocks * terms.total
    gradients[block].W .*= inverse_blocks
    gradients[block].C .*= inverse_blocks
    @views gz[lo:hi] .= inverse_blocks .* gradients[block].z
  end

  fill!(parity_grad, 0.0)
  @inbounds for bit in eachindex(z)
    parity_relaxed[bit] = inner_mask[bit] ?
      _bit_to_bipolar(inner_bits[bit]) : tanh(0.5 * z[bit])
  end
  if weights.parity > 0.0 && !isempty(code.check_vars)
    parity_weight = weights.parity / length(code.check_vars)
    loss += _parity_penalty_and_bit_gradient!(
      parity_grad,
      parity_relaxed,
      code.check_vars,
      parity_weight,
      parity_prefix,
      parity_clamped,
    )
    @inbounds for bit in eachindex(z)
      inner_mask[bit] && continue
      derivative = 0.5 *
        (1.0 - parity_relaxed[bit] * parity_relaxed[bit])
      gz[bit] += parity_grad[bit] * derivative
    end
  end
  loss
end

function _frame_wcz_refine(m::Modulation, code::_Code, layout::_Layout,
                           observations)
  _bpc(m) == 2 || throw(ArgumentError(
    "frame JUNA-WCz implements QPSK only"))
  nblocks = size(observations, 3)
  coded_bits_per_block = Int(m.ldpc_n)
  initial_equalized = _frame_independent_equalized(
    m, layout, observations, _MODE_PFFT)
  initial_candidate = _frame_candidate(
    m, code, layout, initial_equalized)

  inner_pairs = _frame_global_inner_pairs(m, code)
  inner_mask = falses(code.n)
  inner_bits = falses(code.n)
  @inbounds for (position, bit) in inner_pairs
    inner_mask[position] = true
    inner_bits[position] = bit
  end
  problems = [
    _frame_coupled_problem(
      m, code, layout, observations, block, inner_pairs)
    for block in 1:nblocks
  ]
  states = [
    _frame_initial_coupled_state(
      m,
      layout,
      problems[block],
      @view(initial_candidate.posterior_metric[
        1 + (block - 1) * coded_bits_per_block:block * coded_bits_per_block]),
    )
    for block in 1:nblocks
  ]
  gradients = [_CoupledGradient(problem) for problem in problems]
  scratches = [_CoupledScratch(problem) for problem in problems]

  z = clamp.(-Float64.(initial_candidate.posterior_metric),
             -_GRAD_CLIP_Z, _GRAD_CLIP_Z)
  @inbounds for bit in eachindex(z)
    inner_mask[bit] || continue
    z[bit] = inner_bits[bit] ? -_GRAD_CLIP_Z : _GRAD_CLIP_Z
  end
  gz = zeros(Float64, length(z))
  mz = zeros(Float64, length(z))
  vz = zeros(Float64, length(z))
  parity_relaxed = zeros(Float64, code.n)
  parity_grad = zeros(Float64, code.n)
  max_degree = maximum((length(check) for check in code.check_vars); init=0)
  parity_prefix = zeros(Float64, max_degree)
  parity_clamped = zeros(Float64, max_degree)

  _frame_coupled_loss_and_gradient!(
    m, code, problems, states, gradients, scratches,
    gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
    parity_prefix, parity_clamped)
  best = initial_candidate
  best_equalized = initial_equalized
  selected_iteration = 0

  config = _wcz_optimizer_config(m)
  for iteration in 1:config.steps
    @inbounds for block in 1:nblocks
      _coupled_exact_C!(problems[block], states[block];
                        weights=_COUPLED_RUNTIME_WEIGHTS,
                        scratch=scratches[block])
      _coupled_exact_W!(problems[block], states[block];
                        weights=_COUPLED_RUNTIME_WEIGHTS,
                        scratch=scratches[block])
    end
    _frame_coupled_loss_and_gradient!(
      m, code, problems, states, gradients, scratches,
      gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
      parity_prefix, parity_clamped)
    _adam_step_real!(
      z, mz, vz, gz, iteration,
      config.alpha_z, config.beta1, config.beta2, config.epsilon,
      config.gradient_clip, config.logit_clip)
    @inbounds for bit in eachindex(z)
      inner_mask[bit] || continue
      z[bit] = inner_bits[bit] ? -config.logit_clip : config.logit_clip
    end

    loss = _frame_coupled_loss_and_gradient!(
      m, code, problems, states, gradients, scratches,
      gz, z, inner_mask, inner_bits, parity_relaxed, parity_grad,
      parity_prefix, parity_clamped)
    isfinite(loss) || break
    candidate = _frame_wcz_candidate(
      m, code, layout, problems, states, z)
    if _candidate_is_better(best, candidate)
      best = candidate
      best_equalized = _frame_coupled_equalized(
        m, layout, problems, states)
      selected_iteration = iteration
    end
  end

  (
    profile=_MODE_COUPLED,
    initial_candidate,
    best,
    initial_equalized,
    best_equalized,
    selected_iteration,
    data_anchor_counts=Int[],
  )
end

function _frame_stateful_band_rls_refine(m::Modulation, code::_Code, layout::_Layout,
                            observations)
  initial_fit = _frame_stateful_band_rls(m, layout, observations)
  initial_candidate = _frame_candidate(
    m, code, layout, initial_fit.equalized)
  initial_candidate.ldpc_valid && return (
    initial_candidate,
    best=initial_candidate,
    initial_equalized=initial_fit.equalized,
    best_equalized=initial_fit.equalized,
    selected_iteration=0,
    data_anchor_counts=Int[],
  )

  current = initial_candidate
  best = initial_candidate
  best_equalized = initial_fit.equalized
  selected_iteration = 0
  all_anchor_counts = Int[]
  for iteration in 1:_FRAME_JUNA_ITERS
    fit = _frame_stateful_band_rls(
      m, layout, observations; posterior_metrics=current.posterior_metric)
    append!(all_anchor_counts, fit.data_anchor_counts)
    candidate = _frame_candidate(m, code, layout, fit.equalized)
    if _candidate_is_better(best, candidate)
      best = candidate
      best_equalized = fit.equalized
      selected_iteration = iteration
    end
    step_improves = _candidate_is_better(current, candidate)
    step_improves || break
    current = candidate
    candidate.ldpc_valid && break
  end
  (
    initial_candidate,
    best,
    initial_equalized=initial_fit.equalized,
    best_equalized,
    selected_iteration,
    data_anchor_counts=all_anchor_counts,
  )
end

# Frame-wide counterpart of Profiled Gradient. The baseline is the complete
# frame-wide Lite decode (one global BP graph), while the alternative uses the
# existing exact-conditional C/W and global-z gradient trajectory. Selection
# can therefore never be worse than the frame-wide Lite candidate under the
# receiver's audited candidate ordering.
function _frame_profiled_gradient_refine(m::Modulation, code::_Code,
                                         layout::_Layout, observations)
  lite = _frame_lite_refine(m, code, layout, observations)
  steps = _wcz_optimizer_config(m).steps
  if steps == 0 || lite.best.ldpc_valid
    reason = steps == 0 ? :zero_steps : :lite_valid_skip
    m.profiled_gradient_trace = (
      scope=:frame,
      selection_reason=reason,
      selected_gradient=false,
      selected_iteration=0,
      lite=(ldpc_valid=lite.best.ldpc_valid,
            syndrome_weight=lite.best.syndrome_weight,
            selection_score=lite.best.selection_score,
            mean_absolute_posterior_metric=lite.best.mean_absolute_posterior_metric),
      gradient=(ldpc_valid=lite.best.ldpc_valid,
                syndrome_weight=lite.best.syndrome_weight,
                selection_score=lite.best.selection_score,
                mean_absolute_posterior_metric=lite.best.mean_absolute_posterior_metric),
    )
    return (
      profile=_MODE_PROFILED_GRADIENT,
      initial_candidate=lite.best,
      best=lite.best,
      initial_equalized=lite.best_equalized,
      best_equalized=lite.best_equalized,
      selected_iteration=0,
      data_anchor_counts=Int[],
    )
  end

  gradient = _frame_wcz_refine(m, code, layout, observations)
  selection_reason = _juna_selection_reason(lite.best, gradient.best)
  choose_gradient = selection_reason !== :lite_fallback
  m.profiled_gradient_trace = (
    scope=:frame,
    selection_reason,
    selected_gradient=choose_gradient,
    selected_iteration=choose_gradient ? gradient.selected_iteration : 0,
    lite=(ldpc_valid=lite.best.ldpc_valid,
          syndrome_weight=lite.best.syndrome_weight,
          selection_score=lite.best.selection_score,
          mean_absolute_posterior_metric=lite.best.mean_absolute_posterior_metric),
    gradient=(ldpc_valid=gradient.best.ldpc_valid,
              syndrome_weight=gradient.best.syndrome_weight,
              selection_score=gradient.best.selection_score,
              mean_absolute_posterior_metric=gradient.best.mean_absolute_posterior_metric),
  )
  (
    profile=_MODE_PROFILED_GRADIENT,
    initial_candidate=lite.best,
    best=choose_gradient ? gradient.best : lite.best,
    initial_equalized=lite.best_equalized,
    best_equalized=choose_gradient ? gradient.best_equalized : lite.best_equalized,
    selected_iteration=choose_gradient ? gradient.selected_iteration : 0,
    data_anchor_counts=Int[],
  )
end

function _frame_receiver_trace(m::Modulation, code::_Code, layout::_Layout,
                               observations; payload_nbits=nothing)
  profile = _frame_receiver_profile(m)
  profile === _MODE_OFDM_FEC &&
    return _frame_static_trace(
      m, code, layout, observations, _MODE_OFDM_FEC)
  profile === _MODE_PFFT &&
    return _frame_static_trace(
      m, code, layout, observations, _MODE_PFFT)
  profile === _MODE_LITE &&
    return _frame_lite_refine(m, code, layout, observations)
  profile === _MODE_FULL &&
    return _frame_wz_refine(m, code, layout, observations)
  profile === _MODE_COUPLED &&
    return _frame_wcz_refine(m, code, layout, observations)
  profile === _MODE_PROFILED_GRADIENT &&
    return _frame_profiled_gradient_refine(
      m, code, layout, observations)
  profile === _MODE_CZ_REFINEMENT &&
    return _frame_cz_refine(
      m, code, layout, observations; payload_nbits)
  profile === :stateful_lite &&
    return merge((profile=:stateful_lite,),
                 _frame_stateful_band_rls_refine(m, code, layout, observations))
  throw(ArgumentError("unsupported frame receiver profile: $profile"))
end

function _prepare_frame_observations(m::Modulation, nbits, x, fc, fs)
  isvalid(m, fc, fs) || throw(ArgumentError("invalid JUNA modulation settings"))
  nbits2 = _positive_nbits(nbits)
  waveform = _complex_waveform(x)
  _require_finite_waveform(waveform)
  nblocks = _frame_nblocks(m, nbits2)
  layout = _layout(m, fs)
  code = _frame_code(m, nblocks)

  cfo = 0.0
  if m.synchronization_enabled
    waveform, cfo = _coarse_doppler(m, waveform, fc, fs, nblocks)
  end
  _require_block_samples(m, waveform, nblocks)

  observations = Array{ComplexF64}(
    undef, m.partial_fft_parts, Int(m.fft_length), nblocks)
  for block in 1:nblocks
    sample_lo = 1 + (block - 1) * _blocklen(m)
    sample_hi = block * _blocklen(m)
    observations[:, :, block] .= _branch_observations(
      m, @view waveform[sample_lo:sample_hi])
  end
  nbits2, code, layout, nblocks, observations, cfo
end

function _demodulate_frame_methods(m::Modulation, nbits, x, fc, fs)
  nbits2, code, layout, nblocks, observations, _ =
    _prepare_frame_observations(m, nbits, x, fc, fs)
  ofdm_fec = _frame_static_trace(
    m, code, layout, observations, _MODE_OFDM_FEC).best
  partial = _frame_static_trace(
    m, code, layout, observations, _MODE_PFFT).best
  selected_receiver = _frame_receiver_trace(
    m, code, layout, observations; payload_nbits=nbits2).best
  ofdm_fec_metrics = _frame_payload_metrics(
    m, code, ofdm_fec.posterior_metric, nblocks, nbits2)
  (
    ofdm_fec=ofdm_fec_metrics,
    partial=_frame_payload_metrics(
      m, code, partial.posterior_metric, nblocks, nbits2),
    selected_receiver=_frame_payload_metrics(
      m, code, selected_receiver.posterior_metric, nblocks, nbits2),
    receiver_profile=receiver_profile(m),
    standard=ofdm_fec_metrics,
  )
end

function _demodulate_frame_wide_ldpc(m::Modulation, nbits, x, fc, fs)
  nbits2, code, layout, nblocks, observations, cfo =
    _prepare_frame_observations(m, nbits, x, fc, fs)
  trace = _frame_receiver_trace(
    m, code, layout, observations; payload_nbits=nbits2)
  _frame_payload_metrics(
    m, code, trace.best.posterior_metric, nblocks, nbits2), cfo
end
