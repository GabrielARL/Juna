# Style guide - evidence: 7 Chitre FIRST-AUTHOR papers (AF, DELAY, JUGGLE, VITERBI, SHRIMP, ANI, REVIEW)

# THE CHITRE STYLE GUIDE
### A prescriptive manual for rewriting a journal paper, tutorial decks, and slide talks on underwater acoustic OFDM receivers

**Evidence base.** Seven first-author papers. Throughout, quotes are tagged:

| Tag | Paper | Venue |
|---|---|---|
| **[AF]** | On Ambiguity Function Shaping for Broadband Constant-Modulus Signals | Signal Processing (Elsevier), 2020 |
| **[DELAY]** | Throughput of Networks With Large Propagation Delays | IEEE JOE 37(4), Oct 2012 |
| **[JUGGLE]** | Reliable Point-to-point Underwater Acoustic Data Transfer: To Juggle or Not to Juggle? | IEEE JOE, 2014 |
| **[VITERBI]** | Viterbi Decoding of Convolutional Codes in Symmetric α-Stable Noise | IEEE Trans. Comm. 55(12), Dec 2007 |
| **[SHRIMP]** | Optimal and Near-Optimal Signal Detection in Snapping Shrimp Dominated Ambient Noise | IEEE JOE 31(2), Apr 2006 |
| **[ANI]** | Ambient noise imaging in warm shallow waters | JASA 132(2), Aug 2012 |
| **[REVIEW]** | Underwater Acoustic Communications and Networking: Recent Advances and Future Challenges | MTS Journal 42(1), Spring 2008 |

Every rule below is an instruction. Where a paper supplies no instance of a rule, that absence is stated explicitly rather than passed over.

---

## 1. THE SHAPE OF A DOCUMENT

### 1.1 The abstract, sentence by sentence

Write abstracts by filling slots in this order. Do not reorder. Do not merge slots into one sentence.

**Slot 1 — A fact about the physical world or about the object. No "we". No citation. No problem yet.**

> "Constant-modulus signals such as m-sequences are known to have good autocorrelation properties, as well as good peak-to-average power ratio that allows for full utilization of the transmitter's power." **[AF]**

> "Propagation delays in underwater acoustic networks can be large as compared to the packet size." **[DELAY]**

> "The high frequency ambient noise in warm shallow waters is dominated by snapping shrimp." **[ANI]**

> "The optimal detection of signals requires detailed knowledge of the noise statistics." **[SHRIMP]**

> "Reliable data transfer speeds using underwater acoustic communications systems are limited by long propagation delays, small link data rates, and high bit error rates." **[JUGGLE]**

**[ANI]** extends this slot over three sentences, because the physical chain needs three steps: "The loud snapping noises they produce are impulsive and broadband. As the noise propagates through the water, it interacts with the seabed, sea surface, and submerged objects." Use two or three sentences here only when each adds a physical step.

**Slot 2 — What is standardly done, stated fairly, with the reason it is reasonable.**

> "In many applications, the assumption of Gaussian noise allows the use of the linear correlator (LC), which is known to be optimal in these circumstances." **[SHRIMP]**

> "Conventional medium-access control (MAC) protocol design for such networks focuses on mitigation of the impact of propagation delay." **[DELAY]**

> "In a typical ARQ approach, a node transmits one or more packets and waits for the corresponding acknowledgments (ACKs)." **[JUGGLE]**

**Slot 3 — "However," or an equivalent pivot: where the standard thing fails, and under exactly what condition.**

> "However, the broadband ambiguity surface for such signals exhibit high sidelobe levels that are undesirable in applications where the signal is subject to broadband Doppler." **[AF]**

> "However, the performance of the LC is poor in warm shallow waters where snapping shrimp noise dominates in the range 2–300 kHz." **[SHRIMP]**

> "With long propagation delay, the long waiting time for ACKs results in low average throughput." **[JUGGLE]**

> "Most proposed protocols to date achieve, at best, a throughput similar to that of the zero propagation delay scenario." **[DELAY]**

> "Algorithms developed with a Gaussian noise assumption perform poorly in impulsive noise, such as that described by the symmetric α-stable (SαS) distribution." **[VITERBI]** — the three-sentence abstract of a Transactions Letter fuses Slots 1–3 into this one sentence. Do this only when the whole abstract is three sentences.

**Slot 4 (optional) — "Since …": the physical reason for the failure.**

> "Since snapping shrimp noise consists of a large number of individual transients, its statistics are highly non-Gaussian." **[SHRIMP]**

> "As high-order moments of SαS distributions generally do not converge, ANI algorithms based on low-order moments and fractiles are developed and demonstrated." **[ANI]**

**Slot 5 — The move, in one plain verb: formulate, consider, investigate, explore, aim.**

> "We formulate an optimization problem to minimize the maximum sidelobe levels of such signals over a set of delay-Doppler values." **[AF]**

> "We consider the practical problem of transferring a data file or data stream reliably from one half-duplex underwater node to another." **[JUGGLE]**

> "We investigate the performance of antipodal signaling and Viterbi decoding of convolutional codes in SαS noise." **[VITERBI]**

> "In this paper, we systematically explore the possibility that propagation delays can be exploited to make throughput far exceed that of networks without propagation delay." **[DELAY]**

> "In this paper, we aim to provide an overview of the key developments in point-to-point communication techniques as well as underwater networking protocols since the beginning of this decade." **[REVIEW]**

**Slot 6 — The difficulty or the constraint, admitted before the fix.**

> "This problem is non-convex and difficult to solve." **[AF]**

> "The approach needs to satisfy certain timing constraints, and its performance is largely dependent on the network settings and chosen parameters." **[JUGGLE]**

**Slot 7 — Results, one per sentence, in the order the paper produces them, each opening with "We show", "We illustrate", "We demonstrate", "We also establish". Assumptions precede the headline number.**

> "Under the assumptions of the protocol model in a single collision domain for a half-duplex unicast network, we show that the upper bound of throughput in an N-node wireless network with propagation delay is N/2. We illustrate network geometries where this bound can be achieved and study transmission schedules that help achieve it. We show that for any network, the optimal schedule is periodic and present a computationally efficient algorithm to find good schedules. Finally, we show that N-node network geometries that achieve throughput close to the N/2 bound exist for any N and present a lower bound on achievable maximum throughput for bounded geometries." **[DELAY]**

> "We show that the juggling-like ARQ provides good data streaming throughput but performs poorly for small file transfers." **[JUGGLE]** — note the result carries its own negative half.

**Slot 8 — The concessive limitation, using "Although …".**

> "Although the performance of the sign correlator is slightly inferior to that of the ML detector, it is very simple to implement and does not require detailed knowledge of the noise statistics." **[SHRIMP]**

**Slot 9 — The verdict, the application, or the consequence. Never a summary of the abstract.**

> "This makes it an attractive compromise between the simple LC and the complex ML detector." **[SHRIMP]**

> "We demonstrate the advantage of our signal design over conventional unimodular signals for target detection in strong clutter in a continuous active sonar application." **[AF]**

> "We propose a novel rate-less code based juggling-like ARQ protocol that overcomes this limitation and offers high data transfer speeds for small files in long propagation delay environments." **[JUGGLE]**

> "We believe that the novel observations in this paper may motivate further research into this area, especially random access networks with large propagation delay, with a fundamentally changed outlook on maximum achievable throughput." **[DELAY]**

**Abstract rules.**
- Never open with "In this paper, we propose". Slot 1 is always the world, never the paper.
- Do not use a citation number in an abstract.
- The word "novel" gets a budget of **one per document**, only in Slot 9, and only attached to an artifact **[JUGGLE]** or, hedged, to observations **[DELAY]**. Four of the seven abstracts use it zero times.
- Length: 3 sentences **[VITERBI]** to 11 **[DELAY]**. Match length to paper length, not to ambition.

### 1.2 How introductions open

**Rule: the first sentence of the introduction defines, or physically describes, the central object. It never mentions the paper, the contribution, or the field's importance in the abstract.** Four openings, four legitimate forms:

*Form A — definition of the object:*
> "Constant-modulus (a.k.a. unimodular) signals encode information by periodically changing the phase of a carrier." **[AF]**

*Form B — definition from first principles, with the defining equation inline:*
> "PROPAGATION delay is the amount of time it takes a communication signal to travel from the source to the destination over a given transmission medium, i.e., D_p = d/c, where D_p is the propagation delay, d is the distance between the source and the destination, and c is the speed of the signal." **[DELAY]**

*Form C — the physics or biology that produces the object:*
> "SNAPPING shrimp (family Alpheus and Synalpheus) produce loud snapping sounds by extremely rapid closure of their snapper claw. The closure produces a high-velocity water jet leading to the formation of a cavitation bubble, which collapses rapidly, causing a loud broadband snapping sound [1]." **[SHRIMP]**

*Form D — the justification of the standard assumption, so it can be broken in sentence 2:*
> "THE USE of Gaussian noise assumption in communication systems is justified by the central limit theorem and is further motivated by the mathematically tractable probability density function (pdf). However many communication environments do not satisfy the Gaussian noise assumption [1]–[3]." **[VITERBI]**

*Form E — the ubiquity of the problem:*
> "THE problem of transferring a data file or data stream reliably from one node to another is commonly encountered in many applications." **[JUGGLE]**

*Form F — the intellectual history, when the paper stands in a named lineage:*
> "The possibility of using ambient noise in the ocean as the source of acoustic "illumination" for imaging of submerged objects was first explored by Flatté and Munk, and subsequently developed into a concept of acoustic daylight by Buckingham and colleagues." **[ANI]**

*Form G — the field's clock, for a review only:*
> "The past three decades have seen a growing interest in underwater acoustic communications because of its applications in marine research, oceanography, marine commercial operations, the offshore oil industry and defense." **[REVIEW]**

For an OFDM receiver paper, use Form A or Form C. The object is the Doppler-spread, time-varying underwater channel, or the partial-FFT observation. Not "OFDM has become popular".

### 1.3 The order of motivation, prior work, contribution, roadmap

The fixed sequence in the long papers **[AF, DELAY, JUGGLE]**:

1. **Object defined** (§1.2).
2. **Where it is used, and why it suits those uses.** > "They are used in applications such as active sonar, radar, communications, seismology, non-destructive testing, and biomedical imaging [1, 2, 3, 4, 5]. Unimodular signals are particularly well suited to applications that impose constraints on dynamic range, maximum power rating, and maximum permitted source levels [2, 3]." **[AF]**
3. **The complicating physical fact.** > "In the case of active sonar and radar, we are often interested in targets that are possibly moving, and therefore subject to Doppler." **[AF]**
4. **A worked concrete instance with numbers** (see §2.3).
5. **Prior work**, either as its own subsection ("I-A. Literature Survey" **[DELAY]**) or as a paragraph chain. **Each prior-work paragraph ends by positioning this paper's difference**, never by praising the prior work: > "The idea of allowing nodes to transmit simultaneously and letting their packets "cross in flight" has been considered before [9]–[14]. Our contribution is to systematically generalize this observation to understand at a fundamental level the impact of nonzero propagation delays on the throughput of networks." **[DELAY]**
6. **Scope sentence**, one sentence, plain: > "In this paper, we focus on arbitrary-phase unimodular signal design for a broadband setup in the presence of clutter for detecting a target of unknown Doppler." **[AF]**
7. **The open questions, as an explicit list** — this is the strongest available device for an OFDM receiver paper: > "Specifically, we address the following questions: • What is the maximum throughput of a network with nonzero propagation delays? • What geometries and schedules achieve this maximum throughput? • Given a network geometry, how do we determine optimal or near-optimal schedules?" **[DELAY]**
8. **Contributions, bulleted, each tied to a section number**: > "The specific contributions of this paper are as follows: • In Section III, we formulate a scheduling problem for these networks, with throughput as the metric of interest, that allows for different notions of fairness, i.e., per-node and per-link fairness." **[DELAY]**; introduced by > "We now highlight the specific contributions of this paper:" **[AF]**. **[JUGGLE]** uses "we make two key contributions" instead of a bullet list. **[SHRIMP]**, **[VITERBI]**, **[ANI]** and **[REVIEW]** have **no contribution list at all** — for a short paper or a tutorial deck, drop the list and state the contribution in one prose paragraph.
9. **Roadmap paragraph**, last (§4.3).

### 1.4 How conclusions are built

Four permitted forms. Choose by document type.

**Form 1 — Recap in past tense, difficulty re-admitted, each result with its number, application last. Use for the journal paper.**
> "We formulated an optimization problem to minimize the maximum sidelobe levels of unimodular signals over a set of delay-Doppler values. While this problem is non-convex and difficult to solve, we were able to demonstrate that an iterative near-optimal method (USSM) of solving the problem can yield signals with desirable properties. For longer signals, we proposed a statistical approach (p-USSM) to further reduce the computational complexity of the problem, and showed that it is able to generate good signals much faster. … For applications where Doppler is significant, we demonstrated an reduction in maximum sidelobe levels of up to 4 dB (depending on signal parameters such as length, frequency, bandwidth, etc) over a delay-Doppler region of interest." **[AF]**

Note "we were able to demonstrate", not "we have shown". Note the parenthetical that limits the 4 dB claim in the same breath as making it.

**Form 2 — Objective restated, then findings organised by operating regime, then the normative instruction to the reader.**
> "In this paper, we considered the practical problem of transferring a data file or data stream reliably for point-to-point underwater acoustic communications. Our key objective was to provide more insights into the average throughput performance of juggling versus non-juggling based ARQ strategies under different inter-nodal propagation delays.
> We now summarize the findings. When the inter-nodal propagation delay is low, the S&W-2 approach works well for both data streaming and file transfer. … When the propagation delay is high, although fixed block J-ARQ works well for data streaming, it performs worse than V-S&W-2 for file transfer. This is because it wastes a lot of transmission opportunity towards the end of the file transfer due to its rigid block size imposed by its timing constraints. Hence, we cannot just blindly adopt a juggling approach." **[JUGGLE]**

**Form 3 — Findings in the order presented, then the practical verdict, then the afterlife paragraph: what has been done with the result since.**
> "We have demonstrated that snapping shrimp dominated ambient noise can be represented accurately by the SαS probability distribution. The parameters of the SαS distribution can be determined using fractile-based estimators. The knowledge of the noise probability distribution enables us to develop optimal ML and LO detectors. … The simple implementation and near-optimal performance of the SC detector make it an attractive choice for many applications.
> The SC has subsequently been used successfully in several experiments [19]. On certain occasions, we have used the SC and ML detectors cooperatively." **[SHRIMP]**

**Form 4 — Start again from the physics, end with a hedged generalisation beyond the tested case.**
> "As a consequence of the generalized central limit theorem, the pressure time series for snapping shrimp dominated ambient noise is modeled well by a SαS distribution. … Although the statistical methods were developed based on intuitions from SαS noise distribution, the methods are not critically dependent on the distribution; the methods are likely to work well in most impulsive noise environments." **[ANI]**

**Two of the seven have no conclusion section.** **[VITERBI]** ends inside "V. RESULTS" with a practical recommendation and no summary. **[REVIEW]** has no "Conclusion" heading at all; each half ends in a section headed "Summary", one of which closes with a forecast: > "As researchers master the techniques required for point-to-point communication links in the next 5-10 years, we expect that the research emphasis on underwater networking will increase." **[REVIEW]**

**For the surprise result, open the conclusion with the surprise, mid-sentence:**
> "In this paper, we find, rather surprisingly, that large propagation delays in underwater networks, rather than being harmful, lead to significant performance gains as compared to wireless networks with negligible propagation delays." **[DELAY]**

**Never write** "In this paper, we have shown that…" as an inflated closing claim, "In conclusion", "To conclude", "In summary" as a phrase **[REVIEW never-list]**, or a "future work will…" sentence **[VITERBI never-list]**.

---

## 2. MOTIVATION FIRST

### 2.1 What must be established before any mathematics

In order, before the first symbol appears:

**(a) What the thing physically is.**
> "Constant-modulus (a.k.a. unimodular) signals encode information by periodically changing the phase of a carrier." **[AF]**
> "As ambient snapping shrimp noise is composed of impulsive noise sources, the resulting noise statistics are non-Gaussian [4], [5]." **[SHRIMP]**

**(b) Why anyone cares — the application, named concretely, not abstractly.**
> "The problem of detecting a known signal with unknown amplitude in noise is commonly encountered in areas such as communications, target detection, ranging and environmental sensing." **[SHRIMP]**
> "This not only allows an underwater object to be detected or imaged, but also its range to be estimated passively." **[ANI]**

**(c) The mechanism that makes it hard, in physical terms.**
> "The shallow water acoustic communication channel exhibits a long delay spread because of numerous multipath arrivals resulting from surface and bottom interactions. Movement of transducers, ocean surface, and internal waves lead to rapid time variation and, consequently, a high Doppler spread in the channel." **[REVIEW]**
> "As a result of the slow speed of sound in water, the propagation delays in underwater networks are typically large, i.e., comparable to or larger than the packet size." **[DELAY]**

**(d) Why the standard method is still used despite being wrong — granted generously.**
> "In spite of this, many signal processing algorithms still use the LC for signal detection in non-Gaussian noise due to its simple implementation and the lack of detailed statistical information about the noise." **[SHRIMP]**
> "Although forward error correction (FEC) is commonly used to lower the packet error rate (PER) at the expense of the effective data transfer rate, it is often not practical to select an FEC that is able to correct all possible packet errors. Therefore, higher layer protocols are usually also tasked to provide reliable data transfer through mechanisms such as ARQ, erasure coding, etc." **[JUGGLE]**

**(e) The size of the prize, stated as headroom, not as praise.**
> "Since the LC is not optimal in snapping shrimp dominated ambient noise, a significant potential exists for enhancing the detection performance of signal processing algorithms in these waters." **[SHRIMP]**

**(f) Only now, the paper's move.**
> "In this letter, we analyze the performance of uncoded and coded communications in the presence of stable noise." **[VITERBI]**

### 2.2 The three devices that make the reader want the result

**Device 1 — Reframe the obstacle as the resource.** This is his most characteristic motivational move. Two instances:

> "Much effort has been spent to mitigate the ill effects of nonnegligible propagation delay (see related work in Section I-A). In this paper, we take a different approach. Rather than fighting what is a natural phenomenon (which is arguably out of our sphere of influence), we should perhaps explore how we can use propagation delay to our advantage. We draw a parallel to the opportunistic exploitation of another natural and equally troublesome phenomenon, i.e., the wireless fading channel, through the use of multiuser diversity [5]." **[DELAY]**

> "The long propagation delay, however, presents an opportunity for two nodes to simultaneously transmit data and ACKs towards each other in a juggling-like approach, potentially reducing the average waiting time for ACKs." **[JUGGLE]**

> "Rather than average away the variation, Potter and Chitre explored the possibility that these variations contain useful information that can be used for imaging." **[ANI]**

For the OFDM documents: Doppler-induced intercarrier interference is normally the enemy. If any part of the work turns the frame-wide coupling into the source of information, that inversion is the motivating sentence and it belongs in the introduction, phrased as "Rather than … we explore …".

**Device 2 — Ask the reader's question out loud, then admit it is not obvious.**
> "For example, would a rate-less code based solution always outperform the other two ARQ-based solutions? As another example, if the inter-nodal propagation delay is short, would the S&W-2 approach outperform the juggling-like ARQ approach if we were to pick very large block size? … Hence, it is not obvious which mechanism would be the most efficient one for a given network setting, and how should their parameters be chosen." **[JUGGLE]**

> "To complicate the matter further, the best approach may also be different when transferring a finite-size data file versus transferring an infinite data stream, even if all other network settings were to remain the same." **[JUGGLE]**

Rhetorical questions appear in exactly one of the seven papers and are on the explicit never-list of **[VITERBI]**, **[SHRIMP]** and **[REVIEW]**. **Prescription: at most one cluster of questions, in the introduction only, and only when the paper's answer is genuinely "it depends on the regime".** A slide talk may carry the question in the title, as **[JUGGLE]** does: "To Juggle or Not to Juggle?"

**Device 3 — Promise the smallest case first.**
> "To illustrate how one might exploit nonzero propagation delays, we start with the simple two-node (one source–destination pair) network and see what we can learn from it." **[DELAY]**
> "In this section, we study some special geometries of networks with small number of nodes, most of them achieving the N/2 upper bound. This helps us develop some of the intuition which will become important in later sections for the understanding of networks with large number of nodes." **[DELAY]**

### 2.3 The concrete instance with numbers, placed before the general formulation

> "For example, consider two underwater vehicles located 2000 m apart using acoustic communications. Noting the speed of sound in water is about 1500 m/s, the one-way trip takes over 1300 ms. These propagation delays are comparable to typical packet durations in these networks." **[DELAY]**

> "For example, a sonar might be designed to detect ships at a 1–10 km range and speeds of up to 10 knots. The signal used for such a sonar only needs to consider sidelobes in a limited part of the AF, corresponding to a delay of 1–10 km and Doppler of -10–10 knots." **[AF]**

> "At low frequencies, noise from shipping is significant; above ∼ 2 kHz snapping shrimp noise dominate [3]." **[SHRIMP]**

**Prescription for the OFDM documents:** before the receiver model appears, give one sentence of the form *platform speed → Doppler scale → carrier drift over one OFDM symbol → number of carriers of leakage*. The reader must be able to feel the number.

**On slides:** slide 2 or 3 is this number. Not the system diagram.

---

## 3. HOW HE JUSTIFIES

### 3.1 Reasoning from physics

Use when a modelling choice is forced by a physical constraint. The form is *physical fact → "hence"/"therefore" → the modelling consequence*, in one sentence.

> "For an acoustic signal, the mean noise pressure must be zero; hence, the location parameter for the distribution must also be zero." **[SHRIMP]**

> "Since we are dealing with dynamic (high-pass filtered) acoustic pressure signals, the distributions of interest are centered around zero (μ = 0)." **[ANI]**

> "Due to the symmetry of the linear wave equation, if the sound transmitted from one location is received at other locations, reversed and retransmitted, it focuses back at the original source location. This is the principle behind time reversal mirrors (TRM) or its frequency domain equivalent—active phase conjugation." **[REVIEW]**

> "The theoretical justification for the use of the stable family of distributions comes from the generalized central limit theorem [3]." **[VITERBI]**

> "This family of distributions arises out of the generalized central limit theorem which states that the sum of a number of independent and identically distributed random variables with finite or infinite variance will tend to a stable distribution as the number of variables grows." **[ANI]**

> "Since |x_i − x_j| = |x_j − x_i|, delay matrices are symmetric, i.e., D_ij = D_ji. Furthermore, since |x_i − x_i| = 0, delay matrices have an all-zero diagonal, i.e., D_ii = 0." **[DELAY]**

> "Since a constant change in phase does not change the magnitude of the ambiguity function, we can arbitrarily set θ0 to zero [6]." **[AF]**

### 3.2 Reasoning from measurement

Use when the claim is about data. Give the test, the level, and the fact that the deviation is not noise.

> "The impulsive nature of snapping shrimp sound leads to a non-Gaussian distribution. This is clearly seen from the departure from linearity in the normal probability plot of the noise (Fig. 1)." **[SHRIMP]**

> "The deviation of the data from the Gaussian is highly systematic and cannot be attributed to sampling." **[SHRIMP]**

> "The hypothesis that the data was obtained from a Gaussian distribution was rejected for both data sets at a 1% level of significance. The hypothesis that the noise was obtained from an SαS distribution was accepted for both data sets at a 1% level of significance. Similar tests for lower frequency data from other parts of Singapore waters led to the same conclusion." **[SHRIMP]**

> "The algorithm placed an average of 10 feedforward taps and 25 feedback taps; this is a significantly smaller number than the number of taps required in a conventional DFE for shallow water communication." **[REVIEW]**

> "In Fig. 2, we see that the theoretical upper bound derived in (8) is approximately 1 dB higher than the simulation results for hard decision decoding. In Fig. 3, we see that the theoretical upper bound derived in (13) is approximately 2–4 dB higher than the simulation results for 1-norm decoding. The bound is loose at low E_b/N_0 and high α, and becomes tighter when the noise becomes more impulsive and at higher E_b/N_0." **[VITERBI]**

Note the last: he reports *where the bound is loose* in the same breath as reporting the bound.

### 3.3 Reasoning from the failure of the alternative

**Rule: name the obvious alternative, say why one would try it, then say exactly why it fails here, then state your replacement. Never dismiss an alternative without trying it.**

> "For example, we can extract the eigenvector corresponding to the largest eigenvalue, based on a singular value decomposition (SVD). Although the intuition behind the eigenvector approximation is quite straightforward, the quality of the extracted solution is highly problem-dependent, and may even be infeasible (no longer satisfying the original optimization constraints). In our case, the minimax nature of the optimization problem makes it even harder to establish a guarantee on the quality of the extracted eigenvector, and indeed the method did not yield good results." **[AF]**

> "Due to constraints (13), the trace and nuclear norm in our problem are constant, and thus attempting to minimize these does not help to reduce the rank of X. Instead, we follow a generalization of the trace heuristic for rank minimization in [37], and minimize a weighted sum of the original cost function and an eigenvalue residual (sum of all eigenvalues except the highest)." **[AF]**

> "However, in an AWSαSN channel, the Euclidean norm metric is not optimal. Alternative metrics such as the Huber penalty function [8] and the 1-norm metric [9], [10] have been noted for their robustness in non-Gaussian noise. The p-norm (p < α) is often known to be a robust cost function in the presence of α-stable noise [1]. Inspired by these heuristics, we use the p-norm (with p = 1) branch metric μ = Σ_t |y_t − x_t| for the Viterbi algorithm in the presence of SαS noise." **[VITERBI]**

> "In FLOM imaging, we used FLOM to measure the spread of the SαS random variable. However, a more natural measure of the spread is the scale parameter c. We therefore consider the use of c² as the pixel value rather than the sample variance in 3. To do this, we need a good estimator for the scale parameter c. Although FLOM based parameter estimation methods exist, the information captured using them would essentially be the same as the FLOM imaging method outlined earlier." **[ANI]**

> "A joint DFE is optimal for such multichannel combining, but is often too complex. The authors considered alternatives with separate DFE and found that a set of DFE with a log-likelihood ratio (LLR) output yields good performance." **[REVIEW]**

> "However, the gains these techniques achieve are limited and the resulting performance is, at best, no better than that with zero propagation delays." **[DELAY]**

> "Coherent modulation schemes such as phase shift keying (PSK) along with adaptive decision feedback equalizers (DFE) and spatial diversity combining have been shown to be an effective way of communication in such channels (Stojanovic et al., 1993). However, the long delay spread (often hundreds of symbols) and rapid time variation of the channel often makes this approach computationally too complex for real-time implementations." **[REVIEW]**

Note **[JUGGLE]**'s variant: the alternative fails *only in one regime*, and he says so rather than condemning it — "In fact, for very low propagation delay, it performs even better than the J-ARQ protocols, since the latter suffer from high overhead-to-payload ratio imposed by their timing constraints."

### 3.4 How he handles a choice that is arbitrary

**Rule: never hide an arbitrary choice, and never defend it as principled. Do one of five things.**

**(i) Say it is arbitrary and show why it does not matter.**
> "Since a constant change in phase does not change the magnitude of the ambiguity function, we can arbitrarily set θ0 to zero [6]." **[AF]**
> "The multiplicative constant C/N is dropped without any effect, since the final image is scaled to fit the dynamic range of the display pixels." **[ANI]**

**(ii) Give the reason for the specific value: consistency with existing convention.**
> "The factor of 4 is chosen to ensure that this definition reduces to the standard definition of N_0 in the case of Gaussian noise (α = 2), making our analysis consistent with previous literature." **[VITERBI]**
> "The power 2/p is introduced to keep the units consistent with other statistical measures and thereby allowing direct comparison of the resulting images." **[ANI]**

**(iii) Cite whoever chose it first.**
> "In accordance with [18], we use θ = 0.12 for relevant results presented later in this paper." **[JUGGLE]**

**(iv) Tie the value to a physical limit of the apparatus.**
> "We use R_max = 120 m as our 1 m × 1 m target panels are only expected to be detectable by ROMANIS up to this range." **[ANI]**
> "As most practical environments have noise with α in the range of 1.5–2, we limit our analysis in this paper to 1 < α ≤ 2." **[VITERBI]**

**(v) Make the choice a free parameter, then study it and tell the reader how to tune it.**
> "The proposed USSM and p-USSM algorithms are controlled by two free parameters ζ and p. We studied the effect of both parameters, and suggested ways to tune them." **[AF]**

Where an assumption is convenient rather than true, say both — that it is convenient, and why it is defensible:
> "Although we acknowledge that larger packet sizes potentially admit larger FEC block sizes leading to better error performance, we assume that the FEC code (and the BER) is unchanged when the packet size is varied. This assumption is justified as dynamic design of FEC codes with varying block size is computationally expensive, and therefore infeasible in most modems, including currently available underwater modems." **[JUGGLE]**

And where a whole system model is a simplification, give three independent reasons for it and then bound the error it causes:
> "This model allows us to study the effects of propagation delay independently of physical layer considerations such as transmit power and propagation loss. Moreover, the single collision domain model is directly applicable to many underwater sensor networks. … It is also fairly common in the analysis of MAC protocols to assume a fully connected network, or equivalently, a single collision domain (e.g., [8], [10], [21], and [22]). … Since the number and timings of the allowed transmissions are limited by interference constraints, the single collision domain throughput analysis provides a lower bound for more general arbitrarily connected networks." **[DELAY]**

### 3.5 How he handles evidence that only partly supports a claim

**Rule: state the claim at the strength the evidence supports, and name the mechanism you cannot prove as a suspicion.** The verbs are *suspect, may, perhaps, likely, believed to, seems to be*.

> "We suspect that this inconsistent performance may be partially attributed to this lack of theoretical convergence of the statistical measures used." **[ANI]**

> "This may have contributed to the high variability in the images produced by high-order statistical ANI algorithms." **[ANI]**

> "This is perhaps because the higher frequencies are rapidly absorbed with range and therefore dominated by local snaps. Since the number of snapping shrimp in nearby areas is small, one would expect higher statistical variability in the resulting pixel estimates." **[ANI]**

> "This was believed to be due to the statistical variation in ambient noise producing favorable acoustic illumination at times, and unfavorable illumination at other times." **[ANI]**

> "The physics resulting in the time-variation of each arrival is not fully understood, but it may result from micro-multipath or internal waves." **[REVIEW]**

> "For example, we see that in Fig. 4, ζ = 4.8 seems to be that threshold." **[AF]**

> "Although the statistical methods were developed based on intuitions from SαS noise distribution, the methods are not critically dependent on the distribution; the methods are likely to work well in most impulsive noise environments." **[ANI]** — the template for generalising beyond what you tested.

> "We believe that the novel observations in this paper may motivate further research into this area … This could lead to novel scheduling and network configuration approaches with applications in underwater and satellite networks." **[DELAY]**

**[SHRIMP]** and **[JUGGLE]** supply no "we suspect" instance; in those papers every claim is either tested or bounded, and the partial-support case is handled by narrowing the claim instead ("comparable but slightly inferior"). **[VITERBI]** likewise: its partial-support handling is quantitative — "The bound is loose at low E_b/N_0 and high α".

**Never** state a mechanism as fact and let the hedging live in a later sentence. The hedge is inside the sentence that makes the claim.

---

## 4. HOW HE CREATES CLARITY

### 4.1 Worked numbers

**Rule: any quantity the reader is expected to find surprising must appear once as arithmetic they can do in their head.**

> "Assuming no loss due to bit errors, a physical layer data rate of 5 kbps only yields an effective data rate per node of 5 × 0.4% × 97% = 19.4 bps." **[REVIEW]** — the whole numerical argument of a review paper with no equations, done inline.

> "ADONIS effectively records data representing about 48 ms of incoming acoustic energy every second; roughly 95% of the incoming acoustic signal is therefore unavailable for processing." **[ANI]** — the limitation converted into a percentage the reader feels.

> "Noting the speed of sound in water is about 1500 m/s, the one-way trip takes over 1300 ms." **[DELAY]**

> "The 508 acoustic pressure sensors on ROMANIS form a two-dimensional planar array of approximately 1.3 m diameter. Each sensor is 50 mm × 50 mm in size." **[ANI]**

> "The maximum likelihood decoding is optimal and demonstrates the best performance, approximately 2 dB better than that of the hard decision decoding." **[VITERBI]**

### 4.2 Restatement in words after an equation

Covered fully in §6. The rule in one line: **the sentence after a display never contains a new symbol.**

### 4.3 Roadmap sentences

Four papers have one; three do not. **Include one only in the journal paper and the tutorial deck; omit it from a letter-length document.**

> "The paper is organized as follows. Section 2 formulates the optimization problem associated with designing the signal. Section 3 presents a heuristic method that utilizes SDP to iteratively solve a convex relaxation of this problem. Section 4 discusses the convergence of this method. In section 5, we explore further reduction of computational complexity using a statistical optimization approach. We discuss the results of our signal design and demonstrate some examples in section 6, and then conclude the paper in section 7." **[AF]**

> "The rest of this paper is organized as follows. In Sec. II, we introduce the statistical properties of snapping shrimp noise and use them to derive two families of algorithms for ANI. These algorithms rely on fractional low-order moments and fractile measures, respectively. We demonstrate the efficacy of these algorithms using the ROMANIS 2010 dataset in Sec. III." **[ANI]**

> "The rest of the paper is organized as follows. We first define the problem formally in Section II, and describe the different mechanisms in greater details for both finite-size data file and infinite data stream scenarios. We then provide a detailed analysis and performance comparison for each of these cases, and discuss the implications of our findings in Sections III and IV. We finally summarize our findings in Section V." **[JUGGLE]**

> "This paper is divided into two main sections—one on underwater communications and another on underwater networking. Section II concentrates on research on point-to-point communication issues such as channel modeling, modulation, coding and equalization. Key advances in these areas have enabled us to establish reliable high-speed underwater communication links. Using these links as a foundation, underwater networks can be established. Section III focuses on research on algorithms and protocols for such networks." **[REVIEW]** — note the roadmap doubles as an argument: each section is justified by the previous one.

**[VITERBI]** and **[SHRIMP]** have **no roadmap paragraph**; sections simply begin. **[DELAY]** folds its roadmap into the contribution bullets ("In Section III, we formulate…", "In Section IV-A, we prove that N/2 is an upper bound…") — use this fusion when you have both, so the reader is not told the plan twice.

Mid-document roadmaps are also used, one sentence:
> "We now review some of the recent work and future challenges. The key focus of our review will be on the data link layer (DLL) and network topology." **[REVIEW]**
> "We now describe the procedure to model ambient noise using the SαS distribution." **[SHRIMP]**
> "Two optimal parametric detectors are described below." **[SHRIMP]**
> "Analysis of this protocol is presented in Section III-A." **[JUGGLE]**
> "However, we can reformulate it into a near-convex problem as we outline next." **[AF]**

### 4.4 Naming things plainly

**Rule: define the object first, then name it in a separate short sentence. The name is a label, never an argument.**

> "In line with an additive white Gaussian noise (AWGN) channel, we call this channel an additive white SαS noise (AWSαSN) channel." **[VITERBI]**

> "For convenience, we shall refer to this juggling-like ARQ technique as 'J-ARQ', and the time-duplexed SR-ARQ as 'S&W-2' [6] in the rest of this paper." **[JUGGLE]**

> "Schedules that achieve the N/2 upper bound are called perfect schedules." **[DELAY]**

> "This concept is called ambient noise imaging (ANI) and was demonstrated using ADONIS, an ANI camera developed at the Scripps Institution of Oceanography." **[ANI]**

> "The largest propagation delay G = max_{i,j} D_ij characterizes the physical size of the network with respect to cτ and is termed as the size of the network." **[DELAY]**

Acronyms are expanded at first use, in lower case, inside parentheses: "decision feedback equalizers (DFE)", "inter-symbol interference (ISI)", "underwater local area networks (UW-LAN, also known as clusters or cells)" **[REVIEW]**; "the linear correlator (LC)" **[SHRIMP]**; "the probability of bit error (P_b)" **[VITERBI]**.

Where many symbols exist, provide a lookup: > "The symbols used are summarized in Table I for easy reference." **[JUGGLE]**, or the unnumbered **Notation** paragraph placed before Section 2 in **[AF]**.

### 4.5 Analogy

**Rule: one analogy per document, to something the reader already operates, developed for two or three sentences and then dropped. Never extended into a metaphor that carries argument.**

The full form:
> "The concept is similar to the juggling of objects between two hands; although a hand cannot be throwing one object while receiving another concurrently, multiple objects can still be juggled between two hands. Likewise, although the half-duplex underwater acoustic modems cannot transmit and receive concurrently, multiple blocks of data and ACK packets can still be propagating towards each other simultaneously due to the long propagation delay." **[JUGGLE]**

The compact form — analogy to a familiar mathematical object, used to import intuition about a new one:
> "In line with the commonly used Q-function defined in (1), we define a right tail probability function Q_α(x) for the SαS distribution." **[VITERBI]**
> "The scale parameter γ is similar to variance in the Gaussian distribution." **[VITERBI]**
> "The scale parameter (γ), also known as dispersion, determines the spread of the distribution in a similar way to the variance in a Gaussian distribution. When α = 2, γ equals half the variance. A related parameter often used with stable distributions is c (defined as γ^(1/α)), which plays the same role as the standard deviation for stable random variables." **[SHRIMP]**

The reframing analogy — recasting the problem as a familiar problem:
> "The shrimp can be then treated like a deterministic source in a bi-static sonar system with the ANI camera as the receiver." **[ANI]**
> "Hard decision decoding of a rate R code effectively converts the AWSαSN channel into a binary symmetric channel (BSC)." **[VITERBI]**
> "We draw a parallel to the opportunistic exploitation of another natural and equally troublesome phenomenon, i.e., the wireless fading channel, through the use of multiuser diversity [5]." **[DELAY]**

The analogy that is also a warning:
> "Although the acoustic daylight concept has an analog in optical vision and therefore easy to understand, it relies on averaging out the statistical variations in the acoustic noise field." **[ANI]**

**[AF] supplies no analogy.** Its clarity comes entirely from the numbered sonar example (§2.3) and from step-by-step reformulation signposts (§6.4). If an analogy does not come naturally to your material, do not manufacture one — use worked numbers instead.

### 4.6 Figure captions

Two kinds, and the choice is not free.

**Evidence figure → the caption states the finding, in a full sentence, including the caveat.**
> "Figure 1: Average time taken on a typical Desktop computer for signal design using naïve non-convex methods (using MATLAB's optimization toolbox) increases rapidly with signal length." **[AF]**
> "Figure 3: The normalized projection w(k)/n generally reduces as the optimization progresses. As long as ζ is below the threshold, the projection eventually reaches a small value that guarantees a rank-1 solution. Do bear in mind, however, that a small value of w(k) is a sufficient but not necessary condition for a rank-1 solution." **[AF]**
> "Fig. 1. Normal probability plot of snapping shrimp dominated ambient noise shows heavy-tails." **[SHRIMP]**
> "FIG. 1. One-second sample of 25–70 kHz bandpass filtered data collected from ROMANIS hydrophone No. 1 during the 2010 experiment in Singapore showing the impulsive nature of the noise." **[ANI]**

**Definition or illustration figure → a bare noun phrase.**
> "Fig. 1. A two-node network." **[DELAY]**
> "Fig. 2. A more detailed illustration of some of the J-ARQ parameters." **[JUGGLE]**
> "FIGURE 1 — Basic structure of a turbo DFE" **[REVIEW]**

**Line-style legends go in the caption, not only in the figure.**
> "Fig. 1. Performance of antipodal signaling in AWSαSN–based on Q_α (solid line), Cauchy upper bound (dashed line), asymptotic approximation (dash-dot line), performance in Gaussian noise (dotted line), and simulation results (solid dots)." **[VITERBI]**

**Every processing parameter used to make the figure goes in the caption.**
> "FIG. 6. An ambient noise image of the target in the 25–50 kHz band from a 1 s data segment using fractile imaging with f = 0.44. The image is 4× cubic interpolated and sharpened with λ = 0.25. The gridlines demarcate each pixel in the image before interpolation. The estimated position and size of the target based on active insonification is marked in black for reference." **[ANI]**

**On slides:** the slide title takes the role of the evidence caption. Title the slide with the finding — "Frame-wide coupling recovers X dB at 2 m/s" — not with the object — "Simulation results".

### 4.7 Reading a figure in the text

Fixed formulas. Use these and no others.
> "In Fig. 2, we see that the theoretical upper bound derived in (8) is approximately 1 dB higher than the simulation results for hard decision decoding." **[VITERBI]**
> "Fig. 5 shows the detection curves at a moderate SNR of 10 dB." **[SHRIMP]**
> "Figure 6 shows an ambient noise image produced from the first second of the dataset using the fractile imaging algorithm." **[ANI]**
> "The same trend is clearly visible; the ML and LO detectors are the best, followed by the SC, and then the LC." **[SHRIMP]**
> "The FLOM imaging algorithm produces some images of the target, but they show significant variability." **[ANI]**

---

## 5. SENTENCE RULES

**R1. First person plural, always. Never "I", never "the authors" for yourself.**
> "We formulate an optimization problem to minimize the maximum sidelobe levels of such signals over a set of delay-Doppler values." **[AF]**
"The authors" is reserved for people you cite: > "In Stojanovic et al. (1999), the authors proposed an algorithm to track the channel explicitly and determine the tap placement for the DFE based on this channel estimate." **[REVIEW]**

**R2. "We" also carries the reader through the derivation. Use it for the shared walk, not only for authorial acts.**
> "Using (1) and interchanging the order of integration and summations, we get:" **[AF]**
> "Since both nodes are idle for part of the time that the packet is in flight, we see that a fair schedule that allows the nodes to alternately transmit is inefficient." **[DELAY]**
> "Hence, we use robust control packets for the ACK packets, while we use high speed data packets for the transfer of the data in the block." **[JUGGLE]**

**R3. "We" carries every choice — modelling, naming, benchmarking, giving up on a closed form.**
> "we modify this measure by defining N_0 in terms of the dispersion γ such that N_0 = 4γ^{2/α}" **[VITERBI]**
> "we use the ML detector as a benchmark for the performance of other detectors in ambient noise" **[SHRIMP]**
> "Since fα(x) is not available in closed form, we resort to numerical methods to compute the transfer function." **[SHRIMP]**

**R4. Passive voice is reserved for apparatus, procedure, data, and other people's results. Never for your own reasoning or decisions.**
> "The data was acquired at a sampling rate of 500 kilo samples per second (kSa/s) using a high-frequency data acquisition system (HifDAQ) [8]. The acquisition system has an analog bandpass filter that allows acoustic data between 1–180 kHz to be recorded. This data was prewhitened using a 64-order digital finite impulse response (FIR) filter." **[SHRIMP]**
> "The sensors are simultaneously sampled at 196 kSa/s and the data is recorded as a pressure time series for each sensor." **[ANI]**
> "A data packet is considered to be successfully transferred when the packet is successfully received by the receiver and the corresponding ACK is successfully received by the transmitter." **[JUGGLE]**
> "These protocols were shown to be effective for underwater use compared with scheduled protocols early on in the Seaweb project" **[REVIEW]**

**R5. Present tense for facts, properties, claims, and what figures show. Simple past only for what was actually run and for the conclusion's recap. Present perfect for the state of the field.**
> "The hard decision decoding performs significantly better." **[VITERBI]** (present, a property)
> "We simulated a coded BPSK communication system in an AWSαSN channel with a half-rate Odenwalder code." **[VITERBI]** (past, what was run)
> "Two data sets collected at different locations in Singapore waters at different times of the year were used as ambient noise samples." **[SHRIMP]**
> "In the past decade, significant advances have been made in shallow water communication." **[REVIEW]**
> "We studied the effect of both parameters, and suggested ways to tune them." **[AF]** (past, in Conclusions)

**R6. Length 15–35 words. One idea per sentence.**
> "This problem is non-convex and difficult to solve." **[AF]**
> "The hard decision decoding performs significantly better." **[VITERBI]**
> "Typical images from ANI cameras have poor spatial resolution and only a few hundred pixels." **[ANI]**

**R7. Break a long sentence with "i.e.,", a semicolon, or a full stop — never by nesting subordinate clauses.**
> "the propagation delays in underwater networks are typically large, i.e., comparable to or larger than the packet size" **[DELAY]**
> "The same trend is clearly visible; the ML and LO detectors are the best, followed by the SC, and then the LC." **[SHRIMP]**
> "The value of α controls the heaviness of the tails; small values of α result in heavy tails while α = 2 results in a Gaussian distribution." **[VITERBI]**
Exception: **[REVIEW]**'s never-list bans "i.e." and "e.g." entirely — in that paper he writes "such as" or restates in words. **Prescription for the tutorial decks: follow [REVIEW] and spell it out; for the journal paper, follow [DELAY] and use "i.e.," freely.**

**R8. Sentence openers, in order of frequency: "However,", "Since", "Although", "Hence", "Therefore", "Thus", "As", "Note that", "For example,".**
> "However, in an AWSαSN channel, the Euclidean norm metric is not optimal." **[VITERBI]**
> "Since the nodes are static, we assume the channel to be time invariant over the duration of the data transfer." **[JUGGLE]**
> "Since we wish to locate snaps from shrimp on the seabed, we only consider snaps with θ_k < 0." **[ANI]**
> "Therefore, we regard X(k) as rank-1 in a practical sense when w(k) is small enough." **[AF]**
> "Hence most channel impulse response algorithms have difficulty coping with surf zones." **[REVIEW]**
> "As increased model order leads to increased estimation noise, a model order penalty is imposed in the optimization." **[REVIEW]** — "As" fronts the reason for a design decision, in place of "because".
> "Note that k = 3 for the example shown." **[JUGGLE]**

**R9. Concessive-then-step-past is the default rhythm for any difficulty: "Although X, Y" or "X, but Y".**
> "Although the random variable n_t has an infinite variance, the random variable g(√(RE_b) + n_t) has a finite variance because g(y) is bounded." **[VITERBI]**
> "Although MAP equalization is computationally intensive, per-survivor processing (PSP) helps reduce the number of trellis states used in channel equalization." **[REVIEW]**
> "Although each pixel takes a finite value as the sampled x_{b,t} are finite, the infinite expected value implies that pixel values simply do not converge irrespective of the averaging time." **[ANI]**

**R10. Parentheses gloss, define, or give the concrete equivalent. They never editorialise and never carry a joke.**
> "a weighted sum of the original cost function and an eigenvalue residual (sum of all eigenvalues except the highest)" **[AF]**
> "for E_b/N_0 > 0.25 (i.e., −6 dB)" **[VITERBI]**
> "it allows the sender to receive an ACK packet for an earlier (i.e., not the most recent) block of data packets" **[JUGGLE]**
> "as long as we keep X(k−1) (approximately) rank-1 for all the k" **[AF]**
The one licensed informal use is a parenthetical aside carrying a judgement: > "Rather than fighting what is a natural phenomenon (which is arguably out of our sphere of influence)" **[DELAY]**

**R11. Hedge precisely and gradedly. The permitted words: generally, typically, often, usually, roughly, about, approximately, slightly, somewhat, likely, perhaps, may, can, seems to be, believed to.**
> "the SC performs only slightly worse than the ML and LO (Fig. 6)" **[SHRIMP]**
> "the LC performance is somewhat worse than the other detectors" **[SHRIMP]**
> "these are probably surface reflections of snaps originating on the seabed" **[ANI]**
> "Intuitively speaking, when ζ approaches 0, we effectively search for a rank-1 matrix without taking the original cost function into account." **[AF]**

**R12. Flag surprise with a mid-sentence adverb, never with an intensifier or an exclamation.**
> "we find, rather surprisingly, that large propagation delays" **[DELAY]**
> "Not surprisingly, this is the best you can do." **[DELAY]**

**R13. Second person is permitted exactly once, inside a worked example, and nowhere else.** The only instance across seven papers: > "Not surprisingly, this is the best you can do." **[DELAY]**

### What he never does — every one of these is a hard prohibition

| Banned | Evidence | Write instead |
|---|---|---|
| Contractions ("don't", "it's", "we've") | never-lists of all seven papers | "does not", "cannot", "is not" |
| Exclamation marks | never-lists of all seven | — |
| "novel" as self-description, more than once | **[AF]**, **[SHRIMP]**, **[ANI]**, **[REVIEW]** never-lists; one hedged use each in **[JUGGLE]**, **[DELAY]** | "we propose", "we present", "new" |
| "state-of-the-art", "cutting-edge", "groundbreaking", "seminal", "pioneering" | all seven never-lists | name the specific prior method |
| "paradigm", "framework" as a buzzword | **[AF]**, **[DELAY]**, **[JUGGLE]**, **[VITERBI]**, **[SHRIMP]** | say what the thing is |
| "leverage", "utilize", "facilitate", "employ", "showcase", "delve into" | **[DELAY]**, **[VITERBI]**, **[ANI]**, **[JUGGLE]** never-lists | "use", "exploit" |
| "in order to" | **[SHRIMP]**, **[ANI]** never-lists | "to" |
| "crucial", "vital", "critical" as intensifiers | **[AF]**, **[DELAY]**, **[SHRIMP]**, **[ANI]** | "key", or delete |
| "obviously", "clearly" as an argument | **[AF]** | give the reason |
| "It is worth noting that", "It should be emphasized that", "It is interesting to note that" | **[AF]**, **[SHRIMP]**, **[ANI]**, **[JUGGLE]** | "Note that" **[JUGGLE, DELAY]**, or nothing |
| "significantly outperforms" without a number | **[AF]**, **[JUGGLE]**, **[ANI]** | "approximately 2 dB better" **[VITERBI]**, "up to 4 dB" **[AF]**, or "qualitatively better" **[ANI]** |
| "To the best of our knowledge" | **[JUGGLE]**, **[SHRIMP]**, **[ANI]**, **[REVIEW]** never-lists; **one** licensed use in **[AF]** | one use per document, attached to a *problem* not a method: "To the best of our knowledge, this problem has not been previously tackled effectively." **[AF]** |
| "The contribution of this paper is threefold" | **[JUGGLE]**, **[VITERBI]**, **[SHRIMP]**, **[ANI]** | "we make two key contributions" **[JUGGLE]**; "The purpose of the gap is twofold." **[JUGGLE]** |
| "Extensive simulations", "comprehensive evaluation" | **[JUGGLE]** | "Monte Carlo simulation", "all our test scenarios" |
| "Firstly… Secondly… Finally," scaffold | **[SHRIMP]** | "First, we rewrite…", "We next expand…", "Now the optimization problem can be written…" **[AF]** |
| "Moreover"/"Furthermore"/"In addition" as paragraph openers | **[JUGGLE]** | "Hence", "Thus", "However", "Nevertheless", "Also" |
| "robust" as vague praise | **[DELAY]** | "robust in SαS noise" **[VITERBI]** — always with the condition attached |
| Rhetorical questions | **[VITERBI]**, **[SHRIMP]**, **[REVIEW]** never-lists | permitted only as the **[JUGGLE]** device (§2.2) |

---

## 6. MATHEMATICS

### 6.1 The five-part equation unit

Every displayed equation is wrapped in this structure. No exceptions.

**(1) Introduce every symbol in prose, before the display, using "Let … be …" or "Given …".**
> "Let sj = e^{iθj} ∀ j ∈ {0 · · · N − 1} be the symbols of a complex baseband unimodular signal of length N. We assume periodic signals, and hence for all other j, sj = sj mod N. If the symbol duration is T then the baseband signal x(t), with period NT, is given by:" **[AF]**

> "Let x_{b,t} be the band-limited acoustic pressure arriving at the ANI camera in a given receive beam b sampled at time index t. Since acoustic intensity is proportional to the square of the acoustic pressure, the energy in beam b arriving within one sampling period is Cx_{b,t}² for some constant C. The average energy y_{b,k} in frame k is given by" **[ANI]**

> "Letting s(t) be the signal, A the signal strength and n(t) the noise, the observed data x(t) can be written as" **[SHRIMP]**

**(2) The display is grammatically part of the sentence before it.** The lead-in ends in "is given by", "we have", "can be written as", "we get", or a colon. It is never a standalone sentence followed by an orphan equation.
> "The throughput S is therefore given by" **[JUGGLE]**
> "Hence, the expected number of data bits transferred during a block is given by" **[JUGGLE]**
> "Defining matrix Aαδ = [Aαδjk], we can write χ(α, δ) as:" **[AF]**

**(3) Immediately after, a "where" clause defining every symbol not yet defined.**
> "where g(t) is the pulse shaping function." **[AF]**
> "where ω = 2πf." **[AF]**
> "where θ is the shape parameter of the GP distribution." **[JUGGLE]**
> "where N is the length of the frame in samples." **[ANI]**
> "where F_f[X] refers to the fth fractile of the random variable X." **[ANI]**
> "where d_f is the free distance of the code and p_d is the pair-wise probability of error with weight d." **[VITERBI]**
> "where Ď_ij = (cτ D_ij)² and V_N is the Schoenberg auxiliary matrix [23, p. 228]" **[DELAY]**
> "where δ ≥ δmin represents the gap duration's allowance above the ACK packet's duration." **[JUGGLE]**

**(4) Then a sentence in words that says what the equation means, what it now permits, or what physical operation it corresponds to. This sentence contains no new symbol.**
> "The real passband signal transmitted is simply ℜ[x̃(t)], and the passband analytic signal can be easily reconstructed on reception using a Hilbert transform." **[AF]**
> "The sidelobe level at Doppler α and delay δ is defined as |χ(α, δ)|. The mainlobe level is |χ(0, 0)| = 1." **[AF]**
> "In the previous expression, α is the characteristic exponent controlling the heaviness of the tails." **[SHRIMP]**
> "The estimated signal strength is expected to be close to zero when no signal is present." **[SHRIMP]**
> "To implement this, the N beam energy values {x²_{b,Nk} · · · x²_{b,Nk+N−1}} are sorted in ascending order and the (⌊fN⌋ + 1)th value is chosen as y_{b,k}." **[ANI]**
> "If Q_jt = i > 0, then node j transmits a message to node i during time slot t. If Q_jt = −i < 0, then node j receives a message from node i during the time slot t. In all other cases, node j is defined to be idle during time slot t and we set Q_jt = 0." **[DELAY]**

**(5) Then, when applicable, one or more of: the special case that reduces to something familiar; what cannot be done with the equation; the design reason for each factor.**

*Reduction to the familiar:*
> "For the special case of α = 2, the SαS distribution reduces to a Gaussian distribution and the minimization in (5) results in the familiar LC estimator" **[SHRIMP]**

*What cannot be done — stated flatly, immediately:*
> "Q_α(x) is not known in closed form." **[VITERBI]**
> "Unfortunately, no closed form expression exists for the general SαS density and distribution functions, except for the Gaussian (α = 2) and Cauchy (α = 1) cases. However, there are efficient numerical methods for computing the pdf [13]." **[SHRIMP]**
> "In the case of the SαS distribution, the minimization of L̃ does not yield a closed-form solution in general. Numerical minimization of L̃ leads to an optimal estimate of signal strength, but typically is computationally intensive." **[SHRIMP]**
> "Since x_{b,t} is modeled as an SαS random variable, E[x_{b,t}²] is generally infinite (except for the special case of α = 2). Hence E[y_{b,k}] is also generally infinite." **[ANI]**

*Factor-by-factor design justification — the strongest device in the set:*
> "Equation (5) is motivated by 3 but replaces x_{b,t}² by |x_{b,t}|^p to keep the expected value of the pixel finite. The multiplicative constant C/N is dropped without any effect, since the final image is scaled to fit the dynamic range of the display pixels. The power 2/p is introduced to keep the units consistent with other statistical measures and thereby allowing direct comparison of the resulting images." **[ANI]**

**Prescription for the OFDM documents: every term in the JUNA cost function gets one sentence of this kind — why it is there, what would go wrong without it, and whether dropping it changes anything.**

### 6.2 What is never left uninterpreted

- **A term whose presence is not obvious.** See the **[ANI]** three-sentence pattern above.
- **An operator that cannot be simplified.** > "The ambiguity function's sidelobes are determined by s†Aαδ s, which is in general complex, since Aαδ is not Hermitian. Therefore, the | · | operator cannot be dropped, and the problem cannot be reduced to a quadratic form, to which diagonal loading is often applied to further transform the cost function into a convex form that is readily optimized [17, 8]." **[AF]**
- **An infinite sum.** Say how many terms actually matter, with the physical reason: > "While computation of Aαδjk requires infinite sums, we can see from (5) that for practical pulse shapes with finite support and small Doppler, all except one or two of the Āαδjk terms are zero. For most practical Doppler and delays values, we only need to evaluate this sum for m, p ∈ {−1 · · · 1}." **[AF]**; > "Although the summation in (7) has an infinite number of terms, typically the terms are decreasing in magnitude and the summation of the first few terms provides an acceptable upper bound." **[VITERBI]**
- **A bound.** Say how you will use it and how tight it is: > "The mean μ_g and variance σ_g² of g(√(RE_b) + n_t) cannot be evaluated in closed form, but an upper bound on p_d can be found by assuming a Cauchy distribution for n_t, which underestimates the mean and overestimates the variance." **[VITERBI]**
- **How the optimisation is actually solved.** > "The maximization problem is easily solved using an iterative numerical technique such as steepest gradient descent, or simply by an exhaustive search over practical values of nd and m." **[JUGGLE]**

### 6.3 Reformulation is narrated step by step, one signpost sentence per step

> "First, we rewrite the problem in terms of decision variables s, rather than θ:" … "We next expand s into its real and imaginary components:" … "Now the optimization problem can be written in terms of decision variables X:" … "We can simplify the objective function by defining a collection of 2|Q| + 1 new optimization variables:" **[AF]**

> "We choose a new slot length τ′ = τ/LCM{q_ij}, where LCM{q_ij} is the least common multiple of all the denominators in the delay matrix. Using this slot length, the new delay matrix is given by [(4)–(5)]. Since LCM{q_ij} is divisible by all q_ij, all entries in the delay matrix D′ are integers." **[DELAY]**

### 6.4 State the price of every transformation

**Rule: after any reformulation, say in one sentence what was gained and what was paid. Never present a reformulation as free.**
> "In going from (9) to (12), we have not made any approximations or relaxations. However, we have increased the dimensionality of the problem from N to N(2N + 1) + 2|Q| + 1." **[AF]**

### 6.5 Documents with no equations

**[REVIEW]** contains no displayed or numbered equation. Its quantitative reasoning runs inline in prose:
> "For a transmit duty cycle of 0.4%, a 3% loss due to collisions is obtained. Assuming no loss due to bit errors, a physical layer data rate of 5 kbps only yields an effective data rate per node of 5 × 0.4% × 97% = 19.4 bps." **[REVIEW]**

And its physical reasoning likewise:
> "If the received signal is a sum of a large number of multipath arrivals, each of which are modeled as a complex Gaussian stochastic processes, the resulting model is the well-known Rayleigh fading channel." **[REVIEW]**
> "Information theoretic studies have shown that the capacity of a channel increases linearly with the minimum of the number of transmit and receive antennas. This increase in capacity translates to a corresponding increase in achievable data rate through the use of multiple input multiple output (MIMO) processing techniques and space-time coding." **[REVIEW]**

**Prescription for the tutorial decks and slide talks: follow [REVIEW]. Carry every relationship in words and one arithmetic line. A slide that shows an equation must satisfy §6.1 parts (3) and (4) on the same slide — the "where" line and the meaning line — or the equation comes off the slide.**

---

## 7. HONESTY

The exact sentence forms, to be used verbatim as templates.

**Form H1 — The flat admission. A short declarative, no cushioning, placed immediately after the thing being admitted about.**
> "This problem is non-convex and difficult to solve." **[AF]**
> "Q_α(x) is not known in closed form." **[VITERBI]**
> "Typical images from ANI cameras have poor spatial resolution and only a few hundred pixels." **[ANI]**
> "The SαS distribution does not have a general closed-form pdf f_α(x; γ) or cumulative distribution function (cdf) F_α(x, γ) except in the special cases of α = 1 and α = 2." **[VITERBI]**
> "There has been no consensus among researchers on the model applicable in shallow waters." **[REVIEW]**

**Form H2 — "Although X, Y": grant the deficiency, then give the compensating property. The deficiency comes first.**
> "Although the performance of the sign correlator is slightly inferior to that of the ML detector, it is very simple to implement and does not require detailed knowledge of the noise statistics." **[SHRIMP]**
> "Although its computational complexity makes the ML detector impractical for most real-time applications, we use the ML detector as a benchmark for the performance of other detectors in ambient noise." **[SHRIMP]**
> "Although select data from ADONIS was used to successfully produce images of submerged objects at up to 40 m range, much of the data yielded no recognizable images." **[ANI]**
> "Although it is possible to improve the efficiency arbitrarily by choosing a very large block size so as to downplay the effect of the idling time, the average queuing delay resulting from such a strategy could become unacceptably large." **[JUGGLE]**
> "Although TRM helps reduce delay spread of the channel, it does not eliminate ISI completely." **[REVIEW]**

**Form H3 — "However, …": the pivot against your own preceding claim.**
> "However, this is not the case in our problem since our cost function cannot be simplified to a quadratic form, and our constraints are strictly defined as the intersection of the boundaries instead of exteriors of hyper-ellipsoids." **[AF]**
> "However, the performance is significantly poorer at high E_b/N_0 even for a small deviation from Gaussian noise (α = 1.99), as the errors are dominated by the tail behavior of the noise distribution." **[VITERBI]**
> "However, as the beamformer steers the beam away from broadside, the performance drops." **[ANI]**

**Form H4 — The scope limit, with its reason attached in the same sentence.**
> "As most practical environments have noise with α in the range of 1.5–2, we limit our analysis in this paper to 1 < α ≤ 2." **[VITERBI]**
> "We only present results in the lower part of the frequency band (25–50 kHz) of ROMANIS as the robustness of images at higher frequencies was found to be significantly lower." **[ANI]**

**Form H5 — The explicit non-attempt: what this document will not do.**
> "In this paper, we do not attempt to provide an exhaustive survey of all research in the field, but instead concentrate on ideas and developments that are likely to be the keystone of future underwater communication networks." **[REVIEW]**

**Form H6 — The price of a good result, introduced by a semicolon.**
> "However, its throughput comes with a price; a sender can only transmit at most two packets in a single round-trip time, unlike the J-ARQ." **[JUGGLE]**

**Form H7 — What was not tested, and why not.**
> "The ML and LO detectors were not tested due to computational limitations and the unavailability of independent ambient noise samples to obtain detailed noise statistics." **[SHRIMP]**
> "Although the simulations used ambient noise data recordings from the sea, actual mixing of the noise with the signal was performed numerically." **[SHRIMP]**
> "The paper presents strong analytical results and upper bounds on system performance, but the ideas have yet to be experimentally tested." **[REVIEW]**
> "We have previously shown that carefully selected snaps can indeed be used for passive ranging, but the selection process used was not automated." **[ANI]**

**Form H8 — The method that did not work, named and buried honestly.**
> "In our case, the minimax nature of the optimization problem makes it even harder to establish a guarantee on the quality of the extracted eigenvector, and indeed the method did not yield good results." **[AF]**
> "Due to constraints (13), the trace and nuclear norm in our problem are constant, and thus attempting to minimize these does not help to reduce the rank of X." **[AF]**

**Form H9 — The unproven property, declared in the section that would be expected to prove it.** **[AF]** Section 4 "Convergence" opens by stating that global convergence is not proved, defines local convergence, and proves only monotone non-increase. **Prescription: if JUNA's iteration is not proved to converge, the section is still called "Convergence", and its first sentence says what is not proved.**

**Form H10 — The generalisation you cannot verify, hedged inside the claim.**
> "Although the statistical methods were developed based on intuitions from SαS noise distribution, the methods are not critically dependent on the distribution; the methods are likely to work well in most impulsive noise environments." **[ANI]**
> "Our research is but a step in the direction of understanding" **[DELAY]**

**Form H11 — The blunt normative warning to the reader.**
> "Hence, we cannot just blindly adopt a juggling approach." **[JUGGLE]**

**Form H12 — The caveat inside a figure caption, so it cannot be read past.**
> "Do bear in mind, however, that a small value of w(k) is a sufficient but not necessary condition for a rank-1 solution." **[AF]**

**Form H13 — Disagreeing with prior work, without impoliteness.**
> "This conclusion is not in agreement with the results obtained in this paper." **[SHRIMP]**
> "As acknowledged by the authors, the primary limitation of such a channel model is the availability of an accurate and calibrated surface time-variation model. Moreover the time-variation in the channel is not limited to surface reflected arrivals." **[REVIEW]**
> "However, no performance measures are shown, and as noted by the authors, their protocol is only suitable for small networks with specific geometries." **[DELAY]**

**Placement rule.** The limitation goes where the claim is, not in a "Limitations" section at the end. In all seven papers the concession sits in the same paragraph as the claim it qualifies, and in **[AF]**, **[JUGGLE]** and **[SHRIMP]** it also sits in the abstract.

---

## 8. WORKED REWRITES

---

### (a) Original

> "RPC combines M partial-FFT observations per carrier, yet its inferential support remains local: each W_k is constrained only by nearby pilots or by decision-directed recursion over tentative symbols."

### Rewrite

> Partial-FFT combining estimates a separate weight vector W_k for every carrier k, using the M partial-FFT observations of that carrier. Each W_k is estimated from the pilots close to carrier k, or by decision-directed recursion over tentative symbols. However, two carriers far apart in the band are then estimated independently, even though the Doppler that couples them is common to the whole frame. Hence each pilot constrains only a few carriers, and the estimates become noisy when the pilots are sparse.

### Every change, and where the pattern comes from

| # | Change | Pattern source |
|---|---|---|
| 1 | Expanded "RPC" into what it physically does before using the acronym. | "decision feedback equalizers (DFE)", "inter-symbol interference (ISI)" — acronym expanded at first use **[REVIEW]**; "the linear correlator (LC)" **[SHRIMP]** |
| 2 | Split one 33-word sentence with a colon-dump into four sentences of 16–27 words, one idea each. | "The hard decision decoding performs significantly better." **[VITERBI]**; R6/R7 above |
| 3 | Deleted "its inferential support remains local" — an abstract nominalisation stating a property with no mechanism. Replaced with the mechanism ("two carriers far apart … are estimated independently") and the physical fact that makes it wasteful ("the Doppler that couples them is common to the whole frame"). | The factor-by-factor interpretation habit: "Equation (5) is motivated by 3 but replaces x_{b,t}² by \|x_{b,t}\|^p to keep the expected value of the pixel finite." **[ANI]**; §6.1 part (4) |
| 4 | Replaced the mid-sentence "yet" with a sentence-initial "However,". | "However, the broadband ambiguity surface for such signals exhibit high sidelobe levels…" **[AF]**; "However, in an AWSαSN channel, the Euclidean norm metric is not optimal." **[VITERBI]** |
| 5 | Removed the colon as a logical connective. Chitre's colons introduce displayed equations and lists, never a consequence. | Every colon in **[AF]** §3 introduces a display: "First, we rewrite the problem in terms of decision variables s, rather than θ:" |
| 6 | Added a final "Hence …" sentence giving the *cost* of the structural fact. The original states a structure and stops; the reader is not told why to care. | "Hence powerful forward error correction (FEC) codes are needed to ensure low bit error rate (BER) communication." **[REVIEW]**; "Hence, the expected number of data bits transferred during a block is given by" **[JUGGLE]** |
| 7 | Kept the criticism of RPC fair — it is described as doing something reasonable, and the deficiency is a consequence of the design, not a flaw of the designers. | "Coherent modulation schemes such as PSK … have been shown to be an effective way of communication in such channels. However, the long delay spread … often makes this approach computationally too complex for real-time implementations." **[REVIEW]**; "In spite of this, many signal processing algorithms still use the LC … due to its simple implementation" **[SHRIMP]** |
| 8 | Added the condition under which the deficiency bites ("when the pilots are sparse"). A deficiency is never stated unconditionally. | "However, the performance of the LC is poor **in warm shallow waters where snapping shrimp noise dominates in the range 2–300 kHz**." **[SHRIMP]**; "undesirable **in applications where the signal is subject to broadband Doppler**" **[AF]** |

**If this sentence appears on a slide,** it becomes two lines and one picture: the picture shows pilots constraining a local neighbourhood; the title states the consequence ("Each pilot constrains only a few carriers"), following the evidence-caption rule of §4.6.

---

### (b) Original

> "JUNA is the natural lifting of the pilot-stacked inverse problem underlying RPC."

### Rewrite

> Partial-FFT combining estimates each carrier's weights from the pilots in its own neighbourhood. Suppose instead that we stack all the pilots in the frame into a single linear system and solve for the weights of all carriers jointly. We call the resulting estimator JUNA. Partial-FFT combining is then the special case of JUNA in which each carrier is allowed to see only its neighbouring pilots.

### Every change, and where the pattern comes from

| # | Change | Pattern source |
|---|---|---|
| 1 | Deleted "natural". A method is never described by its author as natural, elegant, or principled. | "novel" is on the never-list of **[AF]**, **[SHRIMP]**, **[ANI]**, **[REVIEW]**; **[SHRIMP]** never-list: "he says 'we show', 'we demonstrate', 'we establish', never 'novel' or 'propose'". The one licensed use of a value word for a method is the graded verdict: "This makes it an attractive compromise between the simple LC and the complex ML detector." **[SHRIMP]** |
| 2 | Deleted "lifting". A term of art that the target readership of an OFDM receiver paper does not share, used without gloss. Replaced by the operation it denotes, in verbs: "stack all the pilots … into a single linear system and solve … jointly". | Every parameter is defined in words before symbols: "Stable distributions are characterized by four parameters—characteristic exponent α, location parameter μ, scale parameter c, and skewness parameter β. Characteristic exponent α controls the heaviness of the tails." **[ANI]** |
| 3 | Deleted "pilot-stacked inverse problem underlying RPC" — three stacked modifiers naming an object the reader has not met. Replaced by a sentence that constructs the object step by step. | "First, we rewrite the problem in terms of decision variables s, rather than θ:" / "We next expand s into its real and imaginary components:" **[AF]** |
| 4 | Moved the name to its own short sentence, **after** the definition. | "In line with an additive white Gaussian noise (AWGN) channel, we call this channel an additive white SαS noise (AWSαSN) channel." **[VITERBI]**; "For convenience, we shall refer to this juggling-like ARQ technique as 'J-ARQ'" **[JUGGLE]**; "Schedules that achieve the N/2 upper bound are called perfect schedules." **[DELAY]** |
| 5 | Replaced the unfalsifiable relational claim ("is the natural lifting of") with a checkable one: RPC is the special case obtained under a stated restriction. The reader can now verify the relationship instead of accepting it. | "For the special case of α = 2, the SαS distribution reduces to a Gaussian distribution and the minimization in (5) results in the familiar LC estimator" **[SHRIMP]**; "When α = 2, the distribution reduces to a Gaussian distribution." **[SHRIMP]**; "Hard decision decoding of a rate R code effectively converts the AWSαSN channel into a binary symmetric channel (BSC)." **[VITERBI]** |
| 6 | Introduced "we" for the construction, and "Suppose instead that we …" for the reader-inclusive step. | "Using (1) and interchanging the order of integration and summations, we get:" **[AF]**; "To illustrate how one might exploit nonzero propagation delays, we start with the simple two-node network and see what we can learn from it." **[DELAY]** |
| 7 | Used "Suppose instead" to mark the pivot from the existing method to the new one, so the new method is defined by its difference. | "In FLOM imaging, we used FLOM to measure the spread of the SαS random variable. However, a more natural measure of the spread is the scale parameter c. We therefore consider the use of c² as the pixel value rather than the sample variance in 3." **[ANI]** |

**Note on the one word retained in spirit.** "A more natural measure of the spread" does appear in **[ANI]** — but attached to a *quantity* (the scale parameter c), with the reason given in the following sentences, not attached to the author's own method as a claim of inevitability. If the naturalness of JUNA is genuinely the argument, it must be made as **[ANI]** makes it: name the quantity, say why it is the right one to measure, and show what the previous choice measured instead.

---

### (c) Original

> "The lightweight variant approximates the reduced code-aware update without forming a gradient."

### Rewrite

> Forming the gradient of the code-aware update requires one pass through the decoder for every carrier, which is too expensive for a real-time receiver. We therefore replace the gradient by a single scaling of the pilot-only update, with the scale set by the decoder's soft outputs. We refer to this as JUNA-Lite. It costs about ⟨N⟩ times less computation than the full update, and recovers ⟨X⟩ dB of the ⟨Y⟩ dB gain that the full update provides at ⟨2 m/s⟩.

*The three bracketed placeholders are not optional and must be filled with measured numbers. See change 6.*

### Every change, and where the pattern comes from

| # | Change | Pattern source |
|---|---|---|
| 1 | Put the **cost of the alternative first**. The original assumes the reader already wants a cheaper method; the rewrite establishes the expense before offering the remedy. | "As a maximum likelihood solution for Doppler compensation is computationally far too expensive to be practical, a simpler solution is needed." **[REVIEW]**; "The computational complexity of MAP equalization increases exponentially with channel length. Even with PSP, this complexity can be too high for practical implementation." **[REVIEW]**; "Although its computational complexity makes the ML detector impractical for most real-time applications…" **[SHRIMP]** |
| 2 | Quantified the expense in an operational unit the reader can price — decoder passes per carrier — instead of the adjective "lightweight". | "The algorithm placed an average of 10 feedforward taps and 25 feedback taps" **[REVIEW]**; "roughly 95% of the incoming acoustic signal is therefore unavailable for processing" **[ANI]** |
| 3 | Replaced the negative definition ("without forming a gradient") with a positive one: what the method *does* instead. | "we modify this measure by defining N_0 in terms of the dispersion γ such that N_0 = 4γ^{2/α}" **[VITERBI]**; "Instead, we follow a generalization of the trace heuristic for rank minimization in [37], and minimize a weighted sum of the original cost function and an eigenvalue residual" **[AF]** |
| 4 | Deleted the three stacked pre-modifiers "lightweight … reduced code-aware". Each idea now sits in its own clause. | R6/R7; "Movement of transducers, ocean surface, and internal waves lead to rapid time variation and, consequently, a high Doppler spread in the channel." **[REVIEW]** |
| 5 | Moved the name to its own sentence, after the method is defined. | Same sources as (b) change 4 — **[VITERBI]**, **[JUGGLE]**, **[DELAY]** |
| 6 | Added the quantified trade-off. A cheap approximation is never described only as cheap; the saving and the loss are both given as numbers. **A comparative adjective without a number is one of the few things he never writes.** | **[AF]** never-list: "'significantly outperforms' with no number attached — improvements are always quantified"; the model closing sentence is **[VITERBI]**'s: "The performance of the decoding using the 1-norm metric is very close to that of the maximum likelihood decoding. As the computational complexity of the 1-norm metric is much lower than that of the [ML metric]…"; and **[AF]**'s conclusion: "we demonstrated an reduction in maximum sidelobe levels of up to 4 dB (depending on signal parameters such as length, frequency, bandwidth, etc)" |
| 7 | "We therefore replace …" — the choice is made by "we", in the active voice, with "therefore" carrying the deduction from the cost sentence. | "We therefore consider the use of c² as the pixel value" **[ANI]**; "Since fα(x) is not available in closed form, we resort to numerical methods" **[SHRIMP]**; "Therefore, we regard X(k) as rank-1 in a practical sense when w(k) is small enough." **[AF]** |
| 8 | Named the operating point ("at ⟨2 m/s⟩") with the performance claim. Performance is never quoted without the condition under which it was measured. | "Fig. 5 shows the detection curves at a moderate SNR of 10 dB." **[SHRIMP]**; "approximately 2 dB better than that of the hard decision decoding" **[VITERBI]**; "The bound is loose at low E_b/N_0 and high α, and becomes tighter when the noise becomes more impulsive" **[VITERBI]** |

**The sentence that must follow this one in the paper.** Having claimed that JUNA-Lite recovers most of the gain, the next sentence states where it does not, following Form H2:

> Although JUNA-Lite recovers most of the coding gain at ⟨2 m/s⟩, it falls ⟨Z⟩ dB short of the full update at ⟨higher speeds / low pilot density⟩, where the scaling can no longer track the ⟨…⟩.

Pattern: "We show that the juggling-like ARQ provides good data streaming throughput but performs poorly for small file transfers." **[JUGGLE]**; "The performance of this detector was found to be comparable but slightly inferior to the optimal detectors." **[SHRIMP]**

---

## QUICK CHECKLIST BEFORE SUBMITTING ANY PAGE

1. Does the first sentence of this section describe the world, or the paper? It must be the world.
2. Does every claim of improvement carry a number and the condition it was measured under?
3. Is there a "However," or "Although" within three sentences of every claim?
4. Does every displayed equation have a "where" clause and a following sentence with no new symbols?
5. Is every arbitrary constant either shown not to matter, tied to a convention, cited, tied to the apparatus, or swept as a free parameter?
6. Has every alternative you dismissed been named, granted its motivation, and refuted specifically?
7. Search the file for: `novel`, `state-of-the-art`, `framework`, `paradigm`, `leverage`, `utilize`, `in order to`, `crucial`, `vital`, `clearly`, `obviously`, `It is worth noting`, `'`(apostrophe in contractions), `!`. Each hit is a defect unless it is one of the licensed single uses named in §5.
8. Is any sentence longer than 35 words, or carrying two ideas? Split it at the "i.e.," or the semicolon.
9. Does every evidence figure's caption state the finding rather than name the axes?
10. Would a reader who stopped after the introduction know the number that makes this problem hard?