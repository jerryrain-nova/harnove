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
state.json             workflow state and history
```

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

### Technical design

Include goals/non-goals, current architecture evidence, proposed design, data/API/control
flows, compatibility, security/performance/observability impact, risks, rollout/rollback,
open decisions, and a requirement-to-design matrix.

### Code-change plan

Include approved design version, change boundaries, file/module/symbol-level change list,
per-change details and reasons, requirement IDs, compatibility/migration notes, sequencing,
risks, prohibited changes, and a design-to-code matrix. Product code must remain untouched.

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

## Human review contract

Approval means the named artifact version is frozen as the downstream baseline. Rejection
requires actionable feedback and creates a new artifact version. Review records contain
reviewer, timestamp, decision, artifact hash, and feedback; they are never edited or deleted.
