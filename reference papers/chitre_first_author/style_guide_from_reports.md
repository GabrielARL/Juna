# Style guide — evidence: ARL project reports (D1 Ch1-2, MUSIQUE-D4)
# NOTE: reports are multi-author. D1 Chapter 3 was excluded (it is gab.tex verbatim).
# A second guide built from Chitre FIRST-AUTHOR papers is the stronger evidence.

# THE CHITRE STYLE GUIDE
### A mechanical rewriting manual for papers, tutorial decks, and slide talks on underwater acoustic communications

**Sources and weighting.** Two profiles were used. `[D1]` = AAC D1 v1.1, Ch. 1 "Introduction" and Ch. 2 "Adaptive Communications" (high confidence, PI-authored). `[D4]` = MUSIQUE D4 Final Report, Ch. 1, 2.1, 2.3, 3.1, 3.3 (high confidence). Quotes tagged `[D4-med]` come from the numeric-results subsections (2.2.2, 2.2.3, 3.2.x), which the profiler rated MEDIUM — use these as corroboration only, never as your sole model for a construction. **Dropped entirely:** D1 Ch. 3 (flagged as co-author, not read) and the equation-dense derivation bodies of D4 §2.1.4–2.1.5; only the connective and glossing sentences wrapped around those equations are retained, because those are the editorial hand. Do not imitate long algebraic derivation as a rhetorical mode — it is exactly what was excluded.

**The one genuine conflict:** D1 uses contractions freely; D4 has none. Resolution rule is given at §3, R3.9. Everything else in the two profiles is mutually reinforcing and is stated below as a single rule set.

---

## 1. STRUCTURE

### 1.1 Recipe for a whole document

Execute in this order. Do not insert steps.

1. **No abstract. No executive summary. No epigraph.** The document begins with substance on line one.
2. **First sentence, one of exactly two forms:**
   - *Deliverable/report form* — say what the document is, with a date, then go straight to bullets: "This is the final report for the MUSIQUE project than we undertook over the past 3 years, starting 25 March 2022. The key project objectives were:" `[D4]` (the "than" is an original typo — do not imitate the typo, imitate the flatness).
   - *Paper/technical form* — open on the problem domain, not on yourself: "Acoustic communications in underwater environments face significant challenges due to the complex and highly variable nature of acoustic propagation, multipath effects, and high ambient noise from natural and anthropogenic sources." `[D1]`
3. **Objectives as a bulleted list**, each bullet one fragment or one sentence.
4. **Background/prior-work section.** Reference prior work by *project or deliverable name in prose*, not by citation cluster: "This project builds upon specific work done in Project MUSIQUE where we developed several promising technology components that may be used for improving communication performance." `[D1]` Ceiling of one numbered citation per chapter: "inspired by the technique outlined in [1]" `[D4]`.
5. **Last sentence of Background closes the loop back to the project.** Mandatory: "This project addresses these limitations by developing advanced acoustic communication techniques and adaptive communications protocols designed to maximize communication capacity in dynamic underwater environments." `[D1]`
6. **Scope/aim, in plain first person plural:** "We aim to develop an adaptive communications protocol to optimize communication parameters automatically." `[D1]`
7. **Roadmap — never "The remainder of this chapter is organized as follows."** Instead name chapters by their content: "The main focus of this deliverable, however, is on MIMO communications (Chapter 2), BSS (Chapter 3), D-FEC decoding (Chapter 6), and rapid link adaptation (Chapters 7 to 8)." `[D4]` and "We report on progress on tasks 1, 2 and 3 in Chapter 2." `[D1]`

### 1.2 Recipe for a chapter

1. **Opening sentence = the platform, the general physical claim, or the scenario.** Never a literature review, never a definition of terms.
   - Platform: "Subnero modems use UnetStack — an open-architecture underwater networking stack developed at ARL. Being software-defined, the modems support many modulation and forward error correction (FEC) techniques." `[D1]`
   - General claim before underwater specialisation: "Communication systems with multiple transmit and receive antennas can theoretically benefit from multi-input multi-output (MIMO) communication." `[D4]`
   - Scenario construction: "In multi-node networks sharing an acoustic medium, transmissions from each node use the same frequency band. If such transmissions arrive at a receiver simultaneously, a collision is said to have occurred, and it usually leads unsuccessful reception for both transmissions." `[D4]`
2. **Second move: terminology, if the field is confused.** "There is much confusion on the terminology used related to single/multiple input/output systems. … With this in mind, we use the following terminology consistently in this project:" `[D4]`
3. **Motivation paragraph, ending on the project's aim as a one-sentence declaration.** This is where the single permitted exclamation mark lives: "That is the goal of the work on adaptive communication in this project!" `[D1]`; "This is the aim of the blind source separation (BSS) research in this project." `[D4]`
4. **Theory → Experiment → Discussion**, in that order, for empirical chapters `[D4]`.
5. **Chapter close, one of exactly two forms:**
   - A **Discussion** section that opens on the yardstick, not the finding — "MIMO with 3 transmitters and 3 or more receivers has a theoretical maximum data rate of 3x a SISO/SIMO system." `[D4]` — and that restates *every* failure in plain words before ending.
   - A **numbered "Next steps"** list of actions `[D1]`.
6. **No chapter summary paragraph. No "contributions of this chapter" bullets.**

### 1.3 Recipe for a section

1. Open with **the aim, the prerequisite, or the requirement** — never with apparatus and never with a definition of the section's own scope:
   - Aim: "Now we shift our focus to determining b(theta|xi). We begin with some simplifying assumptions:" `[D1]`
   - Prerequisite: "In order to understand how continuous link adaptation would work, one has to first understand the flow of data in UnetStack." `[D1]`
   - Requirement: "In order to test MIMO theory at sea, we require modems that can transmit synchronously from multiple transmitters." `[D4]`
   - Purpose-then-place-then-date: "To test BSS, we conducted an experiment at St. Johns Island in November 2024." `[D4]`
   - Expectation to be tested, before results: "As FH-BFSK is resilient to collisions, we expect that many FH-BFSK frames would be detected successfully in spite of them colliding at the receiver." `[D4-med]`
2. **Stock-taking sentence when a build completes:** "We now have all the pieces in place to write down the algorithm for recommending a set of OFDM parameters theta (K, L, M, B and k0), frame length N, and code rate R, given CSI xi." `[D1]` Reuse the same construction to open the forward-looking section: "We now have a physics-based algorithm that is able to recommend OFDM schemes based on opportunistic CSI." `[D1]`
3. **Validation sections open by admitting what was done to get there:** "In deriving the OFDM performance model, we made several assumptions, simplifications and approximations." `[D1]`
4. Close a section by **naming what is next**, not by summarising: "In the next few sections, we will focus our attention to the estimation of PSR." `[D1]`

### 1.4 Where motivation sits

Sentences 1–4 of any chapter or section, and nowhere else. It is never revisited as a "why this matters" paragraph later. The motivation always takes the shape: *what people do today* → *why it does not scale or cannot be automated* → *what we therefore want*. Canonical: "By dynamically choosing modulation type, modulation parameters and FEC rate, we are able to adapt to a host of channel conditions, providing the best communication possible in those conditions. However, today, this adaptation requires human expertise, and isn't automated." `[D1]`

### 1.5 Where limitations sit

Four legal positions, and no others:

1. **Inline, at the exact sentence where the choice is made.** "This simplifies the channel estimation, as we shall see, but is inefficient in terms of data rate." `[D4]`
2. **In a parenthetical aside** attached to the claim it qualifies. "they are primarily data-driven (with a little bit of physics encoded in them)" `[D1]`
3. **In a footnote**, so the main text stays assertive `[D4]` — e.g. the footnote explaining that "Communication performance is often not just a function of range. The channel geometry and variability plays an important role, and often at short-to-medium ranges in shallow waters, the MF channel can be more complicated than at longer ranges." `[D4]`
4. **Restated in the Discussion**, in plain words, in the same sentence as the positive result: "In less favorable conditions, MIMO failed to communicate robustly and SISO performance was marginal, but spatial diversity combining (SIMO) retained the ability to communicate robustly." `[D4]`

**Hard rule:** a failure that appears in a results section must reappear in the discussion. A limitation is never deferred to a "Limitations" heading — there is no such heading.

---

## 2. THE ARGUMENT PATTERN

### 2.1 The five-beat move from problem to solution

Write it in this order, one short sentence or clause per beat.

1. **State the general principle as it holds elsewhere.** "Traditional MIMO processing assumes transmissions from M transmit antennas arrive synchronously at the N receive antennas. For radio communications, this assumption is a good approximation of reality, as the speed of radio waves ensures that the time difference due to different path lengths between antennas is negligible."
2. **Name the underwater violation.** "In underwater communication systems, however, the low propagation speed of acoustics can lead to significant violations of this assumption."
3. **Convert the violation into a requirement.** "In order to use conventional MIMO processing in underwater acoustic communication systems, we require the symbol length to be much more than the arrival time spread across all transmit-receive pairs."
4. **Concede the cost of that requirement, then name the technique that pays it.** "While this would lead to very low data rates in single carrier communication, OFDM is well suited to meet this constraint."
5. **Ground it in the hardware you actually have.** "Subnero modems use OFDM for high-speed communication, and so are well placed to implement MIMO processing." (all `[D4]`)

### 2.2 How he dismisses an alternative

Never by calling it wrong. Always by one of these four:

- **By cost/efficiency.** "Even when some links support large transfers, such transfers are not efficient. So links have a recommmended transfer unit (RTU) which may differ from the MTU." `[D1]`
- **By economics of the use case.** "Link adaptation is unnecessary for these, since the amount of data to transfer is too little to benefit from the adaptation." `[D1]`
- **By quantified trade, giving the alternative its due first.** "For method 1, we used a pilot spacing of 9 carriers. For this method, if we choose P = 9, this represents 11% pilots and 89% data carriers — a significant improvement over method 1. However, the estimation procedure in method 2 is more susceptible to noise and so we recommend a higher number of pilots. Even if we choose a conservative P = 4, this represents 25% pilots and 75% data carriers, which potentially gives us a higher data rate than method 1." `[D4]`
- **By showing it is a special case of yours,** which lets you adopt yours "without any loss of generality": "We see that the 2-parameter empirical model is a much better fit. The empirical model is closely related to the Jakes Doppler model — it simplifies to the Jakes Doppler first-order approximation for nu1 = 0 and nu2 = -pi^2 fD^2. We can therefore adopt the empirical model without any loss of generality, fitting a Jakes Doppler model as a special case when the time-variability matches it." `[D1]`

**And when you dismiss something, still say what it is good for:** "At long ranges, incoherent modulation techniques such as FH-BFSK are more suitable. These yield low data rate (tens of bps), but provide very robust performance, as demonstrated up to 20 km during the 'long-range robust communication' project." `[D4]`

### 2.3 Pre-empting the reader's objection

Name the objection in the reader's own words, then defeat it with the use case. Canonical: "While this might seem restrictive at first glance, it is exactly the large datagrams that benefit from the increased data rate via link adaptation. The overhead of adaptation is simply not worth it for small datagrams, since the overhead outweighs any benefit." `[D1]`

### 2.4 Handling a claim the evidence only partly supports

Six licensed moves. Use one; do not stack them.

1. **Concede the gap between agreement and truth, in one sentence, before anyone asks.** Canonical: "While the good match between model and simulation is encouraging, it does not guarantee a good match between model and reality. The simulation is time invariant, whereas real channels are time varying." `[D1]`
2. **State the good match, then the exception, then quantify the exception.** Canonical: "We see a good match between our model and measurements, except for two sets of outliers at K = 4096 and K = 8192. For these sets, the model underpredicts the BER by roughly a factor of 2." `[D1]`
3. **Scope the requirement so the unsupported region stops mattering.** Canonical: "In practice, we are only interested in accurately modeling OFDM performance when OFDM is likely to work; when OFDM fails, it is sufficient for us to predict that it would fail, even if we don't predict the BER accurately. We therefore choose not to add complexity to our model to handle this high-BER regime accurately, as the performance of the current model to predict BERs up to about 15% accurractely is sufficient for our needs." `[D1]`
4. **Turn the defect into a deliberate choice, if it errs safe.** Canonical: "For some code rates, the model is somewhat conservative — this is intentional, as we would want the link adaptation to err on the side of safety." `[D1]`
5. **Accept a weaker approximation with a reason and a practical warrant.** Canonical: "The QPSK version isn't as accurate as the BPSK version, as the differential QPSK BER does not have a nice closed form expression. However, it is a slightly conservative approximation that works well in practice." `[D1]`
6. **Justify calibration by naming the failure mode of the clean version.** Canonical: "The ideal expression uses Delta = 0, but that yields over-optimistic PSR at high BER. We use a calibrated form with Delta = 2 + 90b to get curves similar to ones we observe with the LDPC implementation in Subnero modems. We adopt this calibrated FEC model from here on." `[D1]`

### 2.5 Handling failure

State it flatly, in the same breath as the response, with the date and place in parentheses. Canonical: "Unfortunately, this approach failed in practice (during preliminary tests conducted in November 2024 at St. Johns Island) as the channel varies between OFDM blocks sufficiently for the quasi-static assumption to be invalid. We therefore had to develop a novel method of estimating all channel matrices from a single OFDM block with a small number of pilot carriers." `[D4]`

Quantify the obstacle before offering the workaround: "Since we have MN unknown channel coefficients and only min(M,N) equations, this is a severely underdetermined linear system and cannot be inverted to obtain H_i." `[D4]`

Then the pivot sentence that unlocks the solution is always short and starts with "We note": "We note, however, that the channel matrices H_i are not independent." `[D4]`

### 2.6 Explaining a bad number

Never excuse it. Give the physical mechanism, in short sentences, one reason each. Canonical chain: "The limited bandwidth available in the VLF band is not suitable for further sub-division, and hence multi-carrier modulation (e.g. OFDM) is not well suited for VLF communication. Even with a modest number of carriers, OFDM symbols become long in duration and hence see a lot of time-variability in the channel. OFDM is not robust to channel variability and performs poorly. Phase jitter resulting from scintillation due to inhomogeneities in the water column makes OFDM also unsuitable for long range communication systems." `[D4]`

And for a counter-intuitive number: "While the signal to noise ratio (SNR) is indeed better at 250 m as compared to 750 m, the poorer performance of all OFDM schemes can be attributed to a more difficult channel geometry and variability." `[D4-med]`

### 2.7 Analogy as the explanatory device of last resort

One analogy per chapter, to a system the reader uses in daily life, developed for 3–4 sentences and then dropped completely. Canonical: "This is akin to how maritime VHF voice communications work. All ships tune in to VHF channel 16 by convention. When one ship wants to communicate with another, it initiates the communication on channel 16. Then both ships agree to switch to another VHF channel for a conversation, but after that conversation is completed, both ships switch back to channel 16 to enable other ships to initiate communication when necessary." `[D1]` Shorter form: "Terrestrial wireless communication systems such as 4G and WiFi use MIMO gains to improve network throughput." `[D4]`

### 2.8 Verdicts

End an empirical chapter with an explicit, conditional verdict — never an unconditional one: "We conclude that MIMO OFDM is indeed a feasible option when high rate MF communication is required in favorable channel conditions." `[D4]`

---

## 3. SENTENCE-LEVEL RULES

**R3.1 — Person: first person plural, always, as the acting subject.** Covers intention, choice, observation and failure alike.
> "We focus on tuning only these during continuous adaptation." `[D1]`
> "We adopt this calibrated FEC model from here on." `[D1]`
> "we were unable to improve the performance of MF OFDM BSS any further" `[D4]`

**R3.2 — Never first person singular. Never "the authors", "this report", "the present work".** There is no "I" and no third-person self-reference anywhere in either source.

**R3.3 — Active voice for every decision the team made.** Never "it was decided that", never "an approach was developed".
> "We therefore did not pursue VLF communication at ranges where MF communication is more suitable." `[D4]`

**R3.4 — Tense: present for models, mechanisms and figure readings; past for what was done at sea.**
> Present: "D(.) is usually a deterministic function that is known, but Pi(.) can be difficult to estimate." `[D1]`
> Past: "3 MF MIMO OFDM datasets were collected on the 24th and 25th, and 2 VLF MIMO OFDM datasets were collected on the 26th" `[D4]`
> Future, flat, for work not yet done: "Experiments will be undertaken in the next year to test and fine tune the protocol in Singapore waters." `[D1]`

**R3.5 — One idea per sentence. Build paragraphs as chains of short sentences.**
> "We see 3 distinct distances for the 3 datasets we collected over 2 days. The second panel shows the number of OFDM carriers used. We rotated through 1024, 2048 and 4096 carriers during each dataset." `[D4-med]`

**R3.6 — Interleave one very short declarative among the longer explanatory sentences.**
> "We need to modify the model to correct this." `[D1]`

**R3.7 — No semicolons chaining clauses. Full stop, new short sentence.** `[D4]`

**R3.8 — No em-dash asides. Caveats go in parentheses; interruptions use a spaced dash.**
> "UnetStack - an open-architecture underwater networking stack developed at ARL" `[D1]`
> "nu1 and nu2 require an OFDM transmission from the peer node (a FH-BFSK CONTROL frame is not sufficient)" `[D1]`

**R3.9 — Contractions: decide by document class.** This is the only point where the two sources diverge, so apply this decision rule mechanically. In a **final report, journal paper or externally-facing deliverable, use none** — "cannot", "does not", "did not", "do not" `[D4]`. In an **internal progress deliverable, tutorial deck or spoken talk, contractions are permitted, but only on negations and only in motivating or editorial prose**, never inside a modelling or derivation passage:
> "this adaptation requires human expertise, and isn't automated" `[D1]`
> "even if we don't predict the BER accurately" `[D1]`

**R3.10 — Exclamation marks: at most one per chapter, and only for the project's aim or for a number that genuinely surprised the group.**
> "That is the goal of the work on adaptive communication in this project!" `[D1]`
> "if the channel conditions change (as they inevitably do!)" `[D1]`
> "However, even with the improvement, 69% of the DATA frames were lost!" `[D4]`

**R3.11 — No question marks. Convert every rhetorical question into a declarative naming the question, then answer it.**
> "The key question we need to answer is whether the Jakes Doppler model is a good model for underwater channels. To answer this, we extract channel estimates from underwater channel measurements made in Singapore waters" `[D1]`

**R3.12 — Hedges are single, specific and quantified. Never stacked.**
> "typically ~100 bps"; "somewhat conservative"; "slightly conservative"; "roughly a factor of 2"; "up to about 15%" `[D1]`
> "we expect this condition to be generally met"; "likely destroys the orthogonality" `[D4]`

**R3.13 — Mark the normal case with "usually"/"often" before naming the exception.**
> "D(.) is usually a deterministic function that is known, but Pi(.) can be difficult to estimate." `[D1]`

**R3.14 — Every named threshold or nominal parameter carries an example value in parentheses.**
> "for some threshold eta_L (e.g., 0.95)"; "less than some T_max (e.g., 1 second)"; "nominal values of B and k0 (e.g., B = 0.4, k0 = 0)" `[D1]`

**R3.15 — Recommendations are phrased as recommendations, with a tunable and a suggested range and the meaning of each end.**
> "it is recommended that the BER from the OFDM performance model be inflated by a tunable factor zeta (typically between 1.5 to 3, with 1.5 being agressive and 3 being conservative)" `[D1]`

**R3.16 — Small integers as digits, not words.**
> "3 transmitters and 4 receivers, this gave us 12 different SISO systems"; "With only 3 hydrophones" `[D4]`

**R3.17 — Multiplicative gains use the times sign; ranges use an en dash with the unit attached once.**
> "a theoretical maximum data rate of 3x a SISO/SIMO system" `[D4]`
> "25-33 kHz"; "between 20-50 m"; "a range of 2.7-2.8 km" `[D4]`

**R3.18 — Italicise a term of art exactly once, at its point of definition; plain thereafter.**
> "maximum transfer unit (MTU)" `[D1]`; "a collision is said to have occurred" `[D4]`

**R3.19 — Monospace for concrete implementation handles and protocol objects.**
> "modem parameter phy[DATA].nc"; "We introduce a csi agent in UnetStack" `[D1]`
> "typically are called CONTROL frames on UnetStack-based modems" `[D4]`

**R3.20 — Expand every abbreviation on first use, no exceptions.**
> "forward error correction (FEC)"; "channel state information (CSI)"; "virtual acoustic ocean (VAO)" `[D1]`

**R3.21 — Procedural steps are numbered with bolded imperative leads.**
> "Determine L. Pick minimum L such that:"; "Determine K."; "Adjust R and N when more information becomes available." `[D1]`

**R3.22 — Forward pointers and back-references are explicit and re-anchor the content; never assume the reader remembers.**
> "Recall from Section 2.5.2 that the time-variability model was only valid when K was small enough for OFDM to work well." `[D1]`
> "The method outlined in deliverable D3 is based on this approach." `[D4]`

**R3.23 — Report unflattering conditions plainly.**
> "The weather on all 3 days of the experiment was windy with whitecaps visible on the sea surface and strong currents." `[D4]`

**R3.24 — Raw tool output may be pasted verbatim as evidence, unformatted, followed by one sentence of reading.**
> "Average uncoded BER: 0.094 / Packet success rate: 1.0 / Throughput: 6835 bps" then "This shows that the recommended scheme indeed works as expected in the replay channel." `[D1]`

---

## 4. VOCABULARY TABLE

Every right-hand column entry is verbatim from a quote.

| # | Instead of X | He writes Y | Source |
|---|---|---|---|
| 1 | we attempt to / efforts are made to | **we strive to** — "In this project, we therefore strive to add more physics to the link adaptation algorithm" | D1 |
| 2 | we hypothesise that | **with the hope that** — "with the hope that the physics provides sufficient constraints for rapid convergence" | D1 |
| 3 | a wide range of | **a host of** — "we are able to adapt to a host of channel conditions" | D1 |
| 4 | analogous to | **akin to** — "This is akin to how maritime VHF voice communications work." | D1 |
| 5 | prima facie | **at first glance** — "While this might seem restrictive at first glance" | D1 |
| 6 | adopt a conservative margin | **err on the side of safety** — "we would want the link adaptation to err on the side of safety" | D1 |
| 7 | a confounding factor | **a nuisance for our analysis** — "slow time-variation that is a nuisance for our analysis" | D1 |
| 8 | tractable / elegant / analytically convenient | **nice** — "does not have a nice closed form expression"; "has a nice physical interpretation" | D1 |
| 9 | derive / formulate / it can be shown that | **write down** — "we can write down the expression for data rate" | D1 |
| 10 | the framework is now complete | **all the pieces in place** — "We now have all the pieces in place" | D1 |
| 11 | In summary, | **To summarize,** — "To summarize, small datagram transfers at a data link layer cannot benefit from link adaptation" | D1 |
| 12 | excellent agreement was obtained | **a good match** — "We see a very good match between our model and measurements." | D1 |
| 13 | is not justified | **simply not worth it** — "The overhead of adaptation is simply not worth it for small datagrams" | D1 |
| 14 | under practical operating conditions | **in practice** — "a slightly conservative approximation that works well in practice" | D1 |
| 15 | adequate for the intended application | **sufficient for our needs** — "is sufficient for our needs" | D1 |
| 16 | passively / without dedicated probe signals | **opportunistically** — "to collate CSI by opportunistically observing incoming frames from peer nodes" | D1 |
| 17 | the principal / the primary | **the key** — "The key question we need to answer is" | D1 |
| 18 | it is necessary that / one must | **we require** — "we require modems that can transmit synchronously from multiple transmitters" | D4 |
| 19 | it can be observed that / the results indicate | **we see that** — "We see that the BER depends strongly on suitable choice of number of carriers." | D4 |
| 20 | as will be shown later | **as we shall see** — "This simplifies the channel estimation, as we shall see" | D4 |
| 21 | appropriate / a suitable candidate for | **well suited / well placed to** — "OFDM is well suited to meet this constraint" | D4 |
| 22 | a promising approach for | **a great candidate for** — "FH-BFSK is resilient to collisions and so is a great candidate for CONTROL frames" | D4 |
| 23 | advanced signal processing techniques | **clever signal processing** | D4 |
| 24 | in current commercial implementations | **out-of-the-box today** — "Subnero modems implement SISO and SIMO … out-of-the-box today." | D4 |
| 25 | also known as | **aka** — "SIMO - Single Input Multiple Outputs (aka spatial diversity)" | D4 |
| 26 | occasionally / with non-zero probability | **every now and then** — "but every now and then, collisions occur" | D4 |
| 27 | However, it was found that | **Unfortunately,** — "Unfortunately, this approach failed in practice" | D4 |
| 28 | this is consistent with expectations | **This is not surprising, as** | D4 |
| 29 | this behaviour is attributable to | **This is expected, since** — "This is expected, since the MIMO channel uses the additional receivers for simultaneous data streams" | D4 |
| 30 | Consequently / Therefore in conclusion | **The net result is that** — "The net result is that there is an optimal pilot spacing for each channel" | D4 |
| 31 | benign / adverse propagation environments | **favorable / less favorable channel conditions** | D4 |
| 32 | satisfactorily / adequately | **quite well / reasonably well** — "While MIMO OFDM worked quite well in the MF band" | D4 |
| 33 | informative | **insightful** — "While the BERs are insightful" | D4-med |
| 34 | in the field / in situ | **at sea** — "In order to test MIMO theory at sea" | D4 |
| 35 | approximately (in body prose) | **roughly / about** — "The angular separation between the modems was roughly 86 degrees" | D4 |
| 36 | the approximate experimental geometry | **a rough geometry of the setup** | D4 |
| 37 | exploit | **harness** — "we harness the spatial multiplexing gain that MIMO offers" | D4 |
| 38 | utilize / leverage / facilitate | **use / get** — "we get all channel coefficients" | D4 |
| 39 | a substantial gain was obtained | **we got a large improvement** — "we got a large improvement from BSS processing" | D4 |
| 40 | degraded but non-zero performance | **marginal** — "SISO performance was marginal" | D4 |
| 41 | is defined as (for a term of art) | **is said to have occurred** — "a collision is said to have occurred" | D4 |
| 42 | it was decided not to / this was deemed unnecessary | **we therefore choose not to** — "We therefore choose not to add complexity to our model" | D1 |
| 43 | henceforth / for the remainder of this work | **from here on** — "We adopt this calibrated FEC model from here on." | D1 |
| 44 | a substantial number of frames failed | **N% of the DATA frames were lost** — "69% of the DATA frames were lost!" | D4 |

---

## 5. MATHEMATICS AND FIGURES

### 5.1 Introducing an equation

**R5.1 — Every display is introduced by a sentence naming what is being computed and what for, ending in a colon.** Never "Consider the following equation", never a bare display.
> "With these parameters, we can write down the expression for data rate:" `[D1]`
> "The channel coefficients H_imn can be estimated at carrier i in P_m:" `[D4]`

**R5.2 — Every symbol is glossed immediately after the display in one "where" sentence.**
> "where fs is the baseband sampling rate, Ls is the cyclic suffix length (phy[DATA].ns), and Ts is the time overhead from the detection preamble and synchronization pre- and postambles." `[D1]`
> "where X_im is the pilot symbol transmitted on carrier i by transmitter m, Y_in is the corresponding received symbol on receiver n, and * represents a complex conjugation operation." `[D4]`

**R5.3 — Gloss notation conveniences too; assume nothing.**
> "where {.,.} denotes a vector concatenation, and |.| is the cardinality operation (i.e., |P_m| is the number of pilots)." `[D4]`

**R5.4 — State dimensions in words beside the symbol.**
> "where H_i is a M x N matrix, X_i is a M-vector and Y_i is a N-vector." `[D4]`

**R5.5 — Assumptions are numbered, one sentence each, each followed by its consequence.**
> "The cyclic prefix length L is longer than the delay spread of the channel and hence we can assume per-carrier flat fading."
> "The channel does not vary significantly over the duration of one OFDM block, i.e., the channel is quasi-static. This allows us to ignore inter-carrier interference (ICI) due to loss of orthogonality in FFT." `[D1]`

**R5.6 — Discuss the validity of assumptions; do not assert it.**
> "We can select OFDM parameters such that the two assumptions are approximately true. In determining OFDM parameters, we may eventually need a performance model for what happens when the assumptions are violated, but we expect the violations to be small and so these assumptions provide a good starting point for our investigation." `[D1]`

**R5.7 — State the abstract problem, then read it back in words, then make it concrete.**
> "The above problem definition is rather abstract. We can make it more concrete in the context of Subnero modems." `[D1]`

**R5.8 — Label approximations as approximations, with the reason they are acceptable.**
> "While there is no closed-form expression for LDPC to compute PSR from BER, we can use a finite block length normal approximation based on a binary symmetric channel (BSC) as an estimate:" `[D1]`

**R5.9 — Write a mapping as a bare arrow before any formula.**
> "We focus our attention on a FEC performance model that converts this BER b into a PSR: (b, N, R) -> Pi" `[D1]`

**R5.10 — Give the physical meaning of every parameter alongside its mathematics, and explain limiting behaviour in words.**
> "The Doppler parameter fD has a nice physical interpretation as the Doppler spread of the channel (typically measured in Hz)." `[D1]`
> "for 1 <= beta <= 2. When beta = 1, this expression provides a weak penalty for channel variation. At the other extreme, beta = 2 provides a strong penalty." `[D1]`

**R5.11 — Give the physical reading of every algebraic condition.**
> "For spatial multiplexing to work, we require the channel matrix to be invertible, i.e., have full rank. Physically, this means that every transmit-receive pair must see a slightly different channel. In practice, in presence of multipath arrivals from surface and bottom reflections, we expect this condition to be generally met provided the transmit array and receive array has sufficient inter-antenna spacing." `[D4]`

**R5.12 — Restate a display in counting terms right after it, and state the solvability condition as a plain inequality in prose.**
> "The tensor h has LMN unknowns. Equation (2.6) represents a system of |P|MN simultaneous equations." `[D4]`
> "as long as |P| >= L, this system is invertible to obtain tensor components h_lmn" `[D4]`

**R5.13 — Narrate the one algebraic step you keep, in first person plural, naming the operation. Do not derive at length.**
> "Multiplying (2.4) by X_imn, we get:" `[D4]`
> Say the payoff before the final display: "Once the tensor h is known, we get all channel coefficients (including at non-pilot carriers):" `[D4]`

**R5.14 — Convert symbols to a worked concrete instance with real numbers.**
> "For a MIMO system with 3 transmitters (M = 3), we use P_1 = {0,9,18,...}, P_2 = {1,10,19,...}, and P_3 = {2,11,20,...}. The data carriers are then D = {3,4,5,6,7,8,12,13,14,15,16,17,21,...}. We therefore have 3 pilots for every 9 carriers, i.e., 33% pilots and 67% data carriers." `[D4]`

**R5.15 — Translate mathematical structure into the operation that implements it.**
> "If the pilots are uniformly spaced, the interpolation of channel coefficients to non-pilot carriers can be simplified to an inverse Fourier transform, zero padding, and a Fourier transform:" `[D4]`

**R5.16 — Restrict parameter ranges explicitly, with the hardware reason.**
> "Furthermore, we restrict R in {2/3, 1/2, 1/3, 1/4, 1/5, 1/6} for various LDPC FEC codes implemented in the Subnero modems." `[D1]`
> Present parameter sets as bullets of symbol, domain, meaning, implementation name: "K in {2^7, ..., 2^13} is the number of carriers (modem parameter phy[DATA].nc)" `[D1]`

**R5.17 — Call an easy solution easy, and append the practical consequence.**
> "We can obtain nu1 and nu2 by solving a simple linear system of equations:" `[D1]`
> "This ensures that N is an integer number of bytes, since UnetStack frames are composed of bytes." `[D1]`

### 5.2 Referring to figures

**R5.18 — Point to a figure inside a sentence that carries the finding or the purpose. Never "(see Fig. 4)".**
> "The results are summarized in Figure 2.4." `[D4]`
> "We illustrate the above two link adaptation scenarios in Figure 2.1 and Figure 2.2." `[D1]`
> "In Figure 3.4, we see a beamformer energy plot that has two peaks corresponding to two modems transmitting the OFDM signals." `[D4]`

**R5.19 — The figure pointer is followed immediately by the reading, and the reading verb is "We see".**
> "The results are shown in Figure 2.8. We see a very good match between our model and measurements." `[D1]`
> "We see a good match for K <= 2048, but a gap at higher K." `[D1]`

**R5.20 — Walk a multi-panel figure panel by panel, in order, one sentence per panel.**
> "The top panel shows the communication distance. We see 3 distinct distances for the 3 datasets we collected over 2 days. The second panel shows the number of OFDM carriers used. … The last panel shows the BER for MIMO method 2 for 4 different pilot spacings (P = 2, P = 4, P = 6 and P = 8) in different colors." `[D4-med]`

**R5.21 — Name exceptions in the figure discussion and quantify them; cross-link figures that tell one story.**
> "We see a good match between our model and measurements, except for two sets of outliers at K = 4096 and K = 8192. For these sets, the model underpredicts the BER by roughly a factor of 2." `[D1]`
> "This is consistent with the observation from Figure 2.9 where the BER for K = 4096 and K = 8192 was underpredicted." `[D1]`

**R5.22 — Tables get the same treatment, plus a bolding convention.**
> "This is tabulated in Table 2.2. The best results for each dataset are marked in bold." `[D4]`

### 5.3 Caption style

A caption has up to four parts, in this order: **(a) what the figure shows; (b) the fixed conditions in enough detail to reproduce; (c) the provenance of the data; (d) the take-home message, usually beginning "We see".**

> Show-then-interpret: "Figure 2.3: Modeled PSR against BER for various LDPC code rates R and N = 2048 bits. The dashed lines are show measured performance using LDPC codes on Subnero modems. We see that the model closely matches the measurements, with the model being slightly conservative for some codes." `[D1]`
> Reproducible conditions: "Figure 2.4: Comparison between simulation and performance model for OFDM with differential BPSK and QPSK with two different channels (h0 and h1). Channel h0 is an AWGN channel for benchmarking. Channel h1 is a time-invariant 3-ray 10-tap frequency selective channel. We see a good match between theory and simulation." `[D1]`
> Fixed parameters stated: "Figure 2.10: … Other OFDM parameters are kept fixed at B = 0.4, k0 = 0 and M = 2." `[D1]`
> Provenance: "Figure 2.6: Measured time-varying channel impulse response during the 2024 St Johns island experiment." `[D1]`
> Take-home, not axes: "Figure 2.5: Typical U-shaped curve for K for beta = 1. The time-invariant model predicts improvement in BER as K increases. Time variability severely limits the maximum usable K." `[D1]`
> Schematic captions explain the mechanism the drawing encodes: "Figure 2.1: A sequence diagram showing the single-hop transfer of a mid-size datagram that fits within a single data link MTU but requires fragmentation at the data link layer into 3 physical layer fragments (including erasure correction redundancy). The SETUP* frame contains adaptive DATA channel parameters to use for the transfer. …" `[D1]`
> Hardware photo captions say what was built, with whom, and the one number a reader would ask for: "Figure 2.1: MF and VLF multi-transducer (MT) modems developed in collaboration with Subnero for MIMO testing. Each modem supports up to 3 transmitters that can be synchronously used to transmit at a per-transmitter source level of approximately 185 dB re 1 uPa @ 1 m." `[D4]`
> Deployment photo captions say what is visible and what the geometry was: "Figure 2.2: … Two of the three transducers in each band are visible. The spacing between transducers was 1 m, and both MF and VLF band transducers were attached to the same vertical line with a weight at the bottom." `[D4]`
> A multi-panel caption repeats the panel walk-through so the figure stands alone. `[D4]`

---

## 6. HONESTY MOVES

Copy these frames and substitute your content. Do not invent new ones.

**H1 — Volunteer the limitation of your own scheme, flatly, present tense.**
> "This is sub-optimal in cases where the channel is not reciprocal." `[D1]`
> "Acoustic channel characteristics are not always reciprocal, and so the transmitter may not always have the necessary information for adaptation." `[D1]`

**H2 — "While X, Y" — concede first, then the cost or the residual risk.**
> "This simplifies the channel estimation, as we shall see, but is inefficient in terms of data rate." `[D4]`
> "While beamforming based BSS improves the situation with OFDM greatly, we find that frame loss cannot be completely avoided using BSS. Non-blind techniques may allow us further improvements." `[D4]`
> "While assumption 1 in the previous section is easy to satisfy by choosing a L based on the impulse response from the CSI, assumption 2 can be violated if the chosen K is larger than the coherence time of the channel." `[D1]`

**H3 — Name what your simplifications cost, in one sentence, in the section that used them.**
> "In deriving the OFDM performance model, we made several assumptions, simplifications and approximations. This enabled us to make the mathematics tractable, but potentially at the cost of losing some accuracy." `[D1]`

**H4 — Refuse the over-comparison: say what agreement does *not* prove.**
> "While the good match between model and simulation is encouraging, it does not guarantee a good match between model and reality. The simulation is time invariant, whereas real channels are time varying." `[D1]`

**H5 — Refuse the over-claim about an experiment by naming what that experiment cannot do.**
> "While at-sea experiments provide a real channel, it is impossible to measure the performance of a large number of OFDM schemes in the same channel." `[D1]`

**H6 — Name the exception with its exact coordinates.**
> "We see a good match between our model and measurements, except for two sets of outliers at K = 4096 and K = 8192." `[D1]`
> "For VLF SISO OFDM, we see that this is rarely the case, and so reliable OFDM communication was not achieved in either of the VLF datasets on 26th February." `[D4-med]`

**H7 — State the catastrophic-regime honesty: the model is wrong where it does not matter.**
> "When K is too large, the model predicts that the OFDM performance will degrade, but in reality, OFDM fails even more catastropically than the prediction." `[D1]`

**H8 — Bound the risk you just admitted, in the same sentence.**
> "If the condition is not met for some sub-carriers, errors may be introduced at the receiver, but they may be corrected through error correction codes." `[D4]`
> "With only 3 hydrophones, however, its ability to mask signals from unwanted directions is limited." `[D4]`

**H9 — Say what you could not do, and why the project's own scope prevented it.**
> "Since our focus in this project was on blind source separation, where the receiver assumes no a priori knowledge of the source modulation and location, we were unable to improve the performance of MF OFDM BSS any further." `[D4]`

**H10 — Immediately follow a "could not" with the concrete condition under which it would work.**
> "If we assume knowledge of the source modulation, we may be able to process each OFDM block individually and avoid the windowing operation needed in the BSS processing." `[D4]`
> "In addition, if more than 3 receive hydrophones are available, the improvement in SNR can be more, and the performance of OFDM source separation can be improved further." `[D4]`

**H11 — Report the blunt negative verdict without cushioning.**
> "Neither MIMO type 1 or MIMO type 2 could provide error-free communication." `[D4]`
> "On the same day, at a shorter range of 250 m, MIMO failed to achieve a sufficiently low BER for communication." `[D4-med]`

**H12 — State implementation incompleteness plainly.**
> "Many parts of the algorithm have already been implemented on the Subnero modem, but some parts still need integration." `[D1]`

**H13 — Future validation is stated as future, never implied as done.**
> "Experiments will be undertaken in the next year to test and fine tune the protocol in Singapore waters." `[D1]`

**H14 — When a measurement is stochastic, prescribe the conservative protocol.**
> "Since direct replay BER is stochastic, we recommend running the replay multiple times and taking the maximum measured BER to determine R." `[D1]`

**H15 — Admit a missing input and say the algorithm must cope.**
> "When bootstrapping a data transfer, if a OFDM frame isn't available for estimation, our algorithm has to handle the possibility that nu1 and nu2 may not be available." `[D1]`

---

## 7. NEVER DO

1. **Never** write an abstract, an executive summary, a chapter summary paragraph, or a "contributions of this chapter" bullet list. Chapters begin with substance on line one. `[D1][D4]`
2. **Never** write "The remainder of this chapter is organized as follows." Name chapters by content instead. `[D4]`
3. **Never** open a chapter with a literature review or a citation cluster. One citation per chapter is the observed ceiling. `[D4]`
4. **Never** use agentless passive for the team's own decisions: no "it was decided that", no "an approach was developed", no "efforts were made". `[D1][D4]`
5. **Never** use first person singular, "the authors", "this report", or "the present work". `[D1][D4]`
6. **Never** use hype adjectives: no "novel" (except literally to mark that off-the-shelf methods failed), no "state-of-the-art", "cutting-edge", "paradigm", "revolutionary", "groundbreaking". The strongest permitted claim is "a good match" or "works as expected". `[D1][D4]`
7. **Never** write "to the best of our knowledge" or any novelty-priority claim. `[D4]`
8. **Never** write "It should be noted that", "It is worth mentioning that", "It is important to emphasise that", "It is important to point out that". Just make the note: "We note, however, that the channel matrices H_i are not independent." `[D1][D4]`
9. **Never** ask a rhetorical question. There is not one question mark in the high-confidence corpus. `[D4]`
10. **Never** stack "Furthermore, moreover, additionally" as connective glue. "Furthermore" is permitted once per chapter and must attach to a real restriction. `[D1][D4]`
11. **Never** use "utilize", "leverage", "facilitate", or "in order to obtain optimal performance" padding. Use "use", "harness", "get". `[D4]`
12. **Never** chain clauses with semicolons. Full stop, new short sentence. `[D4]`
13. **Never** use em-dash asides. Parentheses, or a spaced dash. `[D1]`
14. **Never** stack hedges ("may possibly potentially"). One hedge, specific. `[D1]`
15. **Never** use an abbreviation before expanding it. `[D1]`
16. **Never** report a headline number without immediately explaining it or bounding it. A raw result is never left to speak for itself. `[D4]`
17. **Never** confine a negative result to the results section. Every failure is restated in the Discussion in plain words: "MIMO failed to communicate robustly and SISO performance was marginal". `[D4]`
18. **Never** attribute a method to a person or use "et al." name-dropping in body text. Attribute to deliverables: "the method outlined in deliverable D3". `[D4]`
19. **Never** write long step-by-step algebraic derivations as the main rhetorical mode. State the result, name the source or the approximation, and give the reason for the approximation instead of the working. `[D1]`
20. **Never** use "significant" in the statistical sense, and never report p-values or confidence intervals. Agreement is asserted visually: "We see a good match". `[D1]`
21. **Never** claim validation that has not happened. State future work flatly as future. `[D1]`
22. **Never** use decorative section epigraphs. `[D1]`

---

## 8. WORKED BEFORE / AFTER

### Before (colleague's draft)

> "RPC combines M partial-FFT observations per carrier, yet its inferential support remains local: each W_k is constrained only by nearby pilots or by decision-directed recursion over tentative symbols."

### After (house style)

> "RPC combines M partial-FFT observations for each carrier. However, it estimates each W_k locally. Only the pilots near carrier k constrain the estimate, or the tentative symbols from decision-directed recursion do. Information from the rest of the frame is not used. This works well when the channel is smooth across carriers, but the estimate degrades when the pilots near carrier k are noisy."

*(The final clause is a template slot, not a claim. Fill it only with a limitation your evidence supports; if you have measured the degradation, quantify it in the H6 form — "except for … the model underpredicts … by roughly a factor of 2". If you have not, delete the clause. Rule 2.4 forbids asserting a bound you have not measured.)*

### Change-by-change justification

| # | Change | Rule | Warrant |
|---|---|---|---|
| 1 | "per carrier" → "for each carrier" | §4 R38, §7.11 | Latinate compression replaced by plain English; the house register writes "we get all channel coefficients", not compressed nominal phrases. |
| 2 | The comma splice with "yet" → full stop plus "However," | R3.5, R3.7, §7.12 | One idea per sentence; "However" is the sanctioned pivot ("However, the estimation procedure in method 2 is more susceptible to noise" `[D4]`). |
| 3 | "its inferential support remains local" → "it estimates each W_k locally" | R3.1, §7.4 | Abstract nominalisation with an inanimate abstract subject is replaced by an agent doing a concrete action. The corpus writes "The channel coefficients H_imn can be estimated at carrier i in P_m" `[D4]`, never "inferential support". |
| 4 | The colon-plus-abstraction structure deleted | R3.5, R3.6 | Colons introduce *displays*, not clauses (R5.1). Explanatory colons are replaced by a new short sentence. |
| 5 | "constrained only by nearby pilots" → "Only the pilots near carrier k constrain the estimate" | R5.11 | The algebraic condition is given its physical/operational reading; the corpus always says which pilots, at which carriers, cf. "we use P_1 = {0,9,18,...}" `[D4]`. |
| 6 | Added "Information from the rest of the frame is not used." | R3.6, H1 | The short declarative that lands the point, in the register of "We need to modify the model to correct this." `[D1]`. It also converts an implied criticism into a stated limitation, per H1. |
| 7 | Added the "This works well when …, but …" clause | H2, §2.2 | An alternative is never dismissed as wrong, only costed; the corpus gives the alternative its due before naming the cost ("These yield low data rate (tens of bps), but provide very robust performance" `[D4]`). |
| 8 | No hedging cluster, no "remains", no "tentative" as a hedge on "symbols" | R3.12 | "tentative symbols" is retained because it is the technical term for decision-directed inputs, not a hedge; but no additional hedge is stacked on it. |
| 9 | M and W_k kept as-is | R5.2 | Symbols are permitted, but on first use each must be glossed in a "where" sentence — add "where M is the number of partial FFTs per OFDM block and W_k is the equaliser coefficient at carrier k" if this is their first appearance. |
| 10 | Nothing was added about superiority of the proposed alternative | §7.6, §7.16 | The paragraph names the limitation of RPC and stops. The comparison to your own method is made later, by cost and by measured numbers, in the §2.2 form. |