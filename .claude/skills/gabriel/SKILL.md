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
