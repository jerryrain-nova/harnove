# Artifact contracts

## Global rules

Every artifact must contain the iteration ID, user-confirmed iteration name, requirement name,
version, author role, status, source PRD path/hash, repository baseline, and a `需求依据`
section where applicable. Use `REQ-001` style IDs. Distinguish facts, PRD statements, live
code observations, assumptions, and open questions.

The archive layout is fixed:

```text
00-input/              Original input, PRD versions, clarifications, and requirement baseline
01-technical-design/   Technical design versions
02-code-plan/           Code-change plan versions
03-test-design/         Test design versions
04-implementation/      Implementation record and Git evidence
05-test-execution/      Executable test references and reports
06-summary/             Final record, structure abstraction evidence, and retrospective
reviews/                Immutable human review records
agent-runs/             Immutable work orders, leases, and completion evidence
state.json              Workflow state and history
```

The archive is always under `HARNOVE_HOME/iterations/`. Reusable experience lives in
`HARNOVE_HOME/improve/`; post-completion project abstraction lives in
`HARNOVE_HOME/structure/`; project-specific instructions live in `HARNOVE_HOME/custom/`.
These directories do not belong to the product source or clean Harnove distribution.

Every stage/version uses a new subagent identity and one-time run lease.

## Iteration name contract

Before `init`, the orchestrator proposes one concise, branch-safe iteration name based on the
input. The user must explicitly accept it or provide a replacement. Pass that confirmed value
through `--iteration-name`; initialization must not infer a name silently.

## Document information order and version differences

Candidate PRDs, technical designs, and code plans put overview decisions before supporting
details. Their first two content sections are respectively
`文档总览|方案总览|变更总览` and `版本核心差异`. The overview highlights the goal, scope,
key decisions, and acceptance or risk focus. For version 2 or later, `版本核心差异` explicitly
compares with the immediately previous version and records core additions, removals, changed
decisions, and reasons.

## Required content

### Candidate PRD

For either an existing PRD or natural-language input, preserve the original verbatim and
create a separate versioned candidate. Never edit the original. Include original description,
goals/background, users/scenarios, stable-ID functional requirements, non-functional
requirements, in/out scope, acceptance criteria, constraints/dependencies, open questions,
and clarification history. Record every addition or modification with source, reason, and
confirmation state.

Use `PRD_STATUS: NEEDS_CLARIFICATION` while material ambiguity remains and
`PRD_STATUS: READY` only when `待确认问题` says `无（边界已确认）`. Every clarification and
rejection is immutable and produces a new version. A ready PRD requires explicit human
approval; only the approved version/hash becomes downstream scope.

### Technical design

Start with `方案总览` and `版本核心差异`. Include goals/non-goals, current architecture
evidence, proposed design, data/API/control flows, compatibility, security/performance/
observability impact, risks, rollout/rollback, open decisions, and a requirement-to-design
matrix.

Inspect the current repository directly and add `实时代码架构依据` with file/symbol evidence.
Do not read `structure/` as an architecture source. Include `功能变更树` with
`CHANGE_TREE_STATUS: INCLUDED` and a text tree exposing the full functional scope.

Add `架构与流程图`. Use `DIAGRAM_STATUS: INCLUDED` with a useful Mermaid architecture,
sequence, state, or data-flow diagram. Otherwise use `DIAGRAM_STATUS: NOT_APPLICABLE` with a
specific reason of at least 20 characters.

### Code-change plan

Start with `变更总览` and `版本核心差异`. Include the approved design version, change
boundaries, file/module/symbol scope, per-change rules and reasons, requirement IDs,
compatibility/migration notes, sequencing, risks, prohibited changes, and design-to-code
traceability. Product code remains untouched.

Re-read relevant current repository code and add `实时代码架构依据` with file/symbol evidence;
do not read `structure/` as architecture input. Include `代码变更树` with file/module/symbol
branches and `CHANGE_TREE_STATUS: INCLUDED`. Add `改动关系图` under the same diagram contract.

Technical design and code-plan Markdown declare `PRESENTATION_FORMAT: MD` by default. Use
`HTML` only when necessary for precision and provide a same-name `.html` sidecar of at least
500 bytes. Markdown remains authoritative and retains the overview and change tree.

### Test design

Include coverage strategy and a case table with case ID, requirement IDs, planned-change IDs,
purpose, level/type, priority, preconditions, data, steps, expected result, automation target,
and edge/failure behavior. Include requirement and change coverage matrices.

### Implementation record and branch

Before the implementation child starts, Harnove creates and switches to a new branch. Use the
user's exact custom branch rule when one exists; otherwise use
`tmp/{iteration-name}-{implementation-version}`. Record the branch and previous branch in the
work order and state. Implementation must not start on the previous branch.

Include approved artifacts, baseline commit, resulting commit or working-tree diff, changed
files, requirement/change IDs per file, commands, deviations, approvals, and limitations.
Harnove captures Git evidence automatically; do not edit generated evidence.

### Test report

Include actual diff reviewed, executable test locations, environment, commands, case-by-case
results, logs/evidence, failures and diagnoses, regression scope, coverage reconciliation, and
an unambiguous `passed` or `failed` conclusion. A failure identifies the owning requirement or
change and actionable implementation feedback.

### Final summary and structure abstraction

Include background, approved decisions, actual changes, test conclusion, deploy/rollback
notes, residual risks, complete traceability, and 1-10 evidence-based scores for design,
planning, testing, implementation, execution, and workflow. Include `根因`, `经验总结`,
`下次复用规则`, and `用户反馈经验` with exactly one
`FEEDBACK_EXPERIENCE_STATUS: CAPTURED|NONE`.

During summary—not before it—inspect the completed current repository and update `structure/`
with an abstract current-project view. It must cover `功能模块`, `代码框架`, and
`结构定义和关系`, cite live file or symbol evidence, and declare `STRUCTURE_STATUS: UPDATED`
in `项目结构抽象`. Submission fails unless structure content changes relative to summary
dispatch. Requirements, technical design, and code planning must not read structure as an
architecture input.

## Experience reuse contract

At initialization, snapshot every prior `improve/*.md` record and hash into
`00-input/*经验复用上下文.md`. Each stage states which experience it adopted and why apparently
relevant guidance did not apply. Never modify historical experience files; summaries append
new immutable records.

## Structure abstraction contract

Do not snapshot or inject existing structure records into requirement, technical-design, or
code-plan work orders. Structure is project-owned output created or updated only during the
summary from the completed live repository. Exclude it from Harnove releases and product Git
evidence just like `iterations/` and `improve/`.

## Custom context contract

Initialization preserves `custom/user.md` and `custom/self.md`. Snapshot custom Markdown with
hashes before iteration work; every subagent reads the current snapshot. Record durable user
preferences in `user.md` and project-specific Harnove lessons in `self.md`. Use `customize`
before dispatching the next child. Exclude custom files from clean packages and Git evidence.

## Subagent isolation contract

The main Agent only orchestrates. An artifact is submittable only after a fresh subagent has a
matching work order, active lease, and successful completion record for the exact stage/version.
Children cannot approve gates or invoke state commands. Rejection, clarification, test failure,
crash, or abandonment requires a new child identity and run.

## Human review contract

Approval freezes the named artifact version as downstream baseline. Rejection requires
actionable feedback and creates a new version. Review records contain reviewer, timestamp,
decision, artifact hash, and feedback; they are never edited or deleted.
