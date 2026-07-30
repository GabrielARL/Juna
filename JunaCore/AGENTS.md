# Agent Workflow Harness

This repository is test-case oriented. Any AI agent or LLM working here must
treat this file as a mandatory gate, not as optional advice.

If a request cannot be expressed as verifiable behavior and checked by tests,
scripts, reviewable evidence, or an explicit human-approved exception, the
agent must stop and ask for clarification instead of implementing it.

## Non-Negotiable Rule

Do not make implementation changes until the work has a validation target.

Every task must pass this sequence:

1. Define the behavior being changed.
2. Define concrete acceptance criteria.
3. Add or update tests, scripts, fixtures, or an equivalent validation checklist before implementation.
4. Run the new or changed validation and confirm it fails for the expected reason when possible.
5. Implement the smallest change that satisfies the validation.
6. Run targeted validation.
7. Run the broadest practical regression check.
8. Report the exact commands and results.

If any required validation cannot be run, the agent must say why, describe the
residual risk, and avoid claiming the task is complete.

## Progress And Cost Reporting

Every response that reports work must show a twenty-cell progress bar and an
estimated token-consumption bar, counted against denominators declared before
implementation. This covers the opening plan, every intermediate update, and
the final report, including background sweeps and subagent runs.

```text
Progress [██████████░░░░░░░░░░]  50% · step 4/8 · red gate
Tokens   [███████░░░░░░░░░░░░░]  ~35k / 100k budget · estimated
```

- Declare both denominators before implementing.
- Count completed steps only once their validation has actually run.
- Label the token figure `measured` or `estimated`; never fabricate precision.
- Never silently pass the budget: render the bar full, mark it `OVER`, state
  the overrun, and ask the user whether to continue, re-baseline, or stop.
- Re-baseline out loud when scope changes.

## Provenance Gate

This package is a migrated subset of `sonique/research/JunaCore` (see
README.md for the source commit). The migrated algorithm files
(`src/juna/common.jl`, `src/juna/lite.jl`, `src/Modulations.jl`,
`src/LDPC.jl`) are byte-identical to their source commit. Any edit to them
here forks the algorithm from the source repository: surface that to the user
and ask whether the change should also land in sonique before proceeding. If
paper claims and this code disagree, never silently reconcile either side —
ask which is authoritative.

A chain-reference gate (the Lite receiver-chain document served by the
phase-3 explorer on port 8772) will be added when that explorer lands.

## Verification Gate

Default checks for this Julia package:

```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --project=. -e 'using JunaCore'          # load gate: pruned closure complete
julia --project=. test/phase1_smoke.jl         # clean-channel roundtrip, all facades
```

Once the phase-2 suites land, `julia --project=. -e 'using Pkg; Pkg.test()'`
becomes the broadest regression check.

## Done Means

A task is done only when: the spec is clear, the validation target exists,
required checks pass, the diff is scoped to the request, the final report
lists what changed and what was run, and the final report carries both bars
with progress at 100% and the token figure labelled.
