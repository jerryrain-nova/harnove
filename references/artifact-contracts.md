# Artifact contracts

## Global rules

Every artifact must contain iteration ID, requirement name, version, author role, status,
source PRD path/hash, repository baseline, and a `需求依据` section. Use `REQ-001` style IDs.
Distinguish facts, PRD statements, code observations, assumptions, and open questions.

The archive layout is fixed:

```text
00-input/              Original input, PRD versions, clarifications, and requirement baseline
01-technical-design/   technical solution versions
02-code-plan/          code-change plan versions
03-test-design/        test design versions
04-implementation/     implementation record and Git evidence
05-test-execution/     executable test code references and test reports
06-summary/            final change record and retrospective
reviews/               immutable human review records
agent-runs/             immutable subagent work orders, leases, and completion evidence
state.json             workflow state and history
```

The archive is always `HARNOVE_HOME/iterations/<iteration>`. Reusable experience lives in
`HARNOVE_HOME/improve/`; project interpretation lives in `HARNOVE_HOME/structure/`. These directories do not belong to the product source or clean Harnove
distribution. Every stage/version uses a new subagent identity and one-time run lease.

## Required content

### Temporary PRD intake

For either an existing PRD or natural-language description, preserve the original input
verbatim and create a separate versioned candidate PRD. Never edit the original. Include
original description, goals/background, users/scenarios,
functional requirements with stable IDs, non-functional requirements, in-scope and
out-of-scope boundaries, acceptance criteria, constraints/dependencies, open questions, and
user clarification history. Record each addition or modification with its source, reason,
and confirmation state. Use `PRD_STATUS: NEEDS_CLARIFICATION` while material ambiguity
remains and `PRD_STATUS: READY` only when `待确认问题` explicitly says `无（边界已确认）`.
Every clarification and rejection is immutable and produces a new PRD version. A ready PRD
must receive explicit human approval; only the approved version and hash become the
authoritative downstream scope baseline.

### Project structure analysis

Read persistent structure records before scanning code. If the library is empty, declare
`STRUCTURE_SOURCE: FULL_REPOSITORY_SCAN`, inspect the whole project, and create records that
separately cover `功能模块`, `代码框架`, and `结构定义和关系`. If records exist, declare
`STRUCTURE_SOURCE: REUSED_AND_VERIFIED`, inspect demand-related code, and verify the records.
Use `STRUCTURE_STATUS: UPDATED` when records are created or corrected and cite file/symbol
evidence; otherwise use `CONSISTENT`.

### Technical design

Include goals/non-goals, current architecture evidence, proposed design, data/API/control
flows, compatibility, security/performance/observability impact, risks, rollout/rollback,
open decisions, and a requirement-to-design matrix.

Before design, compare demand-related structure records with current code. Add
`结构一致性检查` and declare `STRUCTURE_STATUS: CONSISTENT|UPDATED`; update stale records
before writing the proposal. Add `功能变更树` with `CHANGE_TREE_STATUS: INCLUDED` and a text
tree that makes the full functional scope visible at a glance.

Add `架构与流程图`. Use `DIAGRAM_STATUS: INCLUDED` with a Mermaid architecture, sequence,
state, or data-flow diagram when it improves verification. Otherwise use
`DIAGRAM_STATUS: NOT_APPLICABLE` with a specific reason of at least 20 characters.

### Code-change plan

Include approved design version, change boundaries, file/module/symbol-level change list,
per-change details and reasons, requirement IDs, compatibility/migration notes, sequencing,
risks, prohibited changes, and a design-to-code matrix. Product code must remain untouched.

Repeat the demand-related structure/code consistency check before planning. Add
`代码变更树` with file/module/symbol branches and `CHANGE_TREE_STATUS: INCLUDED`.

Add `改动关系图` under the same diagram status contract. Prefer file/module dependencies,
changed call chains, or control flow; do not add decorative diagrams.

Technical and code-plan Markdown artifacts declare `PRESENTATION_FORMAT: MD` by default.
Use `HTML` only when necessary for precision and provide a same-name `.html` sidecar of at
least 500 bytes. The Markdown file remains authoritative and retains the change tree.

### Test design

Include coverage strategy and a case table with case ID, requirement IDs, planned-change
IDs, test purpose, level/type, priority, preconditions, data, steps, expected result,
automation target, and edge/failure behavior. Include requirement and change coverage matrices.

### Implementation record

Include approved artifact versions, baseline commit, resulting commit or working-tree diff,
changed files, requirement/change IDs per file, commands, deviations, approvals, and known
limitations. Archive `git diff --stat`, `git diff`, and relevant commit IDs when Git exists.
Harnove captures these automatically on implementation submission; do not edit the
generated Git evidence files.

### Test report

Include actual diff reviewed, executable test locations, environment, commands, case-by-case
results, logs/evidence, failures and diagnoses, regression scope, coverage reconciliation,
and an unambiguous `passed` or `failed` conclusion. A failure must identify the owning
requirement/change and actionable feedback for implementation.

### Final summary

Include background, PRD scope, approved decisions, actual changes, test conclusion,
deploy/rollback notes, residual risks, complete traceability, and 1-10 evidence-based scores
for technical design, code plan, test design, implementation, test execution, and workflow.
Record highlights, defects, root causes, and concrete next-iteration improvements.
Include `根因`, `经验总结`, and `下次复用规则`. Harnove extracts these sections together with
scores, highlights, defects, and improvements into a new immutable file in `improve/`.

### Project structure refresh

After tests pass and before summary, reconcile the actual Git diff with persistent structure
records. Update every affected module/framework/relationship record, declare
`STRUCTURE_STATUS: UPDATED`, and cite changed files or symbols. Summary cannot begin until
the persistent structure hash changes and the refreshed records pass the three-part contract.

## Experience reuse contract

At initialization, snapshot every prior `improve/*.md` record and hash into
`00-input/*经验复用上下文.md`. Each stage must state which experience it adopted and why any
apparently relevant rule was not applicable. Never modify a historical experience file;
later summaries add new files so the library grows monotonically.

## Structure knowledge contract

At iteration initialization, snapshot existing `.md` and `.html` structure records and hashes
into `00-input/*项目结构上下文*.md`. Structure is project-owned and grows with the codebase.
Technical design and code planning must verify demand-relevant records against current code;
inconsistency must be corrected before design. Exclude `structure/` from Harnove self-release
packages and product Git evidence just like `iterations/` and `improve/`.

## Subagent isolation contract

The main Agent only orchestrates. A stage artifact is submittable only after a fresh subagent
has a matching work order, active lease, and successful completion record for the exact
stage/version. Children cannot approve gates or invoke state commands. Rejection,
clarification, test failure, crash, or abandonment requires a new child identity and run.

## Human review contract

Approval means the named artifact version is frozen as the downstream baseline. Rejection
requires actionable feedback and creates a new artifact version. Review records contain
reviewer, timestamp, decision, artifact hash, and feedback; they are never edited or deleted.
