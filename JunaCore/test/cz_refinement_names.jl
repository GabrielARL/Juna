using Test
using JunaCore

const CzNameJuna = JunaCore.Juna

@testset "JCM-134 through JCM-150 approved names" begin
    expected_ldpc_functions = (
        :_make_ldpc_method_args,
        :_is_nonempty_file,
        :read_generator,
    )
    removed_ldpc_functions = (
        :method_args,
        :_ok,
        :generator,
        :_tool_args,
    )
    expected_receiver_functions = (
        :_bit_to_bipolar,
        :_solve_small_linear_system!,
        :_candidate_is_better,
        :_WzGradientScratch,
        :_juna_wz_adam_refine,
        :_initial_pilot_W,
        :_wz_state_candidate,
        :_wz_symbol_grid!,
        :_parity_penalty_and_bit_gradient!,
        :_wz_loss_and_gradient!,
        :_frame_wz_loss_and_gradient!,
        :_frame_coupled_loss_and_gradient!,
        :_joint_cwz_loss_and_gradient!,
        :_lite_anchor_targets,
        :_lite_refinement_step,
        :_frame_stateful_band_rls_refine,
        :_cz_regularized_mrc_weights!,
        :_cz_update_C_given_z!,
        :_cz_bootstrap_C_anchor,
        :_cz_update_W!,
        :_cz_copy_logits_to_blocks!,
        :_joint_cwz_step_is_accepted,
        :_joint_cw_anchor_penalty!,
        :_cwz_initial_C_ridge_solve!,
        :_cwz_update_C_from_posterior_moments!,
    )
    removed_receiver_functions = (
        :_pm,
        :_solve_small!,
        :_juna_better,
        :_GradientScratch,
        :_juna_wz_gradient_solve,
        :_initial_gradient_W,
        :_gradient_candidate,
        :_gradient_symbol_grid!,
        :_parity_penalty_and_gradx!,
        :_wz_loss_and_grad!,
        :_frame_wz_loss_and_grad!,
        :_frame_coupled_loss_and_grad!,
        :_joint_cwz_loss_and_grad!,
        :_juna_anchor_targets,
        :_juna_step,
        :_frame_juna_refine,
        :_cz_mmse_weights!,
        :_cz_solve_C_given_z!,
        :_cz_pilot_anchor_C,
        :_cz_refit_W!,
        :_cz_sync_logits!,
        :_joint_cwz_accept,
        :_joint_cwz_penalty!,
        :_profile_initial_coupled_C!,
        :_coupled_em_C!,
        :_write_metrics!,
    )
    expected_fields = (
        :fft_length,
        :cyclic_prefix_length,
        :occupied_bandwidth_fraction,
        :rf_center_offset_khz,
        :bits_per_data_carrier,
        :ldpc_checks_per_column,
        :synchronization_enabled,
        :ldpc_eliminate_length_4_cycles,
        :frame_code_component_block_count,
        :joint_cwz_first_w_iteration,
        :cz_temporal_c_penalty_weight,
        :cz_require_crc_for_replacement,
        :cz_crc_gate_at_selection_only,
        :cz_posterior_moment_update_enabled,
        :cz_response_anchor_weight,
        :cz_response_update_fraction,
        :cz_refit_w_from_decoder_posteriors,
        :cz_decoder_posterior_weight,
        :cz_variable_projection_gradient,
        :anchor_feedback_source,
        :transmitted_symbols,
    )
    removed_fields = (
        :nc,
        :np,
        :bw,
        :dc0,
        :bpc,
        :ldpc_npc,
        :sync,
        :ldpc_no4cycle,
        :frame_code_horizon,
        :joint_cwz_w_start,
        :cz_temporal_c_smoothness,
        :cz_crc_gate,
        :cz_gate_selection_only,
        :cz_em_enabled,
        :cz_em_trust,
        :cz_em_damping,
        :cz_independent_w,
        :cz_bp_feedback,
        :cz_vp_gradient,
        :feedback_mode,
        :genie_symbols,
    )

    @test all(name -> isdefined(JunaCore.LDPC, name),
              expected_ldpc_functions)
    @test all(name -> !isdefined(JunaCore.LDPC, name),
              removed_ldpc_functions)
    @test all(name -> isdefined(CzNameJuna, name),
              expected_receiver_functions)
    @test all(name -> !isdefined(CzNameJuna, name),
              removed_receiver_functions)

    modulation_fields = fieldnames(CzNameJuna.Modulation)
    @test all(name -> name in modulation_fields, expected_fields)
    @test all(name -> !(name in modulation_fields), removed_fields)
    @test !(:bp_projection in fieldnames(CzNameJuna._CoupledSolverSpec))
    @test CzNameJuna._FEEDBACK_MODES == (
        :decoder_posterior,
        :pilots_only,
        :transmitted_symbols,
        :corrupted_transmitted_symbols,
    )
    @test CzNameJuna._CZ_FEEDBACK_SOURCES == (
        :initial_logits,
        :decoder_posterior,
        :transmitted_symbols,
    )

    package_root = normpath(joinpath(@__DIR__, ".."))
    experiment_root = joinpath(
        package_root, "experiments", "2026-08-01-red-lite-search")
    @test isfile(joinpath(
        experiment_root, "results", "results_view_data.json"))
    @test !isfile(joinpath(experiment_root, "results", "viewdata.json"))
    @test isfile(joinpath(package_root, "tools", "parity_reference.json"))
    @test !isfile(joinpath(package_root, "tools", "parity_golden.json"))
    @test isfile(joinpath(
        experiment_root, "results_partial_fft",
        "red_config_finalists_20db_seeds6to7.csv"))
    @test !isdir(joinpath(experiment_root, "results_pfft"))
end

@testset "C,z refinement names" begin
    public_modules = (
        :JunaCzRefinement,
        :JunaCrcCzRefinement,
        :JunaCrcJointCwz,
    )
    public_constructors = (
        :CzRefinementModulation,
        :CrcCzRefinementModulation,
        :CrcTurboCwzModulation,
        :CrcJointCwzComparisonModulation,
        :CrcJointCwzModulation,
    )
    private_names = (
        :_MODE_CZ_REFINEMENT,
        :_MODE_CRC_CZ_REFINEMENT,
        :_frame_cz_refine,
        :_cz_update_C_given_z!,
        :_cz_derive_W_from_C!,
        :_cz_update_W!,
        :_joint_cwz_direction,
        :_joint_cwz_step_is_accepted,
        :_joint_cw_anchor_penalty!,
        :_joint_cwz_loss_and_gradient!,
        :_joint_cwz_pilot_loss,
        :_joint_cwz_step!,
        :_cz_refinement_last_trace,
        :_cz_crc_choose_refinement,
    )
    joint_settings = (
        :joint_cwz_enabled,
        :joint_cwz_c_radius,
        :joint_cwz_w_radius,
        :joint_cwz_z_radius,
        :joint_cwz_first_w_iteration,
        :joint_cwz_pilot_tolerance,
    )
    protected_mechanisms = (
        :_MODE_PROFILED_GRADIENT,
        :_MODE_FRAME_WIDE_LDPC,
        :_frame_profiled_gradient_refine,
        :_frame_receiver_trace,
        :_frame_candidate,
        :FrameWideLDPCModulation,
    )

    @test all(name -> isdefined(JunaCore, name), public_modules)
    @test all(name -> isdefined(CzNameJuna, name), public_constructors)
    @test all(name -> isdefined(CzNameJuna, name), private_names)

    ready = all(name -> isdefined(JunaCore, name), public_modules) &&
        all(name -> isdefined(CzNameJuna, name), public_constructors) &&
        all(name -> isdefined(CzNameJuna, name), private_names)
    if ready
        base = JunaCore.JunaCzRefinement.Modulation()
        crc = JunaCore.JunaCrcCzRefinement.Modulation()
        turbo = CzNameJuna.CrcTurboCwzModulation()
        control = CzNameJuna.CrcJointCwzComparisonModulation(
            joint_cwz_enabled=false)
        treatment = CzNameJuna.CrcJointCwzComparisonModulation(
            joint_cwz_enabled=true)
        joint = JunaCore.JunaCrcJointCwz.Modulation()

        @test all(modem -> CzNameJuna.receiver_profile(modem) ===
                    :frame_wide_ldpc,
                  (base, crc, turbo, control, treatment, joint))
        @test base.frame_receiver === :cz_refinement
        @test CzNameJuna.refinement_objective(base) === :cz_refinement
        @test crc.mode === :crc_cz_refinement
        @test crc.frame_crc_bits == 16
        @test crc.cz_posterior_moment_update_enabled
        @test turbo.cz_refit_w_from_decoder_posteriors
        @test turbo.cz_decoder_posterior_weight == 0.5
        @test !control.joint_cwz_enabled
        @test treatment.joint_cwz_enabled
        @test joint.joint_cwz_enabled
        @test all(field -> field in propertynames(joint), joint_settings)
        @test joint.joint_cwz_c_radius == 0.05
        @test joint.joint_cwz_w_radius == 0.01
        @test joint.joint_cwz_z_radius == 0.5
        @test joint.joint_cwz_first_w_iteration == 2
        @test joint.joint_cwz_pilot_tolerance == 0.01
        @test joint.cz_variable_projection_gradient
        @test joint.cz_decoder_posterior_weight == 0.5
        @test :cz_refinement_trace in propertynames(joint)

        differences = Symbol[]
        for field in propertynames(control)
            getproperty(control, field) == getproperty(treatment, field) ||
                push!(differences, field)
        end
        @test differences == [:joint_cwz_enabled]
    end

    expected_files = (
        joinpath("src", "juna", "cz_refinement.jl"),
        joinpath("test", "juna_cz_refinement.jl"),
        joinpath("test", "juna_crc_cz_refinement.jl"),
        joinpath("test", "juna_cz_refinement_dc.jl"),
    )
    expected_suite_keys = (
        "cz-refinement",
        "cz-refinement-crc",
        "cz-refinement-check-degree",
        "cz-refinement-full-dependency",
        "cz-refinement-objective",
        "cz-refinement-initialization",
        "cz-refinement-optimizer",
        "cz-refinement-block-coordinate",
        "cz-refinement-candidate",
        "cz-refinement-end-to-end",
    )
    package_root = normpath(joinpath(@__DIR__, ".."))
    @test all(relative -> isfile(joinpath(package_root, relative)), expected_files)
    registry = read(joinpath(@__DIR__, "runtests.jl"), String)
    @test all(key -> occursin("key = \"$key\"", registry),
              expected_suite_keys)
    @test occursin("receivers = \"receiver:cz_refinement\"", registry)

    old_public_modules = Symbol.((
        "Juna" * "ProfiledCz" * "Frame",
        "JunaCrc" * "ProfiledCz" * "Frame",
        "JunaCrc" * "ConditionedJointCwz" * "Frame",
    ))
    old_public_constructors = Symbol.((
        "ProfiledCz" * "FrameModulation",
        "CrcProfiledCz" * "FrameModulation",
        "CrcTurboCwz" * "FrameModulation",
        "CrcConditionedCwz" * "FrameModulation",
        "CrcConditionedJointCwz" * "FrameModulation",
    ))
    @test all(name -> !isdefined(JunaCore, name), old_public_modules)
    @test all(name -> !isdefined(CzNameJuna, name), old_public_constructors)

    stale_names = (
        "Profiled" * "CzFrame",
        "CrcProfiled" * "CzFrame",
        "Conditioned" * "JointCwzFrame",
        "profiled" * "_cz",
        "profiled" * "-cz",
        "Profiled" * " C,z",
        "cz_" * "conditioned_joint",
        "_cz_" * "conditioned_",
        "conditioned_" * "accepted_steps",
        "conditioned_" * "rejected_steps",
        "conditioned_" * "step_scales",
        "cz_" * "joint_",
        "hand-" * "gradient",
        "manual" * " gradient",
    )
    stale_occurrences = String[]
    for relative_root in ("src", "test", "tools")
        root = joinpath(package_root, relative_root)
        for (directory, _, files) in walkdir(root)
            for file in files
                path = joinpath(directory, file)
                relative = relpath(path, package_root)
                extension = splitext(file)[2]
                extension in (".jl", ".py", ".js", ".json", ".html", ".md") ||
                    continue
                contents = read(path, String)
                for stale in stale_names
                    occursin(stale, relative) &&
                        push!(stale_occurrences, "$relative path: $stale")
                    occursin(stale, contents) &&
                        push!(stale_occurrences, "$relative contents: $stale")
                end
            end
        end
    end
    @test isempty(stale_occurrences)

    @test all(name -> isdefined(CzNameJuna, name), protected_mechanisms)
    profiled_gradient = CzNameJuna.Modulation(
        mode=:frame_wide_ldpc, frame_receiver=:profiled_gradient)
    @test profiled_gradient.frame_receiver === :profiled_gradient
    @test :profiled_gradient_trace in propertynames(profiled_gradient)
    @test CzNameJuna.FrameWideLDPCModulation().mode === :frame_wide_ldpc
    generic_frame = CzNameJuna.FrameWideLDPCModulation()
    @test all(field -> field in propertynames(generic_frame),
              (:frame_receiver, :frame_crc_bits,
               :frame_code_component_block_count,
               :frame_duration_s))
end
