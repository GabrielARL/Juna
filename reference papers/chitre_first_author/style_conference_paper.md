# Conference-paper style profile
# SOURCE: the paper ucomms24.pdf ACTUALLY contains, namely
# "Generating Multichannel Colored Noise For Underwater Acoustic Simulations" (M. Chitre).
# The ARL publications page mislabelled this file as "Frugal communication".

## IMPORTANT — file/title mismatch (read this first)

The file you pointed me at is **not** "Frugal communication: Strategies to work with limited bandwidth".

`/home/gabiel/Documents/GitHub/Juna/reference papers/chitre_first_author/ucomms24.pdf` is:

> **"Generating Multichannel Colored Noise For Underwater Acoustic Simulations"** — Mandar Chitre, Acoustic Research Laboratory, Tropical Marine Science Institute, and Department of Electrical and Computer Engineering, National University of Singapore. 5 pages, two-column, 11 references, PDF built with `LaTeX via pandoc` / `xdvipdfmx`, created 2024-07-21.

I searched the whole `Juna/` tree for "frugal". It occurs in exactly one file: `/home/gabiel/Documents/GitHub/Juna/reference papers/chitre_first_author/bts2024-chitre.pdf` — a **50-page slide deck**, titled *"doing more with less — effective use of limited acoustic bandwidth"*, footer *"Mandar Chitre – Breaking the Surface 2024, Biograd na Moru, Croatia"*, with slides "Reducing Delivery Overheads / Frugal headers" and a closing "Takeaways: Use frugal communication protocols to minimize overheads / Do more with less bits by leveraging priors". That is a different venue (Breaking the Surface, Croatia — not UComms, Sestri Levante) and a different medium (slides, not a paper).

**So the argumentative/position paper you described does not exist in this folder as a paper.** I profiled the file you gave me, `ucomms24.pdf`, in full. Be aware that this changes the answer to your question 5 substantially: **this is a short methods paper, not a position paper.** It argues no philosophy, poses no questions, and takes no provocative stance. I report what is actually there, and flag the absences explicitly, since absences are as load-bearing for a rewriter as presences. If you want the frugal-communication rhetoric profiled, point me at the deck.

---

## 1. Complete abstract, verbatim

> Abstract—Underwater acoustic communication algorithms typically undergo numerical testing within simulated environments prior to real-world application. These simulations require noise samples that accurately reflect the ambient noise in the underwater environment. The common practice of employing a white Gaussian noise model for additive noise in simulations fails to capture the true nature of underwater noise. Given the wideband nature of most underwater communication systems and the frequency-dependence of ambient noise, the assumption of white noise becomes untenable. Furthermore, communication systems equipped with multiple hydrophones for spatial diversity experience correlated noise across hydrophones. This paper presents a simple technique for generating colored noise that is consistent with the spatial and temporal correlation characteristics of ambient noise measured at sea.

**Measured:** 6 sentences, 117 words, mean 19.5 words/sentence. **Zero numerals. Zero citations. Zero results.** The abstract is entirely problem → gap → "this paper presents". No performance claim of any kind is made in it.

Its internal skeleton, which is reusable verbatim as a template:
1. *X typically undergo … prior to …* (what the field does)
2. *These … require …* (what that demands)
3. *The common practice of employing … fails to capture …* (what the default gets wrong)
4. *Given …, the assumption of … becomes untenable.* (why it is not salvageable)
5. *Furthermore, … experience …* (second, independent failure)
6. *This paper presents a simple technique for …* (the offer)

## 2. First three sentences of the Introduction, verbatim

> Underwater acoustic communication algorithms are often tested via numerical simulations prior to real-world deployment. In order to accurately estimate the performance of these algorithms, the simulations must accurately model the signal distortions introduced by the underwater channel. These distortions include time-varying frequency-selective fading due to multipath propagation, Doppler, and additive noise.

(14, 23, 14 words.) Note the deliberate re-statement of the abstract's first sentence in near-synonymous terms — *"typically undergo numerical testing within simulated environments prior to real-world application"* becomes *"are often tested via numerical simulations prior to real-world deployment."* He does not reuse the abstract sentence; he rewrites it.

## 3. Section headings, in order

Roman numerals, small caps in the typeset PDF.

1. `I. Introduction`
2. `II. Problem Statement`
3. `III. Covariance Estimation`
4. `IV. Noise Generation`
5. `V. Implementation`
6. `VI. Results`
7. `VII. Discussion and Conclusion`
8. `Acknowledgement` (unnumbered)
9. `References` (unnumbered)

Plus one floated box: `Algorithm 1: Generation of passband multichannel colored Gaussian noise, given passband noise sample or an estimated covariance tensor.`

Structural notes for a rewriter: **no Related Work section** (prior art is dispatched in one intro clause with `[1]–[4]`); **no separate Conclusion** — it is fused into `Discussion and Conclusion`; **no Future Work section** (the forward-looking sentence is parked in the Introduction instead); **no appendix**; the derivation lives inline in the body, not in an appendix. Sections III, IV, V are each ~1 short column or less. Section headings are noun phrases, never sentences, never "gerund-heavy" except where the section *is* an operation (`Covariance Estimation`, `Noise Generation`).

## 4. Motivation — every sentence before any formalism

Formalism begins with the first sentence of Section II (*"Consider an acoustic communication system with N receive hydrophones…"*). Everything before it — the entire Introduction, 21 sentences, 352 words, mean 16.8 words/sentence — is motivation. Here it is in full, grouped by the rhetorical move each block performs.

**Block A — establish the practice and locate the gap (5 sentences):**
> Underwater acoustic communication algorithms are often tested via numerical simulations prior to real-world deployment. In order to accurately estimate the performance of these algorithms, the simulations must accurately model the signal distortions introduced by the underwater channel. These distortions include time-varying frequency-selective fading due to multipath propagation, Doppler, and additive noise. While most channel modeling work has focussed on the former two [1]–[4], modeling of additive noise has received less attention. This paper is aimed at addressing this gap.

The gap sentence is the shortest in the Introduction (8 words) and lands at the end of paragraph 1. `This paper is aimed at addressing this gap.` — note the mild `is aimed at` rather than `addresses`.

**Block B — kill the alternatives, one paragraph, two candidates, same two-beat rhythm each (7 sentences):**
> One may use recorded ambient noise from the ocean as additive noise samples for simulation. While this approach yields accurate results, it requires long uncontaminated noise recordings to be available. This limits the duration of transmission that can be simulated without repeating the noise samples. Another common practice is to employ a white Gaussian noise model to generate additive noise samples during simulation. While this approach is simple, it fails to capture the true nature of underwater noise. Ambient noise in the ocean is typically colored, with a frequency-dependent power spectral density [5]. The assumption of white noise is untenable for wideband underwater communication systems. Moreover, underwater ambient noise has directionality and therefore exhibits spatiotemporal correlation across hydrophones in a multichannel system.

The concession-then-defeat template is used **twice, verbatim in form**:
- `While this approach yields accurate results, it requires …`
- `While this approach is simple, it fails to capture …`

He never says a rival approach is bad. He concedes its virtue in the subordinate clause and defeats it in the main clause. This is the single most reusable sentence machine in the paper.

**Block C — the second, independent defect (3 sentences):**
> Even in the case of isotropic noise, the wideband nature of communication systems can lead to noise correlations across channels. A model where noise samples are independently generated for each receive hydrophone fails to capture this correlation. The generative model presented in this paper addresses both these limitations.

`Even in the case of …` pre-empts the reader's escape hatch — "but what if the noise is isotropic?" — before the reader can raise it. The block closes by counting: `addresses both these limitations`.

**Block D — scope the claim before anyone attacks it (5 sentences):**
> The Gaussian noise assumption holds in many underwater environments, especially in deeper or cooler waters. Warm shallow waters, however, exhibit a significant amount of non-Gaussian noise due to snapping shrimp and other biological sources [6]. Some polar regions also exhibit non-Gaussian noise due to ice cracking and bubbles from melting glaciers and icebergs [7]. We limit our discussion to the Gaussian noise model in this paper, but plan to extend the work to non-Gaussian noise in a follow-up paper. The Gaussian noise model is applicable to a wide range of underwater environments and is a good starting point for most underwater communication simulations.

An entire motivation paragraph spent volunteering where his own assumption fails — including citing the counter-evidence `[6]`, `[7]` — then recovering. The recovery sentence is deliberately modest: not "the model is general" but `is applicable to a wide range of underwater environments and is a good starting point for`.

## 5. How he argues — constraint → design principle

**Honest framing:** there is no thesis being defended here, no philosophy, no strategy advocated. The argumentative work is entirely (a) elimination of alternatives in the Introduction and (b) a short derivation chain in III–IV. What follows is the reasoning as it actually appears.

**Chain 1 — from requirement to problem decomposition.** The move is constraint → definitional consequence → formal requirement → split into subproblems:

> A Gaussian random process is fully characterized by its mean and covariance [8]. A hydrophone measures dynamic pressure variations (around a mean static pressure), and the measured Gaussian noise is therefore, by definition, zero-mean. We therefore have: {x̄ᵢₜ} ∼ 𝒩(0, R̄), where R̄ = [R̄ᵢⱼδ] is a N × N × (2L + 1) covariance tensor …

> Since our simulated noise must have similar statistical properties as the measured noise, we require: {xᵢₜ} ∼ 𝒩(0, R), with R ≈ R̄. The problem then reduces to two sub-problems:
> • Estimation of the covariance tensor R̄ from the measured noise samples {x̄ᵢₜ}, and
> • Generation of a noise sequence {xᵢₜ} with covariance tensor R ≈ R̄.

The physical justification (`A hydrophone measures dynamic pressure variations (around a mean static pressure)`) is what licenses the mathematical simplification (`is therefore, by definition, zero-mean`). He grounds a modelling choice in the instrument, not in convenience. `The problem then reduces to two sub-problems` is the pivot from motivation to method — one sentence, then a bulleted split that *becomes the section structure* (III and IV).

**Chain 2 — from goal to optimisation problem.** Stated as an intent before it is stated as mathematics:

> We wish to determine mixing coefficients {αᵢⱼτ} such that the covariance tensor of {xᵢₜ} matches the covariance tensor R̄ of the measured noise samples.

> We determine mixing coefficients {αᵢⱼτ} such that the covariance tensor R of the generated noise matches the covariance tensor R̄ of the measured noise samples by solving an optimization problem: …

Note the paired sentences: `We wish to determine …` announces the goal, then after the covariance derivation the identical clause returns as `We determine … by solving an optimization problem`. Wish, then do. The derivation in between is closed with a bare justification clause rather than a lemma: `since 𝔼[z_{k(t−τ)} z_{m(t+δ−ν)}] = 1 only if k = m, t−τ = t+δ−ν and 0 otherwise.`

**Chain 3 — constraint → practical design principle (the closest thing to a "principle" in the paper).** Section V is where a constraint becomes advice, and it is the most instructive passage for a rewriter:

> In order to aid optimization, it is advisable to scale the measured passband noise {x̄ᵢₜ} to have approximately unit variance for each channel. Scaling does not change the correlation properties of the noise, but alters the absolute noise level. The scale factors can be recorded and the scaling can be undone after generating random noise samples, if the application requires generated noise levels to match the measured noise levels.

The three-beat form: **advice** (`it is advisable to …`) → **what it costs you** (`does not change …, but alters …`) → **how to get it back** (`can be recorded and … can be undone …, if the application requires …`). He never gives advice without immediately stating its side effect and its remedy. Same pattern with the optimiser:

> The problem is easily solved using gradient descent methods [10], with a good initial guess to start iterative optimization. We recommend an initial guess of αᵢᵢ₀ = 1 ∀ i and αᵢⱼτ = 0 otherwise.

`easily solved` is asserted, not shown — but the sentence immediately concedes the condition (`with a good initial guess`) and then supplies the guess. The concession is what makes the unsupported `easily` acceptable.

**Chain 4 — the utility argument in the conclusion** (constraint on data → what the method enables → comparison to the alternative). See §8; the chain runs `While ambient noise data must be obtained by field measurements, only a small amount of training data is required … Once the model is trained, it can be used to generate an infinite amount … While large acoustic recordings … could potentially serve the same purpose, the storage and distribution of channel noise covariance tensors is much easier and more cost-effective.` Again: concede the constraint in the `While` clause, win in the main clause.

## 6. Rhetorical devices

**Report of absence, stated plainly, because you asked:**

- **Questions to the reader: none.** Not one question mark in the paper.
- **Analogies or metaphors: none.**
- **Humour: none.**
- **Provocations, contrarian framing, "conventional wisdom says X": none.** The closest is `the assumption of white noise becomes untenable` — `untenable` is the strongest word in the paper, and he uses it twice (abstract and Introduction).
- **Direct address ("you", "the reader", "note that"): none.** No `Note that`, no `Observe that`, no `Recall that`.
- **Exclamation marks, italics for emphasis, bold in body text: none.**

**What is present:**

- **Imperatives / jussives, mathematical only, 2 instances:** `Consider an acoustic communication system with N receive hydrophones (channels) operating at a sampling rate of fₛ samples per second.` and `Let {zᵢₜ} be independent standard Gaussian random variates:`
- **Impersonal "one", 1 instance, used to introduce a strawman he will demolish:** `One may use recorded ambient noise from the ocean as additive noise samples for simulation.`
- **Advisory first person, 2 instances:** `We recommend an initial guess of …`; `it is advisable to scale …`
- **Guided-looking "we see", the paper's characteristic move in Results (4 instances):** `We see that it agrees well with …`; `we see that the timeseries and spectrograms … are also very similar`; `We can clearly see that most of the energy in the water column is propagating in the horizontal direction`; `the same structure can be seen in the generated noise`. The reader is walked through the figures in the first person plural rather than told a number.
- **Self-annotating figure captions** — the caption teaches you how to read the plot, which is unusual and worth stealing: `Figure 2: Normal probability plot of each of the 12 channels in the KAM11 ambient noise dataset. Data points along the diagonal of a normal probability plot indicate an agreement with Gaussian statistics. Significant deviations from the diagonal suggest non-Gaussianity.` Also `The y-scale is proportional to the acoustic pressure.` and `The color scale is in dB.`
- **Acknowledgement in third person about himself** — a distinct register shift, and he thanks reviewers: `The author would like to thank James Preisig, Milica Stojanovic, Paul van Walree, Andrew Singer and Li Zhengnan for initial discussions that helped shape the work presented here, and for graciously providing the ambient noise data used to validate the work. The author would also like to thank the anonymous reviewers for their valuable suggestions that have helped improve the presentation of the work in this paper.`

## 7. Claims he cannot fully support; limitations and caveats

This is the richest part of the paper for a rewriter, because the caveats are numerous and are placed *early* rather than quarantined at the end.

**Scope limitation, volunteered in the Introduction with its own counter-citations:**
> We limit our discussion to the Gaussian noise model in this paper, but plan to extend the work to non-Gaussian noise in a follow-up paper.

Preceded by the evidence against himself: `Warm shallow waters, however, exhibit a significant amount of non-Gaussian noise due to snapping shrimp and other biological sources [6]. Some polar regions also exhibit non-Gaussian noise due to ice cracking and bubbles from melting glaciers and icebergs [7].` Followed by the recovery: `The Gaussian noise model is applicable to a wide range of underwater environments and is a good starting point for most underwater communication simulations.`

**Data-quality caveat, volunteered about his own dataset:**
> The net sensitivity of the receiver system in KAM11 has not been accounted for, and hence the recorded data should be considered uncalibrated for absolute acoustic pressure.

**Assumption checked rather than asserted:**
> The training data was verified to be stationary by checking the first and second order statistics in 1-second windows over the duration of the sample.

**The headline claim, fenced by a parenthetical:**
> The noise is statistically indistinguishable from noise recorded during experiments in areas where the ambient noise is stationary (over the timescales of interest) and Gaussian.

`statistically indistinguishable` is a strong claim that is *not* supported by any statistical test anywhere in the paper — there is no KS test, no p-value, no error metric. He supports it entirely with six figures and the phrase `agrees well`. The mitigation is the double conditional: `in areas where the ambient noise is stationary (over the timescales of interest) and Gaussian`. **This is the paper's main unsupported claim, and the technique is: strong verb, immediately fenced by conditions.**

**Modality on the forward-looking claim** — the speculative sentence is marked with `may` and the rival option with `could potentially`:
> The method described above may be used to publish channel noise covariance tensors to complements channel replay datasets …
> While large acoustic recordings from the field could potentially serve the same purpose, the storage and distribution of channel noise covariance tensors is much easier and more cost-effective.

**Unsupported convenience claims left bare** (worth noting as a licence, not a virtue): `Estimating the covariance tensor R̄ … is straightforward.`; `The problem is easily solved using gradient descent methods [10]`. No convergence proof, no runtime, no complexity analysis appears in the paper.

**Two typos exist in the published text and are reproduced above verbatim, not corrected:** `to complements channel replay datasets` (Discussion), and `Figure 6: A comparison of frequency-wavenumber plots for for KAM11 ambient noise dataset …` (doubled "for"). Also note the British-style doubled s in `focussed`, which is a genuine Chitre spelling habit, not an OCR artefact.

## 8. Conclusion, verbatim (Section VII, complete)

> ## VII. Discussion and Conclusion
>
> We presented a simple method that can be used to generate realistic additive multichannel Gaussian noise for use in underwater acoustic simulations. The noise is statistically indistinguishable from noise recorded during experiments in areas where the ambient noise is stationary (over the timescales of interest) and Gaussian. The generated noise retains the temporal and spatial correlations arising from frequency-dependence and noise directionality.
>
> In order to train the generative noise model, we require a sample of ambient noise from the environment of interest or a covariance tensor summarizing the noise statistics.
>
> While ambient noise data must be obtained by field measurements, only a small amount of training data is required to build the noise model. Once the model is trained, it can be used to generate an infinite amount of realistic noise samples. Benchmark channel replay datasets such as Watermark [4] provide a way for researchers to simulate acoustic propagation through a measured channel. The method described above may be used to publish channel noise covariance tensors to complements channel replay datasets, allowing researchers to not only simulate realistic acoustic propagation but also realistic ambient noise. While large acoustic recordings from the field could potentially serve the same purpose, the storage and distribution of channel noise covariance tensors is much easier and more cost-effective.

**Measured:** 9 sentences, 213 words, mean 23.7 words/sentence — noticeably longer sentences than the Introduction (16.8). Structure: 3 sentences of what-was-done → 1 sentence of what-it-costs-you → 5 sentences of what-the-community-could-do-with-it. It ends on a **community-infrastructure argument**, not on a results summary and not on "future work". The last sentence is a cost-benefit comparison against the incumbent practice.

## 9. Reusable lexicon — 100+ exact words and phrases from this paper

**Framing / opening moves**
`are often tested via` · `prior to real-world deployment` · `In order to accurately estimate the performance of` · `the signal distortions introduced by` · `These distortions include` · `While most … work has focussed on the former two` · `has received less attention` · `This paper is aimed at addressing this gap` · `One may use` · `Another common practice is to` · `The common practice of employing` · `This paper presents a simple technique for` · `The generative model presented in this paper addresses both these limitations` · `We demonstrate the method outlined in the previous sections by applying to` · `We presented a simple method that can be used to`

**Concession-and-defeat (the signature machine)**
`While this approach yields accurate results, it requires` · `While this approach is simple, it fails to capture` · `While ambient noise data must be obtained by field measurements, only …` · `While large acoustic recordings … could potentially serve the same purpose, …` · `Even in the case of` · `Given the wideband nature of` · `fails to capture the true nature of` · `fails to capture this correlation` · `becomes untenable` · `is untenable for` · `This limits the duration of`

**Connectives / logical glue**
`Moreover` · `Furthermore` · `however` (mid-sentence, comma-fenced) · `therefore` · `and therefore exhibits` · `and hence` · `Since` · `since` (clause-final justification) · `In order to` · `Once` · `then reduces to` · `We therefore have` · `as follows` · `such that` · `only if … and 0 otherwise` · `∀ i and … otherwise` · `not only … but also`

**Hedges, qualifiers, modality**
`typically` · `often` · `most` · `many` · `some` · `approximately` · `a significant amount of` · `a wide range of` · `a good starting point for` · `is aimed at` · `may be considered` · `may be used to` · `could potentially` · `should be considered` · `it is advisable to` · `We recommend` · `is straightforward` · `is easily solved` · `with a good initial guess` · `agrees well with` · `also very similar` · `clearly see` · `much easier and more cost-effective` · `statistically indistinguishable from` · `over the timescales of interest` · `has not been accounted for`

**Working verbs**
`undergo` · `reflect` · `capture` · `employ` · `exhibit` · `holds` · `lead to` · `addresses` · `limit our discussion to` · `plan to extend` · `Consider` · `Let` · `We wish to generate` · `We wish to determine` · `We determine` · `We compute` · `we require` · `is fully characterized by` · `measures` · `estimated as` · `matches` · `solving an optimization problem` · `summarized in` · `aid optimization` · `alters` · `can be recorded` · `can be undone` · `was used for training` · `bandpass filtered` · `to remove out-of-band noise` · `was verified to be stationary` · `retains` · `arising from` · `summarizing` · `provide a way for researchers to` · `allowing researchers to`

**Technical nouns and noun phrases**
`ambient noise` · `additive noise` · `underwater ambient noise` · `covariance tensor` · `mixing coefficients` · `passband noise sequence` · `standard Gaussian random variates` · `power spectral density` · `frequency-dependent power spectral density` · `spatiotemporal correlation` · `time-varying frequency-selective fading` · `multipath propagation` · `Doppler` · `receive hydrophones (channels)` · `spatial diversity` · `sampling rate` · `time index` · `time lag` · `maximum time lag` · `unbiased sample covariances` · `gradient descent methods` · `iterative optimization` · `initial guess` · `unit variance` · `scale factors` · `absolute noise level` · `normal probability plot` · `non-Gaussianity` · `frequency-wavenumber plots` · `noise directionality` · `normalized noise directionality plots` · `vertical array` · `water column` · `vertical wavenumber` · `elevation angle` · `bandlimited` · `out-of-band noise` · `net sensitivity of the receiver system` · `uncalibrated for absolute acoustic pressure` · `first and second order statistics` · `benchmark channel replay datasets` · `channel noise covariance tensors` · `storage and distribution`

**Caption formulas**
`A comparison of X for the KAM11 ambient noise dataset (top) and noise generated using the trained model (bottom).` · `The color scale is in dB.` · `The y-scale is proportional to the acoustic pressure.` · `Data points along the diagonal … indicate an agreement with … Significant deviations from the diagonal suggest …`

## 10. What differs here versus a journal paper

I have not re-read his journal papers in this session, so treat the contrasts as measured-here facts you can diff against your existing journal guide. Hard numbers first.

| Metric | This conference paper |
|---|---|
| Length | 5 pages, ~1,670 words of body text incl. captions; prose alone ≈1,300 words |
| References | **11 total**, ~1 per 150 words of body |
| Citations in Introduction | 7 markers (`[1]–[4]`, `[5]`, `[6]`, `[7]`) in 352 words — the Introduction carries **most of the paper's citations** |
| Citations in Sections III–VII | 4 total (`[8]`, `[9]`, `[10]`, `[11]`), plus one back-reference to `[4]` in the Discussion |
| Mean sentence length, Introduction | **16.8 words** (range 8–25) |
| Mean sentence length, Abstract | 19.5 words |
| Mean sentence length, Conclusion | **23.7 words** (range 15–32) |
| First person | `We` ×6, `we` ×4, `our` ×2; `I` **zero**; `The author` ×2 (Acknowledgement only) |
| Equations | 3 numbered + 3 unnumbered display lines. No theorems, no lemmas, no proofs |
| Figures | 7, all in Results; no schematic/system diagram at all |
| Algorithm boxes | 1 |
| Quantitative results | **zero** — no table, no error metric, no BER, no dB residual, no statistical test |

**Concretely different from journal practice:**

1. **Sentences are short and the paragraphs are shorter.** The Introduction runs 21 sentences across 4 paragraphs — 5, 8, 3, 5 sentences. The 8-word gap sentence (`This paper is aimed at addressing this gap.`) is a deliberate rhythmic stop. Journal prose does not usually afford single-clause paragraph-enders like this.

2. **No Related Work section at all.** Four papers' worth of prior art is dismissed in one subordinate clause: `While most channel modeling work has focussed on the former two [1]–[4], modeling of additive noise has received less attention.` The citation load is front-loaded into the Introduction and then essentially stops.

3. **First person plural is normal and frequent, and is used for actions, not just claims** — `We limit our discussion`, `We wish to generate`, `We compute`, `We determine`, `We recommend`, `We see that`, `We can clearly see`. Singular `I` never appears; when he must speak of himself (Acknowledgement) he switches to third person, `The author would like to thank`.

4. **Validation is visual and narrated, not tabulated.** There is no numeric agreement metric anywhere. The proof is `We see that it agrees well with the power spectral density of KAM11 noise as seen in Figure 1` and `We can clearly see that most of the energy in the water column is propagating in the horizontal direction (small vertical wavenumber) in both the KAM11 data and generated noise.` A journal version would almost certainly carry a table and a goodness-of-fit statistic. **This is the single biggest conference/journal delta in the paper.**

5. **Numbers appear only in the experimental setup, never in the abstract or conclusion.** The full inventory: `12-channel vertical array`, `20 cm spacing`, `47 m depth`, `100 m of water depth`, `55-second ambient noise sample`, `5-60 seconds`, file `1860532F0083_C0_S4`, `39.062 kSa/s`, `5–15 kHz band`, `L = 64`, `10 second multichannel noise sample`, `0.1-second sample`, `1-second sample`, `1-second windows`, `5 kHz`, `10 kHz`. All of these sit in two paragraphs of Section VI. Note the file name is given — reproducibility over polish.

6. **Informality shows up as directness, not as jokes.** `is straightforward`, `is easily solved`, `it is advisable to`, `We recommend`, `a good initial guess`, `much easier and more cost-effective`. These are practitioner registers; there is no colloquialism, no metaphor, no wink. Assertions like `easily solved` go unproven — a length budget the journal format would not grant.

7. **A live software URL sits in the body text, not in a footnote or data-availability statement:** `An implementation based on Algorithm 1 and scaling, as described above, is provided as an open-source Julia package at https://github.com/org-arl/NoiseModels.jl. This implementation was used to generate all the results in the next section.` The second sentence explicitly ties the released code to the reported results.

8. **Future work is displaced into the Introduction**, not the conclusion: `but plan to extend the work to non-Gaussian noise in a follow-up paper`. The conclusion instead ends on a **community-infrastructure pitch** (publish covariance tensors alongside Watermark-style replay datasets) — an argument about what the field should do, which is the only place this paper does anything resembling advocacy.

9. **Sentences lengthen as the paper proceeds** — 16.8 words in the Introduction, 23.7 in the Conclusion. Motivation is clipped; the closing argument is periodic and subordinating (four of nine concluding sentences open with a subordinate clause: `In order to …`, `While …`, `Once …`, `While …`).

10. **Typos survived to publication** (`to complements`, `for for`), consistent with a fast conference turnaround; the acknowledgement nonetheless thanks reviewers for improving the presentation.