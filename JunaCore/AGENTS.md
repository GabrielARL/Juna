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

## Source File Gate

This package was migrated from `sonique/research/JunaCore`; `README.md` records
the source commit. Juna is now a separate entity with its own code, tests, and
change history. Its files and receiver results do not have to match Sonique.

`test/source_file_check.jl` stores the SHA-256 value of each selected Juna file
and reports when a value changes. A reviewed Juna change may update its stored
value in the same change after the user approves it. It does not require a
corresponding Sonique change. `tools/parity_check.jl` checks fixed Juna receiver
results against results stored in this repository. The source details record
where the migration began; they do not impose continuing equality.

If paper claims and this code disagree, never silently reconcile either side.
Ask which is authoritative.

Git safety rules for all agents live at the repository root: `../AGENTS.md`.

## Generated Files And Server Processes

- `tools/explorer/suites.json` is generated from the `SUITES` registry in
  `test/runtests.jl`. Never hand-edit it; regenerate with
  `julia tools/explorer/export_suites.jl` (explorer contract C1 fails
  otherwise).
- `tools/explorer/chain.json` evidence fields are measured against the
  coverage scan; promote or demote them only as explorer contract C5
  directs, never to make a page look better.
- `bench/` and `.migration_progress.log` are gitignored runtime artifacts;
  never commit them.
- The Lite explorer runs permanently on port 8772; the source repository's
  explorer keeps 8771. Before launching a server, check the port is free
  (`ss -ltnp`); stop processes by PID only — never `pkill -f`.

## Chain-Reference Gate

Before implementing any source change, read the declared receiver chain at
`http://127.0.0.1:8772/chain` (data: `tools/explorer/chain.json`) and ask
the user whether the change alters a documented stage. Any change to a
stage's symbols must update `chain.json` in the same change —
`tools/explorer/explorer_contract.py` fails on renamed or missing symbols,
stale `suites.json`, unregistered suites, and overstated evidence.

## Verification Gate

Default checks for this Julia package:

```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --project=. -e 'using JunaCore'            # load gate: pruned closure complete
julia --project=. -e 'using Pkg; Pkg.test()'     # full suite registry
julia --project=. tools/parity_check.jl          # check fixed local receiver results
python3 tools/explorer/explorer_contract.py      # data contracts C1-C7
python3 tools/explorer/server_contract.py        # explorer behavior S1-S13
```

For changes touching encode/decode behavior, LDPC integration,
synchronization, or receiver logic, also run:

```bash
julia --project=. test/runtests.jl roundtrip
```

## Done Means

A task is done only when the spec is clear, the validation target exists,
required checks pass, and the diff is scoped to the request. The final report
lists what changed and what was run. The final report carries both bars with
progress at 100% and the token figure labelled.
