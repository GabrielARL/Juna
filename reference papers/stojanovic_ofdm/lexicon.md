# Stojanovic OFDM lexicon

Every term below appears verbatim in the PDFs beside this file. Where she uses
one word and the field uses another, the column *not her word* records what she
avoids, so a draft can be checked mechanically.

Sources are abbreviated: `ST07` Sea Technology 2007, `ASL09` Asilomar 2009,
`CM09` Comm. Mag. 2009, `PC08` Physical Communication 2008, and author-year for
the supervised journal papers.

---

## 1. The signal

| Her word | Not her word | Evidence |
|---|---|---|
| carrier, subband | tone (except *control tones*, *pilot tones*) | "the available bandwidth is divided into many narrow subbands" ST07 |
| subcarrier | — | used from ~2008 on in co-authored papers; both forms are live |
| OFDM block | OFDM symbol | "The K data symbols comprise one OFDM block, whose duration is T=1/∆f" ST07 |
| frame | packet, burst | "a dedicated high-resolution probe that precedes a frame of OFDM blocks" ST07 |
| data symbol | — | "The estimates of the data symbols" ST07 |
| guard interval | guard time (used once, ASL09: "the multipath guard time Tg") | "A guard interval of length Tg corresponding to the multipath spread" ST07 |
| zero-padding, zero-padded (ZP) | — | "zero-padding saves transmission energy" ST07 |
| cyclic prefix | CP-OFDM (spelled out in prose) | "While cyclic prefix is a traditional choice…" ST07 |
| overlap-add, overlap adding | — | "overlap adding [15] was performed prior to FFT demodulation" ASL09 |
| carrier spacing, carrier separation ∆f | subcarrier spacing (appears in co-authored work) | "the carrier separation ∆f narrows" ST07 |
| modulation level | constellation order | "a varying number of carriers (128-1024), transmitters (1-3), and modulation levels (4 and 8 PSK)" ASL09 |
| null carriers, pilots, pilot tones | reference symbols | "these symbols must be known a-priori (pilots or null carriers)" ASL09 |
| probe | preamble, sync word | "a dedicated high-resolution probe" ST07 |
| control tones | — | "The control tones are digitally optimized to provide PAR reduction" Rojo 2010 |

## 2. The channel

| Her word | Not her word | Evidence |
|---|---|---|
| multipath spread | delay spread (she uses *delay spreading* for the effect) | "Delay spreading over tens or even hundreds of milliseconds" CM09 |
| frequency-selective distortion | — | "the frequency-selective distortion of a multipath channel" ST07 |
| impulse response domain | time domain | "represent the MIMO channel in the impulse response domain" ASL09 |
| significant impulse response coefficients | dominant taps | "J ≤ L as the number of significant impulse response coefficients" ASL09 |
| total contiguous span L | channel memory | "we define L as the total contiguous span" ASL09 |
| sparse channel, channel sparsing, sparsing | pruning, thresholding | "The complexity of the problem can be reduced through channel sparsing" ASL09 |
| truncation in magnitude | hard thresholding | "Optimal coefficient selection (sparsing) is performed by truncation in magnitude" PC08 |
| coherence time Tcoh | — | "constrained by the coherence time of the channel, Tcoh" ASL09 |
| spread factor | — | "constrained by the spread factor of the channel, K/L << Tcoh/Tmp" ASL09 |
| non-minimum phase | — | "an underwater acoustic channel is rarely of minimum phase" ASL09 |
| path loss A(l,f), absorption, spreading loss | — | "The path loss exponent k models the spreading loss" CM09 |
| ambient noise, site-specific noise | — | "Noise in an acoustic channel consists of ambient noise and site-specific noise" CM09 |
| shallow water, deep ocean, main thermocline | — | CM09 throughout |

## 3. Doppler

This is her home ground and the vocabulary is fixed.

| Her word | Evidence |
|---|---|
| Doppler factor `a = v/c` | "The magnitude of the Doppler effect is proportional to the ratio a = v/c" CM09 |
| Doppler rate `a(n)` | "the resulting Doppler rate a=v/c on the order of 10-3" ST07 |
| Doppler scaling factor | "we treat the channel as having a common Doppler scaling factor on all propagation paths" Li 2008 |
| non-uniform Doppler shifting / nonuniform Doppler shifts | "the non-uniform Doppler shifting in a wideband acoustic system" ASL09 |
| motion-induced Doppler distortion | "In a wideband system, motion-induced Doppler distortion results in frequency shifting that is not uniform" ST07 |
| Doppler spreading *and* Doppler shifting (kept distinct) | "motion introduces additional Doppler spreading and shifting" CM09 |
| residual Doppler (after initial resampling) | "at(n) represents the residual Doppler factor (after initial resampling)" ASL09 |
| resampling, front end | "the time-variation caused by the motion-induced Doppler effects that can be compensated for by resampling at the receiver's front end" ASL09 |
| frequency offset | "It can only tolerate a frequency offset that is much smaller than the carrier spacing ∆f" ST07 |
| inter-carrier interference (ICI) | "any residual offset will cause inter-carrier interference (ICI)" ST07 |
| the narrowband assumption, B << fc | "it prevents one from making the narrowband assumption (B << fc)" CM09 |
| truly wideband | "An acoustic system is thus a truly wideband system" ASL09 |

## 4. The receiver

| Her word | Not her word | Evidence |
|---|---|---|
| post-FFT processing | frequency-domain equalization | "The receiver algorithm specifies post-FFT processing" ST07 |
| FFT demodulation | — | "initial synchronization, FFT demodulation, and post-FFT processing" ST07 |
| partial FFT demodulation | — | Yerramalli 2012, title |
| decision-directed | data-aided (she uses *data-aided* only for the pilot case) | "operates in a decision-directed manner" ASL09 |
| block-adaptive / block-oriented (the two camps) | — | "In block-oriented processing, these symbols must be known a-priori… In contrast, block-adaptive processing utilizes symbol decisions" ASL09 |
| pilot-assisted | — | "pilot-assisted, block-oriented detection" ASL09 |
| tentative decision, symbol decisions | soft output | "make a tentative decision" ASL09 |
| overhead, pilot overhead | training cost | "reducing both the computational complexity and the overhead" ASL09 |
| phase tracking, Doppler tracking | carrier recovery | "This model is the key to the phase tracking algorithm" ST07 |
| adaptive channel estimation | channel tracking | "adaptive channel estimation is crucial to the overall system performance" ST07 |
| pre-combining, pre-combiner | — | "a reduced-complexity pre-combining method" PC08 |
| spatial signal combining | beamforming (reserved for the array-steering sense) | "the non-uniform Doppler tracking and the spatial signal combining" ST07 |
| step size µ, filter memory α, forgetting λ | — | "where α ∈ (0,1) accounts for the filter memory" ASL09 |
| the modeling equation | the model | "can thus be used to estimate the Doppler factor via the modeling equation (2)" ASL09 |

## 5. Performance and design

| Her word | Not her word | Evidence |
|---|---|---|
| bandwidth efficiency [bits/second/Hz] | spectral efficiency | "the bandwidth efficiency, defined as the ratio R/B" ST07 |
| bandwidth-efficient | high-throughput | "bandwidth-efficient modulation methods" CM09 |
| figure of merit | metric, KPI | "the overall network lifetime is the figure of merit" CM09 |
| mean squared error (MSE) at the detector output | — | "The overall system performance, as measured by the mean squared error (MSE) at the detector output" ASL09 |
| bit error rate (BER) | — | ASL09 |
| trade-off | — | "Hence, there is a trade-off in the selection of the number of carriers" ST07 |
| the designer's best choice | — | "the corresponding value of K may not necessarily be the designer's best choice" ASL09 |
| pre-specified performance level | target, requirement | "while a pre-specified performance level is met" ASL09 |
| viable | promising, attractive | "OFDM is a viable technique for high-rate underwater acoustic communications" ST07 |
| excellent results | — | "showing excellent results" PC08; "Excellent results are thus achieved at a minimal computational complexity" ST07 |
| prohibitively complex | intractable | "may become prohibitively complex for real-time implementation" PC08 |
| real data, at-sea experiments, sea trials | field trials | "applied to real data transmitted at 10 kbps over 3 km" PC08 |
| a typical data set | representative results | "We report here on a typical data set" ASL09 |

## 6. Words she uses that the `mandar` skill bans

Confirmed by grep over the sole-author corpus. If a document is meant to read as
hers, these are permitted; if it is meant to read as house style, they are not.
See §"Where the two house styles disagree" in the `milica` skill.

| Word | Her usage | Sole-authored? |
|---|---|---|
| crucial | "The signal model is crucial to the design of the receiver algorithm" ST07 | yes |
| elegant | "While it offers an elegant solution to the multipath problem" ST07 | yes |
| framework | "we adopt the framework of decision-directed adaptive block processing" ASL09 | yes |
| paramount | "Reduction of computational complexity is a problem of paramount importance for real-time implementation" PC08 | yes |
| natural | "Signal processing based on channel estimation provides a natural framework for the development of algorithms capable of dealing with extreme motion" PC08 | yes |

`novel` and `state-of-the-art` do **not** appear in her sole-author prose, and
`state of the art` appears there only inside a cited reference title. Both do
appear in the wider corpus: `novel` in Yerramalli 2012 and Aval 2015,
`state-of-the-art` in the Springer handbook chapter (describing modems), in Tu
2011 and in Socheleau 2012. Treat them as student-draft residue, not as her
vocabulary.

## 7. Notation

Fixed across twenty years; a draft that renames any of these is not in her style.

| Symbol | Meaning |
|---|---|
| `k` | carrier / subband index, `k = 0 … K−1` |
| `n` | OFDM block index (time) |
| `t`, `r` | transmit element, receive element |
| `K` | number of carriers |
| `L` | channel span in taps; `J ≤ L` significant taps; `A` taps before the reference tap |
| `M_T`, `M_R` | number of transmit, receive elements |
| `B` | bandwidth; `∆f = B/K` carrier spacing; `f0` lowest carrier; `fk = f0 + k∆f` |
| `T = 1/∆f` | block duration; `Tg` guard interval; `T' = T + Tg` |
| `a`, `a(n)`, `a_t(n)` | Doppler factor / rate |
| `θ_k(n)` | phase distortion |
| `h_l(n)`, `H_k(n)` | impulse response, transfer function |
| `d_k(n)`, `y_k(n)`, `z_k(n)` | data symbol, received signal, noise |
| `c_k(n)` | channel gain (single-input case) |
| `µ`, `λ`, `α`, `γ` | step size, forgetting factor, filter memory, sparsing threshold |
| `β` | raw bandwidth efficiency, symbols/s/Hz/transmitter |
| `P` | number of pilot carriers |

Diacritic conventions, stated in her own words:

- prime — "where the prime denotes conjugate transpose" ASL09
- boldface — "The boldface letters denote column vectors that contain entries
  corresponding to the multiple receiving elements" ST07
- hat `ĥ` estimate, check `θ̌` prediction, bar `d̄` decision.
