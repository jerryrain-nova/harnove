#!/usr/bin/env python3
"""Deterministic, dependency-free state machine for Harnove iterations."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

STAGES = ["prd_intake", "technical_design", "code_plan", "test_design", "implementation", "test_execution", "summary"]
GATED = {"technical_design", "code_plan", "test_design"}
REVIEW_GATED = GATED | {"prd_intake"}
VERSIONED_DOCUMENT_STAGES = REVIEW_GATED
DIRS = {
    "prd_intake": "00-input",
    "technical_design": "01-technical-design",
    "code_plan": "02-code-plan",
    "test_design": "03-test-design",
    "implementation": "04-implementation",
    "test_execution": "05-test-execution",
    "summary": "06-summary",
}
CN_NAMES = {
    "prd_intake": "候选PRD",
    "technical_design": "技术方案",
    "code_plan": "代码修改方案",
    "test_design": "测试方案",
    "implementation": "代码变更记录",
    "test_execution": "测试报告",
    "summary": "迭代总结",
}
REQUIRED_SECTIONS = {
    "prd_intake": ["文档总览", "版本核心差异", "原始需求描述", "目标与背景", "用户与场景", "功能需求", "非功能需求", "范围内", "范围外", "验收标准", "约束与依赖", "信息补充记录", "待确认问题", "用户补充记录"],
    "technical_design": ["方案总览", "版本核心差异", "需求依据", "实时代码架构依据", "目标与非目标", "现状分析", "技术方案", "功能变更树", "架构与流程图", "风险", "回滚", "追溯矩阵"],
    "code_plan": ["变更总览", "版本核心差异", "需求依据", "实时代码架构依据", "改动范围", "改动细则", "代码变更树", "改动关系图", "改动原因", "禁止改动", "追溯矩阵"],
    "test_design": ["测试总览", "版本核心差异", "需求依据", "覆盖策略", "测试用例", "测试目的", "覆盖矩阵"],
    "implementation": ["需求依据", "批准基线", "实际改动", "Git 证据", "方案偏差"],
    "test_execution": ["需求依据", "实际变更审查", "可执行测试", "执行结果", "结论"],
    "summary": ["总结总览", "需求背景", "迭代内容", "测试结论", "追溯矩阵", "项目结构抽象", "用户反馈经验", "环节评分", "亮点", "缺点", "根因", "经验总结", "下次复用规则", "改进项"],
}
PLACEHOLDER = "<!-- 待填写；所有判断须引用 REQ-xxx 或代码证据。 -->"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", value.strip())
    return value.strip("-._") or "requirement"


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def project_defaults() -> tuple[str, str, str, str, str, str, str]:
    runtime_home = Path(__file__).resolve().parent.parent
    direct = runtime_home / "config.json"
    starts = [Path.cwd().resolve(), Path(__file__).resolve().parent]
    seen = set()
    candidates = [direct]
    for start in starts:
        for candidate in [start, *start.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates += [candidate / "harnove" / "config.json", candidate / ".harnove" / "config.json"]
    for config_path in candidates:
        if not config_path.is_file() or config_path.parent.name not in {"harnove", ".harnove"}:
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        home = config_path.parent.resolve()
        project = (home / config.get("project_root", "..")).resolve()
        repo = (project / config.get("repo_root", ".")).resolve()
        archive = (home / config.get("archive_root", "iterations")).resolve()
        improve = (home / config.get("improve_root", "improve")).resolve()
        structure = (home / config.get("structure_root", "structure")).resolve()
        custom = (home / config.get("custom_root", "custom")).resolve()
        if not all(inside(path, home) for path in [archive, improve, structure, custom]):
            raise SystemExit("config.json 中的 archive_root、improve_root、structure_root 和 custom_root 必须位于 Harnove 目录内")
        branch_pattern = config.get("default_branch_pattern", "tmp/{iteration_name}-{implementation_version}")
        return str(repo), str(archive), str(improve), str(structure), str(custom), str(home), branch_pattern
    fallback_home = Path.cwd().resolve()
    return ".", str(fallback_home / "iterations"), str(fallback_home / "improve"), str(fallback_home / "structure"), str(fallback_home / "custom"), str(fallback_home), "tmp/{iteration_name}-{implementation_version}"


def load(archive: Path) -> dict:
    path = archive / "state.json"
    if not path.is_file():
        raise SystemExit(f"找不到状态文件: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version", 1) < 10:
        _, _, discovered_improve, discovered_structure, discovered_custom, discovered_home, discovered_branch_pattern = project_defaults()
        inferred_home = archive.parent.parent.resolve()
        migration_home = Path(discovered_home) if inside(archive, Path(discovered_home)) else inferred_home
        migration_improve = Path(discovered_improve) if inside(Path(discovered_improve), migration_home) else migration_home / "improve"
        migration_structure = Path(discovered_structure) if inside(Path(discovered_structure), migration_home) else migration_home / "structure"
        migration_custom = Path(discovered_custom) if inside(Path(discovered_custom), migration_home) else migration_home / "custom"
        state.setdefault("harnove_home", str(migration_home))
        state.setdefault("improve_root", str(migration_improve))
        state.setdefault("structure_root", str(migration_structure))
        state.setdefault("custom_root", str(migration_custom))
        state.setdefault("used_agent_ids", [])
        state.setdefault("iteration_name", state.get("requirement", "iteration"))
        state.setdefault("default_branch_pattern", discovered_branch_pattern)
        old_schema = state.get("schema_version", 1)
        prior_branches = state.get("implementation_branches", [])
        if prior_branches:
            first_branch, latest_branch = prior_branches[0], prior_branches[-1]
            state.setdefault("initial_implementation_branch", {
                "name": first_branch["name"], "previous_branch": first_branch.get("previous_branch"),
                "prepared_at": first_branch.get("prepared_at"), "source": first_branch.get("source", "migrated"),
                "initial_stage_version": first_branch.get("stage_version", 1),
            })
            if not state.get("implementation_branch"):
                state["implementation_branch"] = {
                    "name": latest_branch["name"], "previous_branch": latest_branch.get("previous_branch"),
                    "prepared_at": latest_branch.get("prepared_at"), "source": latest_branch.get("source", "migrated"),
                    "initial_stage_version": latest_branch.get("stage_version", 1),
                }
        elif state.get("implementation_branch"):
            state.setdefault("initial_implementation_branch", state["implementation_branch"])
        state.setdefault("repair_branch_decisions", [])
        if state.get("stage") in {"structure_analysis", "structure_refresh"}:
            if state.get("status") == "subagent_working":
                raise SystemExit("旧迭代正停留在已移除的 structure 阶段；请用原版本结束该子 Agent 后再升级")
            state["stage"] = "technical_design" if state["stage"] == "structure_analysis" else "summary"
            state["version"] = state.get("stage_versions", {}).get(state["stage"], 0) + 1
            state.setdefault("stage_versions", {})[state["stage"]] = state["version"]
            state["status"] = "awaiting_dispatch"
        state.setdefault("history", []).append({"at": now(), "action": "schema_migration", "from": old_schema, "to": 10})
        if state.get("status") == "drafting":
            state["status"] = "awaiting_dispatch"
        state["schema_version"] = 10
        if not state.get("improvement_index") and (archive / "00-input").is_dir():
            state["improvement_index"] = create_improvement_context(archive, state)
        if not state.get("custom_index") and (archive / "00-input").is_dir():
            state["custom_index"] = create_custom_context(archive, state)
        save(archive, state)
    return state


def save(archive: Path, state: dict) -> None:
    tmp = archive / "state.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(archive / "state.json")


def git(repo: Path, *args: str) -> str | None:
    try:
        p = subprocess.run(["git", "-C", str(repo), *args], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def capture_git_evidence(archive: Path, state: dict) -> list[str]:
    folder, version = archive / DIRS["implementation"], state["version"]
    repo = Path(state["repo"]).resolve()
    scope = ["--", "."]
    for excluded in [Path(state["archive"]).parent, Path(state["improve_root"]), Path(state["structure_root"]), Path(state["custom_root"])]:
        if inside(excluded, repo):
            scope.append(f":(exclude){excluded.resolve().relative_to(repo).as_posix()}/**")
    commands = {
        f"git-head-v{version:03d}.txt": ("rev-parse", "HEAD"),
        f"git-status-v{version:03d}.txt": ("status", "--short", *scope),
        f"git-diff-stat-v{version:03d}.txt": ("diff", "--stat", *scope),
        f"git-diff-v{version:03d}.patch": ("diff", "--binary", *scope),
    }
    written, unavailable = [], False
    for name, args in commands.items():
        value = git(repo, *args)
        if value is None:
            unavailable = True
            continue
        target = folder / name
        target.write_text(value + ("\n" if value else ""), encoding="utf-8")
        written.append(str(target.relative_to(archive)))
    if unavailable:
        target = folder / f"git-unavailable-v{version:03d}.txt"
        target.write_text(f"captured_at={now()}\nrepo={state['repo']}\nreason=Git command unavailable or repository invalid\n", encoding="utf-8")
        written.append(str(target.relative_to(archive)))
    return written


def artifact_name(state: dict, stage: str, version: int) -> str:
    return f"{state['iteration_id']}_{state['requirement']}_{CN_NAMES[stage]}_v{version:03d}.md"


def artifact_path(archive: Path, state: dict) -> Path:
    return archive / DIRS[state["stage"]] / artifact_name(state, state["stage"], state["version"])


def prd_template(state: dict, source_summary: str, version: int) -> str:
    return f"""# {state['iteration_id']} {state['requirement']} - 候选 PRD

- 文档版本：v{version:03d}
- 迭代名称：{state['iteration_name']}
- 输入类型：{state['prd_source_type']}
- 原始输入：`{state['original_input_snapshot']}`
- 原始输入 SHA-256：`{state['original_input_sha256']}`
- 状态标记：`PRD_STATUS: NEEDS_CLARIFICATION`
- 规则：原始文件只读；所有补充必须记录依据；不得把推测写成已确认需求。

## 文档总览

- 需求目标：待从原始输入提炼。
- 核心范围：待明确。
- 关键验收：待明确。
- 当前决策：仍需完成需求整理与边界确认。

## 版本核心差异

首版候选 PRD，无上一版本；后续版本必须概括相对上一版新增、修改和删除的核心内容。

## 原始需求描述

{source_summary.strip()}

## 目标与背景

<!-- 根据原始描述提炼，并区分事实与假设。 -->

## 用户与场景

<!-- 描述目标用户、触发条件和主要场景。 -->

## 功能需求

| ID | 需求 | 依据 | 状态 |
| --- | --- | --- | --- |
| REQ-001 | 待从原始描述提炼 | 原始需求描述 | 待确认 |

## 非功能需求

<!-- 未提供时明确写“未提出”，不得自行添加指标。 -->

## 范围内

<!-- 仅列用户明确表达或已确认的范围。 -->

## 范围外

<!-- 明确不在本次迭代处理的内容。 -->

## 验收标准

<!-- 为每个 REQ-xxx 给出可验证的验收条件。 -->

## 约束与依赖

<!-- 记录技术、业务、兼容性、时间或外部依赖。 -->

## 信息补充记录

| 补充项 | 补充内容 | 依据 | 补充原因 | 确认状态 |
| --- | --- | --- | --- | --- |
| 待整理 | 待整理 | 原始输入/用户确认/代码事实 | 待说明 | 待确认 |

## 待确认问题

1. 请根据真实歧义列出最少且能决定边界的问题；若无问题，写“无（边界已确认）”。

## 用户补充记录

暂无。
"""


def template(state: dict, stage: str, version: int) -> str:
    lines = [
        f"# {state['iteration_id']} {state['requirement']} - {CN_NAMES[stage]}", "",
        f"- 迭代编号：{state['iteration_id']}", f"- 迭代名称：{state['iteration_name']}", f"- 需求名称：{state['requirement']}",
        f"- 文档版本：v{version:03d}", f"- 角色：{CN_NAMES[stage]}", "- 状态：草稿",
        f"- PRD 快照：`00-input/{state['prd_snapshot']}`", f"- PRD SHA-256：`{state['prd_sha256']}`",
        f"- 经验复用索引：`00-input/{state['improvement_index']}`",
        f"- 项目自定义上下文：`00-input/{state['custom_index']}`",
        f"- 仓库基线：`{state.get('git_baseline') or 'GIT_UNAVAILABLE'}`", "",
    ]
    if stage in {"technical_design", "code_plan"}:
        lines += ["- 表达格式：`PRESENTATION_FORMAT: MD`", ""]
    for section in REQUIRED_SECTIONS[stage]:
        initial = PLACEHOLDER
        if section == "版本核心差异" and version == 1:
            initial = "首版文档，无上一版本；本节用于后续版本概括核心变化。"
        lines += [f"## {section}", "", initial, ""]
        if section in {"功能变更树", "代码变更树"}:
            lines += ["CHANGE_TREE_STATUS: INCLUDED", "", "```text", "需求/方案根节点", "├── 待细化变更一", "└── 待细化变更二", "```", ""]
        if section in {"架构与流程图", "改动关系图"}:
            lines += ["DIAGRAM_STATUS: INCLUDED", "", "```mermaid", "flowchart LR", "  A[待细化输入] --> B[待细化处理]", "  B --> C[待细化输出]", "```", ""]
        if section == "用户反馈经验":
            status = "CAPTURED" if user_feedback_items(state) else "NONE"
            lines += [f"FEEDBACK_EXPERIENCE_STATUS: {status}", ""]
        if section == "项目结构抽象":
            lines += ["STRUCTURE_STATUS: UPDATED", "", "总结阶段必须依据完成后的实时代码更新 structure/，覆盖功能模块、代码框架、结构定义和关系，并引用代码证据。", ""]
    return "\n".join(lines)


def validate_artifact(path: Path, stage: str, state: dict | None = None, last_run: dict | None = None) -> list[str]:
    if not path.is_file():
        return [f"缺少产物: {path}"]
    text = path.read_text(encoding="utf-8")
    errors = [f"缺少章节: {s}" for s in REQUIRED_SECTIONS[stage] if f"## {s}" not in text]
    positions = [text.find(f"## {section}") for section in REQUIRED_SECTIONS[stage]]
    if all(position >= 0 for position in positions) and positions != sorted(positions):
        errors.append("文档章节顺序不符合契约；总览和版本差异必须位于细则之前")
    if "REQ-" not in text:
        errors.append("未引用任何稳定需求 ID（REQ-xxx）")
    if state is not None and state.get("iteration_name") not in text:
        errors.append("产物缺少用户确认的迭代名称")
    if "<!--" in text:
        errors.append("仍存在未填写的模板占位符")
    if len(text.strip()) < 500:
        errors.append("产物内容过短，无法形成可审核证据")
    if stage in VERSIONED_DOCUMENT_STAGES:
        overview = {"prd_intake": "文档总览", "technical_design": "方案总览", "code_plan": "变更总览", "test_design": "测试总览"}[stage]
        if len(section_text(text, overview)) < 60:
            errors.append(f"{overview}过短，必须在文档开头集中说明目标、范围、关键决策和风险/验收重点")
        differences = section_text(text, "版本核心差异")
        version = (state or {}).get("version", 1)
        if version > 1 and (len(differences) < 40 or "上一版" not in differences or "首版" in differences):
            errors.append("迭代版本必须在“版本核心差异”中明确概括相对上一版的核心变化")
        if version > 1:
            overview_position = text.find(f"## {overview}")
            difference_position = text.find("## 版本核心差异")
            evolution_position = text.find("## 版本演进摘要")
            detail_position = min(
                position for heading in REQUIRED_SECTIONS[stage][2:]
                if (position := text.find(f"## {heading}")) >= 0
            )
            if evolution_position < 0:
                errors.append("新版本必须新增“版本演进摘要”，历史版本文件不得回写")
            elif not overview_position < difference_position < evolution_position < detail_position:
                errors.append("新版本的版本演进摘要必须位于总览、版本核心差异之后和细则之前")
            evolution = section_text(text, "版本演进摘要")
            entry_matches = list(re.finditer(r"^\s*[-*]\s*v(\d{3})[：:]\s*(.+?)\s*$", evolution, re.MULTILINE))
            entry_versions = [int(match.group(1)) for match in entry_matches]
            expected_versions = list(range(version, 0, -1))
            if entry_versions != expected_versions:
                errors.append(
                    "版本演进摘要必须按当前版本到初代版本完整倒序展示: "
                    + ", ".join(f"v{value:03d}" for value in expected_versions)
                )
            for match in entry_matches:
                entry_version, summary = int(match.group(1)), match.group(2).strip()
                if entry_version <= version and not 12 <= len(summary) <= 180:
                    errors.append(f"v{entry_version:03d} 的演进摘要必须归纳为 12-180 字，不能粘贴全量文档")
        if stage in {"technical_design", "code_plan"} and len(section_text(text, "实时代码架构依据")) < 60:
            errors.append("实时代码架构依据过短，必须记录本轮直接检查的文件、符号和架构结论")
    if stage in {"technical_design", "code_plan"}:
        md_format = "PRESENTATION_FORMAT: MD" in text
        html_format = "PRESENTATION_FORMAT: HTML" in text
        if md_format == html_format:
            errors.append("表达格式必须且只能声明 PRESENTATION_FORMAT: MD 或 HTML")
        elif html_format:
            html = path.with_suffix(".html")
            if not html.is_file() or "<html" not in html.read_text(encoding="utf-8", errors="replace").lower() or html.stat().st_size < 500:
                errors.append("HTML 表达模式必须提供同名、完整且不少于 500 字节的 HTML 文件")
        tree_section = "功能变更树" if stage == "technical_design" else "代码变更树"
        tree = section_text(text, tree_section)
        if "CHANGE_TREE_STATUS: INCLUDED" not in tree or len(re.findall(r"[├└]──", tree)) < 2:
            errors.append(f"{tree_section}必须包含至少两个清晰的树状变更节点")
        if "待细化" in tree:
            errors.append(f"{tree_section}仍包含待细化占位内容")
        included = "DIAGRAM_STATUS: INCLUDED" in text
        not_applicable = "DIAGRAM_STATUS: NOT_APPLICABLE" in text
        if included == not_applicable:
            errors.append("图示必须且只能声明 DIAGRAM_STATUS: INCLUDED 或 NOT_APPLICABLE")
        elif included:
            diagrams = re.findall(r"```mermaid\s*\n([\s\S]*?)```", text)
            allowed = ("flowchart", "graph", "sequenceDiagram", "stateDiagram", "classDiagram", "erDiagram")
            if not diagrams or not any(d.strip().startswith(allowed) for d in diagrams):
                errors.append("INCLUDED 图示必须包含非空且类型受支持的 Mermaid 代码块")
            if any("待细化" in d for d in diagrams):
                errors.append("Mermaid 图仍包含待细化占位内容")
        else:
            reason = re.search(r"DIAGRAM_STATUS: NOT_APPLICABLE[\s\S]*?理由[:：]\s*([^\n]+)", text)
            if not reason or len(reason.group(1).strip()) < 20:
                errors.append("NOT_APPLICABLE 必须给出至少 20 字的具体理由")
    if stage == "summary" and state is not None:
        current = structure_hashes(Path(state["structure_root"]))
        before = (last_run or {}).get("structure_before", {})
        structure_section = section_text(text, "项目结构抽象")
        if "STRUCTURE_STATUS: UPDATED" not in structure_section:
            errors.append("总结阶段必须声明 STRUCTURE_STATUS: UPDATED")
        if not current or current == before:
            errors.append("总结阶段必须依据完成后的实时代码更新 structure 文件")
        else:
            combined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in structure_files(Path(state["structure_root"])))
            for required in ["功能模块", "代码框架", "结构定义和关系"]:
                if required not in combined:
                    errors.append(f"structure 抽象缺少必需部分: {required}")
    if stage == "summary" and state is not None:
        feedback = user_feedback_items(state)
        section = section_text(text, "用户反馈经验")
        captured = "FEEDBACK_EXPERIENCE_STATUS: CAPTURED" in section
        none = "FEEDBACK_EXPERIENCE_STATUS: NONE" in section
        if captured == none:
            errors.append("用户反馈经验必须且只能声明 FEEDBACK_EXPERIENCE_STATUS: CAPTURED 或 NONE")
        elif feedback and not captured:
            errors.append("本次存在用户反馈，必须总结经验并声明 FEEDBACK_EXPERIENCE_STATUS: CAPTURED")
        elif captured:
            distilled = section.replace("FEEDBACK_EXPERIENCE_STATUS: CAPTURED", "").strip()
            if len(distilled) < 40:
                errors.append("用户反馈经验过短，必须提炼具体、可复用的执行规则")
        elif not feedback and not none:
            errors.append("本次无用户反馈时必须声明 FEEDBACK_EXPERIENCE_STATUS: NONE")
    return errors


def validate_original_input(archive: Path, state: dict) -> None:
    path = archive / "00-input" / state["original_input_snapshot"]
    if not path.is_file() or digest(path) != state["original_input_sha256"]:
        raise SystemExit("原始输入副本缺失或已被修改；为保护追溯性，PRD 流程已停止")


def create_requirement_baseline(archive: Path, state: dict) -> None:
    target = archive / "00-input" / f"{state['iteration_id']}_{state['requirement']}_需求基线.md"
    if target.exists():
        return
    target.write_text(
        f"# {state['iteration_id']} {state['requirement']} - 需求基线\n\n- PRD：`{state['prd_snapshot']}`\n- SHA-256：`{state['prd_sha256']}`\n\n"
        "## 需求清单\n\n| ID | PRD 原文位置 | 需求原意摘要 | 验收标准 | 状态 |\n| --- | --- | --- | --- | --- |\n"
        "| REQ-001 | 待定位 | 待按原意摘录 | 待明确 | 待确认 |\n\n不得增加 PRD 未表达的业务范围；歧义进入待确认项。\n",
        encoding="utf-8",
    )


def advance(state: dict) -> None:
    state["stage"] = STAGES[STAGES.index(state["stage"]) + 1]
    state["version"] = state["stage_versions"].get(state["stage"], 0) + 1
    state["stage_versions"][state["stage"]] = state["version"]
    state["status"] = "awaiting_dispatch"


def create_improvement_context(archive: Path, state: dict) -> str:
    improve_root = Path(state["improve_root"])
    improve_root.mkdir(parents=True, exist_ok=True)
    name = f"{state['iteration_id']}_{state['requirement']}_经验复用上下文.md"
    target = archive / "00-input" / name
    files = sorted(improve_root.glob("*.md"))
    lines = [f"# {state['iteration_id']} {state['requirement']} - 历史经验复用上下文", "", "生成时快照，供本次所有子 Agent 读取；不得反向修改历史经验。", ""]
    if not files:
        lines += ["## 当前经验", "", "暂无历史经验。", ""]
    for item in files:
        lines += [f"## {item.name}", "", f"- SHA-256：`{digest(item)}`", "", item.read_text(encoding="utf-8"), ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return name


def structure_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.name != ".gitkeep" and p.suffix.lower() in {".md", ".html"})


def structure_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): digest(p) for p in structure_files(root)}


CUSTOM_DEFAULTS = {
    "user.md": "# 用户个性化诉求\n\n暂无。用户对本项目的长期约束、偏好和额外诉求记录在此。\n",
    "self.md": "# Harnove 项目经验\n\n暂无。Harnove 将在需求完成后追加从用户反馈中提炼的可复用经验。\n",
}


def ensure_custom_files(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, content in CUSTOM_DEFAULTS.items():
        target = root / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")


def create_custom_context(archive: Path, state: dict, label: str = "initial") -> str:
    root = Path(state["custom_root"])
    ensure_custom_files(root)
    name = f"{state['iteration_id']}_{state['requirement']}_项目自定义上下文_{safe_name(label)}.md"
    target = archive / "00-input" / name
    lines = [
        f"# {state['iteration_id']} {state['requirement']} - 项目自定义上下文", "",
        "本快照必须在执行当前需求迭代前读取；user.md 优先表达用户约束，self.md 提供历史经验。", "",
    ]
    for item in sorted(root.glob("*.md")):
        lines += [f"## {item.name}", "", f"- SHA-256：`{digest(item)}`", "", item.read_text(encoding="utf-8", errors="replace"), ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return name


def user_feedback_items(state: dict) -> list[str]:
    items = []
    for event in state.get("history", []):
        if event.get("action") == "user_clarification" and event.get("response"):
            items.append(event["response"].strip())
        elif event.get("action") == "human_review" and event.get("feedback"):
            items.append(event["feedback"].strip())
        elif event.get("action") == "document_change_decision" and event.get("feedback"):
            items.append(event["feedback"].strip())
        elif event.get("action") == "custom_update" and event.get("content"):
            items.append(event["content"].strip())
    return items


def write_custom_experience(archive: Path, state: dict, summary: Path) -> Path | None:
    if not user_feedback_items(state):
        return None
    root = Path(state["custom_root"])
    ensure_custom_files(root)
    target = root / "self.md"
    experience = section_text(summary.read_text(encoding="utf-8"), "用户反馈经验")
    block = [
        "", f"## {dt.date.today():%Y-%m-%d} {state['iteration_id']} {state['requirement']}", "",
        f"- 来源归档：`{archive}`", f"- 来源总结 SHA-256：`{digest(summary)}`", "",
        experience, "",
    ]
    with target.open("a", encoding="utf-8") as stream:
        stream.write("\n".join(block))
    return target


def write_improvement(archive: Path, state: dict, summary: Path) -> Path:
    improve_root = Path(state["improve_root"])
    improve_root.mkdir(parents=True, exist_ok=True)
    text = summary.read_text(encoding="utf-8")
    base = f"{dt.date.today():%Y%m%d}_{state['iteration_id']}_{state['requirement']}_经验总结_v{state['version']:03d}.md"
    target = improve_root / base
    if target.exists():
        target = improve_root / f"{target.stem}_{dt.datetime.now():%H%M%S%f}.md"
    lines = [
        f"# {state['iteration_id']} {state['requirement']} - 可复用经验", "",
        f"- 来源归档：`{archive}`", f"- 来源总结：`{summary.relative_to(archive)}`",
        f"- 来源 SHA-256：`{digest(summary)}`", f"- 沉淀时间：{now()}", "",
    ]
    for heading in ["环节评分", "亮点", "缺点", "根因", "经验总结", "下次复用规则", "改进项"]:
        lines += [f"## {heading}", "", section_text(text, heading) or "未记录。", ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def cmd_init(a: argparse.Namespace) -> None:
    root, repo = Path(a.root).resolve(), Path(a.repo).resolve()
    home = Path(getattr(a, "home", root.parent)).resolve()
    improve_root = Path(getattr(a, "improve_root", home / "improve")).resolve()
    structure_root = Path(getattr(a, "structure_root", home / "structure")).resolve()
    custom_root = Path(getattr(a, "custom_root", home / "custom")).resolve()
    if not all(inside(path, home) for path in [root, improve_root, structure_root, custom_root]):
        raise SystemExit("迭代归档、improve、structure 和 custom 必须位于 Harnove 自身目录内")
    prd_arg = getattr(a, "prd", None)
    description = getattr(a, "description", None)
    description_file = getattr(a, "description_file", None)
    supplied = sum(bool(x) for x in [prd_arg, description, description_file])
    if supplied != 1:
        raise SystemExit("必须且只能提供 --prd、--description 或 --description-file 之一")
    if description_file:
        source = Path(description_file).resolve()
        if not source.is_file():
            raise SystemExit(f"自然语言描述文件不存在: {source}")
        description = source.read_text(encoding="utf-8")
    if description is not None and not description.strip():
        raise SystemExit("自然语言描述不能为空")

    ident, iteration_name, req = safe_name(a.iteration_id), safe_name(a.iteration_name), safe_name(a.requirement)
    archive = root / f"{dt.date.today():%Y%m%d}_{ident}_{iteration_name}"
    if archive.exists():
        raise SystemExit(f"归档目录已存在: {archive}")
    for folder in sorted(set(DIRS.values())) + ["reviews", "00-input/clarifications", "agent-runs"]:
        (archive / folder).mkdir(parents=True, exist_ok=True)
    baseline = git(repo, "rev-parse", "HEAD")
    state = {
        "schema_version": 10, "iteration_id": ident, "iteration_name": iteration_name, "requirement": req,
        "default_branch_pattern": getattr(a, "branch_pattern", "tmp/{iteration_name}-{implementation_version}"),
        "archive": str(archive), "repo": str(repo), "harnove_home": str(home),
        "improve_root": str(improve_root), "structure_root": str(structure_root), "custom_root": str(custom_root), "git_baseline": baseline,
        "created_at": now(), "history": [], "approved": {}, "test_cycles": 0,
        "stage_versions": {stage: 0 for stage in STAGES}, "used_agent_ids": [],
        "implementation_branch": None, "initial_implementation_branch": None, "repair_branch_decisions": [],
    }
    structure_root.mkdir(parents=True, exist_ok=True)
    state["improvement_index"] = create_improvement_context(archive, state)
    state["custom_index"] = create_custom_context(archive, state)

    if prd_arg:
        prd = Path(prd_arg).resolve()
        if not prd.is_file():
            raise SystemExit(f"PRD 不存在: {prd}")
        original = f"{ident}_{req}_原始PRD{prd.suffix or '.md'}"
        original_path = archive / "00-input" / original
        shutil.copy2(prd, original_path)
        state.update({
            "prd_source_type": "existing_prd", "prd_source": str(prd),
            "original_input_snapshot": original, "original_input_sha256": digest(original_path),
            "prd_snapshot": None, "prd_sha256": None, "stage": "prd_intake",
            "version": 1, "status": "awaiting_dispatch",
        })
        state["stage_versions"]["prd_intake"] = 1
        target = artifact_path(archive, state)
        target.write_text(prd_template(
            state,
            f"原始 PRD 已只读归档为 `{original}`。请忠实整理其内容，并仅在有明确依据时补充必要信息。",
            1,
        ), encoding="utf-8")
    else:
        source_name = f"{ident}_{req}_自然语言原始输入.txt"
        source_path = archive / "00-input" / source_name
        source_path.write_text(description.strip() + "\n", encoding="utf-8")
        state.update({
            "prd_source_type": "natural_language", "prd_source": source_name,
            "original_input_snapshot": source_name, "original_input_sha256": digest(source_path), "prd_snapshot": None,
            "prd_sha256": None, "stage": "prd_intake", "version": 1, "status": "awaiting_dispatch",
        })
        state["stage_versions"]["prd_intake"] = 1
        target = artifact_path(archive, state)
        target.write_text(prd_template(state, description, 1), encoding="utf-8")
    save(archive, state)
    print(archive)
    print(f"待处理产物: {target}")
    print("下一步: 主 Agent 创建全新子 Agent，并执行 dispatch 绑定该子 Agent。")


def cmd_dispatch(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    if state["status"] != "awaiting_dispatch":
        raise SystemExit(f"当前状态 {state['status']} 不允许派发子 Agent")
    if a.agent_id in state.get("used_agent_ids", []):
        raise SystemExit("agent-id 已在本次迭代使用；每个环节/版本必须使用全新的子 Agent")
    lease = archive / "agent-runs" / "active.lease"
    if lease.exists():
        raise SystemExit("已有子 Agent 租约，拒绝并发派发")
    run_id = uuid.uuid4().hex
    stage, version = state["stage"], state["version"]
    branch_record = None
    created_new_branch = False
    if stage == "implementation":
        repo = Path(state["repo"]).resolve()
        branch_pattern = state.get("default_branch_pattern", "tmp/{iteration_name}-{implementation_version}")
        placeholders = re.findall(r"{([^{}]+)}", branch_pattern)
        stripped_pattern = re.sub(r"{(?:iteration_name|implementation_version)}", "", branch_pattern)
        if set(placeholders) != {"iteration_name", "implementation_version"} or "{" in stripped_pattern or "}" in stripped_pattern:
            raise SystemExit("default_branch_pattern 必须且只能包含 {iteration_name} 和 {implementation_version}")
        try:
            default_branch = branch_pattern.format(
                iteration_name=safe_name(state["iteration_name"]), implementation_version=version,
            )
        except (KeyError, ValueError) as exc:
            raise SystemExit("default_branch_pattern 只能使用 {iteration_name} 和 {implementation_version}") from exc
        prior_preparation = next(
            (item for item in reversed(state.get("implementation_branches", [])) if item.get("stage_version") == version),
            None,
        )
        active_branch = state.get("implementation_branch")
        supplied_branch = getattr(a, "branch", None)
        repair_mode = state.get("repair_branch_mode") if state.get("repair_branch_version") == version else None
        requested_branch = state.get("repair_branch_requested") if repair_mode == "new" else None
        if prior_preparation:
            branch = prior_preparation["name"]
            if supplied_branch and supplied_branch != branch:
                raise SystemExit(f"实施版本 v{version:03d} 已准备分支 {branch}，重派不得改用 {supplied_branch}")
            create_branch = False
        elif active_branch and repair_mode == "new":
            if requested_branch and supplied_branch and supplied_branch != requested_branch:
                raise SystemExit(f"用户已指定新修复分支 {requested_branch}，不得改用 {supplied_branch}")
            branch = requested_branch or supplied_branch or default_branch
            create_branch = True
        elif active_branch:
            branch = active_branch["name"]
            if supplied_branch and supplied_branch != branch:
                raise SystemExit(f"用户已选择复用原有分支 {branch}，不得改用 {supplied_branch}")
            create_branch = False
        else:
            branch = supplied_branch or default_branch
            create_branch = True
        check = subprocess.run(["git", "check-ref-format", "--branch", branch], text=True, capture_output=True)
        if check.returncode != 0:
            raise SystemExit(f"无效的实施分支名称: {branch}")
        previous = git(repo, "branch", "--show-current")
        if previous is None:
            raise SystemExit("代码实施要求可用的 Git 仓库，无法识别当前分支")
        if create_branch and active_branch and previous != active_branch["name"]:
            restore = subprocess.run(
                ["git", "-C", str(repo), "switch", active_branch["name"]], text=True,
                encoding="utf-8", errors="replace", capture_output=True, timeout=30,
            )
            if restore.returncode != 0:
                raise SystemExit(
                    f"新修复分支必须从当前实现分支 {active_branch['name']} 创建: "
                    f"{restore.stderr.strip() or restore.stdout.strip()}"
                )
            previous = active_branch["name"]
        switch_args = ["switch", "-c", branch] if create_branch else ["switch", branch]
        switch = subprocess.run(
            ["git", "-C", str(repo), *switch_args], text=True, encoding="utf-8",
            errors="replace", capture_output=True, timeout=30,
        )
        if switch.returncode != 0:
            raise SystemExit(f"创建并切换实施分支失败: {switch.stderr.strip() or switch.stdout.strip()}")
        if prior_preparation:
            branch_record = {**prior_preparation, "reused_for_redispatch": True}
        elif active_branch and not create_branch:
            branch_record = {
                **active_branch, "stage_version": version, "repair_strategy": "reuse",
                "reused_for_test_fix": True, "reused_for_redispatch": False,
            }
        else:
            created_new_branch = True
            branch_record = {
                "name": branch, "previous_branch": previous, "prepared_at": now(),
                "source": (
                    "repair_user" if active_branch and (requested_branch or supplied_branch)
                    else "repair_default" if active_branch else "user_or_custom" if supplied_branch else "default"
                ),
                "initial_stage_version": version, "stage_version": version,
                "repair_strategy": "new" if active_branch else "initial",
            }
    elif stage == "test_execution":
        repo = Path(state["repo"]).resolve()
        canonical_branch = state.get("implementation_branch")
        if not canonical_branch:
            raise SystemExit("测试执行缺少本次迭代绑定的代码实现分支")
        supplied_branch = getattr(a, "branch", None)
        if supplied_branch and supplied_branch != canonical_branch["name"]:
            raise SystemExit(f"测试执行已绑定代码实现分支 {canonical_branch['name']}，不得改用 {supplied_branch}")
        current_branch = git(repo, "branch", "--show-current")
        if current_branch != canonical_branch["name"]:
            switch = subprocess.run(
                ["git", "-C", str(repo), "switch", canonical_branch["name"]], text=True,
                encoding="utf-8", errors="replace", capture_output=True, timeout=30,
            )
            if switch.returncode != 0:
                raise SystemExit(
                    f"测试执行必须回到代码实现分支 {canonical_branch['name']}: "
                    f"{switch.stderr.strip() or switch.stdout.strip()}"
                )
        branch_record = {**canonical_branch, "test_execution_version": version}
    work_order = {
        "run_id": run_id, "agent_id": a.agent_id, "orchestrator": a.orchestrator,
        "stage": stage, "version": version, "created_at": now(),
        "artifact": str(artifact_path(archive, state)), "repo": state["repo"],
        "prd_snapshot": state.get("prd_snapshot") or state.get("original_input_snapshot"),
        "improvement_context": str(archive / "00-input" / state["improvement_index"]),
        "structure_root": state["structure_root"],
        "structure_before": structure_hashes(Path(state["structure_root"])) if stage == "summary" else {},
        "custom_context": str(archive / "00-input" / state["custom_index"]),
        "custom_root": state["custom_root"],
        "approved_inputs": state.get("approved", {}),
        "revision_context": state.get("approved_change_preview") if stage in VERSIONED_DOCUMENT_STAGES else None,
        "delivery_branch": branch_record or state.get("delivery_branch") or state.get("implementation_branch"),
        "repair_branch_decision": next(
            (item for item in reversed(state.get("repair_branch_decisions", [])) if item.get("implementation_version") == version),
            None,
        ),
        "write_scope": (
            "approved_repo_scope_and_artifact" if stage in {"implementation", "test_execution"}
            else "structure_and_artifact" if stage == "summary"
            else "artifact_only"
        ),
        "rules": [
            "只执行当前 stage/version，不执行状态机命令或人工审批",
            "读取经验复用上下文并记录采用或不适用的经验",
            "开始当前环节前读取项目自定义上下文，遵守 user.md 约束并复用 self.md 经验",
            "需求、技术和代码方案不得把 structure 作为架构输入；必须直接检查当前仓库代码",
            "技术方案和代码方案必须引用本次实时读取的文件或符号证据",
            "文档 v002 及以后新增版本演进摘要，按当前版本到 v001 倒序精简记录轨迹；不得回写任何历史版本文件",
            "测试修复必须遵守用户归档的分支决策：reuse 复用当前实现分支，new 从当前实现分支创建并切换新分支",
            "summary 环节依据完成后的当前代码更新 structure 抽象，覆盖功能模块、代码框架、结构定义和关系",
            "summary 环节必须根据澄清、审核反馈和 custom 更新提炼用户反馈经验",
            "不得执行其他环节的工作，不得复用本次子 Agent 身份",
        ],
    }
    if branch_record:
        work_order["implementation_branch"] = branch_record
    runs = archive / "agent-runs"
    order_path = runs / f"{stage}_v{version:03d}_{run_id}_work-order.json"
    order_path.write_text(json.dumps(work_order, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        with lease.open("x", encoding="utf-8") as f:
            json.dump(work_order, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except FileExistsError as exc:
        order_path.unlink(missing_ok=True)
        raise SystemExit("已有子 Agent 租约，拒绝并发派发") from exc
    state["active_agent"] = {"run_id": run_id, "agent_id": a.agent_id, "work_order": str(order_path.relative_to(archive)), "started_at": now(), "structure_before": work_order["structure_before"]}
    if branch_record:
        state["active_agent"]["implementation_branch"] = branch_record
    if created_new_branch:
        state["implementation_branch"] = {
            key: branch_record[key] for key in ["name", "previous_branch", "prepared_at", "source", "initial_stage_version"]
        }
        if not state.get("initial_implementation_branch"):
            state["initial_implementation_branch"] = state["implementation_branch"]
    if branch_record and not any(
        item.get("stage_version") == version for item in state.setdefault("implementation_branches", [])
    ) and stage == "implementation":
        state["implementation_branches"].append({"stage_version": version, **branch_record})
    state.setdefault("used_agent_ids", []).append(a.agent_id)
    state["status"] = "subagent_working"
    state["history"].append({"at": now(), "action": "subagent_dispatch", "stage": stage, "version": version, **state["active_agent"]})
    save(archive, state)
    print(json.dumps({"run_id": run_id, "work_order": str(order_path), "status": state["status"]}, ensure_ascii=False, indent=2))


def close_agent_lease(archive: Path, run_id: str, result: str, record: dict) -> str:
    lease = archive / "agent-runs" / "active.lease"
    if not lease.is_file():
        raise SystemExit("子 Agent 活跃租约缺失")
    closed = archive / "agent-runs" / f"{run_id}_{result}.json"
    closed.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lease.unlink()
    return str(closed.relative_to(archive))


def cmd_agent_complete(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    active = state.get("active_agent") or {}
    if state["status"] != "subagent_working" or active.get("run_id") != a.run_id:
        raise SystemExit("run-id 与当前活跃子 Agent 不匹配")
    if not a.evidence.strip():
        raise SystemExit("子 Agent 完成记录必须提供 --evidence")
    record = {"at": now(), "action": "subagent_complete", "stage": state["stage"], "version": state["version"], "run_id": a.run_id, "agent_id": active["agent_id"], "result": a.result, "evidence": a.evidence.strip(), "structure_before": active.get("structure_before", {})}
    if active.get("implementation_branch"):
        record["implementation_branch"] = active["implementation_branch"]
    record["record"] = close_agent_lease(archive, a.run_id, a.result, record)
    state["history"].append(record)
    state["last_agent_run"] = record
    state.pop("active_agent", None)
    state["status"] = "ready_for_submit" if a.result == "succeeded" else "awaiting_dispatch"
    save(archive, state)
    cmd_status(argparse.Namespace(archive=str(archive)))


def cmd_abandon(a: argparse.Namespace) -> None:
    a.result = "abandoned"
    a.evidence = a.reason
    cmd_agent_complete(a)


def cmd_status(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    keys = ["iteration_id", "iteration_name", "requirement", "prd_source_type", "stage", "version", "status", "test_cycles", "implementation_branch", "delivery_branch", "pending_repair_branch_decision", "active_agent"]
    payload = {k: state.get(k) for k in keys}
    payload["next_action"] = {
        "awaiting_dispatch": "spawn_fresh_subagent_then_dispatch",
        "subagent_working": "monitor_subagent",
        "ready_for_submit": "orchestrator_submit",
        "awaiting_user_clarification": "ask_user_then_clarify",
        "awaiting_prd_review": "wait_for_explicit_human_review",
        "awaiting_human_review": "wait_for_explicit_human_review",
        "awaiting_change_preview": "orchestrator_explain_document_changes",
        "awaiting_change_confirmation": "human_confirm_or_revise_change_preview",
        "awaiting_repair_branch_decision": "ask_user_reuse_or_create_repair_branch",
        "complete": "none",
    }.get(state["status"], "inspect_state")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if state["status"] != "complete":
        print(f"产物: {artifact_path(archive, state)}")


def cmd_repair_branch_decision(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    pending = state.get("pending_repair_branch_decision") or {}
    if state["status"] != "awaiting_repair_branch_decision" or state["stage"] != "implementation":
        raise SystemExit("当前没有等待用户选择的测试修复分支策略")
    if pending.get("implementation_version") != state["version"]:
        raise SystemExit("修复分支决策与当前 implementation 版本不匹配")
    branch = (a.branch.strip() if a.branch else None) or None
    if a.strategy == "reuse" and branch:
        raise SystemExit("复用原有分支时不能提供 --branch")
    if a.strategy == "new" and branch:
        check = subprocess.run(["git", "check-ref-format", "--branch", branch], text=True, capture_output=True)
        if check.returncode != 0:
            raise SystemExit(f"无效的修复分支名称: {branch}")
    current = state.get("implementation_branch")
    if not current:
        raise SystemExit("修复分支决策缺少上一轮代码实现分支")
    if a.strategy == "new" and branch == current["name"]:
        raise SystemExit("选择新建修复分支时，--branch 必须不同于当前实现分支")
    decision = {
        "at": now(), "action": "repair_branch_decision", "responder": a.responder,
        "strategy": a.strategy, "requested_branch": branch,
        "implementation_version": state["version"], "source_branch": current["name"],
        "failed_test_version": pending.get("failed_test_version"),
    }
    record_path = archive / "reviews" / f"implementation_v{state['version']:03d}_repair-branch-{a.strategy}_{dt.datetime.now():%Y%m%d%H%M%S%f}.json"
    record_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decision["record"] = str(record_path.relative_to(archive))
    state.setdefault("repair_branch_decisions", []).append(decision)
    state["history"].append(decision)
    state["repair_branch_mode"] = a.strategy
    state["repair_branch_version"] = state["version"]
    state["repair_branch_requested"] = branch
    state.pop("pending_repair_branch_decision", None)
    state["status"] = "awaiting_dispatch"
    target = artifact_path(archive, state)
    if not target.exists():
        target.write_text(template(state, state["stage"], state["version"]), encoding="utf-8")
    save(archive, state)
    cmd_status(argparse.Namespace(archive=str(archive)))


def section_text(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def submit_prd_intake(archive: Path, state: dict, path: Path, result: str | None) -> None:
    if result not in {"needs-clarification", "ready"}:
        raise SystemExit("候选 PRD 提交必须提供 --result needs-clarification|ready")
    text = path.read_text(encoding="utf-8")
    event = {"at": now(), "action": "submit", "stage": "prd_intake", "version": state["version"], "result": result, "artifact": str(path.relative_to(archive)), "sha256": digest(path)}
    state["history"].append(event)
    if result == "needs-clarification":
        if "PRD_STATUS: NEEDS_CLARIFICATION" not in text:
            raise SystemExit("待澄清 PRD 必须包含状态标记 PRD_STATUS: NEEDS_CLARIFICATION")
        questions = section_text(text, "待确认问题")
        if not questions or "无（边界已确认）" in questions:
            raise SystemExit("待澄清 PRD 的“待确认问题”必须列出具体问题")
        state["status"] = "awaiting_user_clarification"
        print("请向用户逐项询问候选 PRD“待确认问题”中的最少必要问题，然后执行 clarify。")
    else:
        if "PRD_STATUS: READY" not in text or "PRD_STATUS: NEEDS_CLARIFICATION" in text:
            raise SystemExit("就绪 PRD 必须且只能包含状态标记 PRD_STATUS: READY")
        if "无（边界已确认）" not in section_text(text, "待确认问题"):
            raise SystemExit("就绪 PRD 的“待确认问题”必须明确写“无（边界已确认）”")
        state["prd_candidate"] = path.name
        state["prd_candidate_sha256"] = digest(path)
        state["status"] = "awaiting_prd_review"
        print("候选 PRD 已就绪。必须由用户执行 review approve|reject；未经批准不能进入技术设计。")


def cmd_submit(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    if state["status"] != "ready_for_submit":
        raise SystemExit(f"当前状态 {state['status']} 不允许提交")
    stage, path = state["stage"], artifact_path(archive, state)
    last_run = state.get("last_agent_run") or {}
    if last_run.get("stage") != stage or last_run.get("version") != state["version"] or last_run.get("result") != "succeeded":
        raise SystemExit("当前产物没有匹配的成功子 Agent 执行记录")
    if stage == "prd_intake":
        validate_original_input(archive, state)
    if stage in {"implementation", "test_execution"}:
        expected_branch = (state.get("implementation_branch") or {}).get("name")
        current_branch = git(Path(state["repo"]), "branch", "--show-current")
        if not expected_branch or current_branch != expected_branch:
            raise SystemExit(f"实现与测试产物必须在同一交付分支提交；期望 {expected_branch}，当前 {current_branch}")
    if stage == "summary" and state.get("delivery_branch"):
        expected_branch = state["delivery_branch"]["name"]
        current_branch = git(Path(state["repo"]), "branch", "--show-current")
        if current_branch != expected_branch:
            raise SystemExit(f"最终总结必须在已通过测试的交付分支提交；期望 {expected_branch}，当前 {current_branch}")
    errors = validate_artifact(path, stage, state, last_run)
    if errors:
        raise SystemExit("提交校验失败:\n- " + "\n- ".join(errors))
    if stage == "prd_intake":
        submit_prd_intake(archive, state, path, getattr(a, "result", None))
        save(archive, state)
        cmd_status(argparse.Namespace(archive=str(archive)))
        return
    event = {"at": now(), "action": "submit", "stage": stage, "version": state["version"], "artifact": str(path.relative_to(archive)), "sha256": digest(path)}
    if stage in {"technical_design", "code_plan"} and "PRESENTATION_FORMAT: HTML" in path.read_text(encoding="utf-8"):
        html = path.with_suffix(".html")
        event["html_sidecar"] = {"artifact": str(html.relative_to(archive)), "sha256": digest(html)}
    if stage == "summary":
        event["structure_hashes"] = structure_hashes(Path(state["structure_root"]))
    if stage == "implementation":
        event["git_evidence"] = capture_git_evidence(archive, state)
    state["history"].append(event)
    if stage in GATED:
        state["status"] = "awaiting_human_review"
    elif stage == "test_execution":
        if a.result not in {"passed", "failed"}:
            raise SystemExit("测试执行提交必须提供 --result passed|failed")
        event["result"], state["test_cycles"] = a.result, state["test_cycles"] + 1
        if a.result == "failed":
            failed_test_version = state["version"]
            state["stage"] = "implementation"
            state["version"] = state["stage_versions"].get("implementation", 0) + 1
            state["stage_versions"]["implementation"] = state["version"]
            try:
                suggested_new_branch = state.get(
                    "default_branch_pattern", "tmp/{iteration_name}-{implementation_version}"
                ).format(
                    iteration_name=safe_name(state["iteration_name"]), implementation_version=state["version"],
                )
            except (KeyError, ValueError):
                suggested_new_branch = None
            state.pop("repair_branch_mode", None)
            state.pop("repair_branch_version", None)
            state.pop("repair_branch_requested", None)
            state["pending_repair_branch_decision"] = {
                "failed_test_version": failed_test_version,
                "implementation_version": state["version"],
                "current_branch": (state.get("implementation_branch") or {}).get("name"),
                "suggested_new_branch": suggested_new_branch,
                "asked_at": now(),
            }
            state["status"] = "awaiting_repair_branch_decision"
        else:
            state["delivery_branch"] = state.get("implementation_branch")
            advance(state)
    elif stage == "summary":
        improvement = write_improvement(archive, state, path)
        event["improvement"] = {"path": str(improvement), "sha256": digest(improvement)}
        state["improvement_record"] = event["improvement"]
        custom_experience = write_custom_experience(archive, state, path)
        if custom_experience:
            event["custom_experience"] = {"path": str(custom_experience), "sha256": digest(custom_experience)}
            state["custom_experience_record"] = event["custom_experience"]
            state["custom_index"] = create_custom_context(archive, state, "completed")
        state["status"], state["completed_at"] = "complete", now()
    else:
        advance(state)
    if state["status"] == "awaiting_dispatch":
        target = artifact_path(archive, state)
        if not target.exists():
            target.write_text(template(state, state["stage"], state["version"]), encoding="utf-8")
    save(archive, state)
    cmd_status(argparse.Namespace(archive=str(archive)))


def cmd_clarify(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    if state["stage"] != "prd_intake" or state["status"] != "awaiting_user_clarification":
        raise SystemExit("当前没有等待用户澄清的候选 PRD")
    validate_original_input(archive, state)
    response = a.response
    if a.response_file:
        source = Path(a.response_file).resolve()
        if not source.is_file():
            raise SystemExit(f"澄清回复文件不存在: {source}")
        response = source.read_text(encoding="utf-8")
    if not response or not response.strip():
        raise SystemExit("澄清回复不能为空")
    stamp = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
    record = {"at": now(), "responder": a.responder, "response": response.strip(), "from_version": state["version"]}
    record_path = archive / "00-input" / "clarifications" / f"clarification_{stamp}.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    previous = artifact_path(archive, state)
    state["version"] += 1
    state["stage_versions"]["prd_intake"] = state["version"]
    state["status"] = "awaiting_dispatch"
    target = artifact_path(archive, state)
    content = previous.read_text(encoding="utf-8")
    content += f"\n\n### 用户补充 {record['at']}（{a.responder}）\n\n{response.strip()}\n"
    target.write_text(content, encoding="utf-8")
    state["history"].append({**record, "action": "user_clarification", "record": str(record_path.relative_to(archive)), "to_version": state["version"]})
    save(archive, state)
    print(f"已保留澄清记录并创建新版本: {target}")
    print("请依据回复修订候选 PRD；仍有关键歧义可再次提交 needs-clarification，否则标记 READY 后提交。")


def cmd_customize(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    if state["status"] == "complete":
        raise SystemExit("迭代已完成；请创建新迭代后记录新的 custom 诉求")
    if state["status"] not in {"awaiting_dispatch", "awaiting_user_clarification"}:
        raise SystemExit("custom 只能在派发新子 Agent 前更新；请先结束当前子 Agent，或在人工闸门驳回当前产物")
    content = a.content
    if a.content_file:
        source = Path(a.content_file).resolve()
        if not source.is_file():
            raise SystemExit(f"custom 内容文件不存在: {source}")
        content = source.read_text(encoding="utf-8")
    if not content or not content.strip():
        raise SystemExit("custom 更新内容不能为空")
    root = Path(state["custom_root"])
    ensure_custom_files(root)
    target = root / f"{a.target}.md"
    before = digest(target)
    if a.mode == "replace":
        heading = "# 用户个性化诉求" if a.target == "user" else "# Harnove 项目经验"
        target.write_text(f"{heading}\n\n{content.strip()}\n", encoding="utf-8")
    else:
        with target.open("a", encoding="utf-8") as stream:
            stream.write(f"\n\n## {now()} · {a.actor}\n\n{content.strip()}\n")
    ensure_custom_files(root)
    event = {
        "at": now(), "action": "custom_update", "target": target.name, "mode": a.mode,
        "actor": a.actor, "content": content.strip(), "before_sha256": before, "after_sha256": digest(target),
    }
    state["history"].append(event)
    state["custom_index"] = create_custom_context(archive, state, f"custom-{len(user_feedback_items(state)):03d}")
    event["custom_snapshot"] = state["custom_index"]
    save(archive, state)
    print(json.dumps(event, ensure_ascii=False, indent=2))


def cmd_review(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    expected_status = "awaiting_prd_review" if state["stage"] == "prd_intake" else "awaiting_human_review"
    if state["status"] != expected_status or state["stage"] not in REVIEW_GATED:
        raise SystemExit("当前没有等待人工审核的闸门")
    if state["stage"] == "prd_intake":
        validate_original_input(archive, state)
    reviewer = a.reviewer.strip()
    human_confirmation = getattr(a, "human_confirmation", "").strip()
    if not reviewer:
        raise SystemExit("人工审核必须提供非空的 --reviewer")
    if a.decision == "reject" and not a.feedback.strip():
        raise SystemExit("驳回必须提供可执行的 --feedback")
    if a.decision == "approve" and a.feedback.strip():
        raise SystemExit("带反馈的审核不能直接批准；请使用 reject 进入变更影响确认流程")
    if a.decision == "approve" and len(human_confirmation) < 2:
        raise SystemExit("批准必须通过 --human-confirmation 归档用户明确批准的原文；主 Agent 不得自行判断通过")
    if a.decision == "reject" and human_confirmation:
        raise SystemExit("驳回不能同时提供 --human-confirmation")
    stage, version, path = state["stage"], state["version"], artifact_path(archive, state)
    record = {
        "at": now(), "reviewer": reviewer, "decision": a.decision, "stage": stage,
        "version": version, "artifact": str(path.relative_to(archive)), "sha256": digest(path),
        "feedback": a.feedback.strip(), "human_confirmation": human_confirmation,
    }
    if stage in {"technical_design", "code_plan"} and "PRESENTATION_FORMAT: HTML" in path.read_text(encoding="utf-8"):
        html = path.with_suffix(".html")
        record["html_sidecar"] = {"artifact": str(html.relative_to(archive)), "sha256": digest(html)}
    review_path = archive / "reviews" / f"{stage}_v{version:03d}_{a.decision}_{dt.datetime.now():%Y%m%d%H%M%S}.json"
    review_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state["history"].append({**record, "action": "human_review", "record": str(review_path.relative_to(archive))})
    if a.decision == "approve":
        state["approved"][stage] = {
            "version": version, "artifact": str(path.relative_to(archive)), "sha256": digest(path),
            "reviewer": reviewer, "human_confirmation": human_confirmation,
            "review_record": str(review_path.relative_to(archive)),
        }
        if "html_sidecar" in record:
            state["approved"][stage]["html_sidecar"] = record["html_sidecar"]
        if stage == "prd_intake":
            state["prd_snapshot"] = path.name
            state["prd_sha256"] = digest(path)
            create_requirement_baseline(archive, state)
        state.pop("approved_change_preview", None)
        advance(state)
    else:
        state["pending_document_change"] = {
            "stage": stage, "version": version, "artifact": str(path.relative_to(archive)),
            "artifact_sha256": digest(path), "feedback": [{"at": record["at"], "reviewer": a.reviewer, "content": a.feedback.strip()}],
            "preview_round": 0,
        }
        state["status"] = "awaiting_change_preview"
    save(archive, state)
    cmd_status(argparse.Namespace(archive=str(archive)))


def cmd_change_preview(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    pending = state.get("pending_document_change") or {}
    if state["status"] != "awaiting_change_preview" or pending.get("stage") != state["stage"] or pending.get("version") != state["version"]:
        raise SystemExit("当前没有等待分析的文档反馈")
    summary = a.summary
    if a.summary_file:
        source = Path(a.summary_file).resolve()
        if not source.is_file():
            raise SystemExit(f"变更影响说明文件不存在: {source}")
        summary = source.read_text(encoding="utf-8")
    sections = [item.strip() for item in a.sections.split(",") if item.strip()]
    if not sections:
        raise SystemExit("必须通过 --sections 列出将发生变化的文档部分")
    unknown_sections = [item for item in sections if item not in REQUIRED_SECTIONS[state["stage"]]]
    if unknown_sections:
        raise SystemExit("变更影响包含不存在的文档章节: " + ", ".join(unknown_sections))
    if not summary or len(summary.strip()) < 40:
        raise SystemExit("变更影响说明至少需要 40 字，包含变化内容、原因和边界")
    pending["preview_round"] = pending.get("preview_round", 0) + 1
    preview = {
        "at": now(), "action": "document_change_preview", "orchestrator": a.orchestrator,
        "stage": state["stage"], "version": state["version"], "round": pending["preview_round"],
        "sections": list(dict.fromkeys(sections)), "summary": summary.strip(),
        "feedback": pending["feedback"],
    }
    preview_path = archive / "reviews" / f"{state['stage']}_v{state['version']:03d}_change-preview-r{preview['round']:03d}_{dt.datetime.now():%Y%m%d%H%M%S%f}.json"
    preview_path.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    preview["record"] = str(preview_path.relative_to(archive))
    pending["latest_preview"] = preview
    state["pending_document_change"] = pending
    state["history"].append(preview)
    state["status"] = "awaiting_change_confirmation"
    save(archive, state)
    print(json.dumps({"status": state["status"], "sections": preview["sections"], "summary": preview["summary"], "next_action": "ask_user_approve_or_revise"}, ensure_ascii=False, indent=2))


def cmd_change_decision(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    pending = state.get("pending_document_change") or {}
    preview = pending.get("latest_preview") or {}
    if state["status"] != "awaiting_change_confirmation" or not preview:
        raise SystemExit("当前没有等待确认的文档变更影响预览")
    if a.decision == "revise" and not a.feedback.strip():
        raise SystemExit("不批准当前预览时必须提供新的 --feedback")
    if a.decision == "approve" and a.feedback.strip():
        raise SystemExit("批准变更影响预览时不能同时附加新反馈；请先 revise 并重新分析")
    decision = {
        "at": now(), "action": "document_change_decision", "reviewer": a.reviewer,
        "decision": a.decision, "feedback": a.feedback.strip(), "stage": state["stage"],
        "version": state["version"], "preview_record": preview["record"],
    }
    decision_path = archive / "reviews" / f"{state['stage']}_v{state['version']:03d}_change-{a.decision}_{dt.datetime.now():%Y%m%d%H%M%S%f}.json"
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decision["record"] = str(decision_path.relative_to(archive))
    state["history"].append(decision)
    if a.decision == "revise":
        pending["feedback"].append({"at": decision["at"], "reviewer": a.reviewer, "content": a.feedback.strip()})
        pending.pop("latest_preview", None)
        state["pending_document_change"] = pending
        state["status"] = "awaiting_change_preview"
    else:
        stage, old_version = state["stage"], state["version"]
        source_path = artifact_path(archive, state)
        state["version"] = old_version + 1
        state["stage_versions"][stage] = state["version"]
        target = artifact_path(archive, state)
        revised = source_path.read_text(encoding="utf-8")
        revised = re.sub(r"(- 文档版本：)v\d{3}", rf"\1v{state['version']:03d}", revised, count=1)
        if stage == "prd_intake":
            revised = revised.replace("PRD_STATUS: READY", "PRD_STATUS: NEEDS_CLARIFICATION")
        target.write_text(revised, encoding="utf-8")
        source_html = source_path.with_suffix(".html")
        if source_html.is_file():
            target.with_suffix(".html").write_bytes(source_html.read_bytes())
        state["approved_change_preview"] = {
            "from_version": old_version, "to_version": state["version"], "preview": preview,
            "decision_record": decision["record"], "all_feedback": pending["feedback"],
        }
        state.pop("pending_document_change", None)
        state["status"] = "awaiting_dispatch"
    save(archive, state)
    cmd_status(argparse.Namespace(archive=str(archive)))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="人工闸门驱动的研发迭代状态机")
    sub = p.add_subparsers(dest="command", required=True)
    default_repo, default_archive, default_improve, default_structure, default_custom, default_home, default_branch_pattern = project_defaults()
    x = sub.add_parser("init")
    x.add_argument("--iteration-id", required=True); x.add_argument("--iteration-name", required=True); x.add_argument("--requirement", required=True)
    source = x.add_mutually_exclusive_group(required=True)
    source.add_argument("--prd"); source.add_argument("--description"); source.add_argument("--description-file")
    x.add_argument("--repo", default=default_repo); x.add_argument("--root", default=default_archive)
    x.add_argument("--improve-root", default=default_improve); x.add_argument("--structure-root", default=default_structure); x.add_argument("--custom-root", default=default_custom)
    x.add_argument("--home", default=default_home, help=argparse.SUPPRESS); x.add_argument("--branch-pattern", default=default_branch_pattern, help=argparse.SUPPRESS); x.set_defaults(func=cmd_init)
    x = sub.add_parser("status"); x.add_argument("--archive", required=True); x.set_defaults(func=cmd_status)
    x = sub.add_parser("dispatch"); x.add_argument("--archive", required=True); x.add_argument("--agent-id", required=True); x.add_argument("--orchestrator", required=True); x.add_argument("--branch", help="实施阶段使用的用户指定分支名；省略时使用 tmp/{迭代名称}-{实施轮次}"); x.set_defaults(func=cmd_dispatch)
    x = sub.add_parser("agent-complete"); x.add_argument("--archive", required=True); x.add_argument("--run-id", required=True); x.add_argument("--result", required=True, choices=["succeeded", "failed"]); x.add_argument("--evidence", required=True); x.set_defaults(func=cmd_agent_complete)
    x = sub.add_parser("abandon"); x.add_argument("--archive", required=True); x.add_argument("--run-id", required=True); x.add_argument("--reason", required=True); x.set_defaults(func=cmd_abandon)
    x = sub.add_parser("submit"); x.add_argument("--archive", required=True); x.add_argument("--result", choices=["needs-clarification", "ready", "passed", "failed"]); x.set_defaults(func=cmd_submit)
    x = sub.add_parser("repair-branch-decision"); x.add_argument("--archive", required=True); x.add_argument("--strategy", required=True, choices=["reuse", "new"]); x.add_argument("--responder", required=True); x.add_argument("--branch", help="strategy=new 时可指定精确修复分支；省略则使用默认分支规则"); x.set_defaults(func=cmd_repair_branch_decision)
    x = sub.add_parser("clarify"); x.add_argument("--archive", required=True); x.add_argument("--responder", required=True)
    response = x.add_mutually_exclusive_group(required=True); response.add_argument("--response"); response.add_argument("--response-file"); x.set_defaults(func=cmd_clarify)
    x = sub.add_parser("customize"); x.add_argument("--archive", required=True); x.add_argument("--target", choices=["user", "self"], default="user"); x.add_argument("--mode", choices=["append", "replace"], default="append"); x.add_argument("--actor", required=True)
    custom_content = x.add_mutually_exclusive_group(required=True); custom_content.add_argument("--content"); custom_content.add_argument("--content-file"); x.set_defaults(func=cmd_customize)
    x = sub.add_parser("review"); x.add_argument("--archive", required=True); x.add_argument("--decision", required=True, choices=["approve", "reject"]); x.add_argument("--reviewer", required=True); x.add_argument("--feedback", default=""); x.add_argument("--human-confirmation", default="", help="decision=approve 时必须原样记录用户明确批准文本"); x.set_defaults(func=cmd_review)
    x = sub.add_parser("change-preview"); x.add_argument("--archive", required=True); x.add_argument("--orchestrator", required=True); x.add_argument("--sections", required=True, help="逗号分隔的受影响章节")
    preview_content = x.add_mutually_exclusive_group(required=True); preview_content.add_argument("--summary"); preview_content.add_argument("--summary-file"); x.set_defaults(func=cmd_change_preview)
    x = sub.add_parser("change-decision"); x.add_argument("--archive", required=True); x.add_argument("--decision", required=True, choices=["approve", "revise"]); x.add_argument("--reviewer", required=True); x.add_argument("--feedback", default=""); x.set_defaults(func=cmd_change_decision)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)
