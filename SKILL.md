---
name: harnove
description: Orchestrate a Harnove software iteration from an existing PRD or natural-language requirement using fresh isolated subagents, project-specific custom instructions, persistent structure knowledge, structure-verified designs, mandatory human gates, visual artifacts, Harnove-local archives, and reusable experience.
---

# Orchestrate a Harnove iteration

Locate the nearest Harnove `config.json`; treat its parent as `HARNOVE_HOME`. Use
`HARNOVE_HOME/runtime/harnove.py` as the authoritative state machine and read
`references/artifact-contracts.md` completely. Keep `iterations/`, `improve/`, `structure/`, and `custom/` under
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
5. Monitor the child. The child may work only within the work order, must read the frozen PRD,
   custom context, experience context, and current structure knowledge, and must not call Harnove state
   commands or approve a gate.
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

- `structure_analysis`: read `HARNOVE_HOME/structure/` first. If records exist, inspect only
  demand-relevant code to verify them. If empty, inspect the full repository and create
  structure records split into `功能模块`, `代码框架`, and `结构定义和关系`. Record code evidence.
- `technical_design`: document repository evidence, architecture, flows, constraints, risks,
  rollout, rollback, traceability, and relevant historical experience. Before designing,
  verify demand-related structure records against current code and update stale records.
- `code_plan`: specify file/module/symbol scope, exact rules, boundaries, rationale, risks,
  sequencing, prohibited changes, and traceability. Recheck demand-related structure records
  against current code and update them before planning. Do not modify product code.
- `test_design`: cover every requirement and planned change with purpose, preconditions,
  steps, expected result, type, priority, and edge/failure behavior. Do not modify code.
- `implementation`: modify only approved scope and record deviations and Git evidence.
- `test_execution`: inspect the actual diff, implement and run executable tests, then submit
  `passed|failed`. Failure creates a new implementation version and fresh child.
- `structure_refresh`: after tests pass, inspect the actual diff and update persistent
  structure records so they describe the completed code. This stage must change structure.
- `summary`: reconcile all evidence, score every stage, identify root causes, extract reusable
  experience, and summarize rules learned from user clarifications, review feedback, and custom updates.

Candidate PRD, technical design, code plan, and test design require real human approval.

## Use diagrams when they improve comprehension

In technical design and code-plan artifacts, use Mermaid for architecture, sequence, data
flow, state, dependency, or change-call-chain relationships when a visual makes three or more
related components or steps easier to verify. Set `DIAGRAM_STATUS: INCLUDED` and include a
valid Mermaid block. Avoid decorative diagrams. If a diagram genuinely adds no value, set
`DIAGRAM_STATUS: NOT_APPLICABLE` and provide a concrete reason of at least 20 characters.

In every technical design, include `功能变更树`; in every code plan, include `代码变更树`.
Use a readable text tree with explicit roots, branches, affected boundaries, and at least two
nodes so reviewers can see scope at a glance. Set `CHANGE_TREE_STATUS: INCLUDED`.

Default to `PRESENTATION_FORMAT: MD`. If Markdown cannot express a complex relationship
precisely, set `PRESENTATION_FORMAT: HTML` and create a same-name `.html` sidecar in the
iteration archive. Use HTML only when it materially improves precision; the Markdown artifact
remains the authoritative index and must still contain the change tree and evidence.

## Maintain project structure knowledge

Treat `HARNOVE_HOME/structure/` as project-owned, cumulative knowledge. Use Markdown by
default and HTML only when necessary. Every structure file must cover functional modules,
code framework, and structure definitions/relationships with file or symbol evidence. Use
`STRUCTURE_STATUS: CONSISTENT` only after checking relevant code. If any mismatch exists,
update structure first and use `STRUCTURE_STATUS: UPDATED`. Never package or publish structure
records as Harnove core files.

## Reuse and grow experience

Require every subagent to read the iteration's `00-input/*经验复用上下文.md`, cite adopted
experience, and explain why irrelevant guidance does not apply. On successful summary
submission, Harnove writes an immutable experience record under `HARNOVE_HOME/improve/`.
Future iterations automatically snapshot the accumulated records. Never package, publish,
or include `iterations/`, `improve/`, `structure/`, or `custom/` in product Git evidence when iterating Harnove itself.

## Apply project custom instructions

Treat `HARNOVE_HOME/custom/` as project-owned context similar to `AGENTS.md`. Ensure `user.md`
and `self.md` always exist; avoid additional files unless they are necessary. Snapshot and read
both before beginning an iteration, and require every fresh subagent to read that snapshot.
`user.md` stores durable user constraints and preferences; `self.md` stores Harnove's reusable
lessons for this project. When the user adds a durable request during an iteration, record it
before the next child is dispatched with `customize --target user --content <text> --actor <name>`.

In the final summary, declare `FEEDBACK_EXPERIENCE_STATUS: CAPTURED` when user clarification,
review feedback, or custom updates exist, and distill them into concrete reusable rules. On
successful completion, Harnove appends that section to `custom/self.md`. If no feedback exists,
declare `FEEDBACK_EXPERIENCE_STATUS: NONE`; do not fabricate experience.

## Version Harnove itself

For `a.b.c`, increment only `c` for fixes or optimization without new functionality, increment
`b` and reset `c` for new functionality, and increment `a` while resetting `b.c` for an
architecture change. Validate releases with `scripts/version_policy.py`.
