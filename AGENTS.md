# Juna Repository Root Rules

This is the routing and safety harness for the repository root. Read
`JunaCore/AGENTS.md` completely before touching any package file — it
carries the detailed, mandatory workflow (validation-first eight-step
sequence, red gate, progress and token bars, source file gate,
chain-reference gate, verification gates). The progress and token bars rule
applies to root-level work too.

## Layout And Routing

- The git root is `/home/gabiel/Documents/GitHub/Juna`.
- The Julia package lives under `JunaCore/`. Package commands run after
  `cd JunaCore`, or with `--project=JunaCore`.
- `reference papers/` is tracked. It holds third-party PDFs alongside
  authored notes. Never delete, reorganize, or treat it as a package
  dependency without explicit approval, and do not commit a newly downloaded
  PDF without approval — redistributing someone else's paper is not this
  repository's decision.
- Do not create new top-level directories without explicit approval.

## Explorers

- The Lite explorer serves this package permanently on port 8772
  (`python3 JunaCore/tools/explorer/server.py`).
- The source repository's explorer (port 8771) remains canonical for the
  full nine-receiver family; never repurpose or claim its port.
- Check a port is free before launching (`ss -ltnp`); stop processes by
  PID only — never `pkill -f`.

## Writing Rules

Any writing or rewriting of a document in this repository — paper, note,
tutorial, or slide deck — follows `.claude/skills/mandar/SKILL.md`. Read it
before writing. Its three hard rules bind every agent, whatever tool it runs
under:

1. Use only words that appear in the source material.
2. Never introduce a word or name of your own. If something has no name,
   stop, say so, propose candidates with their sources, and wait.
3. Explain the proposed change in plain words and get agreement before
   writing.

Mechanical checks: `python3 .claude/skills/mandar/style_check.py FILE.tex`.
The checker cannot verify rules 1 to 3; a human must.

## Git Rules For Agents

- Never push, never merge, never merge a pull request. Commit only when
  the user explicitly requests it, naming the change being committed.
- Stage with explicit paths only; `git add -A` and `git add .` are
  forbidden anywhere in this repository.
- Commit messages explain the change and why. Exact commands and detailed
  results belong in the PR body and the final report; exceptional
  provenance information may stay in the commit body.
- Amend or reset only while a commit is unpublished. After pushing,
  correct shared history with `git revert` — never rewrite it.
- Never force-push. Never delete branches you did not create this session.
- Attribution must accurately identify the tool involved. This project
  accepts Claude Code's Co-Authored-By trailer on commits; a neutral
  "Assisted-by" note in the PR body is equally acceptable.
- Merge conflicts are never resolved silently. If both sides carry
  meaningful changes, stop for human review. Purely mechanical conflicts
  may be proposed with the resolving diff displayed — never hidden.
- Before the first push of a session: run `git remote -v` and confirm the
  remote with the user. (History lesson: this workspace once carried an
  origin pointing at an unrelated repository.)

## Branch Protection Checklist

Prepared now; apply only after the user explicitly confirms the intended
GitHub remote.

1. Create the GitHub repository; `git remote add origin <url>`;
   `git push -u origin main` (user-approved).
2. Protect `main`: require pull requests (no direct pushes), require at
   least one human review, dismiss stale approvals on new commits.
3. Forbid force pushes and branch deletion on `main`.
4. Required status checks before merge (wire into CI first): `Pkg.test`
   (includes the source-file-check suite), `tools/parity_check.jl` digest,
   `tools/explorer/explorer_contract.py`, and
   `tools/explorer/server_contract.py`.
5. AI agents open pull requests with an evidence-bearing body (what
   changed, why, what was run, remaining risk); a human reviews and
   merges. No agent self-merge.
