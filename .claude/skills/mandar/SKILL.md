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

---
name: gabriel
description: How Gabriel works with agents — numbered decision registers, terse item-by-item approval, crisp rewrites on demand, and coordination with a second agent through git. Use whenever proposing a change that needs approval, when he says he is lost, when he interrogates a term or label, or when another agent shares the repository.
---

# Working with Gabriel

## The loop

Propose numbered items → he answers each one → record his exact words → act only on approved items.

Never ask "shall I proceed?" about a bundle. Give him items he can answer one at a time.

## Numbered decisions

Assign an identifier before you ask, and write it to the register in the same response that proposes it. Identifiers are per-agent so two agents cannot allocate the same one:

```
CL-1, CL-2, ...    Claude
CX-1, CX-2, ...    Codex
```

A rejected item is never edited in place. It is replaced by a new identifier that records what it replaces.

## How he answers

```
D13, ok
D15, why we need duplicate?
D16, what work?no
D31-D39, I agree
```

`ok` is approval. A bare question is a challenge. A question with `no` attached is a challenge and a rejection at once. Bulk approval arrives once the items are crisp.

**A question is not a request for more detail.** It means the item failed to justify itself. Answer in one or two sentences, then either withdraw it or re-propose under a new identifier. Do not defend, do not elaborate.

## Record his exact words

Rejection reasons go into the register verbatim — *"what work?"*, *"readers no need to know about sonique"*. A paraphrase loses the test that produced the rejection.

## When he says he is lost

Triggers: *"I'm lost"*, *"I don't understand"*, *"make it crisp"*, *"explain it to me"*, *"I've no idea what claude is telling me"*.

These mean **stop adding detail**. Rewrite shorter:

- Lead with the single thing that matters.
- Cut hash tables, verification trails, provenance chains, hedges.
- Under 200 words. Short sentences.
- Diagrams and short lists beat paragraphs.

If he says it twice, the second attempt is still too long. Never answer confusion with more evidence.

## Never coin a term — in conversation either

The `mandar` skill forbids invented names in documents. The ban covers
**chat**, which is where invented names are actually born: a short label
appears in an explanation, goes unchallenged because conversation looks
informal, and then walks into the paper as settled vocabulary. That is how
`arm`, `profiled`, `ladder`, and `conditioned joint step` reached a draft. He
stopped the work twice to ask what they meant — *"what is arm? I don't
understand all these coined terms you come up with"*.

**Default to describing, not naming.** "The receiver that computes the
combiner" costs six words and no confusion; a short label saves you typing
and costs him the meaning.

**When a name is unavoidable and it is not his, not in a source, and not a
code identifier, mark it at first use, in the sentence:** "(my word, not
yours)". The mark is the enforcement — he can see it, or see it missing where
a strange word appeared. A rule with no visible output gets broken silently.

## General before specific — always

When introducing any technique, code, model, or tool, state the general
class first, narrow step by step, claim the work at the most general level
it holds, and name the specific instance last, as the demonstration. His
dictation of the canonical example: *"say that one can choose to use FEC,
then one popular code is linear block codes, then most people uses
LDPC...then work here is not limited to LDPC, any linear block code as long
as have parity constrains can be used. however as a demonstration of this
idea we use LDPC. always ----- general ----- specific-----. write like this
always"*.

The pattern, in order:

1. The general need (error correction).
2. The general class that meets it (linear block codes, via parity
   constraints).
3. The most common instance (LDPC).
4. The work's true scope, stated at the class level (any linear block code
   with parity constraints).
5. The instance used, named as the demonstration (we use LDPC).

Never open with the specific instance, and never let the claim ride on it.
This applies to every such introduction, not only codes.

## One reading only — spell the action out

A noun phrase that compresses an action makes the reader unpack it, and
some readers unpack it wrongly. "A separate receiver" reads as a kind of
hardware; what was meant is *"a receiver that performs demodulation and
decoding separately"*. His dictation: *"what is a separate receiver? say: a
receiver that does separate demodulation and decoding, please avoid
sentence formation that would confuse the human reader"* and *"whatever you
write, recheck it many times to see if it can be intepreted in any other
way that is not intended"*.

Two obligations follow:

1. **Write the action, not a label for the action.** If a phrase stands
   for a process, spell the process out at least once per section, and
   prefer spelling it out everywhere.
2. **Before delivering any sentence, reread it hunting for other
   parses.** Read it as a hostile stranger: every pronoun, every "this",
   every compressed modifier. If a second reading exists, rewrite until
   only the intended one survives. Do this for chat as well as documents.

## What he rejects

- **Duplication.** Two items doing the same job.
- **Internal structure the reader does not need.** Repository names, module layout, agent plumbing.
- **Settled terms reopened.** If a word was argued to a conclusion, it stays concluded.
- **Work with no stated purpose.** *"what work?"* is the standard challenge.
- **A slide or section that repeats its own title.**

## Terminology

He audits terms and expects the audit done properly: where each term appears, what it means in each place, and which usages conflict. Report the conflict; let him choose which governs. Never pick for him, and never invent a name — see the `mandar` skill, rule R2.

## Naming audits

Any label a reader can see — UI text, diagram stages, section names — has an agreement status, and being rendered is not approval:

| Status | Meaning |
|---|---|
| approved verbatim | he chose these exact words |
| working label | introduced by an agent, never reviewed with him |
| code identifier | a source symbol, not a chosen name at all |
| drifted | approved name whose implemented meaning no longer matches what was approved |

Audit first with that table, change nothing, then review label by label. **Accuracy is not agreement** — a label that correctly summarizes the code is still unapproved if he never chose it.

Proposals are current → proposed tables, every proposed label verbatim from a cited source (file:line). A paper-versus-code conflict becomes one question: which governs? Report any divergence between a registry and what is actually rendered.

## When he asks "what is X?"

His questions come in bursts — *"what is symbols here? bpsk symbols? what's interface contract? what's loopback decode exactly?"* Each gets its own answer:

1. **Verdict first.** If the implied reading is wrong, open with "No —". Never soften a wrong label into a partial yes.
2. **Verified, not paraphrased.** Trace the actual code path before answering; cite file:line. *"Exactly"* means run it and show the numbers — bits recovered, sample counts, the modulation actually used — not a restated docstring.
3. **One plain sentence per term.** After the mechanism, restate it in words a new student could repeat.
4. **If the label misdescribes the code, say so.** A test named for something it does not test is a defect. Do not defend it or explain it charitably — report what it actually checks, then propose a replacement.
5. **Disambiguate what "exact" quantifies over.** "Payload-exactly" means every requested bit matched — not that samples or soft values matched. Spell out the quantity.
6. **Replacements arrive as numbered proposals**, each quoting the wording it replaces. Nothing is reworded in place without a number and his approval.

Treat a question about a term as an audit trigger: he has usually spotted a label that is wrong, not asked for a tutorial.

## Two agents, one repository

He routes between agents by hand, pasting messages between sessions.

- **Write the message for him to paste.** Plain, numbered, imperative. Separate messages per agent.
- **One worktree and one branch per agent.** Never touch another agent's working directory or uncommitted files.
- **Forbidden in any shared directory:** `git add -A`, `git add .`, `git stash`, `git clean`, `git checkout --`, `git restore`, `git reset --hard`. Stage explicit paths only.
- **He merges.** Push your own branch; never merge, never merge a pull request.
- **The repository is the only channel between agents.** Anything the other agent must know goes into a file — decisions, reasons, changed files, validation results, open questions. Not transcripts.
- **He pastes one agent's output into the other's session** and asks for explanation or review. Verify the other agent's claims against the files before agreeing; say plainly what checks out and what does not.

## Reporting

Every response that reports work carries a twenty-cell progress bar and a token bar, against denominators declared beforehand. Mark the token figure `measured` or `estimated`. If it passes the budget, render it full, mark `OVER`, state the overrun, and ask whether to continue, re-baseline, or stop.

## Standing constraints

Validation before implementation. Never edit a checksum-pinned file without surfacing the fork. Copy numeric constants byte-for-byte rather than retyping them. Ask which side is authoritative when paper and code disagree.
