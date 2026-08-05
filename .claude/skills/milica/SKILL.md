---
name: milica
description: Write, rewrite or review OFDM and underwater acoustic communications text in Milica Stojanovic's style — physics before algebra, every claim carried by a number, trade-offs closed with a design rule. Use when asked to write like Stojanovic, to match the OFDM literature's voice, to draft a receiver-design or channel section, or to check whether a draft argues the way her papers argue.
---

# Writing in Stojanovic's style

This is a **reference profile**, not the project's governing style. The `mandar`
skill governs house style. Use this one when the task is explicitly to write like
Stojanovic, or when you need a second opinion on how an OFDM argument should be
built. Where the two disagree, see the last section — do not silently blend them.

Evidence base: `reference papers/stojanovic_ofdm/` — 21 full-text papers, the
complete OFDM publication list (`ofdm_papers.md`), and a verbatim terminology
table (`lexicon.md`). Four of those papers are sole-authored; those carry the
most weight. The supervised journal papers (Aval, Tadayon, Ceballos, Zorita,
Radosevic, Tu, Yerramalli) show the style after a student has written the draft —
useful, but weaker evidence.

---

## THE ONE THING

**A property is never stated without its number, and a number is never stated
without its consequence for the design.**

Everything else in this file follows from that. The canonical instance, from the
2007 Sea Technology article, is three sentences long:

> "Because the speed of sound underwater (1500 meters/second) is much lower than
> that of the electro-magnetic waves in air (3·10⁸ meters/second), the resulting
> Doppler distortion is much more pronounced. An autonomous underwater vehicle
> may move at a speed of few meters/second, with the resulting Doppler rate
> a=v/c on the order of 10⁻³. Even in the absence of intentional motion, freely
> suspended transmitters and receivers are subject to drifting at a speed that
> may be a fraction of a meter/second in calm conditions."

Physical cause → the number → the order of magnitude → the case you thought was
safe, which is not. `on the order of` is the most frequent phrase in her prose
(7 per 10 000 words, twice the rate of her co-authors).

---

## THE FIVE MOVES

These five constructions do most of the work. A draft that reads like hers uses
all five; a draft that uses none of them is not in this style however correct it
is.

### M1. The trade-off, closed with a design rule

Never leave a trade-off open. Benefit, then `However,` the first cost, then
`Also,` the second cost, then `Hence, there is a trade-off`, then the rule.

> "For a given bandwidth B=K∆f, the bandwidth efficiency … increases with K.
> **However**, the symbol duration T=K/B increases as well, making it more
> difficult to track the channel on a block-by-block basis. **Also**, the carrier
> separation ∆f narrows, making the signal more vulnerable to Doppler. **Hence,
> there is a trade-off** in the selection of the number of carriers. **Ideally,
> one should choose the greatest K for which the receiver performance is still
> satisfactory.**"

The closing rule is always stated for the designer, in the impersonal `one` or
in the passive: *"that (M_T, K) pair should be chosen for which the bandwidth
efficiency is maximized while a pre-specified performance level is met."*

### M2. The condition, re-read several ways

Derive a constraint, then enumerate what it means. This is the single most
recognisable thing in her technical sections.

> "In order for such a solution to exist, the necessary condition is that
> K ≥ M_T L. This condition can be interpreted in several ways: (1) for a given
> number of carriers K, at most K/M_T channel coefficients can be estimated; (2)
> for a given channel span L, at least M_T L observations are needed, and (3)
> for given K and L, at most K/L data streams can be multiplexed."

One inequality, three readings, each one a sentence a designer can act on.

### M3. `While X, Y.` — concede, then defeat

Her workhorse pivot, at 4.8 per 10 000 words. The virtue goes in the subordinate
clause, the defeat in the main clause. She never calls a rival method bad.

> "**While** it offers an elegant solution to the multipath problem, OFDM
> requires extremely accurate synchronization."

> "**While** noncoherent signaling provides robustness to channel distortions,
> and still represents the preferred method in commercially available acoustic
> modems, it lacks the bandwidth efficiency necessary for achieving high-rate
> digital communications…"

> "**While** cyclic prefix is a traditional choice that enables FFT demodulation
> without any pre-processing, zero-padding saves transmission energy."

The `Although` variant carries a number in the concession:
*"**Although** the total communication bandwidth is very low (5 kHz), the system
is in fact wideband…"*

### M4. `In contrast` — the two-camp split

She organises a literature, a design space, or a comparison into exactly two
camps, names both fairly, and only then says which she takes.

> "Two approaches have been pursued: one based on the classical principles of
> pilot-assisted, block-oriented detection [1], [2], and another based on
> decision-directed, adaptive block processing [3]-[6]."

> "In block-oriented processing, these symbols must be known a-priori (pilots or
> null carriers). **In contrast**, block-adaptive processing utilizes symbol
> decisions, and channel estimation can benefit from signals received on all
> carriers."

Also used to set an acoustic quantity against its radio counterpart, which is
how she makes a reader feel a number:

> "For comparison, let us look at a highly mobile radio system. At 160 km/h (100
> mph), we have a = 1.5·10⁻⁷. … **In contrast to this situation**, a stationary
> acoustic system may experience unintentional motion at 0.5 m/s (1 knot), which
> would account for a = 3·10⁻⁴."

### M5. The parenthetical audit

A dry aside that checks the claim just made against the numbers just given. Short,
never arch.

> "The signal occupied the frequency range between 22 and 46 kHz. **(With a
> bandwidth of 24 kHz, and a center frequency of 34 kHz, this is certainly not a
> narrowband system.)**"

> "…it is not negligible with respect to the center frequency **– on the
> contrary, the two may be comparable.**"

---

## VOICE

| Context | Person | Evidence |
|---|---|---|
| Abstract | impersonal; the work is the subject, not the authors | "MIMO OFDM communication **is considered** for spatial multiplexing…"; "receiver structures … **are investigated**"; "A decision-feedback equalizer **is designed** which relies on…" |
| Abstract, supervised papers | `In this paper, we propose / explore / focus on` | Aval 2015, Radosevic 2014 |
| Choices in the body | `we` | "**we adopt** the framework of decision-directed adaptive block processing"; "**we recognize** that (10) can be re-written as"; "**we make use of** this approach in a MIMO system configuration" |
| Walking the reader | `let us` | "To put a channel model in perspective, **let us denote** by l_p the length of the pth propagation path"; "To illustrate the results of signal processing, **let us consider** an example of a K=1024 OFDM frame" |
| Advice to the designer | impersonal `one` | "**one should** choose the greatest K…"; "**one cannot** count on such a situation"; "prevents **one** from making the narrowband assumption" |
| Apparatus and procedure | passive, past tense | "an experiment **was conducted** at the Woods Hole Oceanographic Institution in the fall of 2005" |

Never `I`. Never `the authors` for yourself.

Sentence length: median 20 words, mode 10–19. Short sentences are frequent and
carry weight — *"There are no decision errors."*, *"Instead, it can be
reconstructed."*, *"The SNR is 20 dB."* Long sentences are broken with `i.e.,`,
`e.g.,`, `namely`, or a semicolon, not by nesting clauses.

---

## DOCUMENT SHAPE

### Abstract

Slot by slot, from the sole-author and supervised papers alike:

1. What is being considered, and for what. Impersonal. *"MIMO OFDM communication
   is considered for spatial multiplexing of independent data streams over
   bandlimited, frequency-selective underwater acoustic channels."*
2. The obstacle, with `however` inside the sentence. *"Long acoustic multipath,
   however, limits the applicability of MIMO channel estimation methods that
   require inversion of a matrix whose size is proportional to both the number of
   transmit elements and the multipath spread."*
3. The move, named by what it avoids. *"To overcome this problem, an adaptive
   algorithm is used that does not require matrix inversion…"*
4. What the move costs or saves. *"…thus reducing both the computational
   complexity and the overhead."*
5. The demonstration, **with the experimental envelope spelled out**. *"System
   performance is successfully demonstrated using real data transmitted over 1 km
   in shallow water, with a varying number of carriers (128-1024), transmitters
   (1-3), and modulation levels (4 and 8 PSK) in the 8-18 kHz band."*

Slot 5 is obligatory and is where her abstracts differ most from the field's:
distance, water, carrier count, transmitter count, modulation, band. Numbers in
the abstract are not merely allowed, they are the point.

### Introduction

Opens on the medium or the method, never on the paper and never on the importance
of the field:

> "High-rate, bandwidth-efficient underwater acoustic communications have
> traditionally used single-carrier modulation that relies on adaptive
> equalization to overcome the frequency-selective distortion of a multipath
> channel [1]."

> "Underwater acoustic channels are generally recognized as one of the most
> difficult communication media in use today."

Prior work is described by **mechanism, not by result**, and generously:

> "The adaptive algorithm [9] eliminates the need for matrix inversion by
> estimating each transmitter's response separately, having canceled the
> interference of other transmitter(s) using channel estimates from a previous
> block. This reference also provides optimal pilot sequences that simultaneously
> avoid matrix inversion and provide MMSE performance."

Close with the roadmap, in her clipped form:

> "The paper is organized as follows. After defining the system model in Sec. II,
> channel estimation is discussed in Sec. III. Sec. IV is devoted to performance
> illustration using real data transmitted over a 1 km shallow water channel in
> the 8-18 kHz band. Concluding remarks are made in Sec. V."

### Mathematics

- Displayed equation → `where` clause → **a sentence saying why the term is
  modelled that way physically**. The third step is hers specifically:
  *"Notably, since all the signal processing is performed digitally, there is no
  mismatch between the frequencies of local oscillators, and the phase distortion
  is modeled as a consequence of the Doppler effect."*
- Name the load-bearing equation and refer back to it as **the modeling
  equation**: *"can thus be used to estimate the Doppler factor via the modeling
  equation (2)"*, *"This form serves as a basis for the design of the channel
  estimator."*
- Say outright which model the design rests on: *"The signal model is crucial to
  the design of the receiver algorithm."*
- State the assumption that makes a term negligible, in symbols, at the point of
  use: *"Assuming that a_t(n)f_k << ∆f, ∀t,k,n, inter-carrier interference is
  treated as additional noise."*
- Footnotes carry the side facts that would break the line of argument — an
  earlier experimental finding, a unit convention, an alternative choice of
  training sequence.

### Experimental sections

Every experiment is placed before it is analysed: **month and year, water body,
depth, range, array, band, modulation, block structure**.

> "an experiment was conducted at the Woods Hole Oceanographic Institution in the
> fall of 2005. The transmitter and receiver were deployed from two vessels
> stationed in 12 meters of water at a distance of 2.5 kilometers. The receiver
> employed a 12-element, 1.5 meters long vertical array."

The composite results figure is a signature: raw received frame, phase estimates,
channel estimates across all receivers, MSE in time, MSE in frequency — and a
**parameter box burned into the figure** listing K, N, L, A, J, P, µ, overlap-add
window, MSE, BER and the code. Receiver settings live in the figure, not the
caption.

Two tables normally accompany it: the signal parameters (K, N, ∆f, T, β) and the
derived bandwidth efficiency in bits/s/Hz.

### Conclusion

Three beats, in this order:

1. **Restate the design constraints in words**, having earned them.
   *"Efficient use of acoustic bandwidth implies the need for a large number of
   carriers in an OFDM system, and multiple transmitters to support spatial
   multiplexing of data streams. However, the channel imposes limits on the
   system design."* — then the algebra, in prose, ending in a single bound.
2. **What the receiver does and what was demonstrated**, with the envelope again.
   *"Experimental results demonstrate successful operation of a 3 × 12 MIMO
   system, using 4 and 8 PSK with 1024 carriers in a 10 kHz acoustic bandwidth
   over 1 km in shallow water."*
3. **The consequence**, usually about implementation.
   *"These results serve as an encouragement for a real time implementation of
   MIMO OFDM in an acoustic modem."*

**She does write future work in the conclusion**, split into near and long term:
*"Future work will focus on experimental testing in varying conditions, and
notably in mobile scenarios. … Longer term research should address the
possibility of optimal energy allocation across subbands…"* This is a direct
conflict with house style; see the last section.

---

## HONESTY MOVES

Obligations, not decorations. Each is attested.

- **Say the shown data set is typical, not best.** *"In general, consistently
  good performance was observed at four different receiver locations… We report
  here on a typical data set."*
- **Report the case that failed, and say what it confirms.** *"Excellent results
  were obtained for all K below 1024. At K=2048, however, the performance
  degraded, confirming our conjecture about the existence of an optimal number of
  carriers to use in a given OFDM system."*
- **Give the spread, not just the headline.** *"The overall system performance …
  was observed to vary by a few dB depending on the particular conditions."*
- **Check the assumption against the measurement you just reported.** *"The
  absolute level of the Doppler rate did not exceed 10⁻⁵, and the assumption of
  negligible ICI is thus justified."*
- **Refuse to conclude from thin evidence.** *"Some histograms resemble a Ricean
  distribution; however, more measurements need to be made before firm
  conclusions can be drawn."* And: *"Channel coherence times below 100 ms have
  been observed [6] but not often."*
- **Say when the field has no answer.** *"In the absence of good statistical
  models for simulation, experimental demonstration of candidate communication
  schemes remains a de facto standard."*
- **Disclose an arbitrary choice as arbitrary.** *"The signals were also coded
  using the BCH(64,10) code. This code was chosen arbitrarily; a practical
  implementation could settle for a less powerful, more bandwidth-efficient one."*
- **Say when the optimum is not the right choice.** *"although the MIMO MSE curves
  exhibit a minimum, the corresponding value of K may not necessarily be the
  designer's best choice."*
- **Bound the scope of a simplification.** *"The individual path dispersion … can
  be ignored for systems whose maximal frequency lies well below the channel
  cutoff… This is normally the case in systems that are in use today; however, as
  transducer technology advances and higher bandwidths become available, this
  effect may become non-negligible."*

---

## TERMINOLOGY

The full table is `reference papers/stojanovic_ofdm/lexicon.md`. Load it before
writing. The traps that catch a draft most often:

| Write | Not |
|---|---|
| OFDM **block** | OFDM symbol |
| **carrier** / **subband** (early), **subcarrier** (later) | tone |
| **bandwidth efficiency** [bits/second/Hz] | spectral efficiency |
| **multipath spread** | delay spread |
| **channel sparsing**, **significant coefficients** | pruning, dominant taps |
| **post-FFT processing** | frequency-domain equalization |
| **overhead**, **pilot overhead** | training cost |
| **figure of merit** | metric |
| **viable** | promising, attractive |
| **the modeling equation** | the model |

Notation is fixed across twenty years — `k` carrier, `n` block, `t`/`r` transmit
and receive element, `K`, `L`, `J`, `A`, `M_T`, `M_R`, `∆f`, `T`, `Tg`, `T'`,
`a(n)`, `θ_k(n)`, `h_l(n)`, `H_k(n)`, `β`, `µ`, `λ`, `α`, `γ`. Renaming any of
them takes the draft out of this style. Prime is conjugate transpose, boldface is
a column vector over receiving elements, hat is an estimate, check is a
prediction, bar is a decision.

---

## WHERE THE TWO HOUSE STYLES DISAGREE

Real conflicts, verified by grep over the sole-author corpus. Decide which style
governs **before** drafting; do not average them.

| Point | `mandar` (house style) | Stojanovic |
|---|---|---|
| `crucial`, `elegant`, `framework`, `paramount`, `natural` | banned | all five attested in her sole-author prose, used sparingly and in earnest |
| Numbers in the abstract | prohibited | obligatory — the experimental envelope |
| Future work in the conclusion | prohibited; belongs in the introduction | present, split into near and long term |
| Conclusion | must not summarise the paper | restates the design constraints, then the demonstration |
| Vocabulary | closed set; coining a term stops the draft | open; she names things freely (*sparsing*, *pre-combining*, *the modeling equation*) |
| Abstract voice | `We show / We illustrate` | impersonal — the work is the subject |
| Concession | `While X, it Y` | same construction, same frequency — **they agree here** |
| Regime-bounded claims | required | required — **they agree here** |

`novel` and `state-of-the-art` appear nowhere in her sole-author prose, and both
styles ban them. They do appear in the supervised papers — `novel` in Yerramalli
2012 and Aval 2015, `state-of-the-art` in the handbook chapter, Tu 2011 and
Socheleau 2012 — so a supervised paper is not by itself evidence that a word is
hers. When the two disagree, the sole-author corpus governs.

---

## BEFORE DECLARING A DRAFT FINISHED

1. Does every property carry a number, and every number a design consequence?
2. Is every trade-off closed with a rule the designer can apply?
3. Has each derived condition been re-read in at least two ways?
4. Does the abstract state distance, water, band, carrier count and modulation?
5. Is every dismissed alternative granted its virtue in a `While` clause first?
6. Does the experimental section give month, year, place, depth, range and array?
7. Are the receiver settings in the figure rather than only in the text?
8. Has any assumption that makes a term negligible been checked against the
   measurement reported?
9. Is the shown data set described as typical, or is it quietly the best one?
10. Are all symbols the ones in `lexicon.md` §7?
11. If the document must also satisfy `mandar`: has the conflict table above been
    resolved explicitly with the user rather than blended?
