---
name: mandar
description: Write or rewrite technical documents (papers, notes, tutorials, slide decks) in Mandar Chitre's writing style, using only vocabulary taken from source documents. Use when asked to write, rewrite, restyle, or review any manuscript, note, or deck in this project, or when asked to match the house style.
---

# Writing in the house style

This skill governs how documents are written in this project. It has two
halves that are equally binding: **how to write** (the style), and **which
words may be used** (the vocabulary discipline). The second half exists
because an AI writes fluently enough that an invented term is
indistinguishable from an established one.

Evidence base, all under `reference papers/chitre_first_author/`:

| File | What it profiles |
|---|---|
| `style_guide_from_papers.md` | seven first-author journal papers |
| `lexicon_from_papers.md` | 1281 words harvested verbatim from those papers |
| `style_conference_paper.md` | one first-author conference paper |
| `style_slide_deck.md` | one 50-slide invited talk |
| `style_guide_from_reports.md` | ARL project reports (multi-author, weaker evidence) |

Where these disagree, the first-author papers win. The reports are
multi-author and D1 Chapter 3 is a co-author's draft, so it carries no
authority for style.

---

## THE THREE HARD RULES

These are not preferences. A document that breaks one of them is not
finished, however good it reads.

### R1. Use only words that appear in the source material

Permitted sources, in order:

1. `lexicon_from_papers.md` and the verbatim quotes in the style files.
2. The project's own documents, for terms this project owns (for example
   *partial-FFT view*, *inner pilots*, *anchor set*, *pre-decoder soft
   symbol*, *candidate score*, *syndrome weight*, *residual pilot
   equalization*).
3. Standard field terms that appear in the cited literature.

Before using a term you have not seen in one of those three places, stop.
See R2.

### R2. Never introduce a word or name of your own

You may not coin a term, an abbreviation, a section name, or a label for a
concept. Not even a convenient one. Not even a clear one.

If the document needs a name for something and no source provides one:

1. Stop writing.
2. Tell the user precisely what has no name, and why the existing words do
   not cover it.
3. Propose two or three candidate wordings, each with the source it is
   drawn from or an explicit note that it has no source.
4. Wait for the user to choose.

The same applies to a term that exists but is used inconsistently across
documents: do not pick the one you prefer. Report the conflict and ask
which governs.

**A term that the project coined must be marked as coined.** If a name is
this project's own rather than the field's, the document says so once, in
the sentence that introduces it. The pattern already exists in this
project: *"RPC here denotes the Section II partial-FFT combining idea."*

### R3. Explain in plain words, get agreement, then write

Before rewriting a document, or before making any change that alters what a
document claims, state in plain words:

- what you propose to change,
- why, citing the rule or the evidence,
- what it will read like afterwards.

Then wait. Do not begin because the reasoning seems obvious. If the user
does not follow the explanation, the explanation is at fault; write it
again more plainly. Only after the user agrees do you edit.

This applies to wording changes only. It applies **doubly** to anything
that changes a technical claim, a number, or a description of what the code
does — those follow the disagreement protocol in `AGENTS.md` as well.

---

## DOCUMENT SHAPE

### The abstract, slot by slot

Fill these in order. One claim per sentence. Do not merge slots, do not
reorder.

| Slot | Function |
|---|---|
| 1 | A fact about the world or the object. No "we". No citation. No problem yet. |
| 2 | What is standardly done, stated fairly, with the reason it is reasonable. |
| 3 | The pivot, usually "However," — where the standard thing fails, **and the regime it fails in**. |
| 4 | Optional "Since …": the physical reason for the failure. |
| 5 | The move, one plain verb: *We formulate / consider / investigate / explore / aim*. |
| 6 | The difficulty or constraint, admitted before the fix. |
| 7 | Results, one per sentence, each opening *We show / We illustrate / We demonstrate*. |
| 8 | The concessive limitation, usually "Although …". |
| 9 | The verdict, application, or consequence. |

Abstract prohibitions, with no exceptions in the evidence: **no numbers, no
citations, no equations, no "to the best of our knowledge", no "first", no
"state-of-the-art".**

### Introductions

The first word is a noun of the domain, not the paper and not the
importance of the field. Motivation occupies the opening sentences and is
never revisited later as a "why this matters" paragraph.

Prior work is dispatched briefly and fairly — one clause is enough:
*"While most channel modeling work has focussed on the former two [1]–[4],
modeling of additive noise has received less attention."* A separate
Related Work section is not the house pattern for short documents.

Forward-looking statements ("we plan to extend …") belong in the
introduction, not the conclusion.

### Sections

A section opens with the aim, the prerequisite, or the requirement — never
with apparatus, and never with a definition of the section's own scope.
Close a section by naming what comes next, not by summarising what was
said.

### Conclusions

State what was considered and what was found. End on the consequence for
the reader or the field — a cost-benefit comparison against current
practice, or what the work makes possible. Do not summarise the paper. Do
not add a future-work section.

---

## SENTENCE RULES

1. **First person plural, always.** "We formulate", "we require", "we
   limit our discussion to". Never "I". "The authors" refers only to people
   you cite.
2. **"We" carries every choice** — modelling, naming, benchmarking, and
   giving up on a closed form: *"Since fα(x) is not available in closed
   form, we resort to numerical methods."*
3. **Passive voice only for apparatus, procedure, and data.** Never for
   your own reasoning: *"The data was acquired at a sampling rate of 500
   kSa/s"* is correct; "it was decided that" is not.
4. **Present tense for facts and properties. Past tense only for what was
   actually run.**
5. **Fifteen to thirty-five words. One idea per sentence.** Short sentences
   are allowed and effective: *"This problem is non-convex and difficult to
   solve."*
6. **Break a long sentence with "i.e.,", a semicolon, or a full stop** —
   never by nesting subordinate clauses.
7. **"However," starts a sentence.** Do not use mid-sentence "yet" as a
   pivot.
8. **Colons introduce displayed equations and lists, never a consequence.**
   For a consequence, use "Hence".
9. **Expand every acronym at first use**, including familiar ones.
10. **No contractions, no exclamation marks** in prose. (Slides differ; see
    below.)

---

## THE CONCESSION-AND-DEFEAT MACHINE

A rival approach is never called bad. Concede its virtue in the
subordinate clause; defeat it in the main clause. This is the single most
characteristic construction in the evidence, used twice in one paragraph:

> "While this approach yields accurate results, it requires long
> uncontaminated noise recordings to be available."

> "While this approach is simple, it fails to capture the true nature of
> underwater noise."

Two further requirements attach to it:

- **A deficiency is never stated unconditionally.** Name the regime:
  *"the performance of the LC is poor **in warm shallow waters where
  snapping shrimp noise dominates in the range 2–300 kHz**"*.
- **Pre-empt the reader's escape hatch** before they raise it: *"Even in
  the case of isotropic noise, …"*.

---

## HONESTY MOVES

These are obligations, not decorations.

- **State your own negative result, then fix it.** *"We show that the
  juggling-like ARQ provides good data streaming throughput but performs
  poorly for small file transfers."* The next sentence is the remedy.
- **Volunteer where your assumption fails, and cite the evidence against
  yourself**, then recover modestly: *"We limit our discussion to the
  Gaussian noise model in this paper, but plan to extend the work to
  non-Gaussian noise in a follow-up paper."* … *"a good starting point for
  most underwater communication simulations."*
- **Fence a strong claim with its conditions** in the same sentence:
  *"statistically indistinguishable from noise recorded during
  experiments **in areas where the ambient noise is stationary (over the
  timescales of interest) and Gaussian**."*
- **Refuse an unfair comparison out loud:** *"we cannot directly compare
  them. Instead, we should compare …"*
- **Give advice in three beats:** the advice, what it costs, how to undo
  it. *"it is advisable to scale … Scaling does not change the correlation
  properties … The scale factors can be recorded and the scaling can be
  undone …"*
- **Disclose a setting that makes a described mechanism inactive.** If a
  threshold is set to zero, or a cap never binds, the document says so
  where the mechanism is described.

---

## MATHEMATICS

- Every displayed equation is followed by a **"where" clause** naming its
  symbols, and then by **a sentence that interprets it and introduces no
  new symbol**.
- No symbol is left uninterpreted. If a factor vanishes, say what that
  means physically.
- Ground a modelling simplification in the instrument or the physics, not
  in convenience: *"A hydrophone measures dynamic pressure variations
  (around a mean static pressure), and the measured Gaussian noise is
  therefore, by definition, zero-mean."*
- Teach a concept with a **toy numeric example** rather than a proof where
  the audience is mixed.
- Announce the goal in words before the mathematics, using the same clause
  you will repeat afterwards: *"We wish to determine …"* then *"We
  determine … by solving an optimization problem"*.

---

## SLIDES

Slides follow different rules from prose. Evidence: a 50-slide invited
talk, roughly seven words per slide.

1. **Titles are one to three word noun phrases**, sentence case. **A title
   never states a finding.** Findings are burned into the figure.
2. **Half the slides have no title at all.** A slide may be a picture
   alone.
3. **Bullets appear on a small minority of slides** — six per slide at
   most, eight words each at most, fragments, no full stops, **no
   sub-bullets ever**.
4. **Figures carry the argument; text annotates them.** Labels go inside
   the figure. Citations go inside the figure in small type.
5. **Compare with identical axes on consecutive slides**, or two parallel
   columns. Never a combined plot, never a results table.
6. **Mathematics appears as a bound stated without explanation**, followed
   immediately by a plot or a toy table that makes it concrete.
7. **Voice the audience's objection as a whole-slide question**, then
   refute it over several picture slides.
8. **Build a complex diagram one node per slide.** A slide that is almost
   empty is fine.
9. **No outline slide, no thank-you slide, no future-work slide, no contact
   slide.** Close with a short takeaway that repeats the title's wording.
10. Exclamation marks are permitted on slides, sparingly, on a short
    assertion that stands alone.

---

## BANNED WORDS

Search for each of these before declaring a document finished. Every hit is
a defect unless the user has approved it:

`novel`, `state-of-the-art`, `framework`, `paradigm`, `leverage`,
`utilize`, `in order to`, `crucial`, `vital`, `clearly`, `obviously`,
`It is worth noting`, `natural`, `elegant`, `principled`, `lifting`,
contractions, exclamation marks in prose.

Also avoid abstract nominalisations that state a property without a
mechanism — "its inferential support remains local" says nothing a reader
can check. Replace with the mechanism and its cost.

---

## BEFORE DECLARING A DOCUMENT FINISHED

1. Does the first sentence describe the world, or the paper? It must be the
   world.
2. Does every claim of improvement carry the condition it was measured
   under?
3. Is there a "However," or "Although" within three sentences of every
   claim?
4. Does every displayed equation have a "where" clause and a following
   sentence with no new symbols?
5. Has every alternative you dismissed been granted its virtue before being
   defeated?
6. Grep the banned-words list. Zero hits.
7. Is any sentence longer than thirty-five words, or carrying two ideas?
8. **Is every term in the document traceable to a source, or explicitly
   marked as this project's own name?** List any that are not, and raise
   them with the user.
9. Does the document compile, and are all equations, symbols, and labels
   unchanged from the version you started with unless the user approved a
   change?

---

## WHEN YOU CANNOT COMPLY

Say so. Do not approximate.

If the style requires a word the sources do not contain, or the technical
content has no name in the project's documents, or two source documents
give a term two meanings — stop and report it. An unfinished document with
an honest question attached is worth more than a finished one with an
invented word in it.
