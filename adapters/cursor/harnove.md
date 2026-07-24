---
description: 启动或继续一次由人工闸门控制、全程可追溯的 Harnove 研发迭代
---

# Harnove

Locate the project Harnove directory by finding its `config.json` (normally
`harnove/config.json` or `.harnove/config.json`). Read the canonical Harnove skill at
`skill/harnove/SKILL.md` under that directory and its referenced artifact contract completely,
then follow it as authoritative instructions for this request.

Remain orchestration-only. For every stage/version, use Cursor's native subagent mechanism to
create a fresh child from the Harnove work order; never author the artifact or product change
in the main Agent. If subagents are unavailable, stop and report that Harnove cannot safely
advance. Keep all iteration, experience, project-structure, and custom data under the discovered
Harnove directory. Require children to read the frozen `custom/user.md` and `custom/self.md`
context before acting. Requirements, technical design, and code planning inspect the live
repository and never read `structure/` as architecture input. Update structure abstraction
only during summary after tests pass.

Before each iteration, allow the state machine to inspect `structure/` only for project-scale
classification and adaptive lease selection. Respect each work order's `timeout_minutes` and
`expires_at`. For a real timeout, use `abandon --timed-out`; do not use that flag for crashes or
ordinary failures. The resulting project-level timeout increase applies to retries and later
iterations.

Treat any text supplied after `/harnove` as either a PRD path or a natural-language iteration
request. Before initialization, propose a concise branch-safe iteration name and require the
user to accept it or provide another. Preserve any supplied PRD as immutable, create a separate candidate PRD, and require
explicit user approval of that candidate before technical design. If no usable input is supplied, report current status when an archive is identifiable;
otherwise ask only for the iteration ID, confirmed iteration name, requirement name, and either a PRD or a requirement
description. For natural language, draft the candidate PRD and actively clarify material
ambiguities according to the canonical skill before technical design begins.

At every reviewed document gate (candidate PRD, technical design, code plan, and test design),
feedback is a proposal rather than permission to rewrite. Do not create a new version or start a
child after feedback. First combine all feedback with the current artifact, explain which sections
would change and why, and ask the user to approve implementation or add feedback. Recompute this
preview until the user explicitly approves it; only then create the next version and dispatch a
fresh child. Every reviewed document puts a concise overview and previous-version differences
before details. Version v002 and later add a summarized evolution ordered from the current
version through v001; never modify historical artifacts to retrofit that section.

In `code_plan`, classify the live-code change scope. For at most three files in one module with
no public-contract, schema, migration, or cross-boundary change, produce one
`DESIGN_MODE: COMBINED` code-and-test design artifact. Present that complete artifact for one
explicit human approval; approval freezes it for both roles and advances directly to
implementation. Otherwise keep code plan and test design separate.

After every failed test, stop and ask whether the user wants to repair on the current
implementation branch or create a new repair branch. Do not dispatch before recording the choice.
For reuse, switch back to the current branch. For new, create the requested or default per-version
branch from the current branch; it then becomes the branch for testing and delivery. Both choices
require a fresh repair child, and every later test failure repeats the question.

Never approve a human gate on the user's behalf and never invent scope beyond the PRD. For the
candidate PRD/product plan, technical design, code plan, and test design, show the complete
current artifact and wait for explicit user approval. Validation success, child completion,
silence, or your own quality judgment is not approval. After the user approves, preserve the
exact user wording with `review --decision approve --reviewer <human>
--human-confirmation <exact-user-approval-text>`; never infer or paraphrase it, and never advance
before the state machine records it.
