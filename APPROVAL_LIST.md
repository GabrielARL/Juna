# Approval register

Every item needing the user's decision is recorded here with a stable
identifier. Read this file before proposing anything, so settled questions are
not reopened.

This is Juna's register. It is governed by `SOP_HUMAN_AI_COWORK.md`.

- One identifier records one decision.
- Identifiers are never reused.
- A rejected item keeps its identifier.
- Silence is not approval.

Next free Juna identifier: **JCM-093**.

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
| JCM-087 | approved | Import all seven portable Sonique regression tests for the restored `full.jl` and `coupled.jl` closure, preserving assertions while adapting obsolete reader-visible labels to the approved `Profiled C,z` family name. User: "087a". |
| JCM-088 | approved | Do not add ForwardDiff or the three automatic-differentiation test files; retain the existing finite-difference coverage. User: "088b". |
| JCM-089 | approved | Attach the imported module tests to the existing `Profiled C,z` Explorer family across Tests, Coverage, Chain, and Source; do not create public Full or Coupled receiver entries. User: "089a". |
| JCM-090 | approved | After validation, restart the permanent port 8772 Explorer from the `profiled-cz-restore` worktree and verify its live APIs. User: "090a". |
| JCM-091 | approved | Commit the validated Profiled C,z restoration on `agent/profiled-cz-restore`, including its implementation, public facades, regression tests, Explorer integration, contracts, parity evidence, generated data, and approval record. User: "091a". |
| JCM-092 | approved | Push `agent/profiled-cz-restore` to the confirmed `origin` at `https://github.com/GabrielARL/Juna.git` so another computer can clone this exact committed copy. User: "092a". |

## Proposed

| Candidate | Wording or action | Source. |
|---|---|---|
| JCM-085a | Update `JunaCore/README.md` to describe JUNA-Lite, Profiled C,z, and the two baselines; list the three existing Profiled C,z facades; keep unrelated receivers in the absent list. | The restored implementation makes the current statement that frame-wide C,z is absent false. |
| JCM-086a | Use `JunaCore explorer` for the application title, page heading, startup message, and contract descriptions. | `JunaCore` is the existing package name; the Explorer now exposes four reader-selectable receiver families. |
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
