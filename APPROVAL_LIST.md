# Approval register

Every item needing the user's decision is recorded here with a stable
identifier. Read this file before proposing anything, so settled questions are
not reopened.

This is Juna's register. It is governed by `SOP_HUMAN_AI_COWORK.md`.

- One identifier records one decision.
- Identifiers are never reused.
- A rejected item keeps its identifier.
- Silence is not approval.

Next free Juna identifier: **JCM-061**.

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
| JCM-027 | approved | Add `paper_note_style.tex` using presentation definitions from an approved existing deck, then review and build all eight dependent sources. User: "027a". Applied: the reconstructed style builds all eight sources. |
| JCM-028 | approved | Keep the documents affected by unresolved JCM-026 and JCM-027 out of the current merge scope. |
| JCM-029 | approved | Prepare explicit-path local commits for the approved merge scope; do not merge or push. |
| JCM-030 | approved | Keep the `milica` writing skill and its evidence set under `reference papers/stojanovic_ofdm/`. Applied: names kept as written. |
| JCM-031 | approved | Use `combiner weights` for the `M` weights that combine the partial-FFT outputs of one carrier. Applied in `JunaCore/juna_lite_ieee.tex`; the specification and notes already used it. |
| JCM-032 | approved | Use `branch` for a single partial-FFT output. Applied in the notes, slides and tutorials. The symbol `N_{\rm view}` in `joe.tex` is held under JCM-045. |
| JCM-033 | approved | Use `branch count` for `M`. Applied with JCM-032. |
| JCM-034 | approved | Use `partial-FFT combining` in place of `ratio combining`, reusing the JCM-007 wording in a new position. Applied in `JunaCore/juna_lite_ieee.tex`, including the section title. |
| JCM-035 | approved | Keep `pre-decoder soft symbol`. No edit required. |
| JCM-036 | approved | Use `anchor` for decoded data reused as training. Applied: `decision-directed pilot` removed from three notes. |
| JCM-037 | approved | Use `residual Doppler factor` and `carrier frequency offset`. Applied in `joe.tex`, `JunaCore/juna_lite_ieee.tex`, and two decks. The symbols `a` and `\theta` are unchanged. |
| JCM-038 | approved | Use `initial resampling` in place of `coarse Doppler correction`. Applied in `joe.tex` and `JunaCore/juna_lite_ieee.tex`. |
| JCM-039 | approved | Use `ICI` for both, with `ICI coefficient` for the single entry. Applied in `JunaCore/juna_lite_ieee.tex`. The cross-symbol uses were resolved separately under JCM-053 and JCM-054. |
| JCM-040 | approved | Create the user-global Codex skill at `/home/gabiel/.codex/skills/wushuangshuang/`. This records the user's approval of the skill decision originally presented as the colliding JCM-031. |
| JCM-041 | approved | Use `references/terminology.md` for the detailed, page-sourced terminology inventory. This records the user's approval of the skill decision originally presented as the colliding JCM-032. |
| JCM-042 | approved | Let the 2025 journal paper govern terminology conflicts while retaining the 2022 and 2021 variants. This records the user's approval of the skill decision originally presented as the colliding JCM-033. |
| JCM-043 | approved | Use the Wu skill for OFDM tuning terminology and technical reasoning while `mandar` continues to govern Juna prose style. This records the user's approval of the skill decision originally presented as the colliding JCM-034. |
| JCM-044 | rejected | Use only the three first-author papers as the primary corpus and keep the 2023 thesis outside the core inventory. This records the user's rejection of the skill decision originally presented as the colliding JCM-035. |
| JCM-045 | rejected | User: "ignore". `joe.tex` keeps `N_{\rm view}` and `V` unchanged; the prose in that file keeps `views`. No edit made. |
| JCM-046 | approved | Replace `leakage` with `ICI coefficient` only where carriers are meant; leave the inter-symbol uses alone pending a separate decision. User: "046a". The two cross-symbol uses were resolved under JCM-053 and JCM-054. |
| JCM-047 | approved | Use `decoder feedback` where the sense is otherwise bare. Applied to four uses in `JunaCore/juna_lite_ieee.tex`; `joe.tex` and the specification were already qualified, and the experiment-arm names `fixed-feedback control` and `corrupted feedback controls` were left alone. |
| JCM-048 | approved | Keep `mode` in the adaptive-modulation note. The note summarises Wan et al. 2015, so importing Wu's `MCS` would name it with a term its cited paper does not use. No edit required. |
| JCM-049 | rejected | User: "ignore". `adaptive-lite` keeps its name in code, tests and JSON. Candidate JCM-049d not taken. |
| JCM-050 | rejected | User: "ignore". `front end` stays unagreed and keeps its three current senses. No name adopted. |
| JCM-051 | approved | Keep the rebuilt results page and its generator, `results/build_view.py` and `results/view_template.html`. User: "yes". |
| JCM-052 | approved | Use `partial-FFT view` for one raw `Y_{k,m}`, `number of partial-FFT views` for `M`, and describe adaptive Lite as supplying one summed input or `M` separate partial-FFT views to the combiner. This supersedes JCM-032 and JCM-033 in prose without renaming code identifiers. User: "052d". Applied in current reader prose and Explorer descriptions. |
| JCM-053 | approved | Use `OFDM symbol` for the indexed transmission unit. Use `ICI` and `ICI coefficient` for same-symbol off-diagonal carrier coupling, and `intersymbol interference (ISI)` for cross-symbol coupling. An insufficient cyclic prefix may produce both classes. User: "approve JCM-053a". Applied under JCM-054. |
| JCM-054 | approved | Put the compact JCM-053a criterion in `joe.tex`, reserve the full teaching derivation for the long Doppler/ICI tutorial, and leave JUNA-Lite with an adequate-prefix scope statement. User: "approve write it in". Applied in the three current reader sources. |
| JCM-055 | approved | Remove the adaptive-lite receiver. User: "just remove this from the code and from the explorer ui". Deleted from `common.jl` and `frame_wide_ldpc.jl` with its pilot cross-validation guard, from `test/`, from `chain.json`, the regenerated `suites.json` and the symbol explorer, and from the results page including the winner-chart rings. The two pinned source hashes were updated in the same change, as `source_file_check.jl` requires. Its rows stay in the search CSVs as the record of the run. |
| JCM-056 | approved | Show only the 60-frame confirmation stage on the results page. User: "only retain 1 state, 60 frame state. remove all other from the code and ui". The Stage control and the Stage column are gone and the 20-frame screening CSVs are no longer loaded. This is 288 rows rather than 13,173; the screening CSVs remain on disk. |
| JCM-057 | approved | Repair the stale references in `tools/explorer/source_symbol_explorer.py`. User: "do it". Removed eight absent facade modules, four dead functions, the `sync_profile` field that is not in the struct, and every `:rpchan` mention including its transmit-layout diagram row. |
| JCM-058 | approved | Apply JCM-032's `branch` in the Explorer. User: "do it". `partial-FFT views` becomes `partial-FFT branches` in `chain.json` and the symbol explorer; the colliding code-path sense in `chain.json` becomes `the standard one-tap path`, reusing that file's own word. |
| JCM-059 | approved | Replace the Source files run-on sentence with a Kind / Count / What it is table, and rescan on every page load. User: "can we have something like this to make it more intuitive. and can it be dynamic. scan each time reload?". This supersedes the JNR-001 to JNR-006 wording that S20 pinned; the counts, the kind labels, and the module, structure, and abstract type names are all read from the analyzer, and S20 now checks the rows instead of the sentence. The rescan fix is separate: the watch list was a snapshot taken at import, so a source file added after the server started was never seen. |
| JCM-060 | approved | Name the checked files in the Source file check introduction. User: "can you write their names in the brief introduction. above the technical details". Edited in `test/runtests.jl`, the source of truth, and `suites.json` regenerated. |

## Proposed

| Candidate | Wording or action | Source. |
|---|---|---|
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

JCM-027a, JCM-046a, and JCM-052d were approved together. JCM-027 is no longer
outside the merge scope under JCM-028 once its style dependency and eight builds
have been verified.

## Claude decisions

Claude's identifiers use the `CL` prefix so two agents cannot allocate the
same one. Next free Claude identifier: **CL-21**.

| ID | State | Decision. |
|---|---|---|
| CL-1 | approved | User: "CL-1". Source tab labels: `Evidence Inspector` becomes `Source`, `Advanced Graph` becomes `Graph`, the `Original Analyzer` tab is removed (its link moves into the description card; S5 requires the link to exist). The three literal label assertions are unpinned from `server_contract.py` S15. |
| CL-2 | approved | User: "CL2-a". Drop the Source tab strip; `Graph` becomes a single toggle so the page title is not repeated by a tab. |
| CL-3 | open | The `Original Analyzer` link wording in the Source description card: rename, register as-is, or drop (dropping requires editing the S5 assertion). |
| CL-4 | approved | User: "CL4-5 approved". When no `"""` docstring exists, Purpose reads the author's `#` comment, labelled "From a source comment, not a docstring". |
| CL-5 | approved | User: "CL4-5 approved". A facade module's Chain role shows the receiver it fronts (`chain.json` `facade` field) instead of "Not part of a declared chain stage". |
| CL-6 | approved | User pasted the row table and wrote "ok". Inspector rows are selected by kind: modules keep Purpose, Defined at, Chain role; gain Modulation binding; drop Signature, Dispatch, Evidence, call graph. |
| CL-7 | approved | User: "CL-7 suppress for now". A `#` comment block that runs back to line 1 is a file header, not a definition's purpose, and is never shown as one. This keeps the sonique migration note off the reader page. |
| CL-8 | open | Ask Codex what still constructs `JunaStandard` on its branch, where it is a compatibility facade with no declared receiver; if nothing does, it goes. |
| CL-9 | open | The reader-visible row name `Modulation binding` was introduced by Claude and needs approval, renaming, or folding into `Defined at`. |
| CL-10 | open | Strip `front end` from `_front_end_seed_candidate` / `_select_front_end_seed`. Under CL-15 the mechanical interim names are `_front_end_initial_candidate` / `_select_front_end_initial_candidate`; candidates a (`_fallback_…`), b (`_valid_…`), c (`_initial_candidate` alone) remain open. |
| CL-11 | open | Cut `front end` from the `common.jl:23` comment "frame-wide FEC front end/refiner"; JCM-050c recorded that no source supports calling the FEC stage a front end. |
| CL-12 | open | Replace `front end` with `demodulator` in the `common.jl:1103` comment "Benchmark baselines stop at their own front end". |
| CL-13 | approved | User: "Cl13b sounds good". The receiver's first decoded guess is named `initial candidate` (source: `chain.json:149` "equalizes and BP-decodes the initial candidate"). The RNG sense of `seed` (`_ldpc_seed`, `_MAX_TOOL_SEED`, packet seeds) is untouched. |
| CL-14 | approved | User: "CL-14, CL-15, CL-16, CL-17 all changed". Reader-visible Explorer text drops receiver-sense `seed`: stage title, chain detail, edge condition, kind legend, `server.py` prose, suite claims. |
| CL-15 | approved | Same answer. Code names: `_seed_candidate` → `_initial_candidate`; `seed_equalized`, `juna_seed`, `seed_fit`, `seed_metrics` and bare receiver-sense locals renamed mechanically with the CL-13 word. Behavior untouched; parity pins outputs, not names. |
| CL-16 | approved | Same answer. Applied: a full classification found 20 receiver-sense `joe.tex` uses, not the 4 first cited; all 20 adopt `initial candidate` and the 6 RNG uses stay. Two sites took an approved word other than the CL-13 term: `seed symbols X_anchor` became `anchor symbols X_anchor` (JCM-036) and `Train/apply the pilot-only Partial-FFT RLS seed` became `... RLS combiner` (JCM-031); revert on request. |
| CL-17 | approved | Same answer. Internal ids: stage id `seed` becomes `initial-candidate` in `chain.json`, `receiver_catalog.jl`, `receivers.json`, contract queries, and links; the stage kind value `seed` becomes `initial`. |
| CL-18 | open | `test/source_file_check.jl:21-23` comments cite "CL-1/2/3" from an earlier unrecorded sequence (the rpchan removal); those numbers now name different decisions in this register. Options: reletter the old comment refs, or record the collision here and leave the comments. |
| CL-19 | open | The user asked Claude to merge his and Codex's branches. JCM-025 and Codex's JCM-081 record merges into `human/merge-review`/`main` as human-only. Claude pushed all branches without merging. Options: (a) the user merges, with Claude's conflict map as the guide; (b) the user reaffirms an agent-performed merge, superseding JCM-025/JCM-081 for this merge only. |
| CL-20 | open | JCM-057 through JCM-060 are double-allocated: Codex's committed register (52f99b6) and this register assign the same four IDs to different approved decisions. Options: (a) this register re-records its four under fresh IDs with supersession notes, keeping Codex's committed numbering; (b) the user rules otherwise. |
