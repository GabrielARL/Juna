# Approval register

Every item needing the user's decision is recorded here with a stable
identifier. Read this file before proposing anything, so settled questions are
not reopened.

This is Juna's register. It is governed by `SOP_HUMAN_AI_COWORK.md`.

- One identifier records one decision.
- Identifiers are never reused.
- A rejected item keeps its identifier.
- Silence is not approval.

Next free Juna identifier: **JCM-030**.

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
| JCM-026 | proposed | Choose the author line for `manual_gradient_ofdm_paper_concepts_chitre.tex`; its current `Project SONIQUE` label conflicts with Juna being a separate entity. |
| JCM-027 | proposed | Decide how the merge handles the missing `paper_note_style.tex` required by eight Beamer note and tutorial sources. |
| JCM-028 | approved | Keep the documents affected by unresolved JCM-026 and JCM-027 out of the current merge scope. |
| JCM-029 | approved | Prepare explicit-path local commits for the approved merge scope; do not merge or push. |
| JCM-030 | approved | Resolve the three Explorer merge conflicts by keeping the reviewed `agent/merge-prep` versions of `server.py`, `server_contract.py`, and `source.js`. |

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

JCM-026 and JCM-027 remain proposed until the user chooses. They are outside
the current merge scope under JCM-028.
