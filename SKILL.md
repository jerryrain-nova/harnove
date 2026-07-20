---
name: harnove
description: Orchestrate a Harnove software iteration from an existing PRD or natural-language requirement using fresh isolated subagents for PRD preparation, technical design, code planning, test design, implementation, testing, and retrospective learning, with mandatory human gates, Mermaid-assisted design documents, Harnove-local archives, and reusable improvement history.
---

# Orchestrate a Harnove iteration

Locate the nearest Harnove `config.json`; treat its parent as `HARNOVE_HOME`. Use
`HARNOVE_HOME/runtime/harnove.py` as the authoritative state machine and read
`references/artifact-contracts.md` completely. Keep `iterations/` and `improve/` under
`HARNOVE_HOME`; never create them at the product repository root.

## Keep the main Agent orchestration-only

Act only as the orchestrator. Inspect status, create work orders, spawn and monitor fresh
subagents, validate their completion evidence, invoke state transitions, and relay human
questions or review gates. Do not author stage documents, modify product code, or write tests.

For every `(stage, version)`:

1. Check `status`; require `awaiting_dispatch`.
2. Choose a globally new subagent/task ID for this iteration.
3. Run `dispatch --archive <dir> --agent-id <id> --orchestrator <name>`.
4. Spawn a fresh platform-native subagent and give it only the generated work-order path.
   Never reuse a subagent across stages, versions, rejections, clarification revisions, or
   test-fix cycles. If the platform cannot create subagents, stop and report the limitation.
5. Monitor the child. The child may work only within the work order, must read the frozen PRD
   and experience context, and must not call Harnove state commands or approve a gate.
6. On success, run `agent-complete ... --result succeeded --evidence <summary>`. On failure,
   run it with `failed`; on timeout/crash use `abandon --reason <reason>`, then dispatch a new
   child. A successful run changes status to `ready_for_submit`.
7. Run `submit` as the orchestrator. Never bypass the run ID, lease, or agent evidence by
   editing `state.json`.

## Prepare and approve the candidate PRD

Accept exactly one input:

- Existing PRD: `init ... --prd <path>`. Preserve it as an immutable, hash-verified original.
- Natural language: `init ... --description <text>` or `--description-file <path>`.

Both modes enter `prd_intake`. The PRD subagent must create a separate versioned candidate,
use stable `REQ-xxx` IDs, and record every addition with its source, reason, and confirmation
state. Never edit the original or invent scope, thresholds, permissions, compatibility, or
acceptance rules.

If material ambiguity remains, submit `needs-clarification`, ask the user the minimum grouped
questions, and archive the reply with `clarify`. Dispatch a fresh PRD subagent for the new
version. When boundaries are sufficient, submit `ready`, stop at `awaiting_prd_review`, and
obtain an explicit human `review`. Rejection requires actionable feedback and a fresh child;
approval alone freezes the candidate PRD and advances the workflow.

## Execute isolated stages

- `technical_design`: document repository evidence, architecture, flows, constraints, risks,
  rollout, rollback, traceability, and relevant historical experience.
- `code_plan`: specify file/module/symbol scope, exact rules, boundaries, rationale, risks,
  sequencing, prohibited changes, and traceability. Do not modify product code.
- `test_design`: cover every requirement and planned change with purpose, preconditions,
  steps, expected result, type, priority, and edge/failure behavior. Do not modify code.
- `implementation`: modify only approved scope and record deviations and Git evidence.
- `test_execution`: inspect the actual diff, implement and run executable tests, then submit
  `passed|failed`. Failure creates a new implementation version and fresh child.
- `summary`: reconcile all evidence, score every stage, identify root causes, extract reusable
  experience, and specify next-iteration reuse rules.

Candidate PRD, technical design, code plan, and test design require real human approval.

## Use diagrams when they improve comprehension

In technical design and code-plan artifacts, use Mermaid for architecture, sequence, data
flow, state, dependency, or change-call-chain relationships when a visual makes three or more
related components or steps easier to verify. Set `DIAGRAM_STATUS: INCLUDED` and include a
valid Mermaid block. Avoid decorative diagrams. If a diagram genuinely adds no value, set
`DIAGRAM_STATUS: NOT_APPLICABLE` and provide a concrete reason of at least 20 characters.

## Reuse and grow experience

Require every subagent to read the iteration's `00-input/*经验复用上下文.md`, cite adopted
experience, and explain why irrelevant guidance does not apply. On successful summary
submission, Harnove writes an immutable experience record under `HARNOVE_HOME/improve/`.
Future iterations automatically snapshot the accumulated records. Never package, publish,
or include `iterations/` or `improve/` in product Git evidence when iterating Harnove itself.
