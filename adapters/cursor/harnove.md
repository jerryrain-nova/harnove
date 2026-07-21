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
advance. Keep all iteration, experience, and project-structure data under the discovered
Harnove directory. Require children to read `structure/` before repository-wide analysis,
verify demand-related structure against code before design, and refresh structure after tests.

Treat any text supplied after `/harnove` as either a PRD path or a natural-language iteration
request. Preserve any supplied PRD as immutable, create a separate candidate PRD, and require
explicit user approval of that candidate before technical design. If no usable input is supplied, report current status when an archive is identifiable;
otherwise ask only for the iteration ID, requirement name, and either a PRD or a requirement
description. For natural language, draft the candidate PRD and actively clarify material
ambiguities according to the canonical skill before technical design begins.

Never approve a human gate on the user's behalf and never invent scope beyond the PRD.
