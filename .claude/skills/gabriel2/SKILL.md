---
name: gabriel2
description: How Gabriel adjudicates work between two agents — the merge-audit register one agent writes about the other's branch, his one-line verdict vocabulary (ok / propose other names / rewrite with <skill>), the approval layers between scope and push, and the readability defect he keeps correcting. Use when preparing a merge audit, when answering one, when he answers an item with a skill name, or when he restates why something is wrong. Companion to the gabriel skill.
---

# Adjudicating between two agents

Companion to `gabriel` (the general loop, the crisp rule, the git discipline).
This records how a **merge between agents** actually runs, distilled from the
JCM-001..025 audit of `agent/claude-writing` (2026-08): Codex audited Claude's
eight commits, produced a register, and Gabriel answered all 25 items in one
message, one line each.

## The merge-audit register

Before anything merges, the *other* agent audits the branch and writes a
numbered register. Its shape is fixed:

- One row per decision. Each row is the decision in one sentence, then its
  meaning or source in one sentence. Nothing longer.
- Rows cite files with line anchors, name the commit they judge, and attribute
  work to the agent that did it ("Claude commit 4a0d8b9").
- The register ends by stating what approval does **not** cover, explicitly:
  *"No push is included in these approvals."*
- It offers the bulk shortcut — *"Approve JCM-001 through JCM-025"* — while
  stating that corrected diffs still return for final wording review. The
  shortcut never collapses the layers (see below).
- An audit row may bundle a correction with its acceptance ("Accept X **after**
  replacing Y"). `ok` on that row approves the correction too.

## Stable IDs and honest gaps

- IDs are never renumbered and never reused. Once issued, an ID is how the
  decision is referred to forever.
- If the canonical register has a gap (D6–D12 unresolved), **do not invent
  entries to fill it**. Open a clearly marked temporary series (JCM-*), say why
  it exists, and promise its stability: *"These IDs will remain stable."*
  Preserving an unresolved gap beats backfilling it — Gabriel approved exactly
  that (JCM-003, `ok`).

## His verdict vocabulary

He answers per ID, in order, one line each. Every answer form has a fixed
meaning:

| His words (verbatim) | Meaning |
|---|---|
| `ok` | Approved as written, including any condition the row attached. |
| `propose other names` | The name is rejected. Draft candidates with the source of each; he picks. Never coin the replacement yourself (mandar R2). |
| `rewrite with mandar.skills` | The named skill is the complete spec for the rework. No further instruction is coming; do not ask for one. |
| `rewrite with only style from mandar` | Scoped invocation: the style rules apply, the rest of the skill's machinery does not. Read the qualifier — it is deliberate. |
| `rewrite, remember mandar.skills?` | Same as above, plus a reproach: the skill already existed and was not applied. The question mark is the reproach. |
| a prose paragraph | His diagnosis replaces yours. It governs the item, its siblings, and future work (see next section). |

A skill name in an answer is a binding pointer to that skill's full text.
Rework answered this way is judged against the skill, not against whatever
summary of it you remember.

## He corrects the diagnosis, not just the artifact

When the register frames a defect wrongly, he does not merely reject the fix —
he restates the actual problem. Verbatim, on JCM-016:

> "the issue is not about over claiming now, is about claude keep inventing
> terminology that confuses the reader, can you tell how hard is it to read
> what it writes just because of its over-emphasis and pedantic-ness."

Rules that follow:

1. The corrected diagnosis governs **every sibling item**, not just the one it
   was written under. Here it explains 009–016 at once: the rewrites are not
   about claims, they are about readability.
2. The recurring defect he names in AI writing is **invented terminology,
   over-emphasis, and pedantic qualification**. A document can be technically
   correct and still defective because it is hard to read. Hard-to-read is a
   defect class of its own.
3. The remedy is already specified: mandar's rules — source vocabulary only,
   one idea per sentence, plain words, no coined names. His skills exist so
   that this correction never has to be typed twice.

## Reader-facing language rules (CL-25, approved 2026-08)

From the same feedback, three rules not already covered by the mandar and
gabriel skills, adopted verbatim:

1. "Explain the observable operation first."
2. "Use one reader-facing term for one meaning."
3. "State each requirement once and identify the test that verifies it."

And the closing test that governs all three: *"If a reader must guess what a
term means, the wording is not finished."* Hard-to-read is a defect class of
its own — a label can be technically correct, sourced, and still fail this.

## The jargon signal

His cheapest way to flag unreadable wording, agreed 2026-08: he quotes the
term with a question mark — *"working label?"* — or asks *"X of what?"*, or
just writes **jargon**. Any of these means the word has already failed. The
required response, in order:

1. Define it in one plain sentence.
2. State whether he ever approved it (almost always: no).
3. Rewrite the passage without it — replace the term with its description,
   never with a new term.

Meta-vocabulary is not exempt. Words invented to *run* the terminology audit
("working label", "maintainer", "provenance") fail the same test the moment
he has to ask. The audit's own language must be plain: say "a name I made up
that you never approved", not "working label".

*"I as a human find it hard to follow you"* is the standing reason. Plain
words first in messages, not only in documents.

## Approval layers

Approval is a ladder, and each rung is separate. Climbing one never implies
the next:

```
scope approved        →  the work stream may exist        (JCM-023: "approves scope, not committing yet")
wording approved      →  corrected diffs reviewed by him  (bulk `ok` still returns diffs for this)
commit approved       →  his explicit word, scoped paths
merge                 →  a human merges; agents are prohibited (JCM-025)
push                  →  never implied by any of the above ("No push is included")
```

Further merge mechanics he approved:

- The audited agent's commit history is preserved through the merge — no
  squashing another agent's commits (JCM-025).
- Separate work streams stay separate commits; one mixed commit is a review
  defect, not a convenience (JCM-023).
- Validation gates must be green before merge, and a known failure is named by
  its register ID, not described vaguely (JCM-024: "the existing JNR-020
  issue").

## Register hygiene across agents

- Per-agent ID prefixes so two agents cannot allocate the same number
  (CL-*, CX-*, JCM-*, JNR-*, D-*).
- When registers overlap, the surviving decision names the one it supersedes.
  A question left unanswered in one agent's register can be settled by an `ok`
  in the other's — record the supersession, do not re-ask.
- The other agent's uncommitted work and register entries are treated as
  intentional. Verify claims against files before agreeing; never revert what
  the other agent wrote unless he directs it.
