# JUNA modulation. Defaults reproduce the JOE paper red_1 controlled config
# n1024_cp256_sym1_p3_r0p25_dc4_sig1_ip2: QPSK, pilot every 3 active tones,
# LDPC rate 0.25, inner pilots every 2 message positions.
Base.@kwdef mutable struct Modulation <: Modulations.Modulation
  nc::UInt16 = 1024
  np::UInt16 = 256
  bw::Float64 = 1.0                    # occupied bandwidth as a fraction of the 24 kHz reference width
  dc0::Int16 = 0                       # RF-centre offset from the 24 kHz reference, in kHz
  bpc::Int = 2                       # bits per data carrier: 1=BPSK, 2=QPSK
  pilot_ratio::Float64 = 1/3         # outer comb-pilot density (fraction of active tones); snapped to the nearest 1/k spacing
  inner_pilot_ratio::Float64 = 1/2   # inner-pilot density among message bits (0 = off); snapped to the nearest 1/k spacing
  sync::Bool = false                 # enable the LFM sync/acquisition wrapping
  frame_duration_s::Float64 = 1.0     # maximum complete frame duration, including sync and guard
  ldpc_k::Int = 340
  ldpc_n::Int = 1360
  ldpc_npc::Int = 3                  # dc: per-column check count passed to make-ldpc
  ldpc_method::Symbol = :auto        # :auto preserves profile default; or :evencol/:evenboth
  ldpc_seed::Int = 51_001            # code seed for explicit ldpc_method builds and the frame code
  ldpc_no4cycle::Bool = true         # request make-ldpc's length-4-cycle elimination
  partial_fft_parts::Int = 4
  partial_fft_nbands::Int = 16
  mode::Symbol = :lite               # receiver: canonical modes plus the legacy :robust alias
  frame_receiver::Symbol = :stateful_lite # frame-wide FEC front end/refiner; preserves the original stateful receiver by default
  frame_crc_bits::Int = 0            # 0=legacy framing; 16=one external CRC-16/CCITT over the complete frame payload
  frame_code_horizon::Int = 0        # 0=one graph over all blocks; h>0=disconnected h-block graph components
  cz_crc_gate::Bool = true           # when CRC is present, require a certified rescue before replacing Lite
  cz_gate_selection_only::Bool = false # opt-in experiment contract: gate selects after an otherwise identical trajectory
  cz_restarts::Int = 1               # constrained C,z trajectories; 1 preserves deployed behavior
  cz_restart_seed::Int = 17_071      # deterministic perturbation seed for diagnostic restart lists
  cz_parity_weight::Float64 = 0.08   # soft parity-product coefficient for C,z ablations
  cz_em_enabled::Bool = false         # use posterior second moments in the profiled C update
  cz_em_trust::Float64 = 0.05         # trust-region weight toward the pilot/unknown-energy C bootstrap
  cz_em_damping::Float64 = 0.5        # accepted fraction of each posterior-moment C solve
  cz_independent_w::Bool = false       # refit W from reliable BP pseudo-pilots instead of deriving it from C
  cz_bp_feedback::Float64 = 0.0        # BP-posterior blend into z between turbo iterations
  cz_feedback_source::Symbol = :legacy # :legacy preserves deployed path; Experiment-B uses :frozen/:real/:genie
  cz_vp_gradient::Bool = false         # variable-projection z-gradient: expected-variance objective + undamped C/W at the gradient point
  cz_conditioned_joint::Bool = false   # simultaneous hand-gradient C,W,z proposals with pilot/trust gating
  cz_gradient_only::Bool = false       # report the gradient's own decode, never falling back to Lite; measures the gradient alone and so may be worse than Lite
  cz_joint_c_radius::Float64 = 0.05    # maximum relative C displacement per accepted joint step
  cz_joint_w_radius::Float64 = 0.01    # maximum relative W displacement per accepted joint step
  cz_joint_z_radius::Float64 = 0.5     # maximum absolute logit displacement per accepted joint step
  cz_joint_w_start::Int = 2            # first turbo iteration allowed to move W away from its pilot anchor
  cz_joint_pilot_tolerance::Float64 = 0.01 # allowed relative known-pilot loss increase
  cz_temporal_c_smoothness::Float64 = 0.0 # adjacent-symbol C smoothness; zero preserves the deployed receiver
  refinement_steps::Int = -1         # -1 uses the receiver default; nonnegative values are explicit solver ablations
  # Mechanism-experiment arms for decoder feedback into channel estimation.
  # :real   deployed behaviour -- posterior soft symbols anchor the re-fit
  # :frozen full coupled machinery, but data decisions never anchor the re-fit
  # :genie  true transmitted symbols anchor the re-fit (upper bound on feedback)
  # :graded genie symbols corrupted at rate feedback_graded_p (dose response)
  # Only :real is a deployable receiver; the others exist to separate the
  # information recovered from feedback from the cost of feeding back errors.
  feedback_mode::Symbol = :real
  feedback_graded_p::Float64 = 0.0
  code::Any = nothing
  layout::Any = nothing
  bp_scratch::Any = nothing
  fully_coupled_trace::Any = nothing
  turbo_map_trace::Any = nothing
  guarded_physical_trace::Any = nothing
  gradient_guarded_trace::Any = nothing
  profiled_gradient_trace::Any = nothing
  cz_gradient_trace::Any = nothing
  # Ground truth for the Lite :genie/:graded arms and the C,z :genie arm,
  # attached per frame by the experiment harness. Deployed receivers leave this
  # nothing and never read it; a missing oracle grid is a hard error rather than
  # a silent fallback to :real, so a mis-wired arm cannot masquerade as a result.
  genie_symbols::Any = nothing
  feedback_trace::Any = nothing
end

const _MODE_STANDARD = :standard
const _MODE_PFFT = :pfft
const _MODE_LITE = :lite
const _MODE_FULL = :full
const _MODE_COUPLED = :coupled
const _MODE_FULLY_COUPLED = :fully_coupled
const _MODE_TURBO_MAP = :turbo_map
const _MODE_GUARDED_PHYSICAL = :guarded_physical
const _MODE_GRADIENT_GUARDED = :gradient_guarded
const _MODE_PROFILED_GRADIENT = :profiled_gradient
const _MODE_PROFILED_CZ = :profiled_cz
const _MODE_FRAME_WIDE_LDPC = :frame_wide_ldpc
const _MODE_CRC_PROFILED_CZ_FRAME = :crc_profiled_cz_frame
const _MODE_ROBUST = :robust
const _REFERENCE_CENTER_HZ = 24_000.0
const _REFERENCE_BANDWIDTH_HZ = 24_000.0
const _FRAME_RECEIVER_PROFILES =
  (_MODE_STANDARD, _MODE_PFFT, _MODE_LITE,
   _MODE_FULL, _MODE_COUPLED,
   _MODE_FULLY_COUPLED, _MODE_TURBO_MAP,
   _MODE_PROFILED_GRADIENT, _MODE_PROFILED_CZ,
   :stateful_lite)
const _RECEIVER_PROFILES =
  (_MODE_STANDARD, _MODE_PFFT, _MODE_LITE,
   _MODE_FULL, _MODE_COUPLED,
   _MODE_FULLY_COUPLED, _MODE_TURBO_MAP, _MODE_GUARDED_PHYSICAL,
   _MODE_GRADIENT_GUARDED, _MODE_PROFILED_GRADIENT,
   _MODE_FRAME_WIDE_LDPC)
const _PUBLIC_RECEIVER_MODES =
  (_MODE_STANDARD, _MODE_PFFT, _MODE_LITE, _MODE_FULLY_COUPLED,
   _MODE_TURBO_MAP, _MODE_PROFILED_GRADIENT,
   _MODE_FRAME_WIDE_LDPC, _MODE_CRC_PROFILED_CZ_FRAME)

receiver_profile(mode::Symbol) =
  mode === _MODE_ROBUST ? _MODE_FULL :
  mode === _MODE_CRC_PROFILED_CZ_FRAME ?
    _MODE_FRAME_WIDE_LDPC : mode
receiver_profile(m::Modulation) = receiver_profile(m.mode)

function Modulations.refinement_objective(m::Modulation)
  profile = receiver_profile(m)
  # The paper's benchmark baselines: :standard optimizes nothing (one-tap
  # interpolated equalization, declared :none), while :pfft's only objective
  # is the pilot-trained per-band ridge LS it solves in closed form
  # (eq:pfft-ls), so that is the capability it must prove executable.
  profile === _MODE_PFFT && return :pilot_band_ls
  profile === _MODE_LITE && return :posterior_anchor_ls
  profile === _MODE_FULL && return :reduced_wz
  profile === _MODE_COUPLED && return :coupled_cwz
  profile === _MODE_FULLY_COUPLED && return :fully_coupled_equalization
  profile === _MODE_TURBO_MAP && return :list_turbo_map
  profile === _MODE_GUARDED_PHYSICAL && return :guarded_physical_fusion
  profile === _MODE_GRADIENT_GUARDED && return :gradient_guarded_channel
  profile === _MODE_PROFILED_GRADIENT && return :profiled_gradient_decode
  profile === _MODE_FRAME_WIDE_LDPC &&
    m.frame_receiver === _MODE_PROFILED_CZ &&
    return :profiled_cz_frame
  profile === _MODE_FRAME_WIDE_LDPC && return :frame_wide_ldpc
  :none
end

StandardModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_STANDARD)...)
PartialFFTModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_PFFT)...)
LiteModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_LITE)...)
FullModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_FULL)...)
CoupledModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_COUPLED)...)
FullyCoupledModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_FULLY_COUPLED)...)
TurboMAPModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_TURBO_MAP)...)
GuardedPhysicalModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_GUARDED_PHYSICAL)...)
GradientGuardedModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_GRADIENT_GUARDED)...)
ProfiledGradientModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_PROFILED_GRADIENT)...)
FrameWideLDPCModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_FRAME_WIDE_LDPC)...)
ProfiledCzFrameModulation(; kwargs...) =
  Modulation(; (; kwargs..., mode = _MODE_FRAME_WIDE_LDPC,
                 frame_receiver = _MODE_PROFILED_CZ)...)

function CrcProfiledCzFrameModulation(; kwargs...)
  supplied = (; kwargs...)
  for (field, expected) in pairs((
      mode=_MODE_CRC_PROFILED_CZ_FRAME,
      frame_receiver=_MODE_PROFILED_CZ,
      frame_crc_bits=16,
  ))
    haskey(supplied, field) || continue
    supplied[field] == expected || throw(ArgumentError(
      "CrcProfiledCzFrameModulation fixes $field=$expected"))
  end
  em_enabled = haskey(supplied, :cz_em_enabled) ?
    supplied.cz_em_enabled : true
  Modulation(; (; kwargs..., mode=_MODE_CRC_PROFILED_CZ_FRAME,
                 frame_receiver=_MODE_PROFILED_CZ,
                 frame_crc_bits=16,
                 cz_em_enabled=em_enabled)...)
end

function CrcTurboCwzFrameModulation(; kwargs...)
  supplied = (; kwargs...)
  for (field, expected) in pairs((
      mode=_MODE_CRC_PROFILED_CZ_FRAME,
      frame_receiver=_MODE_PROFILED_CZ,
      frame_crc_bits=16,
  ))
    haskey(supplied, field) || continue
    supplied[field] == expected || throw(ArgumentError(
      "CrcTurboCwzFrameModulation fixes $field=$expected"))
  end
  Modulation(; (; kwargs...,
                 mode=_MODE_CRC_PROFILED_CZ_FRAME,
                 frame_receiver=_MODE_PROFILED_CZ,
                 frame_crc_bits=16,
                 cz_em_enabled=true,
                 cz_independent_w=true,
                 cz_bp_feedback=0.5)...)
end

"""
Construct the conditioned-C/W/z Experiment-B control or treatment.

Both arms share every receiver setting. `cz_conditioned_joint=false` disables
only the simultaneous conditioned proposal; setting it to `true` enables that
proposal. The legacy `CrcConditionedJointCwzFrameModulation` constructor below
remains the treatment-only public spelling.
"""
function CrcConditionedCwzFrameModulation(; kwargs...)
  supplied = (; kwargs...)
  for (field, expected) in pairs((
      mode=_MODE_CRC_PROFILED_CZ_FRAME,
      frame_receiver=_MODE_PROFILED_CZ,
      frame_crc_bits=16,
  ))
    haskey(supplied, field) || continue
    supplied[field] == expected || throw(ArgumentError(
      "CrcConditionedCwzFrameModulation fixes $field=$expected"))
  end
  conditioned = haskey(supplied, :cz_conditioned_joint) ?
    supplied.cz_conditioned_joint : false
  conditioned isa Bool || throw(ArgumentError(
    "cz_conditioned_joint must be Boolean"))
  Modulation(; (; cz_em_enabled=true,
                 cz_independent_w=false,
                 cz_bp_feedback=0.5,
                 cz_vp_gradient=true,
                 kwargs...,
                 mode=_MODE_CRC_PROFILED_CZ_FRAME,
                 frame_receiver=_MODE_PROFILED_CZ,
                 frame_crc_bits=16,
                 cz_conditioned_joint=conditioned)...)
end

function CrcConditionedJointCwzFrameModulation(; kwargs...)
  supplied = (; kwargs...)
  haskey(supplied, :cz_conditioned_joint) &&
    supplied.cz_conditioned_joint !== true &&
    throw(ArgumentError(
      "CrcConditionedJointCwzFrameModulation fixes cz_conditioned_joint=true"))
  CrcConditionedCwzFrameModulation(
    ; kwargs...,
      cz_em_enabled=true,
      cz_independent_w=false,
      cz_bp_feedback=0.5,
      cz_vp_gradient=true,
      cz_conditioned_joint=true)
end

function _frame_receiver_profile(m::Modulation)
  receiver_profile(m) === _MODE_FRAME_WIDE_LDPC ||
    throw(ArgumentError("frame receiver profile only applies to frame-wide LDPC"))
  m.frame_receiver
end

# Fixed internal constants — folded out of the user-facing config (they are numerical
# defaults / solver internals nobody tunes per run). The _GRAD_* knobs only take effect
# when receiver_profile(m) === :full.
const _BP_ITERS = 20                           # belief-propagation iterations
const _JUNA_ITERS = 2                          # JUNA refinement passes
const _RIDGE = 1e-3                            # Tikhonov ridge on the RLS normal equations
const _LLR_CLIP = 20.0                         # channel-LLR clip magnitude
const _LLR_IP = 20.0                           # inner-pilot clamp magnitude
const _BP_ALPHA = 0.8                          # normalized min-sum scaling
const _JUNA_CONFIDENCE_MIN = 0.0               # min posterior confidence for a soft data anchor
const _JUNA_MAX_DATA_ANCHORS = typemax(Int)    # cap on soft data anchors used in the refit
const _GRAD_STEPS = 20
const _GRAD_LAMBDA_CODE = 0.08                 # parity-surrogate weight
const _GRAD_TRUST_MU = 50.0                    # trust region ‖z-z0‖
const _GRAD_GAMMA_Z = 1e-4                     # ridge on z
const _GRAD_ETA_W = 0.02                       # combiner anchor ‖W-W0‖
const _GRAD_TIE_WEIGHT = 1.0
const _GRAD_PILOT_WEIGHT = 2.0
const _GRAD_ALPHA_W = 0.006
const _GRAD_ALPHA_Z = 0.02
const _GRAD_CLIP_Z = 10.0

_wz_refinement_steps(m::Modulation) =
  m.refinement_steps < 0 ? _GRAD_STEPS : m.refinement_steps
const _GRAD_CLIP_W = 25.0
const _GRAD_CLIP = 100.0
const _GRAD_BETA1 = 0.9
const _GRAD_BETA2 = 0.999
const _GRAD_EPS_ADAM = 1e-8
const _SYNC_LEN = 2048                         # LFM sync samples front+back when sync=true (best estimation in a len×bw×SNR sweep)
const _SYNC_BW = 0.9                           # chirp sweep as a fraction of the baseband band (sharp delay-Doppler peak, small guard)
const _SYNC_PROFILE_LFM = :lfm

const _FEEDBACK_REAL = :real
const _FEEDBACK_FROZEN = :frozen
const _FEEDBACK_GENIE = :genie
const _FEEDBACK_GRADED = :graded
const _FEEDBACK_MODES =
  (_FEEDBACK_REAL, _FEEDBACK_FROZEN, _FEEDBACK_GENIE, _FEEDBACK_GRADED)
# Arms that replace posterior decisions with (possibly corrupted) ground truth.
const _FEEDBACK_ORACLE_MODES = (_FEEDBACK_GENIE, _FEEDBACK_GRADED)
const _CZ_FEEDBACK_SOURCES = (:legacy, :frozen, :real, :genie)
const _LDPC_METHOD = "evencol"                 # make-ldpc construction
const _PARTIAL_FFT_NBANDS = 16                 # frequency bands for the bandwise RLS combiner
const _MAX_PARTIAL_FFT_PARTS = 16              # public complexity cap; band solves scale cubically in this count
const _BETA_FLOOR = 0.02                       # floor on the LLR-scale estimate from pilot residuals

struct _Code
  k::Int
  n::Int
  npc::Int
  method::String
  seed::Int
  no4cycle::Bool
  icols::Vector{Int}
  gen::BitMatrix
  H::BitMatrix
  check_vars::Vector{Vector{Int}}              # check_vars[c] = variable indices in check c
  var_edges::Vector{Vector{Tuple{Int,Int}}}    # var_edges[v] = (check, local-index) edges
  invperm::Vector{Int}                         # undoes the systematic column permutation
end

struct _Layout
  signature::Tuple
  active::Vector{Int}
  pilot_idx::Vector{Int}
  data_idx::Vector{Int}
  pilot_syms::Vector{ComplexF64}
  bands::Vector{Vector{Int}}
  band_ids::Vector{Int}
  active_rank::Vector{Int}
end

struct _BPScratch
  signature::Tuple{Int,Int,Int,String,Int,Bool}
  lch::Vector{Float64}
  lpost::Vector{Float64}
  bits::Vector{Bool}
  q::Vector{Vector{Float64}}
  r::Vector{Vector{Float64}}
end

function Modulations.init(m::Modulation, fc, fs)
  m.nc = 1024
  m.np = 256
  fs_value = try
    Float64(fs)
  catch
    NaN
  end
  m.bw = isfinite(fs_value) && fs_value > 0 ?
    min(fs_value / _REFERENCE_BANDWIDTH_HZ, 1.0) : 1.0
  m.dc0 = something(_dc0_for_fc(fc), Int16(0))
  m.bpc = 2
  m.pilot_ratio = 1/3
  m.inner_pilot_ratio = 1/2
  m.ldpc_k = 340
  m.ldpc_n = 1360
  m.ldpc_npc = 3
  m.partial_fft_parts = 4
  m.partial_fft_nbands = _PARTIAL_FFT_NBANDS
  # m.mode is left untouched so Modulation(mode=:robust) survives init()
  # Other acquisition choices remain untouched so constructor-selected settings survive init().
  m.code = nothing
  m.layout = nothing
  m.bp_scratch = nothing
  m.fully_coupled_trace = nothing
  m.guarded_physical_trace = nothing
  m.gradient_guarded_trace = nothing
  m.profiled_gradient_trace = nothing
  m.cz_gradient_trace = nothing
  nothing
end

_bpc(m::Modulation) = Int(m.bpc)
_dc0_hz(m::Modulation) = 1_000.0 * Int(m.dc0)
_rf_center_hz(m::Modulation) = _REFERENCE_CENTER_HZ + _dc0_hz(m)
_occupied_bandwidth_hz(m::Modulation) = Float64(m.bw) * _REFERENCE_BANDWIDTH_HZ

function _rf_band_edges(m::Modulation)
  half_width = _occupied_bandwidth_hz(m) / 2
  centre = _rf_center_hz(m)
  (centre - half_width, centre + half_width)
end

function _dc0_for_fc(fc)
  centre = try
    Float64(fc)
  catch
    return nothing
  end
  isfinite(centre) || return nothing
  offset = (centre - _REFERENCE_CENTER_HZ) / 1_000.0
  rounded = round(Int, offset)
  typemin(Int16) <= rounded <= typemax(Int16) || return nothing
  isapprox(offset, rounded; rtol=0, atol=32eps(max(abs(offset), 1.0))) ||
    return nothing
  Int16(rounded)
end

_baseband_occupancy(m::Modulation, fs::Real) =
  _occupied_bandwidth_hz(m) / Float64(fs)
_pm(b::Bool) = b ? -1.0 : 1.0    # bipolar map 1-2b: bit 0 -> +1, bit 1 -> -1

# Snap a pilot DENSITY ratio (fraction of positions that are pilots, e.g. 0.3) to the nearest
# achievable 1/k spacing ("every k-th position"), k >= kmin. ratio <= 0 means "off" (0).
function _ratio_spacing(ratio::Real, kmin::Int)
  ratio <= 0 && return 0
  inv = 1 / ratio
  klo = max(kmin, floor(Int, inv)); khi = klo + 1
  pick = abs(ratio - 1 / klo) <= abs(ratio - 1 / khi) ? klo : khi   # nearest unit fraction 1/k to the ratio
  max(kmin, pick)
end
_pilot_spacing(m::Modulation) = _ratio_spacing(m.pilot_ratio, 2)              # outer comb pilot every k-th active tone (k >= 2)
_inner_pilot_spacing(m::Modulation) = _ratio_spacing(m.inner_pilot_ratio, 1)  # inner pilot every k-th message bit (0 = off)

# Unknown payload bits per block = message bits minus inner pilots.
function Modulations.bitspersymbol(m::Modulation)
  k = Int(m.ldpc_k)
  ninner = _n_inner(m, k)
  k - ninner
end

_n_inner(m::Modulation, k::Integer) =
  (isp = _inner_pilot_spacing(m)) < 1 ? 0 : cld(Int(k), isp)

function Modulations.signallength(m::Modulation, nbits, fc, fs)
  isvalid(m, fc, fs) || throw(ArgumentError("invalid JUNA modulation settings"))
  nbits = _positive_nbits(nbits)
  _nblocks(m, nbits) * _blocklen(m) + _sync_overhead(m, fs)
end

function Base.isvalid(m::Modulation, fc, fs)
  fc isa Real && fs isa Real || return false
  isfinite(fc) && isfinite(fs) && fc > 0 && fs > 0 || return false
  try
    isfinite(Float64(fc)) && isfinite(Float64(fs)) || return false
  catch
    return false
  end
  N = Int(m.nc)
  L = Int(m.np)
  N > 2 && iseven(N) || return false
  0 <= L < N || return false
  _bpc(m) in (1, 2) || return false
  0 < m.bw <= 1 && isfinite(m.bw) || return false
  isapprox(Float64(fc), _rf_center_hz(m); rtol=0,
           atol=32eps(max(abs(Float64(fc)), _REFERENCE_CENTER_HZ))) || return false
  occupancy = _baseband_occupancy(m, Float64(fs))
  0 < occupancy <= 1 + 64eps(1.0) || return false
  0 < m.ldpc_k < m.ldpc_n || return false
  0 < m.ldpc_npc <= m.ldpc_n - m.ldpc_k || return false
  0 < m.partial_fft_parts <= min(N, _MAX_PARTIAL_FFT_PARTS) || return false
  0 < m.partial_fft_nbands <= N || return false
  profile = receiver_profile(m)
  profile in _RECEIVER_PROFILES || return false
  profile in (_MODE_FULL, _MODE_COUPLED, _MODE_FULLY_COUPLED, _MODE_TURBO_MAP,
              _MODE_GUARDED_PHYSICAL, _MODE_GRADIENT_GUARDED,
              _MODE_PROFILED_GRADIENT) &&
    _bpc(m) != 2 && return false
  m.refinement_steps >= -1 || return false
  m.feedback_mode in _FEEDBACK_MODES || return false
  isfinite(m.feedback_graded_p) &&
    0.0 <= m.feedback_graded_p <= 1.0 || return false
  if profile === _MODE_FRAME_WIDE_LDPC
    m.frame_crc_bits in (0, 16) || return false
    m.frame_code_horizon >= 0 || return false
    1 <= m.cz_restarts <= 5 || return false
    m.cz_restart_seed >= 0 || return false
    isfinite(m.cz_parity_weight) && m.cz_parity_weight >= 0.0 || return false
    isfinite(m.cz_em_trust) && m.cz_em_trust >= 0.0 || return false
    isfinite(m.cz_em_damping) &&
      0.0 < m.cz_em_damping <= 1.0 || return false
    isfinite(m.cz_bp_feedback) &&
      0.0 <= m.cz_bp_feedback <= 1.0 || return false
    m.cz_feedback_source in _CZ_FEEDBACK_SOURCES || return false
    isfinite(m.cz_joint_c_radius) && m.cz_joint_c_radius > 0.0 ||
      return false
    isfinite(m.cz_joint_w_radius) && m.cz_joint_w_radius > 0.0 ||
      return false
    isfinite(m.cz_joint_z_radius) && m.cz_joint_z_radius > 0.0 ||
      return false
    m.cz_joint_w_start >= 1 || return false
    isfinite(m.cz_joint_pilot_tolerance) &&
      m.cz_joint_pilot_tolerance >= 0.0 || return false
    isfinite(m.cz_temporal_c_smoothness) &&
      m.cz_temporal_c_smoothness >= 0.0 || return false
    m.frame_receiver in _FRAME_RECEIVER_PROFILES || return false
    m.frame_receiver in (_MODE_FULL, _MODE_COUPLED, _MODE_TURBO_MAP,
                         _MODE_PROFILED_GRADIENT, _MODE_PROFILED_CZ) &&
      _bpc(m) != 2 &&
      return false
  end
  m.ldpc_seed >= 0 || return false
  isfinite(m.frame_duration_s) && m.frame_duration_s > 0 || return false
  0 < m.pilot_ratio <= 1 || return false      # pilot densities snap to a 1/k spacing (outer needs k >= 2)
  0 <= m.inner_pilot_ratio <= 1 || return false
  Modulations.bitspersymbol(m) > 0 || return false
  _pilot_spacing(m) > 1 || return false
  layout = _layout(m, fs)
  m.ldpc_n <= _bpc(m) * length(layout.data_idx) || return false
  _pilot_training_sufficient(m, layout) || return false
  true
end

function _pilot_training_sufficient(m::Modulation, layout::_Layout)
  counts = zeros(Int, length(layout.bands))
  @inbounds for k in layout.pilot_idx
    band = layout.band_ids[k]
    band > 0 && (counts[band] += 1)
  end
  !isempty(counts) && minimum(counts) >= m.partial_fft_parts
end

# Transmit pipeline:
# 1. Pad and split payload bits into bitspersymbol-sized blocks.
# 2. Insert deterministic inner pilots into each k-bit LDPC message.
# 3. LDPC-encode each message from k information bits to n coded bits.
# 4. Map coded bits and outer pilots into the OFDM carrier layout.
# 5. IFFT, cyclic prefix, and normalization produce one complex baseband block.
# 6. Optional LFM sync wrapping produces [sync][blocks...][sync].
#
# How fc, fs, bw, and dc0 affect modulation: the modem reference centre and
# width are both 24 kHz. `bw * 24 kHz` is the occupied RF width, while integer
# `dc0` records the tuned centre as `24 kHz + dc0 kHz`; that centre must equal
# `fc`. `fs` is the complex-baseband grid width, so the active FFT fraction is
# `(bw * 24 kHz) / fs`. Thus fc=25 kHz, fs=9.6 kHz, bw=0.4, dc0=1 occupies
# 20.2--29.8 kHz and fills the baseband grid. RF tuning does not shift the
# generated complex-baseband bins. `fs` also sets the optional sync time scale.
function Modulations.modulate(m::Modulation, bits, fc, fs)
  isvalid(m, fc, fs) || throw(ArgumentError("invalid JUNA modulation settings"))
  payload = Bool.(bits)
  isempty(payload) && throw(ArgumentError("JUNA modulation requires at least one payload bit"))
  receiver_profile(m) === _MODE_FRAME_WIDE_LDPC &&
    return _modulate_frame_wide_ldpc(m, payload, fs)
  code = _code(m)
  layout = _layout(m, fs)
  bps = Modulations.bitspersymbol(m)
  pad = mod(length(payload), bps)
  pad != 0 && append!(payload, falses(bps - pad))

  nblocks = div(length(payload), bps)
  out = Vector{ComplexF64}(undef, nblocks * _blocklen(m))
  for block in 1:nblocks
    blo = 1 + (block - 1) * bps
    bhi = block * bps
    message = _build_message(m, code, @view payload[blo:bhi])
    samples = _modulate_block(m, layout, _encode(code, message))
    copyto!(out, 1 + (block - 1) * _blocklen(m), samples, 1, _blocklen(m))
  end
  m.sync || return out
  sync = _sync_waveform(m, fs)
  vcat(sync, out, sync)
end

function _prepare_demodulation(m::Modulation, nbits, x, fc, fs)
  isvalid(m, fc, fs) || throw(ArgumentError("invalid JUNA modulation settings"))
  nbits2 = _positive_nbits(nbits)
  waveform = _complex_waveform(x)
  _require_finite_waveform(waveform)
  code = _code(m)
  layout = _layout(m, fs)
  nblocks = _nblocks(m, nbits2)
  nbits2, waveform, code, layout, nblocks
end

function _require_block_samples(m::Modulation, waveform, nblocks::Integer)
  required = Int(nblocks) * _blocklen(m)
  length(waveform) >= required ||
    throw(ArgumentError("received $(length(waveform)) samples, need at least $required"))
  waveform
end

function Modulations.demodulate(m::Modulation, nbits, x, fc, fs)
  receiver_profile(m) === _MODE_FRAME_WIDE_LDPC &&
    return _demodulate_frame_wide_ldpc(m, nbits, x, fc, fs)
  receiver_profile(m) === _MODE_FULLY_COUPLED &&
    return _demodulate_fully_coupled(m, nbits, x, fc, fs)
  receiver_profile(m) === _MODE_GUARDED_PHYSICAL &&
    return _demodulate_guarded_physical(m, nbits, x, fc, fs)
  nbits, waveform, code, layout, nblocks =
    _prepare_demodulation(m, nbits, x, fc, fs)
  cfo = 0.0
  if m.sync
    waveform, cfo = _coarse_doppler(m, waveform, fc, fs, nblocks)
  end
  _require_block_samples(m, waveform, nblocks)

  metrics = Vector{Float64}(undef, Int(nbits))
  pos = 1
  for block in 1:nblocks
    lo = 1 + (block - 1) * _blocklen(m)
    hi = block * _blocklen(m)
    candidate = _demodulate_block_candidate(m, code, layout, @view waveform[lo:hi])
    pos = _write_payload_metrics!(metrics, pos, m, code, candidate.lpost_metric, Int(nbits))
  end

  metrics, cfo
end

function demodulate_methods(m::Modulation, nbits, x, fc, fs)
  receiver_profile(m) === _MODE_FRAME_WIDE_LDPC &&
    return _demodulate_frame_methods(m, nbits, x, fc, fs)
  receiver_profile(m) === _MODE_FULLY_COUPLED &&
    return _demodulate_fully_coupled_methods(m, nbits, x, fc, fs)
  receiver_profile(m) === _MODE_GUARDED_PHYSICAL &&
    return _demodulate_guarded_physical_methods(m, nbits, x, fc, fs)
  nbits, waveform, code, layout, nblocks =
    _prepare_demodulation(m, nbits, x, fc, fs)
  _require_block_samples(m, waveform, nblocks)

  standard = Vector{Float64}(undef, Int(nbits))
  partial = Vector{Float64}(undef, Int(nbits))
  juna = Vector{Float64}(undef, Int(nbits))
  spos = ppos = jpos = 1
  for block in 1:nblocks
    lo = 1 + (block - 1) * _blocklen(m)
    hi = block * _blocklen(m)
    block = @view waveform[lo:hi]
    yparts = _branch_observations(m, block)
    standard_candidate = _standard_candidate(m, code, layout, yparts)
    initial_candidate = _initial_candidate(m, code, layout, yparts)
    juna_initial_candidate = _select_front_end_initial_candidate(standard_candidate, initial_candidate)
    juna_candidate = _juna_candidate(m, code, layout, yparts, juna_initial_candidate)
    spos = _write_payload_metrics!(standard, spos, m, code, standard_candidate.lpost_metric, Int(nbits))
    ppos = _write_payload_metrics!(partial, ppos, m, code, initial_candidate.lpost_metric, Int(nbits))
    jpos = _write_payload_metrics!(juna, jpos, m, code, juna_candidate.lpost_metric, Int(nbits))
  end

  (standard=standard, partial=partial, juna=juna,
   provenance=receiver_profile(m))
end

_blocklen(m::Modulation) = Int(m.nc) + Int(m.np)
function _positive_nbits(nbits)
  nbits isa Integer && !(nbits isa Bool) ||
    throw(ArgumentError("nbits must be a positive integer"))
  0 < nbits <= typemax(Int) || throw(ArgumentError("nbits must be a positive integer"))
  Int(nbits)
end

_nblocks(m::Modulation, nbits::Integer) =
  receiver_profile(m) === _MODE_FRAME_WIDE_LDPC ?
    _frame_nblocks(m, nbits) :
    cld(_positive_nbits(nbits), Modulations.bitspersymbol(m))
_ndata_tones(m::Modulation, ncoded::Integer) = cld(Int(ncoded), _bpc(m))
_complex_waveform(x::AbstractVector{ComplexF64}) = x
_complex_waveform(x) = ComplexF64.(x)

function _require_finite_waveform(waveform)
  all(isfinite, waveform) ||
    throw(ArgumentError("received waveform must contain only finite samples"))
  waveform
end

# ---- coarse Doppler via a per-frame sync (LFM) pre/postamble ----------------
_synclen(m::Modulation) =
  m.sync ? _SYNC_LEN : 0

function _sync_overhead(m::Modulation, fs)
  m.sync ? 2 * _SYNC_LEN : 0
end

"""
    frameblockcount(m, fs)

Largest positive number of complete OFDM blocks whose synchronization
overhead and samples fit within `m.frame_duration_s`.
"""
function Modulations.frameblockcount(m::Modulation, fs::Real)
  rate = Float64(fs)
  isfinite(rate) && rate > 0 ||
    throw(ArgumentError("sample rate must be finite and positive"))
  isfinite(m.frame_duration_s) && m.frame_duration_s > 0 ||
    throw(ArgumentError("frame duration must be finite and positive"))
  budget = floor(Int, m.frame_duration_s * rate)
  overhead = _sync_overhead(m, rate)
  available = budget - overhead
  blocks = fld(available, _blocklen(m))
  blocks >= 1 || throw(ArgumentError(
    "frame duration $(m.frame_duration_s) s cannot hold one complete OFDM block after $overhead overhead samples"))
  blocks
end

"""
    framepayloadbits(m, fs)

Maximum user-payload bits carried by `frameblockcount(m, fs)` complete OFDM
blocks. Frame-wide modes account for global inner pilots and the configured
CRC; packet modes use their per-block payload capacity.
"""
function Modulations.framepayloadbits(m::Modulation, fs::Real)
  blocks = Modulations.frameblockcount(m, fs)
  capacity = receiver_profile(m) === _MODE_FRAME_WIDE_LDPC ?
    _frame_payload_capacity(m, blocks) :
    blocks * Modulations.bitspersymbol(m)
  capacity > 0 || throw(ArgumentError(
    "time-budgeted frame has no user-payload capacity"))
  capacity
end

# Deterministic dual-slope baseband LFM used as the per-frame sync pre/postamble.
# The opposite slopes make common delay cancel in the signed carrier-offset
# estimate while retaining the existing total synchronization duration.
function _sync_chirp(samples::Int, fs, direction::Real)
  samples <= 0 && return ComplexF64[]
  T = samples / fs
  k = clamp(_SYNC_BW, 0.05, 1.0) * fs / T
  ComplexF64[
    cispi(direction * k * (n / fs - T / 2)^2) for n in 0:samples-1]
end

function _sync_components(m::Modulation, fs)
  S = _synclen(m)
  S == 0 && return ComplexF64[], ComplexF64[]
  front = div(S, 2)
  back = S - front
  _sync_chirp(front, fs, 1.0), _sync_chirp(back, fs, -1.0)
end

function _sync_waveform(m::Modulation, fs)
  front, back = _sync_components(m, fs)
  vcat(front, back)
end

# |matched filter| of rx against the known sync, over every lag.
function _matched_corr(rx::AbstractVector{<:Complex}, sync::AbstractVector{<:Complex})
  S = length(sync); M = length(rx); L = M - S + 1
  L <= 0 && return Float64[]
  sconj = conj.(sync)
  c = Vector{Float64}(undef, L)
  @inbounds for lag in 1:L
    acc = zero(ComplexF64)
    for i in 1:S
      acc += rx[lag + i - 1] * sconj[i]
    end
    c[lag] = abs(acc)
  end
  c
end

# Linear-interpolation resample of x to exactly `target` samples (coarse timing fix; the CP absorbs residual).
function _resample_to(x::AbstractVector{<:Complex}, target::Int)
  n = length(x)
  (target <= 0 || n == 0) && return ComplexF64[]
  n == target && return ComplexF64.(x)
  out = Vector{ComplexF64}(undef, target)
  @inbounds for i in 1:target
    pos = target == 1 ? 1.0 : 1 + (i - 1) * (n - 1) / (target - 1)
    lo = clamp(floor(Int, pos), 1, n); hi = min(lo + 1, n); frac = pos - lo
    out[i] = (1 - frac) * x[lo] + frac * x[hi]
  end
  out
end

# Sub-sample correlation peak inside a bounded acquisition window.
function _sync_peak_near(correlation::AbstractVector{<:Real}, expected, radius::Int)
  isempty(correlation) && return nothing
  lo = max(1, floor(Int, expected - radius))
  hi = min(length(correlation), ceil(Int, expected + radius))
  lo <= hi || return nothing
  peak = lo - 1 + argmax(@view correlation[lo:hi])
  offset = 0.0
  if 1 < peak < length(correlation)
    left = correlation[peak - 1]
    centre = correlation[peak]
    right = correlation[peak + 1]
    denominator = left - 2centre + right
    abs(denominator) > eps(max(abs(centre), 1.0)) &&
      (offset = clamp(0.5 * (left - right) / denominator, -0.5, 0.5))
  end
  peak + offset
end

function _scaled_segment(waveform::AbstractVector{<:Complex}, start, scale,
                         samples::Int)
  samples <= 0 && return ComplexF64[]
  output = Vector{ComplexF64}(undef, samples)
  @inbounds for index in 1:samples
    position = start + (index - 1) * scale
    lo = clamp(floor(Int, position), 1, length(waveform))
    hi = min(lo + 1, length(waveform))
    fraction = position - lo
    output[index] = (1 - fraction) * waveform[lo] + fraction * waveform[hi]
  end
  output
end

function _sync_phase_rate(segment, reference, fs, scale)
  length(segment) == length(reference) || return 0.0
  length(segment) < 2 && return 0.0
  dechirped = segment .* conj.(reference)
  increment = sum(
    @view(dechirped[2:end]) .* conj.(@view(dechirped[1:end-1])))
  abs(increment) <= eps(Float64) && return 0.0
  angle(increment) * fs / (2pi * scale)
end

function _sync_impairments(m::Modulation,
                           waveform::AbstractVector{<:Complex}, fs, nblocks)
  S = _synclen(m)
  blocklen = _blocklen(m)
  nominal_spacing = S + nblocks * blocklen
  front, back = _sync_components(m, fs)
  (isempty(front) || isempty(back)) && return 0.0, 1.0

  radius = max(16, div(S, 4))
  padding = zeros(ComplexF64, radius)
  padded = vcat(padding, ComplexF64.(waveform), padding)
  front_correlation = _matched_corr(padded, front)
  back_correlation = _matched_corr(padded, back)
  front_start = _sync_peak_near(
    front_correlation, radius + 1, radius)
  back_start = _sync_peak_near(
    back_correlation, radius + 1 + length(front), radius)
  repeated_front_start = _sync_peak_near(
    front_correlation, radius + 1 + nominal_spacing, radius)
  any(isnothing, (front_start, back_start, repeated_front_start)) &&
    return 0.0, 1.0

  first_front = front_start - radius
  first_back = back_start - radius
  second_front = repeated_front_start - radius
  duration_scale = (second_front - first_front) / nominal_spacing
  isfinite(duration_scale) && duration_scale > 0 || return 0.0, 1.0

  # Opposite chirp slopes turn a common timing error into equal and opposite
  # dechirped phase rates. Their mean is therefore the signed carrier offset.
  common_start = (first_front + first_back -
                  duration_scale * length(front)) / 2
  received_front = _scaled_segment(
    waveform, common_start, duration_scale, length(front))
  received_back = _scaled_segment(
    waveform, common_start + duration_scale * length(front),
    duration_scale, length(back))
  carrier_offset = (
    _sync_phase_rate(received_front, front, fs, duration_scale) +
    _sync_phase_rate(received_back, back, fs, duration_scale)) / 2
  isfinite(carrier_offset) || return 0.0, duration_scale
  carrier_offset, duration_scale
end

# Joint carrier-offset and duration acquisition. Carrier rotation is removed
# before OFDM observations; front-sync spacing retains the independent coarse
# duration correction.
function _coarse_doppler(m::Modulation, waveform::AbstractVector{<:Complex}, fc, fs, nblocks)
  _ = fc
  S = _synclen(m); blocklen = _blocklen(m)
  nominal_blocks = nblocks * blocklen
  D0 = S + nominal_blocks
  carrier_offset, _ = _sync_impairments(m, waveform, fs, nblocks)
  sample = collect(0:length(waveform)-1)
  derotated = ComplexF64.(waveform) .*
    cispi.(-2 * carrier_offset .* sample ./ fs)

  front, _ = _sync_components(m, fs)
  radius = max(16, div(S, 4))
  padding = zeros(ComplexF64, radius)
  correlation = _matched_corr(vcat(padding, derotated, padding), front)
  p1 = _sync_peak_near(correlation, radius + 1, radius)
  p2 = _sync_peak_near(correlation, radius + 1 + D0, radius)
  (p1 === nothing || p2 === nothing) && return derotated, carrier_offset
  p1 -= radius
  p2 -= radius
  D = p2 - p1
  duration_scale = (D > 0 && D0 > 0) ? D / D0 : 1.0
  bstart = round(Int, p1 + duration_scale * S)
  bstop = round(Int, p2) - 1
  (bstart < 1 || bstop > length(waveform) || bstop <= bstart) &&
    return derotated, carrier_offset
  corrected = _resample_to(@view(derotated[bstart:bstop]), nominal_blocks)
  corrected, carrier_offset
end


function _write_metrics!(out::Vector{Float64}, pos::Int, payload, nbits::Int)
  @inbounds for bit in payload
    pos > nbits && break
    out[pos] = bit ? 1.0 : -1.0
    pos += 1
  end
  pos
end

function _write_payload_metrics!(out::Vector{Float64}, pos::Int, m::Modulation,
                                 code::_Code, metrics::AbstractVector{<:Real}, nbits::Int)
  mparity = code.n - code.k
  isp = _inner_pilot_spacing(m)
  @inbounds for p in 1:code.k
    isp >= 1 && (p - 1) % isp == 0 && continue
    pos > nbits && break
    out[pos] = metrics[code.invperm[mparity + p]] > 0 ? 1.0 : -1.0
    pos += 1
  end
  pos
end

function _layout(m::Modulation, fs)
  sig = (Int(m.nc), Float64(m.bw), _pilot_spacing(m), Int(m.partial_fft_nbands),
         Int(m.dc0), Float64(fs))
  m.layout isa _Layout && m.layout.signature == sig && return m.layout::_Layout

  N, bw, pilot_spacing, nbands, dc0_khz, fsr = sig
  _ = dc0_khz
  occupied_fraction = min(1.0, bw * _REFERENCE_BANDWIDTH_HZ / fsr)
  nactive = clamp(floor(Int, (N - 1) * occupied_fraction), 2, N - 1)
  npos = nactive ÷ 2
  nneg = nactive - npos
  active = vcat(collect(2:1+npos), collect(N-nneg+1:N))        # nactive carriers centred on DC
  pilot_idx = [k for k in active if (k - 2) % pilot_spacing == 0]
  pilot_set = Set(pilot_idx)
  data_idx = [k for k in active if !(k in pilot_set)]
  pilot_syms = ComplexF64[
    isodd((1103515245 * k + 12345) & 0x7fffffff) ? -1.0 + 0.0im : 1.0 + 0.0im
    for k in pilot_idx
  ]
  bands = Vector{Vector{Int}}(undef, nbands)
  for b in 1:nbands
    lo, hi = _part_bounds(length(active), nbands, b)
    bands[b] = collect(@view active[lo:hi])
  end
  band_ids = zeros(Int, N)
  active_rank = zeros(Int, N)
  for (rank, k) in enumerate(active)
    active_rank[k] = rank
  end
  for (band_id, band) in enumerate(bands)
    band_ids[band] .= band_id
  end

  m.layout = _Layout(sig, active, pilot_idx, data_idx, pilot_syms, bands,
                     band_ids, active_rank)
  m.layout::_Layout
end

function _code(m::Modulation)
  method = _code_method(m)
  seed = _code_seed(m, m.ldpc_k, m.ldpc_n, m.ldpc_npc)
  if m.code === nothing ||
      m.code.k != m.ldpc_k ||
      m.code.n != m.ldpc_n ||
      m.code.npc != m.ldpc_npc ||
      m.code.method != method ||
      m.code.seed != seed ||
      m.code.no4cycle != m.ldpc_no4cycle
    m.code = _create_code(
      m.ldpc_k, m.ldpc_n, m.ldpc_npc, method, seed, m.ldpc_no4cycle)
    m.bp_scratch = nothing
  end
  m.code
end

# Build the LDPC code through the shared LDPC.jl builder. `ldpc_npc` (the per-column
# check count dc) is the configurable knob; the make-ldpc construction is fixed to the
# _LDPC_METHOD constant ("evencol") and threaded in here as the `method` argument.
function _code_method(m::Modulation)
  m.ldpc_method === :auto && return _LDPC_METHOD
  m.ldpc_method in (:evencol, :evenboth) || throw(ArgumentError(
    "LDPC method must be :auto, :evencol, or :evenboth"))
  String(m.ldpc_method)
end

_code_seed(m::Modulation, k::Integer, n::Integer, npc::Integer) =
  m.ldpc_method !== :auto ? m.ldpc_seed : _ldpc_seed(k, n, npc)

function _create_code(k::Int, n::Int, npc::Int, method::AbstractString,
                      seed::Int=_ldpc_seed(k, n, npc), no4cycle::Bool=true)
  0 < k < n || throw(ArgumentError("LDPC dimensions must satisfy 0 < k < n"))
  0 < npc <= n - k ||
    throw(ArgumentError("LDPC column degree must satisfy 0 < npc <= n-k"))
  method == "frame_sparse" &&
    return _create_sparse_systematic_code(k, n, npc, seed, method, no4cycle)
  r = try
    LDPC.build(k, n; method=method, dc=npc, no4cycle, seed=seed)
  catch err
    err isa InterruptException && rethrow()
    detail = sprint(showerror, err)
    throw(ArgumentError("failed to construct LDPC ($k, $n, npc=$npc): $detail"))
  end
  check_vars, var_edges = _build_graph(r.H)
  _Code(k, n, npc, String(method), seed, no4cycle,
        r.icols, BitMatrix(r.gen), BitMatrix(r.H),
        check_vars, var_edges, invperm(r.icols))
end

function _create_sparse_systematic_code(k::Int, n::Int, dc::Int, seed::Int,
                                        method::AbstractString,
                                        no4cycle::Bool=true)
  m = n - k
  # Identity parity columns make encoding proportional to Tanner-graph edges.
  # This is the ReplayCh code shape and also keeps large frame-wide codes usable.
  column_degree = min(m, dc)
  rng = MersenneTwister(seed)
  generator = falses(m, k)
  H = falses(m, n)
  check_vars = [Int[] for _ in 1:m]
  chosen = Vector{Int}(undef, column_degree)
  @inbounds for column in 1:k
    used = 0
    while used < column_degree
      row = rand(rng, 1:m)
      any(i -> chosen[i] == row, 1:used) && continue
      used += 1
      chosen[used] = row
      generator[row, column] = true
      H[row, column] = true
      push!(check_vars[row], column)
    end
  end
  @inbounds for row in 1:m
    parity_variable = k + row
    H[row, parity_variable] = true
    push!(check_vars[row], parity_variable)
  end
  icols = vcat(collect(m+1:n), collect(1:m))
  var_edges = _build_var_edges(check_vars, n)
  _Code(k, n, dc, String(method), seed, no4cycle,
        icols, generator, H, check_vars,
        var_edges, invperm(icols))
end

function _ldpc_seed(k, n, npc)
  # Keep the reviewed paper-default graph stable while deriving distinct,
  # range-safe helper seeds for other code geometries.
  mixed = Int128(10_001) +
          (Int128(k) - 340) * 1_000_003 +
          (Int128(n) - 1360) * 1_009 +
          (Int128(npc) - 3)
  Int(mod(mixed, Int128(LDPC._MAX_TOOL_SEED) + 1))
end

function _build_graph(H)
  mrows, n = size(H)
  check_vars = [findall(@view H[c, :]) for c in 1:mrows]
  check_vars, _build_var_edges(check_vars, n)
end

function _build_var_edges(check_vars, n::Integer)
  var_edges = [Tuple{Int,Int}[] for _ in 1:n]
  for c in eachindex(check_vars)
    for (a, v) in enumerate(check_vars[c])
      push!(var_edges[v], (c, a))
    end
  end
  var_edges
end

# Systematic LDPC encoding: generator rows form the parity prefix while the
# original k message bits occupy the permuted systematic positions.
function _encode(code::_Code, bits::AbstractVector{Bool})
  length(bits) == code.k ||
    throw(ArgumentError("LDPC encoder expects $(code.k) bits, got $(length(bits))"))
  block_diagonal_sparse =
    startswith(code.method, "frame_blockdiag_") &&
    endswith(code.method, "_frame_sparse")
  if block_diagonal_sparse
    # Each repeated sparse component has H=[G I], but its physical
    # [message; parity] variables are interleaved component by component.
    # `icols` maps those physical variables back to the composite systematic
    # coordinates, so populate every message variable first and then evaluate
    # each identity-parity check in edge-linear time.
    nparity = code.n - code.k
    codeword = falses(code.n)
    @inbounds for variable in 1:code.n
      source = code.icols[variable]
      source > nparity &&
        (codeword[variable] = bits[source - nparity])
    end
    @inbounds for check in eachindex(code.check_vars)
      parity_variable = code.invperm[check]
      parity = false
      for variable in code.check_vars[check]
        variable == parity_variable && continue
        parity ⊻= codeword[variable]
      end
      codeword[parity_variable] = parity
    end
    return codeword
  end
  if code.method == "frame_sparse"
    # For H=[G I], the transmitted order is [message; parity].
    codeword = falses(code.n)
    copyto!(codeword, 1, bits, 1, code.k)
    @inbounds for check in eachindex(code.check_vars)
      parity = false
      for variable in code.check_vars[check]
        variable <= code.k && (parity ⊻= bits[variable])
      end
      codeword[code.k + check] = parity
    end
    return codeword
  end
  nparity = code.n - code.k
  codeword = Vector{Bool}(undef, code.n)
  @inbounds for outpos in 1:code.n
    src = code.icols[outpos]
    if src <= nparity
      s = false
      for j in 1:code.k
        code.gen[src, j] && (s ⊻= bits[j])
      end
      codeword[outpos] = s
    else
      codeword[outpos] = bits[src - nparity]
    end
  end
  codeword
end

# ----- message <-> payload (inner pilots are known message bits) ---------------

_inner_bit(p::Integer) = isodd((1103515245 * p + 12345) & 0x7fffffff)

_known_inner_bit(m::Modulation, message_position::Integer) =
  _inner_bit(message_position)

# Expand one payload block into the k-bit LDPC message. Known inner-pilot bits
# occupy every isp-th message position; payload fills the positions between them.
function _build_message(m::Modulation, code::_Code, payload::AbstractVector{Bool})
  message = falses(code.k)
  max_payload = code.k - _n_inner(m, code.k)
  length(payload) <= max_payload ||
    throw(ArgumentError("block holds $(max_payload) payload bits, got $(length(payload))"))
  i = 1
  isp = _inner_pilot_spacing(m)
  for p in 1:code.k
    if isp >= 1 && (p - 1) % isp == 0
      message[p] = _inner_bit(p)
    elseif i <= length(payload)
      message[p] = payload[i]
      i += 1
    end
  end
  message
end

function _payload_from_metrics(m::Modulation, code::_Code, metrics::AbstractVector{<:Real})
  payload = Vector{Bool}(undef, code.k - _n_inner(m, code.k))
  mparity = code.n - code.k
  i = 1
  isp = _inner_pilot_spacing(m)
  @inbounds for p in 1:code.k
    isp >= 1 && (p - 1) % isp == 0 && continue
    payload[i] = metrics[code.invperm[mparity + p]] > 0
    i += 1
  end
  payload
end

# Inner-pilot clamps are written directly into the BP channel LLR buffer.
function _apply_inner_clamps!(m::Modulation, code::_Code, lch::Vector{Float64},
                              message_block_k::Int=code.k)
  isp = _inner_pilot_spacing(m)
  isp < 1 && return lch
  valid_block = 0 < message_block_k <= code.k && code.k % message_block_k == 0
  valid_block ||
    throw(ArgumentError("message block size must divide the LDPC message length"))
  mparity = code.n - code.k
  Lip = min(_LLR_CLIP, _LLR_IP)
  @inbounds for p in 1:code.k
    local_p = (p - 1) % message_block_k + 1
    (local_p - 1) % isp == 0 || continue
    lch[code.invperm[mparity + p]] = _known_inner_bit(m, local_p) ? -Lip : Lip
  end
  lch
end

# ----- modulation -------------------------------------------------------------

# BPSK consumes one coded bit per data tone. QPSK consumes an I/Q pair using
# bit 0 -> +1 and bit 1 -> -1, then divides by sqrt(2) for unit symbol power.
function _carrier_symbol(m::Modulation, codeword::AbstractVector{Bool}, tone::Int)
  if _bpc(m) == 1
    _bpsk_symbol(codeword[tone])
  else
    j = 2 * (tone - 1) + 1
    bI = codeword[j]
    bQ = j + 1 <= length(codeword) ? codeword[j + 1] : false
    ComplexF64(_pm(bI), _pm(bQ)) / sqrt(2)
  end
end

# Render one LDPC codeword as one CP-OFDM block: deterministic outer pilots and
# coded data fill frequency bins, IFFT creates N time samples, the final L samples
# become the cyclic prefix, and standard-deviation normalization fixes block scale.
function _modulate_block(m::Modulation, layout::_Layout, codeword::AbstractVector{Bool})
  carriers = zeros(ComplexF64, Int(m.nc))

  for (k, s) in zip(layout.pilot_idx, layout.pilot_syms)
    carriers[k] = s
  end

  ntones = _ndata_tones(m, length(codeword))
  for (i, k) in enumerate(layout.data_idx)
    carriers[k] = i <= ntones ? _carrier_symbol(m, codeword, i) : one(ComplexF64)
  end

  sym = ifft(carriers)
  L = Int(m.np)
  N = Int(m.nc)
  block = Vector{ComplexF64}(undef, L + N)
  @inbounds for i in 1:L
    block[i] = sym[N - L + i]
  end
  @inbounds for i in 1:N
    block[L + i] = sym[i]
  end
  scale = std(block)
  @inbounds for i in eachindex(block)
    block[i] /= scale
  end
  block
end

# ----- demodulation branches --------------------------------------------------

function _demodulate_block(m::Modulation, code::_Code, layout::_Layout, waveform)
  _payload_from_metrics(m, code, _demodulate_block_candidate(m, code, layout, waveform).lpost_metric)
end

function _demodulate_block_candidate(m::Modulation, code::_Code, layout::_Layout, waveform)
  yparts = _branch_observations(m, waveform)
  profile = receiver_profile(m)
  # Benchmark baselines stop at their own front end: :standard never pays for
  # the partial-FFT initial candidate, and :pfft is the pure partial column of
  # demodulate_methods (no standard fallback, no refinement).
  profile === _MODE_STANDARD && return _standard_candidate(m, code, layout, yparts)
  profile === _MODE_PFFT && return _initial_candidate(m, code, layout, yparts)
  initial_candidate = _front_end_initial_candidate(m, code, layout, yparts)
  _juna_candidate(m, code, layout, yparts, initial_candidate)
end

function _demodulate_block_standard(m::Modulation, code::_Code, layout::_Layout, yparts)
  _payload_from_metrics(m, code, _standard_candidate(m, code, layout, yparts).lpost_metric)
end

function _demodulate_block_partial(m::Modulation, code::_Code, layout::_Layout, yparts)
  _payload_from_metrics(m, code, _initial_candidate(m, code, layout, yparts).lpost_metric)
end

function _standard_candidate(m::Modulation, code::_Code, layout::_Layout, yparts)
  equalized = _residual_pilot_equalize(m, layout, _sum_branches(yparts))
  _candidate_from_equalized(m, code, layout, equalized)
end

function _candidate_from_equalized(m::Modulation, code::_Code, layout::_Layout, equalized, metrics=nothing)
  if metrics === nothing
    metrics, pilot_mse = _channel_metrics_from_equalized(m, code.n, layout, equalized)
  else
    pilot_mse = _pilot_mse(layout, equalized)
  end
  _decode_candidate(m, code, layout, equalized, metrics, pilot_mse)
end

function _pilot_mse(layout::_Layout, equalized)
  pilot_sum = 0.0
  @inbounds for i in eachindex(layout.pilot_idx)
    pilot_sum += abs2(equalized[layout.pilot_idx[i]] - layout.pilot_syms[i])
  end
  pilot_sum / max(length(layout.pilot_idx), 1)
end

function _channel_metrics_from_equalized(m::Modulation, ncoded::Integer,
                                         layout::_Layout, equalized)
  n = Int(ncoded)
  ntones = _ndata_tones(m, n)
  pilot_mse = _pilot_mse(layout, equalized)
  beta = max(pilot_mse, _BETA_FLOOR)
  metrics = Vector{Float64}(undef, n)
  if _bpc(m) == 1
    for t in 1:n
      s = equalized[layout.data_idx[t]]
      metrics[t] = clamp((-2.0 * real(s)) / beta, -_LLR_CLIP, _LLR_CLIP)
    end
  else
    for t in 1:ntones
      s = equalized[layout.data_idx[t]]
      metrics[2t-1] = clamp((-2.0 * real(s)) / beta, -_LLR_CLIP, _LLR_CLIP)
      2t <= n && (metrics[2t] = clamp((-2.0 * imag(s)) / beta, -_LLR_CLIP, _LLR_CLIP))
    end
  end
  metrics, pilot_mse
end

# JUNA receiver dispatch: :lite (posterior-anchor RLS refit), :full
# (reduced-gradient Adam over W,z), or :coupled (exact conditional C/W solves
# with Adam only on z). :robust is
# accepted as a legacy alias for :full.
function _demodulate_block_juna(m::Modulation, code::_Code, layout::_Layout, yparts, initial_candidate=nothing)
  _payload_from_metrics(m, code, _juna_candidate(m, code, layout, yparts, initial_candidate).lpost_metric)
end

function _juna_candidate(m::Modulation, code::_Code, layout::_Layout, yparts, initial_candidate=nothing)
  profile = receiver_profile(m)
  profile === _MODE_STANDARD && return _standard_candidate(m, code, layout, yparts)
  profile === _MODE_PFFT &&
    return initial_candidate === nothing ? _initial_candidate(m, code, layout, yparts) : initial_candidate
  profile === _MODE_FRAME_WIDE_LDPC &&
    return initial_candidate === nothing ? _initial_candidate(m, code, layout, yparts) : initial_candidate
  profile === _MODE_COUPLED && return _juna_wcz_candidate(m, code, layout, yparts, initial_candidate)
  profile === _MODE_TURBO_MAP && return _turbo_map_candidate(m, code, layout, yparts, initial_candidate)
  profile === _MODE_GRADIENT_GUARDED &&
    return _gradient_guarded_candidate(m, code, layout, yparts, initial_candidate)
  profile === _MODE_PROFILED_GRADIENT &&
    return _profiled_gradient_candidate(m, code, layout, yparts, initial_candidate)
  profile === _MODE_FULL && return _juna_wz_candidate(m, code, layout, yparts, initial_candidate)
  _juna_lite_candidate(m, code, layout, yparts, initial_candidate)
end

function _initial_candidate(m::Modulation, code::_Code, layout::_Layout, yparts)
  equalized = _equalize_from_targets(m, yparts, layout, layout.pilot_idx, layout.pilot_syms)
  _candidate_from_equalized(m, code, layout, equalized)
end

function _select_front_end_initial_candidate(standard, partial)
  partial.valid && return partial
  standard.valid ? standard : partial
end

function _front_end_initial_candidate(m::Modulation, code::_Code, layout::_Layout, yparts)
  partial = _initial_candidate(m, code, layout, yparts)
  partial.valid && return partial
  _select_front_end_initial_candidate(_standard_candidate(m, code, layout, yparts), partial)
end

function _decode_candidate(m::Modulation, code::_Code, layout::_Layout, equalized, metrics, pilot_mse)
  bp = _bp_decode(m, code, metrics)
  tie_mse = _posterior_tie_mse(m, equalized, layout, bp.lpost_metric)
  syndrome_norm = bp.syndrome / max(size(code.H, 1), 1)
  mean_abs_lpost = mean(abs, bp.lpost_metric)
  score = pilot_mse + 0.25 * tie_mse + 0.05 * syndrome_norm - 1e-4 * mean_abs_lpost
  (
    lpost_metric=bp.lpost_metric,
    valid=bp.valid,
    syndrome=bp.syndrome,
    mean_abs_lpost=mean_abs_lpost,
    pilot_mse=pilot_mse,
    tie_mse=tie_mse,
    score=score,
  )
end

function _bp_check_normalized_min_sum!(out, incoming)
  length(out) == length(incoming) ||
    throw(DimensionMismatch("check-message buffers must have equal length"))
  L = length(incoming)
  L == 0 && return out
  if L == 1
    out[1] = _LLR_CLIP
    return out
  end

  signtot = 1.0
  min1 = Inf
  min2 = Inf
  argmin1 = 0
  @inbounds for a in 1:L
    value = incoming[a]
    signtot *= ifelse(value < 0.0, -1.0, 1.0)
    magnitude = abs(value)
    if magnitude < min1
      min2 = min1
      min1 = magnitude
      argmin1 = a
    elseif magnitude < min2
      min2 = magnitude
    end
  end
  @inbounds for a in 1:L
    sign_without_self = signtot * ifelse(incoming[a] < 0.0, -1.0, 1.0)
    magnitude = a == argmin1 ? min2 : min1
    out[a] = _BP_ALPHA * sign_without_self * magnitude
  end
  out
end

function _bp_check_sum_product!(out, incoming)
  length(out) == length(incoming) ||
    throw(DimensionMismatch("check-message buffers must have equal length"))
  L = length(incoming)
  L == 0 && return out
  if L == 1
    out[1] = _LLR_CLIP
    return out
  end
  limit = tanh(0.5 * _LLR_CLIP)
  @inbounds for a in 1:L
    product = 1.0
    for b in 1:L
      b == a && continue
      product *= tanh(0.5 * clamp(Float64(incoming[b]), -_LLR_CLIP, _LLR_CLIP))
    end
    out[a] = clamp(2atanh(clamp(product, -limit, limit)), -_LLR_CLIP, _LLR_CLIP)
  end
  out
end

# BP over the cached Tanner graph (array-based, no Dicts). The measured receiver
# uses normalized min-sum; the exact sum-product path is retained as a paper
# reference and executable cross-check.
function _bp_decode_impl(m::Modulation, code::_Code, metrics, check_update!;
                         message_block_k::Int=code.k)
  cv = code.check_vars
  ve = code.var_edges
  n = code.n
  bp = _bp_scratch(m, code)
  lch = bp.lch
  lpost = bp.lpost
  bits = bp.bits
  q = bp.q
  r = bp.r

  @inbounds for v in 1:n
    lch[v] = -Float64(metrics[v])               # channel LLR, positive = bit 0
    lpost[v] = lch[v]
    bits[v] = false
  end
  _apply_inner_clamps!(m, code, lch, message_block_k)

  @inbounds for c in eachindex(cv)
    qc = q[c]
    for a in eachindex(qc)
      qc[a] = lch[cv[c][a]]
    end
  end

  syndrome = typemax(Int)
  for _ in 1:_BP_ITERS
    for c in eachindex(cv)
      qc = q[c]
      rc = r[c]
      check_update!(rc, qc)
    end

    for v in 1:n
      total = lch[v]
      for (c, a) in ve[v]
        total += r[c][a]
      end
      lpost[v] = total
      bits[v] = total < 0.0
      for (c, a) in ve[v]
        q[c][a] = total - r[c][a]
      end
    end

    syndrome = _syndrome_weight(code, bits)
    syndrome == 0 && break
  end

  lpost_metric = Vector{Float64}(undef, n)
  @inbounds for v in 1:n
    lpost_metric[v] = -lpost[v]
  end
  (lpost_metric=lpost_metric, valid=syndrome == 0, syndrome=syndrome)
end

_bp_decode(m::Modulation, code::_Code, metrics) =
  _bp_decode_impl(m, code, metrics, _bp_check_normalized_min_sum!)

_bp_decode_sum_product(m::Modulation, code::_Code, metrics) =
  _bp_decode_impl(m, code, metrics, _bp_check_sum_product!)

function _bp_scratch(m::Modulation, code::_Code)::_BPScratch
  sig = (code.k, code.n, code.npc, code.method, code.seed, code.no4cycle)
  m.bp_scratch isa _BPScratch &&
    (m.bp_scratch::_BPScratch).signature == sig &&
    return m.bp_scratch::_BPScratch

  q = [Vector{Float64}(undef, length(vars)) for vars in code.check_vars]
  r = [Vector{Float64}(undef, length(vars)) for vars in code.check_vars]
  m.bp_scratch = _BPScratch(sig, zeros(Float64, code.n), zeros(Float64, code.n),
                            falses(code.n), q, r)
  m.bp_scratch::_BPScratch
end

function _syndrome_weight(code::_Code, bits::AbstractVector{Bool})
  cnt = 0
  for vars in code.check_vars
    s = false
    for v in vars
      s ⊻= bits[v]
    end
    s && (cnt += 1)
  end
  cnt
end

# ----- carrier / pilot geometry -----------------------------------------------

_bpsk_symbol(bit::Bool) = bit ? ComplexF64(-1.0, 0.0) : ComplexF64(1.0, 0.0)

function _branch_observations(m::Modulation, waveform)
  N = Int(m.nc)
  L = Int(m.np)
  yparts = Matrix{ComplexF64}(undef, m.partial_fft_parts, N)
  chunk = zeros(ComplexF64, N)

  for p in 1:m.partial_fft_parts
    lo, hi = _part_bounds(N, m.partial_fft_parts, p)
    fill!(chunk, 0.0 + 0.0im)
    @views chunk[lo:hi] .= waveform[L+lo:L+hi]
    fft!(chunk)
    @views yparts[p, :] .= chunk
  end

  yparts
end

function _equalize_from_targets(m::Modulation, yparts, layout::_Layout, target_idx, targets;
                                target_weights = nothing)
  _validate_target_weights(target_idx, target_weights)
  equalized = zeros(ComplexF64, Int(m.nc))
  P = m.partial_fft_parts
  A = Matrix{ComplexF64}(undef, P, P)
  b = Vector{ComplexF64}(undef, P)
  weights = Vector{ComplexF64}(undef, P)
  target_pos = zeros(Int, Int(m.nc))
  @inbounds for i in eachindex(target_idx)
    target_pos[target_idx[i]] = i
  end
  local_targets = Int[]
  sizehint!(local_targets, length(target_idx))

  for band in layout.bands
    empty!(local_targets)
    @inbounds for k in band
      pos = target_pos[k]
      pos == 0 || push!(local_targets, pos)
    end
    if length(local_targets) < m.partial_fft_parts
      resize!(local_targets, length(target_idx))
      @inbounds for i in eachindex(target_idx)
        local_targets[i] = i
      end
    end
    _fit_branch_weights!(
      weights, A, b, m, yparts, target_idx, targets, local_targets;
      target_weights = target_weights,
    )
    for k in band
      acc = 0.0 + 0.0im
      @inbounds for p in 1:m.partial_fft_parts
        acc += yparts[p, k] * weights[p]
      end
      equalized[k] = acc
    end
  end

  _residual_pilot_equalize(m, layout, equalized)
end

function _fit_branch_weights!(weights::Vector{ComplexF64}, A::Matrix{ComplexF64},
                              b::Vector{ComplexF64}, m::Modulation, yparts,
                              target_idx, targets, positions;
                              target_weights = nothing)
  _validate_target_weights(target_idx, target_weights)
  P = m.partial_fft_parts
  fill!(A, 0.0 + 0.0im)
  fill!(b, 0.0 + 0.0im)
  @inbounds for row in positions
    k = target_idx[row]
    target = ComplexF64(targets[row])
    row_weight = target_weights === nothing ? 1.0 : Float64(target_weights[row])
    for p in 1:P
      yp = yparts[p, k]
      cyp = conj(yp)
      b[p] += row_weight * cyp * target
      for q in 1:P
        A[p, q] += row_weight * cyp * yparts[q, k]
      end
    end
  end
  @inbounds for p in 1:P
    A[p, p] += _RIDGE
  end
  _solve_small!(weights, A, b)
end

function _validate_target_weights(target_idx, target_weights)
  target_weights === nothing && return nothing
  length(target_weights) == length(target_idx) ||
    throw(DimensionMismatch("target weights must match target indices"))
  all(weight -> isfinite(weight) && weight >= 0, target_weights) ||
    throw(ArgumentError("target weights must be finite and nonnegative"))
  nothing
end

function _solve_small!(x::Vector{ComplexF64}, A::Matrix{ComplexF64}, b::Vector{ComplexF64})
  n = length(x)
  copyto!(x, b)
  @inbounds for k in 1:n
    pivot = k
    pivot_abs = abs(A[k, k])
    for i in k+1:n
      cand = abs(A[i, k])
      if cand > pivot_abs
        pivot = i
        pivot_abs = cand
      end
    end
    if pivot != k
      for j in k:n
        A[k, j], A[pivot, j] = A[pivot, j], A[k, j]
      end
      x[k], x[pivot] = x[pivot], x[k]
    end
    akk = A[k, k]
    for i in k+1:n
      factor = A[i, k] / akk
      A[i, k] = 0.0 + 0.0im
      for j in k+1:n
        A[i, j] -= factor * A[k, j]
      end
      x[i] -= factor * x[k]
    end
  end
  @inbounds for i in n:-1:1
    acc = x[i]
    for j in i+1:n
      acc -= A[i, j] * x[j]
    end
    x[i] = acc / A[i, i]
  end
  x
end

function _residual_pilot_equalize(m::Modulation, layout::_Layout, carriers)
  equalized = carriers isa Vector{ComplexF64} ? carriers : ComplexF64.(carriers)
  response = Vector{ComplexF64}(undef, length(layout.pilot_idx))
  @inbounds for i in eachindex(layout.pilot_idx)
    response[i] = equalized[layout.pilot_idx[i]] / layout.pilot_syms[i]
  end
  pilot_positions = [layout.active_rank[k] for k in layout.pilot_idx]
  for k in layout.active
    h = _interp_response(pilot_positions, response, layout.active_rank[k])
    abs(h) > eps(Float64) && (equalized[k] /= h)
  end
  equalized
end

function _sum_branches(yparts)
  P, N = size(yparts)
  carriers = Vector{ComplexF64}(undef, N)
  @inbounds for k in 1:N
    acc = 0.0 + 0.0im
    for p in 1:P
      acc += yparts[p, k]
    end
    carriers[k] = acc
  end
  carriers
end

function _interp_response(pidx, response, k)
  pos = searchsortedlast(pidx, k)
  pos <= 0 && return response[1]
  pos >= length(pidx) && return response[end]
  t = (k - pidx[pos]) / (pidx[pos + 1] - pidx[pos])
  (1 - t) * response[pos] + t * response[pos + 1]
end

function _part_bounds(n::Int, nparts::Int, p::Int)
  base = div(n, nparts)
  extra = rem(n, nparts)
  lo = 1 + (p - 1) * base + min(p - 1, extra)
  hi = lo + base - 1 + (p <= extra ? 1 : 0)
  lo, hi
end

# ----- posterior soft information ---------------------------------------------

# Per-tone posterior-mean constellation points from posterior metrics.
function _posterior_symbols(m::Modulation, lpost_metric)
  if _bpc(m) == 1
    anchors = Vector{ComplexF64}(undef, length(lpost_metric))
    @inbounds for i in eachindex(lpost_metric)
      anchors[i] = ComplexF64(-tanh(0.5 * lpost_metric[i]), 0.0)
    end
    anchors
  else
    ntones = _ndata_tones(m, length(lpost_metric))
    anchors = Vector{ComplexF64}(undef, ntones)
    invsqrt2 = 1 / sqrt(2)
    @inbounds for t in 1:ntones
      base = 2t - 1
      xr = -tanh(0.5 * lpost_metric[base])
      xi = base + 1 <= length(lpost_metric) ? -tanh(0.5 * lpost_metric[base + 1]) : 0.0
      anchors[t] = ComplexF64(xr, xi) * invsqrt2
    end
    anchors
  end
end

# Per-tone confidence: BPSK |xi|, QPSK min(|xi_I|, |xi_Q|).
function _posterior_confidence(m::Modulation, lpost_metric)
  if _bpc(m) == 1
    confidence = Vector{Float64}(undef, length(lpost_metric))
    @inbounds for i in eachindex(lpost_metric)
      confidence[i] = abs(tanh(0.5 * lpost_metric[i]))
    end
    confidence
  else
    ntones = _ndata_tones(m, length(lpost_metric))
    confidence = Vector{Float64}(undef, ntones)
    @inbounds for t in 1:ntones
      base = 2t - 1
      xr = abs(tanh(0.5 * lpost_metric[base]))
      xi = base + 1 <= length(lpost_metric) ? abs(tanh(0.5 * lpost_metric[base + 1])) : xr
      confidence[t] = min(xr, xi)
    end
    confidence
  end
end

function _posterior_tie_mse(m::Modulation, equalized, layout::_Layout, lpost_metric)
  anchors = _posterior_symbols(m, lpost_metric)
  confidence = _posterior_confidence(m, lpost_metric)
  n = min(length(layout.data_idx), length(anchors), length(confidence))
  n == 0 && return Inf
  acc = 0.0
  weight_sum = 0.0
  @inbounds for i in 1:n
    weight = max(confidence[i], 1e-3)
    acc += weight * abs2(equalized[layout.data_idx[i]] - anchors[i])
    weight_sum += weight
  end
  acc / weight_sum
end

function _juna_better(base, candidate)
  candidate.valid != base.valid && return candidate.valid
  candidate.syndrome != base.syndrome && return candidate.syndrome < base.syndrome
  score_margin = 0.005 * max(abs(base.score), eps(Float64))
  candidate.score < base.score - score_margin && return true
  candidate.mean_abs_lpost > 1.01 * base.mean_abs_lpost + 1e-6
end

function _juna_selection_reason(base, candidate)
  candidate.valid != base.valid && return candidate.valid ? :validity : :lite_fallback
  candidate.syndrome != base.syndrome &&
    return candidate.syndrome < base.syndrome ? :syndrome : :lite_fallback
  score_margin = 0.005 * max(abs(base.score), eps(Float64))
  candidate.score < base.score - score_margin && return :score
  candidate.mean_abs_lpost > 1.01 * base.mean_abs_lpost + 1e-6 &&
    return :posterior_magnitude
  :lite_fallback
end
