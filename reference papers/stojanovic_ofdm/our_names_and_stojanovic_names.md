# Our names and Stojanovic's names

Every row records where each name appeared, what it meant in that place, and
whether the two usages conflicted.

**Settled.** JCM-031 to JCM-039 were approved and applied. The names in force
are listed in `## 0. Decided` below; the rest of this file is the audit that
produced them, kept so a settled question is not reopened. Two follow-on
questions are still open: JCM-045 (the `joe.tex` symbol) and JCM-046
(`leakage` outside the JUNA-Lite paper).

---

## 0. Decided

| Object | Name in force | Register |
|---|---|---|
| The `M` weights per carrier | `combiner weights` | JCM-031 |
| One partial-FFT output | `branch` | JCM-032 |
| The count `M` | `branch count` | JCM-033 |
| Weighting the branches and summing | `partial-FFT combining` | JCM-034 |
| The scalar handed to the decoder | `pre-decoder soft symbol` (unchanged) | JCM-035 |
| Decoded data reused as training | `anchor` | JCM-036 |
| Frequency error after the front end | `residual Doppler factor` `a`, `carrier frequency offset` `θ` | JCM-037 |
| Removing the bulk of the Doppler | `initial resampling` | JCM-038 |
| One off-diagonal entry | `ICI coefficient`; the sum stays `ICI` | JCM-039 |

Four of the nine take Stojanovic's word, four keep ours, and one reuses the
`Partial-FFT combining` wording already approved under JCM-007. `pre-decoder
soft symbol`, `branch`, `anchor` and `confidence` remain ours because they say
something her vocabulary does not.

Symbols were not renamed. `a` and `θ` keep their letters, and the `joe.tex`
branch-count symbol is held under JCM-045.

---

Her sources are the papers beside this file. Ours are `JunaCore/` and
`reference papers/gab/`, cited as file:line.

---

## 1. Where we were split against ourselves

These were defects regardless of what Stojanovic calls the thing: two of our own
documents gave one object two names. All four are now settled by JCM-031 to
JCM-036, except the `joe.tex` symbol under JCM-045.

The audit undercounted `view`. `joe.tex` also uses it, as the symbol
`N_{\rm view}` in 32 places and as `V` in two more — so that file names one
quantity two ways on its own. That is why JCM-045 exists.

| Object | Name A | Name B | Her name |
|---|---|---|---|
| The `M` weights that combine the partial-FFT outputs on one carrier | `combining vector` — `JunaCore/juna_lite_ieee.tex:26,27,32,56` | `combiner weights` — `reference papers/gab/scjuna_llm_implementation_spec_v3.tex:351`, `reference papers/gab/paper_partial_fft_demodulation_concepts.tex:55`, `reference papers/gab/manual_gradient_ofdm_paper_concepts.tex:163` (`branch-combiner weights`) | **`combiner weights`** — Yerramalli 2012 (35 uses), Aval 2015 (24 uses); also `weight vector` |
| One partial-FFT output, carrier `k`, slice `m` | `branch` — 138 uses; `branch observation` `JunaCore/juna_lite_ieee.tex:170`; `branch vector` `paper_partial_fft_demodulation_concepts.tex:41`; `branch response` `manual_gradient_ofdm_paper_concepts.tex:237` | `view` — `manual_gradient_ofdm_paper_concepts_chitre.tex:46,216,219,294,407,409,413,434`; `juna_slides.tex:357`; `doppler_ici_partial_fft_tutorial_grad_version.tex:735` | **`partial FFT output`** — Yerramalli 2012 |
| The count `M` | `branch count` — `manual_gradient_ofdm_paper_concepts.tex:163,331,354` | `view count` — `manual_gradient_ofdm_paper_concepts_chitre.tex:219,407,434` | **`number of partial FFTs`** / `number of partial intervals` / `number of partial segments` |
| Decoded data reused as training | `anchor`, `data anchor`, `posterior anchor` — 296 uses across `JunaCore/` and the notes | `decision-directed pilot` — `manual_gradient_ofdm_paper_concepts.tex:182`, `manual_gradient_ofdm_paper_concepts_chitre.tex:238`, `paper_sparse_channel_estimation_concepts.tex:95` | **`decision-directed`** (the mode) + **`tentative decisions`** (the symbols) |

The `branch` / `view` split runs along the Chitre-rewrite boundary: the
`_chitre` variant of the manual-gradient note says `view` everywhere its sibling
says `branch`. Both files are in the tree.

## 2. Where one name of ours risks being read as something else

| Our name | Where | What we mean | What a reader of the OFDM literature will think |
|---|---|---|---|
| `ratio combining` | `JunaCore/juna_lite_ieee.tex:43,67,202,676` | Weighting the `M` partial-FFT outputs of one carrier and summing them | **Maximal ratio combining** across receive elements. Aval 2015 uses `MRC` and `D-MRC` for exactly that, in a partial-FFT paper. Her name for our operation is `post-FFT combining`, or `weighted combining of the partial FFT outputs`. |

This is the one row where the two vocabularies actively collide: the same words
name different operations in her paper and ours.

## 3. Where we simply use different words

No internal defect and no collision. Sync only if a shared vocabulary is worth
the edit.

| Object | Ours | Hers |
|---|---|---|
| The scalar handed to the decoder | `pre-decoder soft symbol`, `scalar soft symbol`, `pre-decoder statistic` — `juna_lite_ieee.tex:26,204,681` | `decision variable` (Aval 2015); `an estimate of the data symbol` (Sea Technology 2007) |
| Frequency error left after coarse Doppler correction | `residual scale` `a` — `joe.tex:327,333,348`; `common frequency offset` `θ` — `juna_lite_ieee.tex:101` | `residual Doppler factor (after initial resampling)` `a_t(n)` — Asilomar 2009; `residual Doppler shift` — Aval 2015 (10 uses); `carrier frequency offset (CFO)` — Yerramalli 2012 |
| Removing the bulk of the Doppler at the front end | `coarse correction`, `coarse Doppler correction` — `joe.tex:348` | `initial resampling`; `resampling at the receiver's front end` |
| Energy arriving at bin `k` from carrier `ℓ` | was `leakage` (31 uses) for the coefficient; `ICI` for the sum | `ICI coefficient` — Tu 2011, 21 uses; `ICI term` — Tu 2011. Her one use of `leakage` means something else: energy spread across *channel taps* in sparse estimation. |
| The time slice | `segment window` `g_m[n]` — `juna_lite_ieee.tex:162` | `windowed segment`; `non-overlapping rectangular windows`; `OFDM sub-interval`; `partial segment` |

## 4. Where we already agree

Recorded so they are not reopened. Same word, same meaning, both sides.

`pilot` · `pilot overhead` · `OFDM block` · `banded` · `equal gain combining`
(Yerramalli: *"equal gain combining of the partial FFT outputs is optimal when
the channel is time-invariant"*; ours: `scjuna_llm_implementation_spec_v3.tex:1583`)
· `computational complexity` · `mean squared error` · `bit error rate` ·
`intercarrier interference (ICI)` as the summed term.

The symbol `a` also agrees: her post-resampling Doppler factor and our residual
scale are the same quantity under the same letter.

## 5. Ours alone

No counterpart in her OFDM work. Nothing to sync; listed so the audit is
complete.

| Ours | Why she has no word for it |
|---|---|
| `confidence` `ω` | Her decision-directed receivers use hard tentative decisions, unweighted. |
| `carrier band`, band sharing `W_k = W_b` — `juna_lite_ieee.tex:250` | Her nearest is the assumption itself: *"assuming the channel to be equal between adjacent carriers"* (Asilomar 2009). She never names the group. |
| `candidate`, `candidate score`, `decoder score`, `posterior tie error`, `syndrome weight` | No candidate-comparison stage exists in her receivers. |
| `bit latent` `z`, `posterior-mean symbol` `s_k` | No decoder-coupled estimation in her OFDM work. |
| `JUNA`, `JUNA-Lite`, `Partial-FFT combining` | Project names. `Partial-FFT combining` is approved under JCM-007. |
