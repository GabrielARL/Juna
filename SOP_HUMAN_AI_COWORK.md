# Standard operating procedure — human-AI cowork

Status: in force from 2026-07-31. Decisions D1 to D4 approved; see
`APPROVAL_LIST.md`.

This procedure binds any AI agent working in this repository, whatever tool it
runs under. It exists because an AI writes fluently enough that a name it
invented is indistinguishable from a name the project agreed on, and because a
new session starts with no memory of what was agreed.

---

## 1. The rule this all reduces to

**An AI may not put a reader-visible name into the project without the human
approving that exact name first.**

Everything below is the procedure for getting that approval without stalling
the work.

---

## 2. Every item needing a decision gets an identifier

Write it as `D` followed by a number: `D1`, `D2`, `D3`. Rules:

1. **One identifier, one decision.** Approving `D3` approves `D3` and nothing
   else. Never bundle.
2. **Identifiers are stable.** The same identifier is used in the proposal, in
   the implementation, in the commit message, and in the review. A reader who
   sees `D4` in a diff can find what was agreed.
3. **Identifiers are never reused.** A rejected item keeps its number and stays
   in the register with the rejection recorded. Reuse would make an old
   approval look like it covers a new thing.
4. **Numbering is continuous across sessions**, because the register is a file,
   not a memory.

States: `proposed`, `approved`, `rejected`, `superseded by Dn`.

---

## 3. What requires an identifier

Anything a reader other than the author will see:

- exported functions, types, struct fields, keyword arguments
- file names, directory names, script names
- registry keys, requirement names, configuration keys
- command-line flags, environment variable names
- plot labels, axis labels, table headings
- error text, log text, user-facing messages
- section names and slide titles in a document
- any abbreviation

And, separately from naming, anything that changes what the project asserts:

- a change to what a document claims
- any number in a manuscript
- deleting a file, a test, or a claim
- any git action that leaves the machine
- moving work between tiers, or changing what CI proves

## 4. What does not require an identifier

An agent that must ask about everything is useless. These are the agent's own:

- local variables, loop indices, accumulators, temporary values
- anything that never crosses a boundary another person reads
- reading, searching, inventorying, and reporting
- running checks and reporting what they say
- adding a case to work that already exists under an approved name
- fixing a tool that produces false results, and saying so

---

## 5. How to propose

One table. Nothing else counts as a proposal.

| ID | Proposed wording | What it means | Where the words come from | Replaces |
|---|---|---|---|---|
| D1 | tests currently run by CI | registered tests that decide whether a change passes | plain words; `CI` already used in AGENTS.md | active tree |

The fourth column is the load-bearing one. It is either a source the project
already uses, or the honest admission that the words are new. An agent that
cannot fill that column has not finished thinking.

When a wording is being replaced, show the rejected wording beside it. The
comparison is what lets a human judge quickly.

---

## 6. The reader test

A proposed term passes only if a person new to the project understands it
without being handed a glossary first.

Compression that helps the writer and costs the reader is a defect, not a
style. Calibration from decisions already made here:

| Rejected | Why | Accepted instead |
|---|---|---|
| active tree | which tree | tests currently run by CI |
| evidence | too general | paper result checks |
| manual tier | what context | long tests run only when requested |
| claim_id | what is a claim, what is an id | requirement name |
| covers | covers what | source_files |
| default read set | vague | files the AI reads first |
| budget gate | what budget, what gate | test growth report |
| project lexicon | what is a lexicon | project terms and definitions |
| symbol map | reads as symbol mapping | paper and code names |
| canonical suite | how would a reader know | the existing test for that requirement |

Two terms survived unchanged because they are already common: `Git history`,
and `PR` where it is written out as pull request on first use.

**Do not defend a compressed term by explaining it.** If it needs the
explanation, replace it with the explanation.

### Three further tests, applied after the reader test

A name can pass the reader test and still fail. Calibration from a second round
of rejections:

| Rejected | Reason given | Test it establishes |
|---|---|---|
| Human–AI work | "what work?" | **Action.** A noun that names no action says nothing. Compare "Agent work", which was accepted because the subject is named. |
| Current tests | "what current?" | Reader test again. *Current* is the same vague qualifier as *active*. |
| Test lifecycle, as a slide inside a deck titled Human–AI test lifecycle | already settled | **No self-repetition.** A section title must not repeat the document title. It gives the reader nothing the cover did not. |
| Test requirements, beside Current tests and Test lifecycle | "again duplicate for what?" | **Distinguishing.** Names in one set must be told apart from one another, not merely understood one at a time. |
| Sonique changes | "readers no need to know about sonique" | **Need.** Clarity is not a reason for a thing to exist. Name only what this audience needs. |
| `check_test_requirements_contract.py` | "why we need duplicate?" | **Existence first.** Do not propose a name for a thing whose existence is not yet agreed. Agree the thing, then name it. |

Two of these are set-level, not item-level. An agent that checks each proposed
name on its own will pass a list that fails as a whole, so the check is: read
the proposed names together and say which two could be confused.

### Approval is scoped to a place

A name approved in one position is not approved everywhere. "Test lifecycle"
was approved as a document title and rejected as a slide title inside that same
document, and both decisions are right. When reusing an approved name in a new
position, say which approval is being relied on and confirm it still holds.

---

## 7. Waiting

1. Nothing is created, renamed, or deleted under a proposed name.
2. Silence is not approval. An unanswered item stays `proposed`.
3. Approval of one item does not extend to the next item, the next file, or
   the next session.
4. Work that does not depend on the pending name continues. Work that does
   stops, and the report says which parts stopped and why.
5. If a name must exist to make progress at all, the agent writes it, registers
   it in the same response, and states that it will be renamed on the human's
   word.

---

## 8. Where the register lives

`APPROVAL_LIST.md`, beside this file. Not in a conversation. Every session reads
it before proposing anything, so numbering continues and settled questions are
not reopened.

**One file, all agents.** More than one AI works on this project, and they share
the identifier sequence. An agent that numbers from its own memory rather than
from this file will reuse an identifier another agent has already spent, and an
identifier that resolves to two decisions is worse than no identifier at all.

So, before proposing anything: read the file, take the number it says is next,
and write the proposal into the file in the same response that puts it to the
human. An agent that cannot write to the file states the numbers it intends to
use and asks the human to reserve them.

A term that has been approved is then used in the position it was approved for,
without re-asking. See section 6 on scope.

---

## 9. Reporting

Every response that reports work carries both bars, twenty cells each:

```text
Progress [██████████░░░░░░░░░░]  50% · step 4/8 · red gate
Tokens   [███████░░░░░░░░░░░░░]  ~35k / 100k budget · estimated
```

Declare both denominators before starting. Label the token figure `measured`
or `estimated`. When the estimate reaches the budget, render the bar full, mark
it `OVER`, state the overrun, and ask whether to continue, re-baseline, or
stop. Never pass a declared budget silently.

---

## 10. When blocked

State the recommendation first, then the question. A report that ends in a
question with no recommendation makes the human do the agent's thinking.

Group the options so the answer is short. The pattern that works:

> The branch has three separate uncommitted groups. My recommendation is three
> commits, excluding generated output. Which groups should I commit?

---

## 11. Disagreement

When a document and the code disagree, report the disagreement and name both
sides. Do not reconcile them. The human decides which side is authoritative.

When two source documents give one term two meanings, report the conflict and
ask which governs. Do not pick the one that reads better.

---

## 12. Instructions are advisory; checks bind

An instruction is followed only by an agent that reads it and chooses to
comply. Evidence from this project: an agent ran git commands here against an
explicit prohibition, and disclosed doing so afterwards.

So every rule that matters carries a check that fails. A rule without a check
is documentation.

A check that produces false results is worse than no check, because it teaches
everyone to ignore it. Fixing the check is part of the work, and the fix is
reported.

---

## 13. What an agent never does without an explicit request

- delete a file another person is expected to find
- change the meaning of an existing approved name
- widen an approved name to cover more than it did
- push, merge, or merge a pull request
- stage with `git add -A` or `git add .`
- resolve a merge conflict silently

---

## 14. This document is pinned

A copy lives at the Juna repository root. The two copies are byte-identical and
the digest is pinned in `JunaCore/test/provenance_contract.jl`, so a change to
one that does not land in the other fails the test suite.

Do not update the pin to make a failure pass. Land the change in both copies in
one reviewed change, as the fork protocol in that file requires.

---

The register is `APPROVAL_LIST.md`. Decisions D1 to D4, which govern this document,
are recorded there as approved on 2026-07-31.
