# Slide / presentation style profile
# SOURCE: "doing more with less - effective use of limited acoustic bandwidth",
# M. Chitre, Breaking the Surface 2024, Biograd na Moru (50 slides).

I read all 50 slides (page images plus the extracted text layer). Total deck: **50 slides**, 1280×720, produced in **Deckset** (a Markdown-to-slides tool) — which explains the rigidly constrained layouts. Source: `/home/gabiel/Documents/GitHub/Juna/reference papers/chitre_first_author/bts2024-chitre.pdf`

---

# Chitre presentation style — mechanical profile

## 0. Deck vitals

| Metric | Value |
|---|---|
| Slides | 50 |
| Slides with a title | 24 (+1 title slide) |
| Slides with **no** title at all | 25 (50%) |
| Slides with bullet lists | **3** (slides 6, 20/21, 25) |
| Total prose words in the whole deck | ≈ 350–400, i.e. **~7 words/slide** |
| Slides carrying an image/plot/diagram | ~38 |
| Slides carrying mathematics | 11 |
| Sub-bullets / nested lists | **0** |
| Outline/agenda slide | none |
| References slide | none (citations inline, tiny) |
| Logos | none |

Every slide carries the same footer, bottom-left, small bold white: `Mandar Chitre – Breaking the Surface 2024, Biograd na Moru, Croatia`, with the slide number bottom-right. It appears even on full-bleed photo slides.

---

## 1. TITLE SLIDE (slide 1)

Full-bleed dimmed photograph of the Biograd na Moru waterfront at sunset. Two lines of white text, left-ish, huge:

> # doing **more** with *less*
> ## effective use of limited acoustic bandwidth

Mechanics worth copying exactly:
- **All lowercase.** No capital letters anywhere in the title or subtitle.
- "**more**" is bold, "*less*" is italic — a typographic joke embodying the thesis. This exact treatment returns on the final slide.
- Subtitle is a plain noun phrase, no colon, no "A study of…", no "Towards…".
- **No author block, no affiliation, no logo, no date, no email on the title slide.** The only attribution is the standard footer.

---

## 2. SLIDE TITLES, VERBATIM, IN ORDER

`—` marks a slide that has **no title**; I note what occupies it instead.

| # | Title (verbatim) |
|---|---|
| 1 | `doing more with less` / `effective use of limited acoustic bandwidth` (title slide) |
| 2 | `Why acoustics?` |
| 3 | — *(three display equations only)* |
| 4 | — *(one plot only)* |
| 5 | `Bits are a precious resource!` |
| 6 | `Reducing Delivery Overheads` |
| 7 | `Payload Compression` |
| 8 | — *(two display equations only)* |
| 9 | `Entropy Example` |
| 10 | `Isn't it reasonable to assume that application data is already high-entropy?` |
| 11 | `10 kB JPG` |
| 12 | — *(four images, 2×2, no text)* |
| 13 | — *(figure; internal caption `Space of all possible bit sequences of length N`)* |
| 14 | — *(same figure, + `Valid JPG images`)* |
| 15 | — *(same figure, + thumbnails on dots)* |
| 16 | — *(same figure, + `Underwater photographs`)* |
| 17 | — *(same figure, + enclosing ellipses)* |
| 18 | — *(same figure, + `2^k`, `2^N`)* |
| 19 | — *(same figure, + `Compression ratio: N/k`)* |
| 20 | `Energy / time usage` |
| 21 | `Energy / time usage` *(same title, second build step)* |
| 22 | `We can afford to spend a lot more time & energy on computation to reduce the number of bits to transmit!` |
| 23 | `Example` / subtitle `NMEA data from a tether-less ROV` |
| 24 | `Generic per-message compression (gzip)` |
| 25 | `Application-specific compression` |
| 26 | — *(block diagram: Sample Messages → Dictionary → Tx/Rx)* |
| 27 | `Application-specific compression` *(title repeated from 25)* |
| 28 | `Example` / subtitle `Reinspection with a tether-less ROV` |
| 29 | — *(block diagram: Sample Images → Prior Model → Tx/Rx)* |
| 30 | `Prior model*` |
| 31 | `Prior model (3DGS)` |
| 32 | — *(vertical pipeline: `Camera image` → … → `Synthesized image`)* |
| 33 | `Latent image` *(right-panel heading; left is the untitled pipeline)* |
| 34 | `Latent image` *(same, second example)* |
| 35 | `Reconstruction` |
| 36 | `Reconstruction` *(build step 2)* |
| 37 | `Reconstruction` *(build step 3)* |
| 38 | — *(architecture build, step 1: `Sample Images`)* |
| 39 | — *(step 2: + `Pose estimation` → `Sample Poses`)* |
| 40 | — *(step 3: + `Train` → `3DGS`)* |
| 41 | — *(step 4: + `3DGS⁻¹`)* |
| 42 | — *(step 5: + `Transmitter`, `Image (from camera)`)* |
| 43 | — *(step 6: + `Latent Image (pose + diff)`)* |
| 44 | — *(step 7: + `Receiver`)* |
| 45 | — *(step 8: + `Image (reconstructed)`)* |
| 46 | — *(full-bleed 2×2 result quad, labels inside image)* |
| 47 | — *(same, second scene)* |
| 48 | — *(same, third scene)* |
| 49 | `Acknowledgements&` |
| 50 | `Takeaways` |

Only **18 unique title strings** across 50 slides. Repetition is deliberate: a repeated title means "same claim, new evidence" (`Application-specific compression` on 25 and 27 invites you to compare the histogram on 27 against the one on 24).

---

## 3. TITLE GRAMMAR — breakdown with counts

Of the 24 titled content slides:

| Form | Count | % | Examples |
|---|---|---|---|
| **Noun phrase** | 20 | 83% | `Payload Compression`, `Entropy Example`, `Energy / time usage`, `Prior model (3DGS)`, `Reconstruction`, `Takeaways` |
| **Question** | 2 | 8% | `Why acoustics?`, `Isn't it reasonable to assume that application data is already high-entropy?` |
| **Assertion (full sentence, exclamation)** | 2 | 8% | `Bits are a precious resource!`, `We can afford to spend a lot more time & energy on computation to reduce the number of bits to transmit!` |
| **Statement of a finding** | **0** | 0% | — |

Two things a rewriter must internalise:

1. **Not a single title states a result.** There is no `X reduces BER by 3 dB`. Findings live *inside the pictures* — as numbers burned into the image (`4688 bytes`, `ratio: 9.8x`, `PSNR: 37.9 dB`). The title only names the object under discussion.
2. **Titles are short.** Median length ≈ 2 words. Titles of 1–3 words: `Example`, `Reconstruction`, `Latent image`, `10 kB JPG`, `Takeaways`, `Prior model`, `Acknowledgements`. The two long titles are both full-sentence rhetorical moves, and they occupy the *entire slide* — they are not headers over content.
3. Capitalisation is inconsistent but sentence case dominates the second half (`Energy / time usage`, `Application-specific compression`, `Prior model`, `Latent image`). Early slides use Title Case (`Reducing Delivery Overheads`, `Payload Compression`, `Entropy Example`).

---

## 4. TEXT DENSITY

**Only three slides in fifty carry bullets.** Every one of them is a "list of things I'm about to skip or summarise", never the main argument.

- Bullets per slide: **4–6** (max 6).
- Words per bullet: **1–8** (max 8).
- All bullets are **fragments**: no verb agreement with a subject, no terminal punctuation, no full stops anywhere.
- **Zero sub-bullets** in the whole deck.

### Slide 6, in full
> **Reducing Delivery Overheads**
> - Frugal headers
> - "Short-circuiting"
> - Time-to-live (TTL)
> - Mailboxes
> - "Juggling" and "super-TDMA"
> - Erasure control coding (to reduce need for ACKs)
> ⋮

(19 body words for six bullets. Note the vertical ellipsis `⋮` as a final "list item" — it means "there are more, I'm not enumerating them", and licenses him to move on without apology.)

### Slide 25, in full
> **Application-specific compression**
> - Not all bit patterns are equally likely (compressible!)
> - Generic compression performs poorly due to short messages
> - Learn distribution from a large sample dataset of messages
> - Use distribution (dictionary) as *prior* for message compression

(32 body words. All four bullets are **exactly 8 words** — the block is visually rectangular. One italicised keyword, `prior`, which is the concept the whole talk turns on.)

### Slide 21, in full (two columns)
> **Energy / time usage**
>
> | Typical terrestrial wireless: | Typical acoustic modem: |
> |---|---|
> | • 4G LTE: 10 µJ/bit, 100 Mbps | • 185 dB 1 µPa @ 1m, 5 kbps |
> | • 5G: 0.3 µJ/bit, 1 Gbps | • 5 mJ/bit |
> | | • ~10³ − 10⁴ × larger! |

(26 words, almost all numerals. The comparison is made by *side-by-side columns with parallel headers*, not by a sentence saying "acoustic is worse". The punchline is a single bullet with an exclamation mark.)

### Slide 22, in full (no title, whole slide is the sentence)
> We can afford to spend
> a lot more time & energy on computation
> to reduce the number of bits to transmit!

(21 words, hard-wrapped over three lines at the rhetorical breaks, centred, nothing else on the slide.)

---

## 5. OPENING SEQUENCE (slides 1–6)

| Slide | What it does | Content |
|---|---|---|
| 1 | **Thesis as a slogan**, on a photo of the conference venue | `doing more with less` |
| 2 | **Question as a section divider**, on a *different, light-grey* background | `Why acoustics?` |
| 3 | **Bound, stated as mathematics, with no title and no explanation** | `Data Rate ≤ Capacity` / `Capacity = C_monotonic(Δf, SNR)` / `SNR_dB(f,R) = SL + G − α log₁₀R − A(f)R − N(f)` |
| 4 | **The plot that makes the bound concrete**, no title, no caption | attenuation/noise vs frequency for 1/2/5/10 km, with the Stojanovic citation in 8pt *inside* the figure |
| 5 | **The verdict**, on the same light-grey background as slide 2 | `*Bits* are a precious resource!` |
| 6 | **The only "here are the techniques" list**, deliberately skimmed | 6 bullets + `⋮` |

The move to steal: **slides 2 and 5 use the same light background and bracket the technical justification.** Question → equation → plot → answer. He spends **zero slides** on motivation prose, related work, or "underwater acoustic communication is important because…". The reason bandwidth is scarce is delivered as one equation and one plot, in under 60 seconds, and closed with a five-word verdict.

There is no outline slide, no "structure of this talk", no self-introduction.

---

## 6. CLOSING SEQUENCE (slides 46–50)

| Slide | What it does |
|---|---|
| 46–48 | **Three result slides that are pure full-bleed imagery** (almost certainly playing video). 2×2 quad: `Camera` / `Reconstructed` / `3DGS` / `Difference`. All numbers burned into the image corners: `45807 bytes`, `4688 bytes`, `ratio: 9.8x`; then `43302 bytes`, `7789 bytes`, `ratio: 5.6x`; then `33297 bytes`, `3147 bytes`, `ratio: 10.6x`, `PSNR: 37.9 dB`. **No slide title, no caption, no results table anywhere in the deck.** |
| 49 | **Acknowledgements**, with six *faces* not just names: `... based on excellent work by:` `Too Yuen Min, Peng Luyuan, Hari Vishnu, Bharath Kalyan, Rajat Mishra, Tan Soo Pieng`, plus a superscript-`&` footnote carrying the A*STAR grant text |
| 50 | **Takeaways: two lines, on the title slide's photograph** |

Slide 50 in full:
> **Takeaways**
>
> Use frugal communication protocols to minimize overheads
>
> Do **more** with *less* bits by leveraging priors

Note: **no bulleted conclusions, no future work, no "Thank you", no Q&A slide, no contact details.** Two imperative sentences, one per section of the talk, matching the two halves exactly (protocols ↔ slides 6; priors ↔ slides 7–48). The `**more**` / `*less*` typography is byte-identical to the title slide, and the background photo is the same image — a visual callback that closes the loop.

---

## 7. FIGURES

**Figures carry the argument; text annotates them.** Roughly 38 of 50 slides carry an image, plot, diagram or photo. Only 3 carry bullets.

**Slides that are just a picture, with no title:** 4, 12, 13–19, 26, 29, 32, 38–45, 46–48 — about **17 slides, a third of the deck.**

Captioning rules he follows:
- **Figures almost never get a caption.** Labels are *inside* the figure: axis labels (`Fraction of messages`, `Compression ratio`), in-diagram callouts (`Valid JPG images`, `Underwater photographs`, `Compression ratio: N/k`), in-image overlays (`Camera`, `Difference`, `ratio: 9.8x`).
- **Where a title exists, it is the caption**: `10 kB JPG`, `Prior model (3DGS)`, `Generic per-message compression (gzip)`.
- **Citations go inside the figure at ~8pt**, not in a reference list: `More info: Stojanovic, "On the relationship between capacity and distance in an underwater acoustic communication channel", WUWNet 2006.` (slide 4). Or as superscript footnotes below a rule (slides 30, 49).
- **Plots are not restyled.** He drops the raw white-background matplotlib output as a white panel floating on the dark slide. He does not fight to make figures match the theme.
- **Comparison is by identical axes on consecutive slides, never by a combined plot.** Slide 24 (gzip: everything piled at ratio 1.0) and slide 27 (app-specific: mass spread from 1.5 to 7) have *identical axes and limits* and near-identical titles. The reader does the differencing.

Two figure devices worth stealing wholesale:

**(a) The 7-step conceptual build (13–19).** One hand-drawn-looking white schematic, revealed one element at a time: the space `2^N` → scattered dots → dots with image thumbnails attached → a second class of dots → nested ellipses → `2^k` inside `2^N` → the payoff line `Compression ratio: N/k`. Seven slides to deliver one idea, with zero prose.

**(b) The 8-step architecture build (38–45).** The full system diagram assembled node by node: `Sample Images` alone on an otherwise empty slide → `Pose estimation` → `Sample Poses` → `Train` → `3DGS` → `3DGS⁻¹` → `Transmitter` → `Latent Image (pose + diff)` → `Receiver` → `Image (reconstructed)`. Slide 38 is a single database cylinder on an empty slide — he is not afraid of a slide that is 98% background.

**(c) The structural rhyme.** Slide 26 and slide 29 are the *same diagram template* with substituted labels — `Dictionary (112 kB)` ↔ `Prior Model`, `Message` ↔ `Image (from camera)`, `Compressed` ↔ `Latent Image (compressed)`. The second case study is presented as *the same machine with different parts*, and the diagram says so without a word.

**(d) Preview → detail → rebuild.** He shows the abstract diagram first (26, 29), unpacks its internals over many slides, then rebuilds it fully piece-by-piece (38–45). The audience sees the shape three times.

---

## 8. EQUATIONS

**11 of 50 slides (22%) carry mathematics.** Two slides (3, 8) are *pure* mathematics with no title and no words.

How maths is presented:
- **Large, centred, serif (Computer Modern) on the flat dark background.** No box, no colour, no highlight.
- **Maximum three equations per slide**, generously spaced.
- **No equation numbers. No derivations. No "where SL is the source level…" legend.** Symbols are either defined by the *next* slide's plot (the `A(f)R − N(f)` terms on slide 3 become the y-axis of slide 4) or simply left standing.
- **The recurring form is a bound / inequality used as a chapter opener:**
  - Slide 3: `Data Rate ≤ Capacity` — opens the acoustics section
  - Slide 8: `Compressed Payload Size ≥ Entropy S(x)` — opens the compression section

  Both are followed immediately by something concrete: an equation slide, then a picture or a toy table, then "so what".
- **Toy numeric example instead of proof.** Slide 9 (`Entropy Example`) is two 8-row `x`/`P(x)` tables side by side — uniform vs two-valued — with a small equation under each: `S = −8 × 0.125 log₂(0.125) = 3 bits` and `S = −2 × 0.5 log₂(0.5) = 1 bit`. Entropy is taught in one slide, by arithmetic, to a mixed audience.
- **Notation as shorthand in diagrams.** `pose ≡ (x, y, z, q₁, q₂, q₃, q₄)`, `⟨3DGS⁻¹ Model⟩`, `⟨3DGS Model⟩` are used as *nodes in a flow*, chained with `↓` arrows, rather than as standalone equations (slides 30, 32–37).

---

## 9. RHETORICAL DEVICES

- **Question as section divider.** `Why acoustics?` (2), on a distinct light background, alone on the slide.
- **Voicing the audience's objection, then demolishing it.** Slide 10 is nothing but: `Isn't it reasonable to assume that application data is already high-entropy?` Slides 11–19 are the answer — a 10 kB JPG, then the same JPG's bits scrambled into noise, then the 2^N/2^k set-inclusion build. This is the deck's single most transferable structure: **state the reasonable objection in the audience's own voice, give it a whole slide, then spend nine slides refuting it with pictures.**
- **Exclamation-mark assertions**, always short, always alone: `Bits are a precious resource!`, `~10³ − 10⁴ × larger!`, `We can afford to spend a lot more time & energy on computation to reduce the number of bits to transmit!`, `(compressible!)`.
- **Analogy by juxtaposition.** Slide 12: a horse standing in a green field next to an underwater pile, and beneath each, the same file's bits randomised into grey noise. No caption. The argument — that meaningful images are a vanishingly thin subset of bit-space — is made entirely by the four pictures, and only then formalised in 13–19.
- **Scare quotes for coined or informal terms**: `"Short-circuiting"`, `"Juggling"`, `"super-TDMA"`. He flags his own jargon as jargon.
- **Callbacks.** Title photo → Takeaways photo. `doing more with less` → `Do **more** with *less* bits by leveraging priors`. `Example` used twice as a title, in identical layout, to signal "same kind of move, new domain".
- **Inclusive first person.** `We can afford to spend…` — never "you", never "I show that". The one first-person move in the deck is inclusive.
- **Modesty at the end.** `... based on excellent work by:` — the leading ellipsis makes the acknowledgement a continuation of the talk, not a separate ritual, and the six faces make it personal.
- **Humour is dry, visual, never verbal.** The horse; the deliberately illegible NMEA wall on slide 23 (which is *supposed* to be unreadable — it is a picture of "too much data", not text to read); the `⋮`.

---

## 10. VERBATIM PHRASES (reusable)

1. `doing more with less`
2. `effective use of limited acoustic bandwidth`
3. `Why acoustics?`
4. `Data Rate ≤ Capacity`
5. `Capacity = C_monotonic(Δf, SNR)`
6. `Bits are a precious resource!`
7. `Reducing Delivery Overheads`
8. `Frugal headers`
9. `"Short-circuiting"`
10. `Time-to-live (TTL)`
11. `Mailboxes`
12. `"Juggling" and "super-TDMA"`
13. `Erasure control coding (to reduce need for ACKs)`
14. `Payload Compression`
15. `Compressed Payload Size ≥ Entropy S(x)`
16. `Entropy Example`
17. `Isn't it reasonable to assume that application data is already high-entropy?`
18. `10 kB JPG`
19. `Space of all possible bit sequences of length N`
20. `Valid JPG images`
21. `Underwater photographs`
22. `Compression ratio: N/k`
23. `Energy / time usage`
24. `Typical terrestrial wireless:`
25. `4G LTE: 10 µJ/bit, 100 Mbps`
26. `5G: 0.3 µJ/bit, 1 Gbps`
27. `Typical acoustic modem:`
28. `185 dB 1 µPa @ 1m, 5 kbps`
29. `5 mJ/bit`
30. `~10³ − 10⁴ × larger!`
31. `We can afford to spend a lot more time & energy on computation to reduce the number of bits to transmit!`
32. `Example`
33. `NMEA data from a tether-less ROV`
34. `Generic per-message compression (gzip)`
35. `Application-specific compression`
36. `Not all bit patterns are equally likely (compressible!)`
37. `Generic compression performs poorly due to short messages`
38. `Learn distribution from a large sample dataset of messages`
39. `Use distribution (dictionary) as prior for message compression`
40. `Sample Messages (150,000 samples)`
41. `Dictionary (112 kB)`
42. `Message (16-81 bytes, avg 39.7)`
43. `Compressed (8-56 bytes, avg 14.6)`
44. `Fraction of messages` (y-axis) / `Compression ratio` (x-axis)
45. `Reinspection with a tether-less ROV`
46. `Prior Model`
47. `Image (from camera)`
48. `Latent Image (compressed)`
49. `Image (reconstructed)`
50. `Prior model`
51. `Novel View Synthesis (NVS) techniques`
52. `Neural Radiance Fields (NeRF)`
53. `3D Gaussian Splatting (3DGS)`
54. `Prior model (3DGS)`
55. `Camera image`
56. `Synthesized image`
57. `Latent image`
58. `Difference image`
59. `Reconstruction`
60. `Reconstructed`
61. `Pose estimation`
62. `Train`
63. `Sample Images` / `Sample Poses`
64. `Latent Image (pose + diff)`
65. `ratio: 9.8x` / `ratio: 5.6x` / `ratio: 10.6x`
66. `PSNR: 37.9 dB`
67. `Acknowledgements`
68. `... based on excellent work by:`
69. `This work was partially supported by A*STAR under its RIE2020 Advanced Manufacturing and Engineering (AME) Industry Alignment Fund - Pre-Positioning (IAF-PP) Grant No. A20H8a0241.`
70. `Takeaways`
71. `Use frugal communication protocols to minimize overheads`
72. `Do more with less bits by leveraging priors`
73. `More info: Stojanovic, "On the relationship between capacity and distance in an underwater acoustic communication channel", WUWNet 2006.`
74. `Mandar Chitre – Breaking the Surface 2024, Biograd na Moru, Croatia` (footer, every slide)

---

## 11. SECTION TRANSITIONS

He uses **three distinct transition mechanisms**, and never a "Section 3: Methods" style header.

**(a) The lone-phrase divider on a different background.** Slides 2 (`Why acoustics?`) and 5 (`Bits are a precious resource!`) sit on a pale grey abstract gradient, unlike every other slide's flat slate. They form a matched pair bracketing the framing argument — the question opens it, the verdict closes it.

**(b) The bold word divider on the normal background.** Slide 7 (`Payload Compression`) is one bold phrase, centred, on the standard dark slide. This is the "new section" marker for the body of the talk. Note the inconsistency with (a) — he does not enforce a single divider template.

**(c) The hinge slide.** Slide 22 is the structural pivot of the entire talk: a full-slide sentence that *concludes the section just finished* (energy/time budgets) and *licenses everything that follows* (spend compute, save bits). Everything from 23 to 48 is the cash-out of that one sentence.

**(d) `Example` as the case-study opener.** Slides 23 and 28 use an identical two-line layout — the word `Example` as title, a one-line subtitle naming the scenario (`NMEA data from a tether-less ROV`, `Reinspection with a tether-less ROV`), then the raw material. The repeated layout tells the audience "we are starting over in a new domain, same argument shape."

**(e) Build-slides do the within-section work.** Of 50 slides, roughly 20 are incremental build steps of just five underlying figures (13–19, 20–21, 33–34, 35–37, 38–45). The deck's real content is closer to **30 distinct ideas over 50 slides** — which is why it reads fast despite the slide count. There is no transition prose at all; the animation *is* the transition.

---

## Ten-line summary for the rewriter

1. Titles are **1–3 word noun phrases**, sentence case. Never a finding, never a full sentence — unless the sentence *is* the whole slide.
2. Half the slides have **no title**.
3. Bullets appear on **6% of slides**, max 6 bullets, max 8 words, all fragments, zero nesting, no full stops.
4. Every claim is carried by a **picture, plot, or diagram**; captions live inside the figure, or the title is the caption, or there is neither.
5. Maths appears as a **bound stated with no explanation**, immediately followed by a plot or a toy table that makes it concrete.
6. Comparisons use **identical axes on consecutive slides**, or **two parallel columns**, never a combined plot and never a results table.
7. Results numbers are **burned into the images** (`4688 bytes`, `ratio: 9.8x`), not tabulated.
8. Voice the audience's objection as a **whole-slide question**, then spend many picture-slides refuting it.
9. Build complex diagrams **one node per slide** — a slide that is 98% empty is fine.
10. Close with **two imperative lines** on the title slide's photograph, repeating the title's exact typography. No thank-you slide, no future work, no contact details.