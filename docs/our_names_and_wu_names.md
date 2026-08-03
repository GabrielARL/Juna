# Our names and Wu Shuangshuang's names

An audit, not a change. Nothing here has been renamed. Sources are the Wu
terminology reference at `~/.codex/skills/wushuangshuang/references/terminology.md`
and our own tree, cited as file:line.

The register entries JCM-047 to JCM-049 in `APPROVAL_LIST.md` put the conflicts
to the user. This file name renames on the user's word.

---

## 0. The short answer

Most of Wu's vocabulary has no counterpart in Juna, and that is deliberate, not
an oversight. `scjuna_llm_implementation_spec_v3.tex:143` states the scope:

> "Receiver-side adaptation only. No transmitter feedback, no waterfilling, and
> no adaptive rate control."

Wu tunes a **link**: the transmitter picks a scheme, the receiver reports CSI,
and a scheduler decides how often to report. Juna is a **receiver**: it changes
how one received signal is processed and sends nothing back. So the halves of
her vocabulary that concern the transmitter and the CONTROL link have nothing to
match against.

What does match is our adaptive-modulation note, which covers the same problem
from a different paper.

## 1. `adaptive-lite` is not her MCS

The two look alike and are not the same decision.

| | `adaptive-lite` | Wu's MCS |
|---|---|---|
| What is chosen | The partial-FFT front-end configuration | `a_j = (n_c, n_p, B)` plus the LDPC rate |
| Which end chooses | Receiver | Transmitter |
| What it changes | How the same received signal is processed | What is transmitted next |
| Input to the choice | The received frame itself | CSI fed back over the CONTROL link |
| Needs a return path | No | Yes |
| Where | `JunaCore/src/juna/common.jl:77`, `frame_wide_ldpc.jl:780` | 2022 pp. 1–3; 2025 pp. 8–15 |

What is genuinely alike is the *shape* of the decision: a finite candidate set,
a score, and a commitment to the best. Ours is `frontend_choices` guarded by
`frontend_guard_min_relative_gain` (`common.jl:150`); hers is the modulation
scheme space `A` explored by the dynamic epsilon-greedy algorithm. The shape is
shared; the quantity being tuned is not.

Separately, `adaptive-lite` names neither what adapts nor what it adapts to.
That is the qualifier the cowork procedure's reader test already rejected twice,
in `active tree` and `current tests`. It is also a code identifier
(`:adaptive_lite`) and a suite key, not a name chosen with the user. JCM-049
puts it to him.

## 2. `feedback` means two different things

This is the collision, and it is the same shape as `ratio combining` against
maximal ratio combining in the Stojanovic audit.

| | Our `feedback` | Wu's `feedback` |
|---|---|---|
| Between | The LDPC decoder and the front end, inside one receiver | The receiver node and the transmitter node, across the link |
| Carries | Posterior means and confidences | CSI |
| Scheduled by | Nothing; it runs every iteration | The Feedback Report Interval `h_j` |
| Costs | Computation | Channel time, as `feedback overhead` |

All 19 of our uses are the first sense: `joe.tex` speaks of the
`decoder-to-front-end feedback` and the `code-aware feedback loop`;
`juna_lite_ieee.tex` has `fixed-feedback control` and `corrupted feedback`.
None is link-level. A reader who arrives from Wu's work will read every one of
them the other way.

## 3. Where our adaptive-modulation note does match

`reference papers/gab/paper_adaptive_modulation_coding_concepts.tex` summarises
Wan et al. 2015, not Wu, but it works the same problem and its terms line up.

| Ours | Where | Wu's term | Note |
|---|---|---|---|
| `mode` ∈ {(M_1,R_1),…,(M_5,R_5)} | note frame 1 | `MCS`; `a_j`; modulation scheme space `A` | Hers is `(n_c, n_p, B)` plus LDPC rate; ours is modulation order and code rate. |
| `transmission mode` | frame 1 | `modulation scheme` | |
| `AMC loop` | frame 3 | `Adaptive Modulation and Coding`; `AMC` | Same expansion. |
| `channel quality from recent packet reception` | frame 3 | `CSI`; measured BER `epsilon_j(a)` | |
| `Select the highest rate meeting the reliability target` | frame 3 | `LDPC Rate Selection Criterion`; `maximal LDPC rate` | |
| `reliability target` | frame 3 | `frame success rate` | Her reported 75% design is tied to the QAD setting and tested conditions. |
| `Validate at sea, not only in simulation` | frame 3 | sea trials | Her skill forbids `validated at sea` without the reported conditions. |
| `effective SNR`, `ESNR` | frame 2 | `Effective Signal-to-Noise Ratio` | **Thesis background only.** Her three papers select on BER, not ESNR. Matching this term to Wu would misattribute it. |
| `candidate score` | frame 4, JCM-008 | nearest is `epsilon_hat_j(a)`, `BER upperbound` | Not the same object. Ours scores a decoded candidate; hers estimates a BER before transmitting. |
| `LDPC` | throughout | `LDPC` | Already agree. |

## 4. Hers, with nothing to match

Present in Wu, absent from Juna by scope. Listed so the audit is complete and
so nobody tries to import them.

`Feedback Report Interval` `h_j` · `feedback scheduling` · `DATA link` ·
`CONTROL link` · `test mode` · `TS-DQN`, `TS-DQN1`, `TS-DQN2` · `K-MCTS` ·
`dynamic epsilon-greedy algorithm` · `BER upperbound` · `QAD` ·
`Gaussian Process Regression` · `FHBFSK` · `throughput`, `feedback overhead` ·
`TX`, `RX` · boundary planes `Bc1`–`Bc3`.

## 5. Ours, with nothing to match

`partial-FFT` and everything under it — `partial-FFT view`, `combiner weights`, `anchor`,
`confidence`, `pre-decoder soft symbol`, `ICI coefficient`, `candidate score`,
`syndrome weight`. Wu's thesis names `ICI` once, in a literature review, and
never as a quantity her methods act on.
