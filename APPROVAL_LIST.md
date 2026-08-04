# Approval register

Every item needing the user's decision is recorded here with a stable
identifier. Read this file before proposing anything, so settled questions are
not reopened.

This is Juna's register. It is governed by `SOP_HUMAN_AI_COWORK.md`.

- One identifier records one decision.
- Identifiers are never reused.
- A rejected item keeps its identifier.
- Silence is not approval.

Next free Juna identifier: **JCM-152**. JCM-126 through JCM-133 remain
reserved and unapproved.

Next free Claude identifier: **CL-21**. The former spoken labels CL-22
through CL-27 are provenance only; their decisions are recorded without
collision as JCM-097 through JCM-102.

The earlier D sequence still has a gap. D6 to D12 were approved in another
session but were never recorded. They remain reserved and must not be reused.

## Earlier decisions

| ID | State | Item. |
|---|---|---|
| D1 | approved | File name `SOP_HUMAN_AI_COWORK.md`. |
| D2 | approved | One `D` prefix for the earlier shared sequence. |
| D3 | approved | The register lives in its own file. |
| D4 | superseded by JCM-004 | The earlier requirement that the Juna and Sonique procedures match. |
| D5a | rejected | File name `DECISIONS.md`. |
| D5b | rejected | File name `NAMES_AND_DECISIONS.md`. |
| D5c | approved | File name `APPROVAL_LIST.md`. |
| D5d | rejected | File name `APPROVALS.md`. |

## Juna decisions

| ID | State | Decision. |
|---|---|---|
| JCM-001 | approved | Keep the current root `AGENTS.md` rules. |
| JCM-002 | approved | Use the cowork procedure as Juna's local procedure after correcting its stale D4 statement and mechanical findings. |
| JCM-003 | approved | Create this Juna-local approval register and preserve the unresolved D6 to D12 gap. |
| JCM-004 | approved | Juna is a separate entity. Keep historical Sonique attribution, but remove every requirement for Juna files or receiver results to match Sonique. |
| JCM-005 | approved | Keep the five files under `reference papers/chitre_first_author/` as the house-style evidence set. |
| JCM-006 | approved | Keep the updated mechanical style checker. It does not verify technical truth, vocabulary sources, or human approval. |
| JCM-007 | approved | Replace unexplained `RPC` with `Partial-FFT combining` in `JUNA_vs_RPC.tex`. |
| JCM-008 | approved | Replace `JUNA score` with the code-facing name `candidate score` in the adaptive-modulation note. |
| JCM-009 | approved | Use `receiver refinement` in place of the clustered-adaptation note's `self-calibrating receiver` wording. |
| JCM-010 | approved | Use `Interference in Part of the Band` as the partial-band-interference note's reader title. |
| JCM-011 | approved | Rewrite the Partial-FFT-demodulation note with the Mandar skill. |
| JCM-012 | approved | Rewrite the progressive-ICI-equalization note with the Mandar skill. |
| JCM-013 | approved | Rewrite only the style of the sparse-channel-estimation note with the Mandar skill. |
| JCM-014 | approved | Match each `tanh(z)` or `tanh(z/2)` equation to its actual code path in the manual-gradient plan. |
| JCM-015 | approved | Rewrite `joe.tex` with the Mandar skill and check its equations against the code. |
| JCM-016 | approved | Rewrite the implementation specification in receiver execution order, using code and source vocabulary while preserving its technical content. |
| JCM-017 | approved | Add `manual_gradient_ofdm_paper_concepts_chitre.tex` after correcting its six long sentences. |
| JCM-018 | approved | Keep the active expanded JUNA-Lite paper, correct its mechanical findings, and resolve its three citations. |
| JCM-019 | approved | Keep the new top-level `docs/` directory. |
| JCM-020 | approved | Keep the cowork deck source and its approved title and slide titles. |
| JCM-021 | approved | Track the cowork deck PDF generated from the approved source. |
| JCM-022 | approved | Exclude downloaded papers, build files, backups, duplicate root deck files, and other generated output from the merge. |
| JCM-023 | approved | Keep the Claude writing and governance work separate from existing Juna source and Explorer changes. |
| JCM-024 | approved | Do not merge until both Explorer contracts pass. |
| JCM-025 | approved | After scoped commits and passing checks, a human may merge while preserving Claude's eight commits. Agents do not perform the merge. |
| JCM-026 | rejected | User: "ignore". |
| JCM-027 | approved | Add `paper_note_style.tex` using presentation definitions from an approved existing deck, then review and build all eight dependent sources. User: "027a". A reconstructed version builds all eight sources in the dirty primary worktree; repository integration remains pending under JCM-083. |
| JCM-028 | approved | Keep the documents affected by unresolved JCM-026 and JCM-027 out of the current merge scope. |
| JCM-029 | approved | Prepare explicit-path local commits for the approved merge scope; do not merge or push. |
| JCM-030 | approved | Keep the `milica` writing skill and its evidence set under `reference papers/stojanovic_ofdm/`. Approved; the repository skill and evidence files remain pending for a separate reviewed integration under JCM-083. |
| JCM-031 | approved | Use `combiner weights` for the `M` weights that combine the partial-FFT outputs of one carrier. Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-032 | approved | Use `branch` for a single partial-FFT output. Historical approval superseded by JCM-052 before repository integration; do not apply `branch` in reader prose. |
| JCM-033 | approved | Use `branch count` for `M`. Historical approval superseded by JCM-052 before repository integration; do not apply `branch count` in reader prose. |
| JCM-034 | approved | Use `partial-FFT combining` in place of `ratio combining`, reusing the JCM-007 wording in a new position. Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-035 | approved | Keep `pre-decoder soft symbol`. No edit required. |
| JCM-036 | approved | Use `anchor` for decoded data reused as training. Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-037 | approved | Use `residual Doppler factor` and `carrier frequency offset`; keep the symbols `a` and `\theta` unchanged. Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-038 | approved | Use `initial resampling` in place of `coarse Doppler correction`. Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-039 | approved | Use `ICI` for both, with `ICI coefficient` for the single entry. Approved; the affected document files remain pending for reconciliation with JCM-053 and JCM-054 under JCM-083. |
| JCM-040 | approved | Create the user-global Codex skill at `/home/gabiel/.codex/skills/wushuangshuang/`. This records the user's approval of the skill decision originally presented as the colliding JCM-031. |
| JCM-041 | approved | Use `references/terminology.md` for the detailed, page-sourced terminology inventory. This records the user's approval of the skill decision originally presented as the colliding JCM-032. |
| JCM-042 | approved | Let the 2025 journal paper govern terminology conflicts while retaining the 2022 and 2021 variants. This records the user's approval of the skill decision originally presented as the colliding JCM-033. |
| JCM-043 | approved | Use the Wu skill for OFDM tuning terminology and technical reasoning while `mandar` continues to govern Juna prose style. This records the user's approval of the skill decision originally presented as the colliding JCM-034. |
| JCM-044 | rejected | Use only the three first-author papers as the primary corpus and keep the 2023 thesis outside the core inventory. This records the user's rejection of the skill decision originally presented as the colliding JCM-035. |
| JCM-045 | rejected | User: "ignore". `joe.tex` keeps `N_{\rm view}` and `V` unchanged; the prose in that file keeps `views`. No edit made. |
| JCM-046 | approved | Replace `leakage` with `ICI coefficient` only where carriers are meant; leave the inter-symbol uses to JCM-053 and JCM-054. User: "046a". Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-047 | approved | Use `decoder feedback` where the sense is otherwise bare; leave the experiment-arm names `fixed-feedback control` and `corrupted feedback controls` unchanged. Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-048 | approved | Keep `mode` in the adaptive-modulation note. The note summarises Wan et al. 2015, so importing Wu's `MCS` would name it with a term its cited paper does not use. No edit required. |
| JCM-049 | rejected | User: "ignore". The rename candidate JCM-049d was not taken; the later removal of `adaptive-lite` is governed separately by JCM-055. |
| JCM-050 | rejected | User: "ignore". `front end` stays unagreed and keeps its three current senses. No name adopted. |
| JCM-051 | approved | Keep the rebuilt results page and its generator, `results/build_view.py` and `results/view_template.html`. User: "yes". |
| JCM-052 | approved | Use `partial-FFT view` for one raw `Y_{k,m}` and `number of partial-FFT views` for `M`. This supersedes JCM-032 and JCM-033 in prose without renaming code identifiers. User: "052d". Applied in the surviving Explorer descriptions; the affected document files remain pending for reconciliation under JCM-083. |
| JCM-053 | approved | Use `OFDM symbol` for the indexed transmission unit. Use `ICI` and `ICI coefficient` for same-symbol off-diagonal carrier coupling, and `intersymbol interference (ISI)` for cross-symbol coupling. An insufficient cyclic prefix may produce both classes. User: "approve JCM-053a". Approved; the affected document files remain pending for a separate reviewed integration under JCM-083. |
| JCM-054 | approved | Put the compact JCM-053a criterion in `joe.tex`, reserve the full teaching derivation for the long Doppler/ICI tutorial, and leave JUNA-Lite with an adequate-prefix scope statement. User: "approve write it in". Approved; the three reader sources remain pending for a separate reviewed integration under JCM-083. |
| JCM-055 | approved | Remove the adaptive-lite receiver. User: "just remove this from the code and from the explorer ui". Deleted from `common.jl` and `frame_wide_ldpc.jl` with its pilot cross-validation guard, from `test/`, from `chain.json`, the regenerated `suites.json` and the symbol explorer, and from the results page including the winner-chart rings. The two pinned source hashes were updated in the same change, as `source_file_check.jl` requires. Its rows stay in the search CSVs as the record of the run. |
| JCM-056 | approved | Show only the 60-frame confirmation stage on the results page. User: "only retain 1 state, 60 frame state. remove all other from the code and ui". The Stage control and the Stage column are gone and the 20-frame screening CSVs are no longer loaded. This is 288 rows rather than 13,173; the screening CSVs remain on disk. |
| JCM-057 | approved | Resolve the three Explorer merge conflicts by keeping the reviewed `agent/merge-prep` versions of `server.py`, `server_contract.py`, and `source.js`. This is the approved Explorer decision originally recorded as JCM-030 in the merged register; it was moved here because the current register already used JCM-030 for `milica`. |
| JCM-058 | approved | Organize the results workspace into five views: `Summary`, `Search landscape`, `Factor analysis`, `Configurations`, and `Reading guide`. Use shared data, persistent navigation, and URL state without omitting current information. |
| JCM-059 | approved | Keep the confirmation-only scope from JCM-056 and do not add a Stage control. Make each displayed filter affect every result where that filter is shown. |
| JCM-060 | approved | Add click- or tap-pinned details, keyboard navigation, accessible sorting, row details, and filtered-data download. |
| JCM-061 | approved | Add a stable experiment ID and a completeness manifest with source hashes, row counts, schema, and an exact-value policy. Preserve exact source values in data and downloads; display rounding is presentation only. |
| JCM-062 | approved | Add a `Path dossier` showing the selected winner's geometry, other finalists, Partial FFT comparison, configurations, and factor sensitivity. |
| JCM-063 | approved | Rename the reader-facing `Path dossier` to `Selected channel and hydrophone`, and replace the Results page's other reader-facing `path` wording with explicit channel-and-hydrophone wording. User: "do a rename". Internal code identifiers remain unchanged. |
| JCM-064 | approved | Remove `phase`, `start_index`, `K (horizon)`, `seed`, `frames`, `frame_blocks`, `payload_bits`, and `bit_errors` from the main Configurations table. Retain them in Details and downloads so no source information is omitted. User: "remove phase, start index ... remove K, seed frames, frame_blocks ... remove payload bits, bit errors". |
| JCM-065 | approved | Display the receiver source value `standard` as `OFDM+FEC` throughout the Results page while retaining the source identifier in Details and downloads. User: "receiver change to OFDM+FEC". |
| JCM-066 | approved | Display `outer_spacing` as `outer pilot ratio` and `inner_spacing` as `inner pilot ratio`, while retaining the source column names in Details and downloads. User: "inner spacing to inner pilot ratio, and outer pilot ratio". |
| JCM-067 | approved | Put PSR in the first Configurations column and BER in the second; move the Details action to the end of each row. User: "psr move to first column ... BER move to second column". |
| JCM-068 | approved | Remove both reader-visible `Unregistered experiment output` notices. Keep access to the completeness manifest in the Reading guide. User: "remove un" beside the displayed notice. |
| JCM-069 | approved | Use the technically correct reader-facing name `OFDM+FEC`, not the transposed spelling `ODFM+FEC`. User: "069a - approve". |
| JCM-070 | approved | Use `ofdm_fec` as the canonical machine identifier, with `OFDMFECModulation`, `JunaOFDMFEC`, `_MODE_OFDM_FEC`, and `_ofdm_fec_candidate` as the corresponding Julia names. Rename the documented chain stage without changing receiver processing. User: "070a - ofdm_fec is fine". |
| JCM-071 | approved | Make the `ofdm_fec` migration backward compatible. Keep the former `:standard`, `StandardModulation`, `JunaStandard`, `_standard_candidate`, result-field, and query forms as compatibility aliases while using the new names canonically. User: "071a - make it backward compatible". |
| JCM-072 | approved | Make the three-panel page the main `Source` route, scan the full source on every reload, preserve compatibility routes, and remove no information. User: "continue". |
| JCM-073 | approved | Use `Types and interface methods`. User: "continue". |
| JCM-074 | approved | Use `Receiver stages`. User: "continue". |
| JCM-075 | approved | Use `Static calls`. User: "continue". |
| JCM-076 | approved | Use `Public interface`. User: "continue". |
| JCM-077 | approved | Use `Modulation fields`. User: "continue". |
| JCM-078 | approved | Restore the complete CRC, turbo, and conditioned C,z receiver family, including its required implementation closure and tests. User: "078b". |
| JCM-079 | approved | Expose the restored receiver family through JunaCore and the Explorer; update its facade, receiver catalog, Source graph, chain evidence, and contracts together. User: "079a". |
| JCM-080 | approved | Use `Profiled C,z` as the reader-facing name. Keep the existing source identifiers unless a separate rename is approved. User: "080a". |
| JCM-081 | approved | Create one scoped Results, receiver, and Explorer commit on `agent/results-workspace`, then prepare human-only fast-forward merges into `human/merge-review` and `main`. Do not merge the already-integrated Claude branch again. User: "81a". |
| JCM-082 | approved | Track the minimal self-contained Results bundle: the generator, template, rendered page, manifest, view data, and the two 60-frame finalist CSV inputs. Leave the 20-frame screening files and other unused experiment outputs local. User: "082A". |
| JCM-083 | approved | Keep this merge focused. Repository-backed portions of JCM-027, JCM-030, and JCM-031 through JCM-054 remain pending separate reviewed integration; JCM-040 through JCM-043 remain applied globally, and settled no-edit and rejected decisions remain unchanged. User: "083A". |
| JCM-084 | approved | Remove absent Rpchan and receiver-function entries from the reader-facing Receiver stages walkthrough so it describes only the current source. User: "084A". |
| JCM-086 | approved | Use `JunaCore explorer` for the application title, page heading, startup message, and contract descriptions. User: "I approve all changes you propose". |
| JCM-087 | approved | Import all seven portable Sonique regression tests for the restored `full.jl` and `coupled.jl` closure, preserving assertions while adapting obsolete reader-visible labels to the approved `Profiled C,z` family name. User: "087a". |
| JCM-088 | approved | Do not add ForwardDiff or the three automatic-differentiation test files; retain the existing finite-difference coverage. User: "088b". |
| JCM-089 | approved | Attach the imported module tests to the existing `Profiled C,z` Explorer family across Tests, Coverage, Chain, and Source; do not create public Full or Coupled receiver entries. User: "089a". |
| JCM-090 | approved | After validation, restart the permanent port 8772 Explorer from the `profiled-cz-restore` worktree and verify its live APIs. User: "090a". |
| JCM-091 | approved | Commit the validated Profiled C,z restoration on `agent/profiled-cz-restore`, including its implementation, public facades, regression tests, Explorer integration, contracts, parity evidence, generated data, and approval record. User: "091a". |
| JCM-092 | approved | Push `agent/profiled-cz-restore` to the confirmed `origin` at `https://github.com/GabrielARL/Juna.git` so another computer can clone this exact committed copy. User: "092a". |
| JCM-093 | approved | Repair stale `source_symbol_explorer.py` references by removing absent facade modules, dead functions, the nonexistent `sync_profile` field, and `:rpchan` entries. Formerly recorded as JCM-057 on `agent/integrate-source-graph`; re-recorded under CL-20 because reconciled JCM-057 names a different approved decision. User: "I approve all." |
| JCM-094 | approved | Record the then-approved application of JCM-032's `branch` wording in the Explorer. Formerly recorded as JCM-058 on `agent/integrate-source-graph`; re-recorded under CL-20 and subsequently superseded for current reader prose by JCM-052's `partial-FFT view` wording. User: "I approve all." |
| JCM-095 | approved | Present Source files as a reload-rescanned `Kind` / `Count` / `What it is` table whose values come from the analyzer. Formerly recorded as JCM-059 on `agent/integrate-source-graph`; re-recorded under CL-20 because reconciled JCM-059 names a different approved decision. User: "I approve all." |
| JCM-096 | approved | Name the checked source files in the reader introduction generated from `test/runtests.jl`. Formerly recorded as JCM-060 on `agent/integrate-source-graph`; re-recorded under CL-20 because reconciled JCM-060 names a different approved decision. User: "I approve all." |
| JCM-097 | approved | Use `hydrophone` in reader-facing wording for the receiving element; retain `lane` only where it is an existing source field or code identifier and explain it at that point. This re-records the former spoken CL-22 decision. User: "I approve all." |
| JCM-098 | approved | Include the `:pfft` receiver arm in the shared public-interface execution check and retain that arm during reconciliation. This re-records the former spoken CL-23 decision. User: "I approve all." |
| JCM-099 | approved | Keep the three Gabriel2 reader rules: explain the observable operation first; use one reader-facing term for one meaning; state each requirement once and identify its test. Keep the closing test: if a reader must guess what a term means, the wording is not finished. This re-records the former spoken Gabriel2 decision. User: "I approve all." |
| JCM-100 | approved | Apply the reader layer to terminal list output, CLI title matching, and `Pkg.test` titles while retaining technical titles in Technical details. This re-records the former spoken terminal-title decision and supersedes the colliding CL-24a record. User: "I approve all." |
| JCM-101 | approved | Use `search` instead of `sweep` in reader-facing test wording; retain an existing code identifier only where changing it would alter the implementation interface. This re-records the former spoken search-wording decision. User: "I approve all." |
| JCM-102 | approved | During reconciliation, keep the twelve approved reader-facing test titles from `agent/integrate-source-graph`, including `Each receiver recovers its own clean test bits`, `Every receiver sends and recovers test bits`, and `Standard, Partial FFT, and JUNA-Lite provide the same operations`; do not restore conformity's interim titles such as `Clean transmission and recovery`. Preserve the restored four-receiver implementation and its additional Profiled C,z suites. This re-records the former spoken test-title decision. User: "I approve all." |
| JCM-103 | open | Decide which Mandar checker governs document completion: (a) the global Codex checker, (b) the repository checker, or (c) require both copies to be identical before either governs. On the conformity `joe.tex`, both return `OK`, while `--list-terms` reports 229 and 227 terms; the only inventory difference is the synthetic checker placeholders `BLOCK` and `MATH`. Neither checker verifies vocabulary provenance, coined terminology, or prior agreement. |
| JCM-104 | approved | Use `Profiled C,z combiner weights and zero-update result` for `profiled-cz` in both title layers. This records 28-1 with the approved `combiner weights` wording. User: "you do all the changes". |
| JCM-105 | approved | Use `Profiled C,z CRC, turbo, and conditioned forms` for `profiled-cz-crc` in both title layers. This records 28-2. User: "you do all the changes". |
| JCM-106 | approved | Use `Profiled C,z under three code settings` for `profiled-cz-check-degree` in both title layers. This records 28-3. User: "you do all the changes". |
| JCM-107 | approved | Use `Profiled C,z response and combining updates` for `wcz-solves` in both title layers. This records 28-4. User: "you do all the changes". |
| JCM-108 | approved | Use `Profiled C,z W,z calculations` for `profiled-cz-full-dependency` in both title layers. This records 28-5 without the unexplained word `shared`. User: "you do all the changes". |
| JCM-109 | approved | Use `Profiled C,z objective and gradient checks` for `profiled-cz-objective` in both title layers. This records 28-6. User: "you do all the changes". |
| JCM-110 | approved | Use `Profiled C,z starting values` for `profiled-cz-initialization` in both title layers. This records 28-7. User: "you do all the changes". |
| JCM-111 | approved | Use `Profiled C,z conditional updates and rollback` for `profiled-cz-optimizer` in both title layers. This records 28-8. User: "you do all the changes". |
| JCM-112 | approved | Use `Profiled C,z update cycles` for `profiled-cz-block-coordinate` in both title layers. This records 28-9. User: "you do all the changes". |
| JCM-113 | approved | Use `Profiled C,z candidate selection` for `profiled-cz-candidate` in both title layers. This records 28-10. User: "you do all the changes". |
| JCM-114 | approved | Use `Profiled C,z clean and impaired receiver checks` for `profiled-cz-end-to-end` in both title layers; do not imply error-free recovery for every noisy case. This records 28-11. User: "you do all the changes". |
| JCM-115 | approved | Use `JunaCrcJointCwz` as the canonical public facade name for the CRC-bearing joint C,W,z form. Omit `Frame` because it no longer distinguishes this receiver family. Compatibility treatment of `JunaCrcConditionedJointCwzFrame` remains a separate decision. User: "all approve". |
| JCM-116 | approved | Use `C,z refinement` as the reader-facing family name in place of `Profiled C,z`. This supersedes the reader-facing wording in JCM-080 without renaming its source identifiers; dependent exact title changes remain separate decisions. User: "all approve". |
| JCM-117 | approved | Use `analytical gradient`, not `manual gradient`, in reader explanations of this implementation. User: "yes, analytical gradient", followed by "all approve". |
| JCM-118 | approved | Rename the base public facade and constructor to `JunaCzRefinement` and `CzRefinementModulation`; remove the old `JunaProfiledCzFrame` and `ProfiledCzFrameModulation` spellings. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-119 | approved | Rename the CRC public facade and constructor to `JunaCrcCzRefinement` and `CrcCzRefinementModulation`; remove the old `JunaCrcProfiledCzFrame` and `CrcProfiledCzFrameModulation` spellings. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-120 | approved | Use `CrcTurboCwzModulation`, `CrcJointCwzComparisonModulation`, and `CrcJointCwzModulation` for the remaining public family constructors. These names remove redundant `Frame` and replace the experiment label `Conditioned` with the implemented joint C,W,z distinction. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-121 | approved | Use the `cz_refinement` stem for the family mode, receiver identity, objective, source and test filenames, suite selectors, Explorer routes, parity key, and family-specific helper names. Remove the corresponding `profiled_cz` and `profiled-cz` spellings rather than keeping compatibility aliases. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-122 | approved | Use the `joint_cwz` stem for the joint-update Boolean, radii, start and tolerance settings, helper functions, local variables, and trace fields. Remove the corresponding family-specific `conditioned` spellings. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-123 | approved | Rename family-specific conditional-solve helpers to state their operations: `_cz_solve_C_given_z!`, `_cz_derive_W_from_C!`, and `_cz_refit_W!`. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-124 | approved | Rename the family result trace and candidate fields from `gradient` to `refinement` where they identify a selected receiver result; retain `gradient` where it denotes the analytical derivative itself. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-125 | approved | Apply `C,z refinement` and `analytical gradient` to all current reader-facing suite, Explorer, and source explanations for this family; retain generic complete-frame terms and the separate Profiled Gradient receiver because they name different mechanisms. User: "update all modules, the code, the variable names, the function names, etc". |
| JCM-134a | approved | Rename `method_args` to `_make_ldpc_method_args`. User: "JCM134 - 150 all approve". |
| JCM-134b | approved | Rename `_ok` to `_is_nonempty_file`. User: "JCM134 - 150 all approve". |
| JCM-134c | approved | Rename the exported LDPC parser `generator` to `read_generator`. User: "JCM134 - 150 all approve". |
| JCM-134d | approved | Rename `_pm` to `_bit_to_bipolar`. User: "JCM134 - 150 all approve". |
| JCM-134e | approved | Rename `_solve_small!` to `_solve_small_linear_system!`. User: "JCM134 - 150 all approve". |
| JCM-134f | approved | Rename `_juna_better` to `_candidate_is_better`. User: "JCM134 - 150 all approve". |
| JCM-135a | approved | Rename `_GradientScratch` to `_WzGradientScratch`. User: "JCM134 - 150 all approve". |
| JCM-135b | approved | Rename the scratch field `S` to `symbols`. User: "JCM134 - 150 all approve". |
| JCM-135c | approved | Rename the scratch field `xbit` to `relaxed_bits`. User: "JCM134 - 150 all approve". |
| JCM-135d | approved | Rename the scratch field `gS` to `symbol_gradient`. User: "JCM134 - 150 all approve". |
| JCM-135e | approved | Rename the scratch field `gradx` to `bit_gradient`. User: "JCM134 - 150 all approve". |
| JCM-135f | approved | Rename `_juna_wz_gradient_solve` to `_juna_wz_adam_refine`. User: "JCM134 - 150 all approve". |
| JCM-135g | approved | Rename `_initial_gradient_W` to `_initial_pilot_W`. User: "JCM134 - 150 all approve". |
| JCM-135h | approved | Rename `_gradient_candidate` to `_wz_state_candidate`. User: "JCM134 - 150 all approve". |
| JCM-135i | approved | Rename `_gradient_symbol_grid!` to `_wz_symbol_grid!`. User: "JCM134 - 150 all approve". |
| JCM-135j | approved | Rename `_parity_penalty_and_gradx!` to `_parity_penalty_and_bit_gradient!`. User: "JCM134 - 150 all approve". |
| JCM-136a | approved | Rename `_juna_anchor_targets` to `_lite_anchor_targets`. User: "JCM134 - 150 all approve". |
| JCM-136b | approved | Rename `_juna_step` to `_lite_refinement_step`. User: "JCM134 - 150 all approve". |
| JCM-136c | approved | Rename `_frame_juna_refine` to `_frame_stateful_band_rls_refine`. User: "JCM134 - 150 all approve". |
| JCM-137a | approved | Rename `_cz_mmse_weights!` to `_cz_regularized_mrc_weights!`. User: "JCM134 - 150 all approve". |
| JCM-137b | approved | Rename `_cz_solve_C_given_z!` to `_cz_update_C_given_z!`. User: "JCM134 - 150 all approve". |
| JCM-137c | approved | Rename `_cz_pilot_anchor_C` to `_cz_bootstrap_C_anchor`. User: "JCM134 - 150 all approve". |
| JCM-137d | approved | Rename `_cz_refit_W!` to `_cz_update_W!`. User: "JCM134 - 150 all approve". |
| JCM-137e | approved | Rename `_cz_sync_logits!` to `_cz_copy_logits_to_blocks!`. User: "JCM134 - 150 all approve". |
| JCM-138a | approved | Rename `_joint_cwz_accept` to `_joint_cwz_step_is_accepted`. User: "JCM134 - 150 all approve". |
| JCM-138b | approved | Rename `_joint_cwz_penalty!` to `_joint_cw_anchor_penalty!`. User: "JCM134 - 150 all approve". |
| JCM-138c | approved | Spell out `gradient` in `_wz_loss_and_gradient!`, `_frame_wz_loss_and_gradient!`, `_frame_coupled_loss_and_gradient!`, and `_joint_cwz_loss_and_gradient!`. User: "JCM134 - 150 all approve". |
| JCM-139a | approved | Rename `_profile_initial_coupled_C!` to `_cwz_initial_C_ridge_solve!`. User: "JCM134 - 150 all approve". |
| JCM-139b | approved | Rename `_coupled_em_C!` to `_cwz_update_C_from_posterior_moments!`. User: "JCM134 - 150 all approve". |
| JCM-140a | approved | Rename the public modulation field `nc` to `fft_length`. User: "JCM134 - 150 all approve". |
| JCM-140b | approved | Rename the public modulation field `np` to `cyclic_prefix_length`. User: "JCM134 - 150 all approve". |
| JCM-140c | approved | Rename the public modulation field `bw` to `occupied_bandwidth_fraction`. User: "JCM134 - 150 all approve". |
| JCM-140d | approved | Rename the public modulation field `dc0` to `rf_center_offset_khz`. User: "JCM134 - 150 all approve". |
| JCM-140e | approved | Rename the public modulation field `bpc` to `bits_per_data_carrier`. User: "JCM134 - 150 all approve". |
| JCM-140f | approved | Rename the public modulation field `ldpc_npc` to `ldpc_checks_per_column`. User: "JCM134 - 150 all approve". |
| JCM-141a | approved | Rename the public modulation field `sync` to `synchronization_enabled`. User: "JCM134 - 150 all approve". |
| JCM-141b | approved | Rename the public modulation field `ldpc_no4cycle` to `ldpc_eliminate_length_4_cycles`. User: "JCM134 - 150 all approve". |
| JCM-141c | approved | Rename the public modulation field `frame_code_horizon` to `frame_code_component_block_count`. User: "JCM134 - 150 all approve". |
| JCM-141d | approved | Rename the public modulation field `joint_cwz_w_start` to `joint_cwz_first_w_iteration`. User: "JCM134 - 150 all approve". |
| JCM-141e | approved | Rename the public modulation field `cz_temporal_c_smoothness` to `cz_temporal_c_penalty_weight`. User: "JCM134 - 150 all approve". |
| JCM-142a | approved | Rename `cz_crc_gate` to `cz_require_crc_for_replacement`. User: "JCM134 - 150 all approve". |
| JCM-142b | approved | Rename `cz_gate_selection_only` to `cz_crc_gate_at_selection_only`. User: "JCM134 - 150 all approve". |
| JCM-142c | approved | Rename `cz_em_enabled` to `cz_posterior_moment_update_enabled`. User: "JCM134 - 150 all approve". |
| JCM-142d | approved | Rename `cz_em_trust` to `cz_response_anchor_weight`. User: "JCM134 - 150 all approve". |
| JCM-142e | approved | Rename `cz_em_damping` to `cz_response_update_fraction`. User: "JCM134 - 150 all approve". |
| JCM-142f | approved | Rename `cz_independent_w` to `cz_refit_w_from_decoder_posteriors`. User: "JCM134 - 150 all approve". |
| JCM-142g | approved | Rename `cz_bp_feedback` to `cz_decoder_posterior_weight`. User: "JCM134 - 150 all approve". |
| JCM-142h | approved | Rename `cz_vp_gradient` to `cz_variable_projection_gradient`. User: "JCM134 - 150 all approve". |
| JCM-143a | approved | Rename `feedback_mode` to `anchor_feedback_source`. User: "JCM134 - 150 all approve". |
| JCM-143b | approved | Use `:decoder_posterior`, `:pilots_only`, `:transmitted_symbols`, and `:corrupted_transmitted_symbols` as the anchor-feedback source values. User: "JCM134 - 150 all approve". |
| JCM-143c | approved | Rename `genie_symbols` to `transmitted_symbols`. User: "JCM134 - 150 all approve". |
| JCM-143d | approved | Use `:initial_logits`, `:decoder_posterior`, and `:transmitted_symbols` as the C,z feedback-source values. User: "JCM134 - 150 all approve". |
| JCM-144a | approved | Use the exact candidate keys `posterior_metric`, `ldpc_valid`, `syndrome_weight`, `mean_absolute_posterior_metric`, `pilot_mse`, `tie_mse`, and `selection_score`. User: "JCM134 - 150 all approve". |
| JCM-144b | approved | Rename `selected_iter` to `selected_iteration`. User: "JCM134 - 150 all approve". |
| JCM-144c | approved | Rename the `demodulate_methods` result key `provenance` to `receiver_profile`. User: "JCM134 - 150 all approve". |
| JCM-144d | approved | Rename the `demodulate_methods` result key `juna` to `selected_receiver`. User: "JCM134 - 150 all approve". |
| JCM-145a | approved | Replace `optimized_variables` with `configured_update_variables`, add `executed_update_variables`, and add `refinement_executed`. User: "JCM134 - 150 all approve". |
| JCM-145b | approved | Always expose `baseline`; use `refinement=nothing` when no refinement executes and expose the refinement result when it does. User: "JCM134 - 150 all approve". |
| JCM-145c | approved | Expose separate `lite_ldpc_valid` and `refinement_ldpc_valid` values, and use `nothing` for CRC validity when CRC is disabled. User: "JCM134 - 150 all approve". |
| JCM-145d | approved | Use `selection_gate=:candidate_order` for ordinary candidate ordering and retain `selection_gate=:crc` for CRC gating. User: "JCM134 - 150 all approve". |
| JCM-145e | approved | Use `crc_replacement_gate_enabled`, `baseline_allows_early_skip`, and `:initial_response` in the C,z refinement implementation. User: "JCM134 - 150 all approve". |
| JCM-146a | approved | Rename complete-frame `block_n` variables to `coded_bits_per_block`. User: "JCM134 - 150 all approve". |
| JCM-146b | approved | Rename the coupled-problem `active2` variable to `active_indices`. User: "JCM134 - 150 all approve". |
| JCM-146c | approved | Rename the coupled-problem coded-bit count `nbits2` to `coded_bit_count`; payload-bit uses of `nbits2` are not part of this decision. User: "JCM134 - 150 all approve". |
| JCM-147a | approved | Delete the unused `_tool_args`. User: "JCM134 - 150 all approve". |
| JCM-147b | approved | Delete the unused `_write_metrics!`; retain `_write_payload_metrics!`. User: "JCM134 - 150 all approve". |
| JCM-147c | approved | Delete `_CoupledSolverSpec.bp_projection` and its validation and test handling. User: "JCM134 - 150 all approve". |
| JCM-148a | approved | Rename `results/viewdata.json` to `results/results_view_data.json`. User: "JCM134 - 150 all approve". |
| JCM-148b | approved | Rename `tools/parity_golden.json` to `tools/parity_reference.json`. User: "JCM134 - 150 all approve". |
| JCM-148c | approved | Rename the experiment directory `results_pfft` to `results_partial_fft`. User: "JCM134 - 150 all approve". |
| JCM-149 | approved | Use `conditional C solve` in place of the reader claim `profiled C`, update the authoritative suite registry, and regenerate Explorer suite data. User: "JCM134 - 150 all approve". |
| JCM-150 | approved | Expand BP to `belief propagation` and DAG to `directed acyclic graph` in Explorer reader text while retaining internal code identifiers where appropriate. User: "JCM134 - 150 all approve". |
| JCM-151a | approved | Add `cz_refinement` and `joint_cwz` as the two machine identifiers in the five-arm confirmation evidence. Use `C,z refinement` and `joint C,W,z` in reader-facing Results text. User approved the complete audit fix list: "I approve all the fixes". |
| JCM-151b | approved | Rank the five confirmed receiver results by mean effective rate, then lower bit error rate, then lower decode time. Use the in-run JUNA-Lite control when decode time breaks an outcome tie. User approved the complete audit fix list: "I approve all the fixes". |
| JCM-151c | approved | Preserve the confirmation evidence under the `cz_refinement_confirmation` stem with current receiver and trace names, explicit historical package and harness provenance, and no obsolete compatibility identifiers. User approved the complete audit fix list: "I approve all the fixes". |
| JCM-151d | approved | Correct the Results explanation to distinguish selected CRC rescues from exact frame success, state the two fallback counts separately, qualify the inherited configuration search, and explain the joint-step counters as call-level counts. User approved the complete audit fix list: "I approve all the fixes". |
| JCM-151e | approved | Extend validation for five-arm Results ranking, retained joint-step scales, backtracking, and radius bounds without changing the receiver mathematics or documented stage sequence. User approved the complete audit fix list: "I approve all the fixes". |

## Concurrent Claude decisions reconciled

| ID | State | Decision. |
|---|---|---|
| CL-3 | approved | Rename the retained Source-description action to `Open in Source definitions`; keep the link and its route-contract coverage. User: "I approve all." |
| CL-8 | approved | Keep `JunaStandard` as a backward-compatible facade: JCM-071 and CX-009a retain the legacy constructor, and the interface and source-layout tests construct it. User: "I approve all." |
| CL-9 | approved | Fold the `Modulation` binding signature and source location into `Defined at`; do not keep a separate reader-visible `Modulation binding` row. User: "I approve all." |
| CL-10 | approved | Use `_initial_candidate`, `_select_initial_candidate`, and `_initial_candidate_from_ofdm_fec_and_partial_fft`; CX-017 supersedes the interim `front_end` candidates. User: "I approve all." |
| CL-11 | approved | In `common.jl`, describe the stage as the `frame-wide FEC receiver`; remove `front end` from that comment, consistent with JCM-050c and CX-017. User: "I approve all." |
| CL-12 | approved | In `common.jl`, write `Benchmark baselines stop at their own result`; do not call that endpoint a `front end` or `demodulator`. User: "I approve all." |
| CL-18 | approved | Remove the reused `CL-1/2/3` citations from `test/source_file_check.jl` and state each source divergence directly. User: "I approve all." |
| CL-19 | approved | The human performs this merge using a conflict map regenerated after the conformity commit; agents may prepare and review it but do not merge, preserving JCM-025 and JCM-081. User: "I approve all." |
| CL-20 | approved | Keep the reconciled register's JCM-057 through JCM-060 allocations and re-record the four concurrent Claude decisions as JCM-093 through JCM-096 with their former IDs noted as provenance. User: "I approve all." |

## Conformity audit decisions

The `CX` sequence is the stable, one-decision-per-row sequence used for the
cross-tree conformity audit. It does not fill or renumber any `JCM` gap. The
user approved every row below with: "I approve all changes you propose".

| ID | State | Decision. |
|---|---|---|
| CX-001 | approved | Remove accepted standalone and frame receiver settings whose implementations are absent; test every accepted setting through a public execution path. |
| CX-002 | approved | Give `demodulate_methods` the same synchronization and initial-resampling path as public `demodulate`, including a time-dilated waveform test. |
| CX-003 | approved | Validate required transmitted-symbol input before valid-candidate and zero-step early returns in block and frame receivers. |
| CX-004 | approved | At zero Profiled C,z steps, return the frame Lite starting result for every Profiled form; retain OFDM+FEC as a benchmark. |
| CX-005 | approved | Remove the unused `feedback_graded_p` and `feedback_trace` fields; callers supply corrupted transmitted symbols explicitly, with block and frame tests. |
| CX-006 | approved | Remove the unsupported feedback-score ordering assertion while retaining the output-divergence checks. |
| CX-007 | approved | When ridge is zero and the central response is zero, `_cz_mmse_weights!` returns zero combiner weights. |
| CX-008 | approved | Treat the string form of `LDPC.create` as a strict parsed compatibility form: reject unknown or extra tokens and require `0 < k < n`. |
| CX-009a | approved | Preserve legacy constructors, query aliases, the `standard` result field, and `:standard` provenance for `StandardModulation`; keep the current five-field result shape without guaranteeing the former exact tuple shape. |
| CX-010a | approved | Keep the implementation geometry of 1023 active carriers, 341 pilots, 682 data carriers, and an LDPC length of 1360; correct the paper and test references. |
| CX-011a | approved | Keep the implementation default of 16 frequency bands and describe the paper benchmark accurately as four bands. |
| CX-012 | approved | Replace nonexistent and line-number-fragile paper references in tests with `reference papers/gab/joe.tex` and stable labels. |
| CX-013 | approved | Make the shared interface contract explicitly check the Lite default and equality with the four reader-selectable modes; describe declared implementation separately from receiver execution. |
| CX-014 | approved | Give the eleven Profiled C,z suites distinct operation-based reader titles and add a fixed separator between CLI keys and file names. |
| CX-015 | approved | Limit the three performance descriptions to the packets, impairment, objective, and state dimensions actually checked. |
| CX-016 | approved | Remove unused receiver-descriptor fields and add a synchronization round trip for all four reader-selectable receivers. |
| CX-017 | approved | Apply `initial candidate` across source, tests, and Explorer; remove generic reader-facing `front end` and name the OFDM+FEC and Partial-FFT results directly. |
| CX-018 | approved | Describe Profiled C,z in two layers: complete-frame replacement behavior for readers, then conditional C, z, and W processing for technical detail. |
| CX-019 | approved | Make the receiver chain match the implementation: synchronization, carriers, payload-bit estimates, complete candidate order, Profiled baselines, and zero-step behavior. |
| CX-020 | approved | State that genie arms replace posterior decisions with transmitted symbols and that a null result is limited to this receiver's refit. |
| CX-021 | approved | Correct Health streaming offsets, status values, timestamp units, and contract labeling; add multi-chunk, status, and timestamp contracts. |
| CX-022 | approved | Link overloaded source definitions by stable symbol identity rather than name alone. |
| CX-023 | approved | Stop treating Julia file names as qualified symbols in coverage and include `Modulations`, `LDPC`, and facade containers. |
| CX-024 | approved | Sandbox rendered Results HTML while preserving its scripts, and require matching-origin JSON requests for mutation endpoints. |
| CX-025 | approved | Remove nonexistent `JNR-001` through `JNR-019` approval claims and use actual decisions or neutral contract wording. |
| CX-026 | approved | Escape every JSON control character correctly in both Julia exporters and test round trips. |
| CX-027 | approved | Put the complete server-contract fixture lifecycle under temporary-directory and `try/finally` cleanup. |
| CX-028 | approved | Give chain stages keyboard-operable buttons and command-palette listbox/option semantics with focus restoration. |
| CX-029 | approved | Change standalone analyzer scan and restart mutations from unprotected GET requests to protected POST requests. |
| CX-030 | approved | Keep Sonique attribution in technical details, show the current Juna commit on Home, and say `current source tree` rather than `pinned`. |
| CX-031 | approved | Remove the abstract-interface claim that payload rate is always at most the sample rate. |
| CL-24a | superseded by JCM-100 | Apply the reader layer to CLI matching, list output, and `Pkg.test` titles. The substance is re-recorded under a fresh non-colliding ID. |

## Proposed

| Candidate | Wording or action | Source. |
|---|---|---|
| JCM-085a | Update `JunaCore/README.md` to describe JUNA-Lite, Profiled C,z, and the two baselines; list the three existing Profiled C,z facades; keep unrelated receivers in the absent list. | The restored implementation makes the current statement that frame-wide C,z is absent false. |
| JCM-009a | `receiver refinement` | `refinement_objective` in the package interface. |
| JCM-009b | `JUNA-Lite refinement` | `test/juna_lite_refinement.jl`. |
| JCM-009c | `candidate refinement` | Candidate and refinement wording in the receiver code. |
| JCM-010a | `Interference in Part of the Band` | Words used in the note and cited paper, written without compression. |
| JCM-010b | `OFDM With Partial-Band Interference` | Standard terminology in the cited work. |
| JCM-010c | `Cancelling Partial-Band Interference` | The action and terminology used by the cited work. |
| JCM-016a | Rewrite the implementation specification in receiver execution order. Keep Julia identifiers only where they match code, remove invented umbrella labels and repeated emphasis, and preserve every equation, default, shape, test, and requirement. | User's readability objection and the existing implementation. |
| JCM-026a | Omit the author line. | The note does not otherwise identify a person as its author. |
| JCM-026b | `Gabriel Chua Yu Han` | Author shown in `JunaCore/juna_lite_ieee.tex`. |
| JCM-027a | Add `paper_note_style.tex` using presentation definitions from an approved existing deck, then review and build all eight dependent sources. | The file name already appears in all eight sources; `JUNA_vs_RPC.tex` and the cowork deck provide approved Beamer definitions. |
| JCM-027b | Keep the eight sources out of the merge until their original style file is supplied. | Preserves the requirement that merged documents build without inventing a replacement. |
| JCM-027c | Merge the sources with the missing dependency documented. | Preserves the rewrites now, but leaves all eight sources unable to build. |
| JCM-031a | `combiner weights` | `scjuna_llm_implementation_spec_v3.tex:351`, `paper_partial_fft_demodulation_concepts.tex:55`; Yerramalli 2012 and Aval 2015 use it throughout. |
| JCM-031b | `combining vector` | `JunaCore/juna_lite_ieee.tex:26`. Says it is one vector per carrier, which `weights` does not. |
| JCM-032a | `branch` | 138 uses across `JunaCore/` and the notes; `JunaCore/juna_lite_ieee.tex:170`. |
| JCM-032b | `view` | `manual_gradient_ofdm_paper_concepts_chitre.tex:294`; `juna_slides.tex:357`. |
| JCM-032c | `partial FFT output` | Yerramalli 2012, the paper we cite for the method. |
| JCM-033a | `branch count` | `manual_gradient_ofdm_paper_concepts.tex:163`. |
| JCM-033b | `view count` | `manual_gradient_ofdm_paper_concepts_chitre.tex:219`. |
| JCM-033c | `number of partial FFTs` | Yerramalli 2012. |
| JCM-034a | `partial-FFT combining` | Approved wording under JCM-007, reused in a new position. |
| JCM-034b | `post-FFT combining` | Aval 2015. Requires the reader to know what post-FFT means. |
| JCM-034c | `weighted combining` | Yerramalli 2012: `weighted combining of the partial FFT outputs`. |
| JCM-035a | `pre-decoder soft symbol` | `JunaCore/juna_lite_ieee.tex:26`. Says where in the chain it sits. |
| JCM-035b | `decision variable` | Aval 2015. |
| JCM-036a | `anchor` | 296 uses; `JunaCore/src/juna/lite.jl:40`. |
| JCM-036b | `decision-directed pilot` | `manual_gradient_ofdm_paper_concepts.tex:182`; Stojanovic's `decision-directed` plus our `pilot`. |
| JCM-037a | Keep `residual scale` and `common frequency offset`. | `joe.tex:327`; `JunaCore/juna_lite_ieee.tex:101`. |
| JCM-037b | `residual Doppler factor` and `carrier frequency offset`. | Stojanovic, Asilomar 2009; Yerramalli 2012. |
| JCM-038a | Keep `coarse Doppler correction`. | `joe.tex:348`. |
| JCM-038b | `initial resampling` | Stojanovic, Asilomar 2009 and Aval 2015. |
| JCM-039a | Keep `leakage` for the coefficient and `ICI` for the sum. | `JunaCore/juna_lite_ieee.tex:121,141`. |
| JCM-039b | Use `ICI` for both. | Stojanovic uses one word throughout. |
| JCM-045a | Rename the symbol to `N_{\rm branch}` and drop `V`. | Follows JCM-032; removes the second symbol. |
| JCM-045b | Keep `N_{\rm view}` as a symbol and drop `V`. | Symbols are not prose; JCM-037 already held symbols out of a prose rename. |
| JCM-045c | Rename to `M`, matching the other documents. | `JunaCore/juna_lite_ieee.tex:162` and the notes call the branch count `M`. |
| JCM-046a | Replace `leakage` with `ICI coefficient` only where carriers are meant; leave the inter-symbol uses alone. | Tu 2011 uses `ICI coefficients`; `joe.tex:462` is about neighbouring OFDM symbols. |
| JCM-046b | Keep `leakage` everywhere outside the JUNA-Lite paper. | The tutorials use it as a teaching word across 18 slides. |
| JCM-047a | `decoder feedback` | `joe.tex` already writes `decoder-to-front-end feedback` and `No decoder feedback`. |
| JCM-047b | Keep `feedback` unqualified. | Current wording in `JunaCore/juna_lite_ieee.tex`; the receiver sends nothing to a transmitter, so there is no second sense inside Juna. |
| JCM-048a | Keep `mode`. | `paper_adaptive_modulation_coding_concepts.tex` frame 1, following Wan et al. 2015. |
| JCM-048b | `MCS` | Wu 2025 defines `Modulation and Coding Scheme`; the note's own frame 3 already says `AMC`. |
| JCM-049a | Keep `adaptive-lite`. | `JunaCore/src/juna/common.jl:77`; changing it touches the code, tests, `suites.json` and `chain.json`. |
| JCM-049b | withdrawn | `guarded front-end selection`. Built on the unagreed word `front end`. Replaced by JCM-050. |
| JCM-049c | withdrawn | `front-end selection`. Built on the unagreed word `front end`. Replaced by JCM-050. |
| JCM-049d | `branch-count selection` | `common.jl` selects `selected_parts` per block, which is the branch count named in JCM-033. |
| JCM-050a | `post-FFT processing` | Stojanovic, 8 uses: "initial synchronization, FFT demodulation, and post-FFT processing". Names the combining stage. |
| JCM-050b | `receiver front end` | Stojanovic, 6 uses, including the section heading "MR-Based Receiver Front-End" for a stage of parallel branches. Names the resampling and demodulation stage. |
| JCM-050c | Do not name it as one thing. | The three current uses are three different stages; `common.jl:24` calls the FEC stage a front end, which no source supports. |
| JCM-052a | Remove reader-facing `branch` terminology. Use `partial FFT output` for one raw `Y_{k,m}`, `number of partial FFT outputs` for `M`, and `number of inputs supplied to the combiner` for adaptive Lite's `selected_parts`. Rewrite derived phrases according to their meaning. | Yerramalli 2012 defines `partial FFT output`; Aval 2015 uses `combiner inputs`; `common.jl` shows that the one-input case sums every raw partial-FFT output. |
| JCM-052b | Use `partial FFT output` for one raw `Y_{k,m}` and `number of partial FFTs` for `M`. | Yerramalli 2012 uses both forms. The count must not describe adaptive Lite's one-input case because all raw partial FFTs are still computed. |
| JCM-052c | withdrawn | `Keep branch and branch count` remains recorded under this ID. The user requested a skill-derived alternative, now JCM-052d. |
| JCM-052d | Use `partial-FFT view` for one raw `Y_{k,m}`, `number of partial-FFT views` for `M`, and describe adaptive Lite as supplying one summed input or `M` separate partial-FFT views to the combiner. | The `mandar` skill lists `partial-FFT view` as approved project vocabulary; `joe.tex` uses `number of partial-FFT views`. The `wushuangshuang` skill supplies no name for this object. |
| JCM-053a | Use `OFDM symbol` for the indexed transmission unit. Classify same-symbol off-diagonal carrier coupling as `ICI` or an `ICI coefficient`, and cross-symbol coupling as `intersymbol interference (ISI)`. An insufficient cyclic prefix may create both. | Wu 2025 uses `intersymbol interference`; Cisek and Zielinski 2019 separate the previous-symbol term from the same-symbol correction in an insufficient-prefix OFDM model. |
| JCM-054a | Put a compact carrier-index/OFDM-symbol-index criterion after the insufficient-prefix model in `joe.tex`; keep the complete derivation and conditional `N`-scaling explanation for the long Doppler/ICI tutorial; add at most an adequate-prefix scope statement to JUNA-Lite. | `joe.tex` already contains the multi-symbol model and explicitly marks it as untested; JUNA-Lite assumes an adequate cyclic prefix and implements a carrier-indexed, single-block receiver model. |
| JCM-078a | Restore only the base `profiled_cz` receiver. | The operational implementation is the three-file `full.jl`, `coupled.jl`, and `profiled_cz_frame.jl` path retained in Sonique. |
| JCM-078b | Restore the complete CRC, turbo, and conditioned C,z receiver family. | The historical test tree covers the extended constructors and all 19 `cz_*` controls. |
| JCM-079a | Expose the restored receiver through JunaCore and the Explorer. | A public restoration requires the facade, receiver catalog, Source graph, chain evidence, and contracts to agree. |
| JCM-079b | Keep the restored receiver internal. | This avoids adding a public facade and Explorer entry while retaining a callable implementation path. |
| JCM-080a | Reader-facing name `Profiled C,z`. | The historical test suite calls it the frame C,z profiled-gradient receiver, and the code identifier is `profiled_cz`. |
| JCM-080b | Reader-facing name `C,z receiver`. | This is shorter but omits the profiling distinction from the historical source wording. |
| JCM-115a | Public facade `JunaCrcJointCwz`. Selected under JCM-115. | Keeps the source-supported `CRC`, `joint`, and `C,W,z` distinctions while removing the redundant `Frame` and the unexplained experiment label `Conditioned`. |
| JCM-115b | Public facade `JunaCrcConditionedJointCwz`. Not selected. | Retains `Conditioned`, whose concrete meaning requires the pilot, trust-region, and acceptance checks to be explained separately. |
| JCM-115c | Public facade `JunaCrcWcz`. Not selected. | Shorter, but risks confusion with the diagnostic `JUNA-WCz` solver used in the paper. |
| JCM-116a | Reader-facing family name `C,z refinement`. Selected under JCM-116. | `test/runtests.jl` already uses `C,z refinement functions`; the wording remains true across the base, CRC, turbo, control, and joint forms. |
| JCM-116b | Reader-facing family name `C,z receiver`. Not selected. | Existing source wording and the earlier JCM-080 alternative; it does not name the additional processing. |
| JCM-116c | Reader-facing family name `Response and codeword refinement`. Not selected. | Expands physical response C and relaxed codeword z in plain words, but is longer than the selected name. |

## Displaced concurrent proposals

These proposals were never approved. They appeared concurrently under IDs that
were required for the reconciled approved history, so their wording is retained
here without assigning a second decision to either identifier.

- Former JCM-057 proposal: Repair stale Receiver stages references. Its
  substance was later approved and completed under JCM-084.
- Former JCM-058 proposal: Settle reader-facing Explorer use of `branch`. Its
  substance was resolved under JCM-052; current reader prose uses
  `partial-FFT view`, while internal identifiers remain unchanged.

Under JCM-083, repository artifacts for JCM-027, JCM-030, and the document
portions of JCM-031 through JCM-054 remain outside this focused merge pending
separate reviewed commits. JCM-040 through JCM-043 remain applied globally.
