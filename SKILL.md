---
name: harnove
description: Run a Harnove PRD-driven software iteration through technical design, code-change planning, test design, implementation, executable testing, and retrospective summary. Use when the user mentions Harnove or when a development task requires explicit human approval gates, rejection loops, requirement-to-change traceability, Git evidence, complete test coverage, and iteration artifact archiving.
---

# Run a development iteration

Locate the nearest Harnove `config.json`; treat its parent as `HARNOVE_HOME`. Use
`HARNOVE_HOME/runtime/harnove.py` as the authoritative state machine. On Windows, prefer
`HARNOVE_HOME/run.ps1`. Read
`references/artifact-contracts.md` before producing or reviewing an artifact.

## Start

1. Confirm `HARNOVE_HOME/config.json` exists. If absent, stop and ask the user to run the plugin `init.py`; project initialization is an explicit owner action.
2. Locate the PRD and repository root. Do not infer missing requirements.
3. Run `HARNOVE_HOME/run.ps1 init --iteration-id <ID> --requirement <slug> --prd <path>` or invoke the installed Python runtime directly.
4. Work only in the created archive directory. Treat its `state.json` as authoritative.
5. Preserve the PRD snapshot. Cite requirement IDs in every proposal, change, and test.

## Execute the state machine

For each `drafting` stage, produce the artifact named by `harnove.py status`, then run
`harnove.py submit --archive <dir>`. Never perform work belonging to a later stage.

- `technical_design`: Act as the technical solution designer. Inspect the repository and PRD; document architecture, constraints, interfaces, risks, and requirement evidence. Do not design unrequested features.
- `code_plan`: Act as the code framework designer. Specify files/symbols, exact change rules, boundaries, rationale, risks, and requirement IDs. Do not modify product code.
- `test_design`: Act as the test expert. Map every requirement and planned change to tests, purpose, preconditions, steps, expected results, type, and priority. Do not modify product code.
- `implementation`: Act as the code expert. Change only approved scope. Record deviations and their approval; capture Git evidence. Do not weaken tests to make failures pass.
- `test_execution`: Act as the test expert. Inspect the actual diff, implement executable tests, run them, and record commands and results. Run `submit --result passed|failed`. A failure returns the iteration to implementation.
- `summary`: Act as the summary expert. Reconcile PRD, approved artifacts, actual diff, and test results. Score every stage with evidence and write reusable improvements.

## Human gates

Technical design, code plan, and test design require a real human decision via
`harnove.py review`. Never approve on the human's behalf. On rejection, incorporate the
review feedback into a new version without deleting the rejected version or review record.

## Integrity rules

- Treat the PRD as the scope ceiling. Label unresolved ambiguity and stop the affected work.
- Cite stable requirement IDs. If the PRD lacks them, create IDs in the requirement baseline without changing meaning.
- Never overwrite submitted artifacts; Harnove creates the next version.
- Keep planned scope, actual Git diff, and tests mutually traceable.
- Do not mark testing passed unless every mandatory executable test passed and evidence is archived.
- Finish only after `harnove.py submit` validates the summary and reports `complete`.
