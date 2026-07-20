---
name: harnove
description: Run a Harnove software iteration from either an existing PRD or a natural-language requirement through versioned PRD supplementation and mandatory human approval, technical design, code planning, test design, implementation, testing, and retrospective summary with archived evidence.
---

# Run a development iteration

Locate the nearest Harnove `config.json`; treat its parent as `HARNOVE_HOME`. Use
`HARNOVE_HOME/runtime/harnove.py` as the authoritative state machine. On Windows, prefer
`HARNOVE_HOME/run.ps1`. Read `references/artifact-contracts.md` completely before acting.

## Select the input mode

Accept exactly one of these inputs:

1. An existing PRD: run `init ... --prd <path>`. Preserve it as an immutable original and
   create a separate candidate PRD. Never edit the source file or its archived original.
2. A natural-language description: run `init ... --description <text>` or
   `init ... --description-file <path>`. Preserve the description and create a candidate PRD.

Both modes begin `prd_intake`. Do not begin technical design until the candidate PRD passes
human review.

If neither input is usable, ask only for the missing iteration ID, requirement name, and PRD
or requirement description. Never require a PRD when the user can describe the requirement.

## Prepare and approve the candidate PRD

When `stage=prd_intake` and `status=drafting`:

1. Read the immutable original input and the current candidate PRD version.
2. Create or revise only the candidate PRD. For an existing PRD, reproduce its meaning and
   add only information necessary to make scope and acceptance executable.
3. Record every addition in `信息补充记录`, including content, source, reason, and confirmation
   status. Treat repository observations as technical facts, not new product requirements.
4. Preserve the user's meaning. Mark unsupported details as unknown; never invent business
   behavior, scope, thresholds, permissions, compatibility guarantees, or acceptance rules.
5. Identify only ambiguities that materially affect scope, architecture, implementation, or
   acceptance. Group related questions and ask the minimum necessary set.
6. If questions remain, keep `PRD_STATUS: NEEDS_CLARIFICATION`, list each question under
   `待确认问题`, and submit with `--result needs-clarification`. Ask the user those questions.
7. Record the answer with `clarify --responder <name> --response <text>` (or
   `--response-file`). Revise the newly created PRD version and repeat if necessary.
8. When boundaries are sufficient, set exactly `PRD_STATUS: READY`, write
   `无（边界已确认）` under `待确认问题`, and submit with `--result ready`.
9. Stop at `awaiting_prd_review` and ask the user to review the complete candidate PRD.
   Never approve it on the user's behalf.
10. Record the decision with `review --decision approve|reject --reviewer <name>`. On reject,
    require actionable feedback, revise the newly created candidate PRD version, and submit
    it for review again. On approve, Harnove freezes the approved version and proceeds.

Only human approval freezes the candidate PRD as the downstream scope ceiling. Never bypass
clarification or approval by editing `state.json`.

## Execute the development state machine

For each `drafting` stage, produce the artifact named by `status`, then run `submit`. Never
perform work belonging to a later stage.

- `technical_design`: inspect the repository and frozen PRD; document architecture,
  constraints, interfaces, risks, and requirement evidence.
- `code_plan`: specify files/symbols, exact changes, boundaries, rationale, and requirement
  IDs. Do not modify product code.
- `test_design`: map every requirement and planned change to tests, purposes, preconditions,
  steps, expected results, types, and priorities. Do not modify product code.
- `implementation`: change only approved scope; record deviations and Git evidence.
- `test_execution`: inspect the actual diff, implement and run executable tests, then submit
  `--result passed|failed`. Failure returns the iteration to implementation.
- `summary`: reconcile the PRD, approved artifacts, actual diff, and test results; score each
  stage with evidence and record reusable improvements.

## Human gates and integrity

Candidate PRD, technical design, code plan, and test design require a real human `review`.
Never approve on the human's behalf. A rejection creates a new version and retains feedback.

- Treat the frozen PRD as the scope ceiling and cite stable `REQ-xxx` IDs throughout.
- Preserve all original inputs, candidate PRD versions, clarifications, submitted artifacts,
  reviews, Git evidence, tests, and summaries in the iteration archive.
- Do not weaken tests to make failures pass or claim success without archived evidence.
- Finish only when summary submission reports `complete`.
