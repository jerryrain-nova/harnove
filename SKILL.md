---
name: harnove
description: Orchestrate expert or agile Harnove software iterations from an existing PRD or natural-language requirement using a user-confirmed mode and iteration name, fresh isolated subagents, live repository inspection, implementation branches, mandatory human gates, Harnove-local archives, post-completion structure abstraction, and reusable experience.
---

# Orchestrate a Harnove iteration

Locate the nearest Harnove `config.json`; treat its parent as `HARNOVE_HOME`. Use
`HARNOVE_HOME/runtime/harnove.py` as the authoritative state machine and read
`references/artifact-contracts.md` completely. Keep `iterations/`, `improve/`, `structure/`,
`custom/`, and `timeout-policy.json` under
`HARNOVE_HOME`; never create them at the product repository root.

## Confirm mode and iteration name before initialization

Read the requirement input and propose one concise, branch-safe iteration name that expresses
the business change. Ask the user to choose `expert` (专家模式) or `agile` (敏捷模式), and to
confirm the suggestion or provide a replacement. Explain briefly that expert mode keeps the full
design-and-test workflow while agile mode keeps requirements, code planning, implementation,
and an implementation-time structure refresh. Do not run `init` until the user explicitly supplies or accepts both. Pass them
through `--iteration-name` and `--mode`; never silently substitute them. Existing callers that
omit `--mode` remain in `expert` for compatibility.

## Keep the main Agent orchestration-only

Act only as the orchestrator. Inspect status, create work orders, spawn and monitor fresh
subagents, validate their completion evidence, invoke state transitions, and relay human
questions or review gates. Do not author stage documents, modify product code, or write tests.

For every `(stage, version)`:

1. Check `status`; require `awaiting_dispatch`.
2. Choose a globally new subagent/task ID for this iteration.
3. Run `dispatch --archive <dir> --agent-id <id> --orchestrator <name>`. For implementation,
   inspect the custom snapshot for a user branch rule and pass the resolved exact name through
   `--branch`; otherwise let Harnove use its default branch. In agile mode, do not dispatch until
   the mandatory implementation-branch decision below is recorded.
4. Spawn a fresh platform-native subagent and give it only the generated work-order path.
   Never reuse a subagent across stages, versions, approved feedback revisions, clarification revisions, or
   test-fix cycles. If the platform cannot create subagents, stop and report the limitation.
5. Monitor the child. The child may work only within the work order, must read the frozen PRD,
   custom context and experience context, and must not call Harnove state
   commands or approve a gate. Respect `timeout_minutes` and `expires_at`.
6. On success, run `agent-complete ... --result succeeded --evidence <summary>`. On failure,
   run it with `failed`. On a real timeout, use
   `abandon --run-id <id> --reason <reason> --timed-out`; on a non-timeout crash omit
   `--timed-out`. Then dispatch a new child. A successful run changes status to
   `ready_for_submit`.
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
obtain an explicit human `review`. Approval freezes the candidate PRD and advances the workflow.
Feedback enters the document-change preview loop below; it does not create a version or child yet.

## Execute expert-mode stages

In `workflow_mode=expert`, retain the complete existing workflow:

- `technical_design`: inspect the current repository directly and document file/symbol evidence,
  architecture, flows, constraints, risks, rollout, rollback, traceability, and relevant
  historical experience. Never use `structure/` as an architecture input.
- `code_plan`: specify file/module/symbol scope, exact rules, boundaries, rationale, risks,
  sequencing, prohibited changes, and traceability. Re-read the relevant current code before
  planning; never use `structure/` as an architecture input. Do not modify product code.
  Record `AFFECTED_FILES`, `AFFECTED_MODULES`, and `CROSS_BOUNDARY_CHANGE`. If the change is
  limited to at most three files in one module with no public-contract, data-schema,
  migration, or cross-boundary change, set `CHANGE_SCOPE: SMALL` and
  `DESIGN_MODE: COMBINED`, then include the complete test design in this same artifact.
  Otherwise set `CHANGE_SCOPE: REGULAR` and `DESIGN_MODE: SEPARATE`.
- `test_design`: cover every requirement and planned change with purpose, preconditions,
  steps, expected result, type, priority, and edge/failure behavior. Do not modify code.
- `implementation`: start only after `dispatch` creates and switches to a new branch. Use the
  user's branch rule when present; otherwise use `tmp/{iteration-name}-{implementation-version}`.
  Modify only approved scope and record deviations and Git evidence.
- `test_execution`: inspect the actual diff, implement and run executable tests, then submit
  `passed|failed`. Failure creates a new implementation version but stops before dispatch so the
  user can choose the repair branch strategy as described below.
- `summary`: reconcile all evidence, inspect the completed current repository, and update
  `structure/` with an abstract current-project view covering `功能模块`, `代码框架`, and
  `结构定义和关系` plus code evidence. Then score every stage, identify root causes, extract
  reusable experience, and summarize rules learned from user feedback. Structure abstraction
  happens only here.

Candidate PRDs and code plans in both modes, plus technical and test designs in expert mode,
require real human approval. After submitting any of these artifacts, present the complete
artifact to the user and stop. Passing validators, subagent completion, silence, lack of
feedback, or the main Agent's quality judgment never counts as approval. Only after the user
explicitly approves the complete current version may the main Agent run:

`review --decision approve --reviewer <human> --human-confirmation <exact-user-approval-text>`

Preserve the user's approval wording exactly; never invent, infer, or paraphrase it. Do not
dispatch the next stage until this command has recorded the approval and the state machine has
advanced.

For `DESIGN_MODE: COMBINED`, the one artifact is both the code-plan and test-design baseline.
Present the complete combined artifact for one explicit human review. Approval freezes the same
path/hash for both roles and advances directly to implementation; it does not create or dispatch
a separate `test_design` child. Rejection uses the normal document-change preview loop and must
cover any affected code or test sections.

## Execute agile mode independently

In `workflow_mode=agile`, use exactly:

`prd_intake → code_plan → implementation`

Do not create, dispatch, or infer `technical_design`, `test_design`, `test_execution`, or
`summary`.
Continue to use a fresh child for every stage/version and enforce all custom context, timeout,
lease, review, live-code, branch, and archive rules.
Create only `00-input/`, `02-code-plan/`, and `04-implementation/` for agile stages, plus the
same common `reviews/`, `agent-runs/`, and state files as expert mode. Never
create empty expert-only stage directories in a new agile archive.

- `prd_intake`: accept natural language or a PRD, clarify every material boundary and ambiguity,
  asking the user only when clarification questions actually exist. Submit a ready candidate
  only when the user-controlled boundaries are explicit. Present the complete READY PRD and ask
  for its explicit approval. Treat approval of that PRD as confirmation that no clarification
  request remains; do not require a second decision or special wording that separately confirms
  clarification completion.
- `code_plan`: inspect the live repository and produce the same file/module/symbol-level code
  change plan quality as expert code planning. Set `DESIGN_MODE: AGILE` and
  `CHANGE_SCOPE: AGILE`. This child designs only; it must not modify product code. Present the
  complete plan and require explicit human approval.
- `implementation`: after plan approval, create and switch to the normal implementation branch
  only after the state stops at `awaiting_implementation_branch_decision`. Proactively show the
  user both `current_branch` and `suggested_new_branch`, then ask them to choose the current
  original branch or a new branch. Record the answer with
  `implementation-branch-decision --strategy current|new --responder <human>`; for `new`, add
  `--branch <exact-name>` when the user supplies one. Never infer a choice or dispatch before
  this command succeeds. Then implement the approved scope, capture Git evidence, and inspect the
  completed live repository and update `structure/` with functional modules, code framework,
  structure definitions/relationships, and code evidence. A valid implementation submission
  completes the agile iteration directly without a summary stage.

Agile document feedback uses the same preview-before-regeneration loop. Approval of a change
preview only creates the next document version; it never approves that new version. Expert-only
combined code/test design, test repair, and test execution rules must never affect agile state.

## Adapt subagent leases to project scale and timeouts

Before initializing every iteration, let the state machine inspect `structure/` only to classify
project scale. Explicit `PROJECT_SCALE: SIMPLE|NON_SIMPLE` wins; otherwise file count, total size,
and structural-node heuristics determine the result. Never use structure content to make
requirements, architecture, or code decisions.

If structure is empty, keep the base thresholds for the first iteration. For a non-simple
project, the initializer multiplies the product/requirements, technical-design, code-plan,
test-design, and implementation thresholds by 1.5. Every work order records its exact timeout
and expiry.

When a real timeout occurs, `abandon --timed-out` updates
`HARNOVE_HOME/timeout-policy.json`, expands every stage threshold, and immediately applies the
new profile to the retry and later iterations. The first timeout adds 50%, the second adds 30%,
and the third and every later timeout add 10%. Do not mark crashes, ordinary failures, or manual
cancellations as timeouts.

## Ask how to branch for every expert-mode test repair

This section never applies to agile mode. After an expert-mode failed test submission, stop at
`awaiting_repair_branch_decision`. Tell the user the
current implementation branch and the suggested default new-branch name, then ask whether to
repair on the current branch or create a new repair branch.
Never choose on the user's behalf and never dispatch the repair child before the decision.
Relay `pending_repair_branch_decision.suggested_new_branch` exactly; do not add `v`, zero-pad the
version, or reconstruct the name. The default is normally like `tmp/order-export-2`.

- Reuse: run `repair-branch-decision --strategy reuse --responder <name>`. The repair version
  switches back to the current implementation branch and rejects a different `--branch`.
- New branch: run `repair-branch-decision --strategy new --responder <name>`; optionally add
  `--branch <exact-name>`. Dispatch then creates the new branch from the current implementation
  branch, following the 5.1.0 per-version branch behavior when no exact name is supplied.

Both choices require a fresh repair subagent. After a new branch is created, it becomes the
current implementation branch for the next test cycle and, if tests pass, the delivery branch.
If another test cycle fails, ask the same question again.

## Preview feedback impact before revising documents

Apply this loop to every reviewed document present in the selected mode: candidate PRDs and code
plans in both modes, plus technical and test designs in expert mode:

1. Treat any requested document change at a review gate as rejection of the current version unless
   the user explicitly approves it unchanged. Run `review --decision reject ...`. Stop;
   do not increment the version, create a work order, or spawn a child.
2. Read the reviewed artifact and all accumulated feedback. Explain directly to the user which
   sections would change, the core change in each, the reason, preserved boundaries, and risks.
   Archive the explanation with `change-preview --sections <list> --summary <text>`.
3. Ask whether to implement that preview or revise it. Do not treat feedback as implementation approval.
4. If the user requests changes, run `change-decision --decision revise --feedback <text>`,
   recompute the affected sections from all feedback, submit a new `change-preview`, and ask again.
5. Only after explicit approval run `change-decision --decision approve`. Harnove then creates
   the next document version and enters `awaiting_dispatch`; spawn a fresh subagent at that point.

The main Agent may author only the short change-impact preview in this loop. It must not edit
the stage artifact itself. Never dispatch while status is `awaiting_change_preview` or
`awaiting_change_confirmation`.

## Put decisions before details

Candidate PRDs and code plans in both modes, plus expert technical and test designs, begin with their required
overview and `版本核心差异`. Version v002 and later must add `版本演进摘要` immediately afterward;
never retrofit this section into an earlier artifact. Keep the overview decision-oriented: goal, scope, key decision, and
acceptance or risk focus. Put supporting analysis, tables, and detailed rules afterward. For
version 2 or later, compare with the immediately previous version and summarize core additions,
removals, changed decisions, and reasons. In `版本演进摘要`, retain one concise entry for every
version in descending order from the current version through v001. Summarize decisions instead
of copying full sections, feedback, or prior documents. Historical artifact files are immutable.

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

## Maintain post-completion project structure knowledge

Treat `HARNOVE_HOME/structure/` as project-owned post-completion abstraction. Before init, it
may be inspected only for the scale classification described above; it is never an architecture
or design input. Use Markdown by default and HTML only when necessary. During expert summary or
agile implementation, inspect the completed live repository and update structure so
it covers functional modules, code framework, and structure definitions/relationships with
file or symbol evidence. Declare `STRUCTURE_STATUS: UPDATED`. Never package or publish
structure records as Harnove core files.

## Reuse and grow experience

Require every subagent to read the iteration's `00-input/*经验复用上下文.md`, cite adopted
experience, and explain why irrelevant guidance does not apply. On successful expert summary
submission, Harnove writes an immutable experience record under `HARNOVE_HOME/improve/`.
Future iterations automatically snapshot the accumulated records. Never package, publish,
or include `iterations/`, `improve/`, `structure/`, `custom/`, or `timeout-policy.json` in
product Git evidence when iterating Harnove itself.

## Apply project custom instructions

Treat `HARNOVE_HOME/custom/` as project-owned context similar to `AGENTS.md`. Ensure `user.md`
and `self.md` always exist; avoid additional files unless they are necessary. Snapshot and read
both before beginning an iteration, and require every fresh subagent to read that snapshot.
`user.md` stores durable user constraints and preferences; `self.md` stores Harnove's reusable
lessons for this project. When the user adds a durable request during an iteration, record it
before the next child is dispatched with `customize --target user --content <text> --actor <name>`.

In the expert final summary, declare `FEEDBACK_EXPERIENCE_STATUS: CAPTURED` when user clarification,
review feedback, or custom updates exist, and distill them into concrete reusable rules. On
successful completion, Harnove appends that section to `custom/self.md`. If no feedback exists,
declare `FEEDBACK_EXPERIENCE_STATUS: NONE`; do not fabricate experience.

## Version Harnove itself

For `a.b.c`, increment only `c` for fixes or optimization without new functionality, increment
`b` and reset `c` for new functionality, and increment `a` while resetting `b.c` for an
architecture change. Validate releases with `scripts/version_policy.py`.
