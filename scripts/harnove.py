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

STAGES = ["prd_intake", "structure_analysis", "technical_design", "code_plan", "test_design", "implementation", "test_execution", "structure_refresh", "summary"]
GATED = {"technical_design", "code_plan", "test_design"}
REVIEW_GATED = GATED | {"prd_intake"}
DIRS = {
    "prd_intake": "00-input",
    "structure_analysis": "00-input",
    "technical_design": "01-technical-design",
    "code_plan": "02-code-plan",
    "test_design": "03-test-design",
    "implementation": "04-implementation",
    "test_execution": "05-test-execution",
    "structure_refresh": "06-summary",
    "summary": "06-summary",
}
CN_NAMES = {
    "prd_intake": "候选PRD",
    "structure_analysis": "项目结构分析",
    "technical_design": "技术方案",
    "code_plan": "代码修改方案",
    "test_design": "测试方案",
    "implementation": "代码变更记录",
    "test_execution": "测试报告",
    "structure_refresh": "项目结构刷新记录",
    "summary": "迭代总结",
}
REQUIRED_SECTIONS = {
    "prd_intake": ["原始需求描述", "目标与背景", "用户与场景", "功能需求", "非功能需求", "范围内", "范围外", "验收标准", "约束与依赖", "信息补充记录", "待确认问题", "用户补充记录"],
    "structure_analysis": ["分析范围", "功能模块", "代码框架", "结构定义和关系", "需求相关结构一致性", "结构更新记录", "代码证据"],
    "technical_design": ["需求依据", "结构一致性检查", "目标与非目标", "现状分析", "技术方案", "功能变更树", "架构与流程图", "风险", "回滚", "追溯矩阵"],
    "code_plan": ["需求依据", "结构一致性检查", "改动范围", "改动细则", "代码变更树", "改动关系图", "改动原因", "禁止改动", "追溯矩阵"],
    "test_design": ["需求依据", "覆盖策略", "测试用例", "测试目的", "覆盖矩阵"],
    "implementation": ["需求依据", "批准基线", "实际改动", "Git 证据", "方案偏差"],
    "test_execution": ["需求依据", "实际变更审查", "可执行测试", "执行结果", "结论"],
    "structure_refresh": ["实际变更依据", "受影响结构", "结构更新", "一致性验证", "代码证据"],
    "summary": ["需求背景", "迭代内容", "测试结论", "追溯矩阵", "用户反馈经验", "环节评分", "亮点", "缺点", "根因", "经验总结", "下次复用规则", "改进项"],
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


def project_defaults() -> tuple[str, str, str, str, str, str]:
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
        return str(repo), str(archive), str(improve), str(structure), str(custom), str(home)
    fallback_home = Path.cwd().resolve()
    return ".", str(fallback_home / "iterations"), str(fallback_home / "improve"), str(fallback_home / "structure"), str(fallback_home / "custom"), str(fallback_home)


def load(archive: Path) -> dict:
    path = archive / "state.json"
    if not path.is_file():
        raise SystemExit(f"找不到状态文件: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version", 1) < 6:
        _, _, discovered_improve, discovered_structure, discovered_custom, discovered_home = project_defaults()
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
        state.setdefault("history", []).append({"at": now(), "action": "schema_migration", "from": state.get("schema_version", 1), "to": 6})
        if state.get("status") == "drafting":
            state["status"] = "awaiting_dispatch"
        state["schema_version"] = 6
        if not state.get("improvement_index") and (archive / "00-input").is_dir():
            state["improvement_index"] = create_improvement_context(archive, state)
        if not state.get("structure_index") and (archive / "00-input").is_dir():
            state["structure_index"] = create_structure_context(archive, state)
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
- 输入类型：{state['prd_source_type']}
- 原始输入：`{state['original_input_snapshot']}`
- 原始输入 SHA-256：`{state['original_input_sha256']}`
- 状态标记：`PRD_STATUS: NEEDS_CLARIFICATION`
- 规则：原始文件只读；所有补充必须记录依据；不得把推测写成已确认需求。

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
        f"- 迭代编号：{state['iteration_id']}", f"- 需求名称：{state['requirement']}",
        f"- 文档版本：v{version:03d}", f"- 角色：{CN_NAMES[stage]}", "- 状态：草稿",
        f"- PRD 快照：`00-input/{state['prd_snapshot']}`", f"- PRD SHA-256：`{state['prd_sha256']}`",
        f"- 经验复用索引：`00-input/{state['improvement_index']}`",
        f"- 项目结构索引：`00-input/{state['structure_index']}`",
        f"- 项目自定义上下文：`00-input/{state['custom_index']}`",
        f"- 仓库基线：`{state.get('git_baseline') or 'GIT_UNAVAILABLE'}`", "",
    ]
    if stage in {"technical_design", "code_plan"}:
        lines += ["- 表达格式：`PRESENTATION_FORMAT: MD`", ""]
    if stage == "structure_analysis":
        source_mode = "REUSED_AND_VERIFIED" if structure_hashes(Path(state["structure_root"])) else "FULL_REPOSITORY_SCAN"
        lines += [f"- 结构读取模式：`STRUCTURE_SOURCE: {source_mode}`", ""]
    for section in REQUIRED_SECTIONS[stage]:
        lines += [f"## {section}", "", PLACEHOLDER, ""]
        if section in {"需求相关结构一致性", "结构一致性检查", "一致性验证"}:
            lines += ["STRUCTURE_STATUS: CONSISTENT", ""]
        if section in {"功能变更树", "代码变更树"}:
            lines += ["CHANGE_TREE_STATUS: INCLUDED", "", "```text", "需求/方案根节点", "├── 待细化变更一", "└── 待细化变更二", "```", ""]
        if section in {"架构与流程图", "改动关系图"}:
            lines += ["DIAGRAM_STATUS: INCLUDED", "", "```mermaid", "flowchart LR", "  A[待细化输入] --> B[待细化处理]", "  B --> C[待细化输出]", "```", ""]
        if section == "用户反馈经验":
            status = "CAPTURED" if user_feedback_items(state) else "NONE"
            lines += [f"FEEDBACK_EXPERIENCE_STATUS: {status}", ""]
    return "\n".join(lines)


def validate_artifact(path: Path, stage: str, state: dict | None = None, last_run: dict | None = None) -> list[str]:
    if not path.is_file():
        return [f"缺少产物: {path}"]
    text = path.read_text(encoding="utf-8")
    errors = [f"缺少章节: {s}" for s in REQUIRED_SECTIONS[stage] if f"## {s}" not in text]
    if "REQ-" not in text:
        errors.append("未引用任何稳定需求 ID（REQ-xxx）")
    if "<!--" in text:
        errors.append("仍存在未填写的模板占位符")
    if len(text.strip()) < 500:
        errors.append("产物内容过短，无法形成可审核证据")
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
    if stage in {"structure_analysis", "technical_design", "code_plan", "structure_refresh"}:
        consistent = "STRUCTURE_STATUS: CONSISTENT" in text
        updated = "STRUCTURE_STATUS: UPDATED" in text
        if consistent == updated:
            errors.append("结构检查必须且只能声明 STRUCTURE_STATUS: CONSISTENT 或 UPDATED")
        if state is not None:
            current = structure_hashes(Path(state["structure_root"]))
            before = (last_run or {}).get("structure_before", {})
            if not current:
                errors.append("structure 目录为空，必须先完成项目结构解读")
            else:
                combined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in structure_files(Path(state["structure_root"])))
                for required in ["功能模块", "代码框架", "结构定义和关系"]:
                    if required not in combined:
                        errors.append(f"structure 记录缺少必需部分: {required}")
            if stage == "structure_analysis" and not before and not updated:
                errors.append("structure 为空时必须扫描全仓并声明 STRUCTURE_STATUS: UPDATED")
            if stage == "structure_analysis" and not before and "STRUCTURE_SOURCE: FULL_REPOSITORY_SCAN" not in text:
                errors.append("structure 为空时必须声明 STRUCTURE_SOURCE: FULL_REPOSITORY_SCAN")
            if stage == "structure_analysis" and before and "STRUCTURE_SOURCE: REUSED_AND_VERIFIED" not in text:
                errors.append("已有 structure 时必须优先复用并声明 STRUCTURE_SOURCE: REUSED_AND_VERIFIED")
            if stage == "structure_refresh" and not updated:
                errors.append("需求完成后必须更新 structure 并声明 STRUCTURE_STATUS: UPDATED")
            if updated and current == before:
                errors.append("声明 UPDATED 但 structure 文件内容未发生变化")
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


def create_structure_context(archive: Path, state: dict, label: str = "initial") -> str:
    root = Path(state["structure_root"])
    root.mkdir(parents=True, exist_ok=True)
    name = f"{state['iteration_id']}_{state['requirement']}_项目结构上下文_{safe_name(label)}.md"
    target = archive / "00-input" / name
    files = structure_files(root)
    lines = [
        f"# {state['iteration_id']} {state['requirement']} - 项目结构上下文", "",
        "优先复用此处记录；设计前必须用需求相关代码验证其时效性。", "",
    ]
    if not files:
        lines += ["## STRUCTURE_EMPTY", "", "structure 当前为空；结构分析子 Agent 必须读取整个项目，并按功能模块、代码框架、结构定义和关系三个部分建立记录。", ""]
    for item in files:
        relative = item.relative_to(root).as_posix()
        language = "html" if item.suffix.lower() == ".html" else "markdown"
        lines += [f"## {relative}", "", f"- SHA-256：`{digest(item)}`", "", f"```{language}", item.read_text(encoding="utf-8", errors="replace"), "```", ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return name


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

    ident, req = safe_name(a.iteration_id), safe_name(a.requirement)
    archive = root / f"{dt.date.today():%Y%m%d}_{ident}_{req}"
    if archive.exists():
        raise SystemExit(f"归档目录已存在: {archive}")
    for folder in sorted(set(DIRS.values())) + ["reviews", "00-input/clarifications", "agent-runs"]:
        (archive / folder).mkdir(parents=True, exist_ok=True)
    baseline = git(repo, "rev-parse", "HEAD")
    state = {
        "schema_version": 6, "iteration_id": ident, "requirement": req,
        "archive": str(archive), "repo": str(repo), "harnove_home": str(home),
        "improve_root": str(improve_root), "structure_root": str(structure_root), "custom_root": str(custom_root), "git_baseline": baseline,
        "created_at": now(), "history": [], "approved": {}, "test_cycles": 0,
        "stage_versions": {stage: 0 for stage in STAGES}, "used_agent_ids": [],
    }
    state["improvement_index"] = create_improvement_context(archive, state)
    state["structure_index"] = create_structure_context(archive, state)
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
    run_id = uuid.uuid4().hex
    stage, version = state["stage"], state["version"]
    work_order = {
        "run_id": run_id, "agent_id": a.agent_id, "orchestrator": a.orchestrator,
        "stage": stage, "version": version, "created_at": now(),
        "artifact": str(artifact_path(archive, state)), "repo": state["repo"],
        "prd_snapshot": state.get("prd_snapshot") or state.get("original_input_snapshot"),
        "improvement_context": str(archive / "00-input" / state["improvement_index"]),
        "structure_context": str(archive / "00-input" / state["structure_index"]),
        "structure_root": state["structure_root"],
        "structure_before": structure_hashes(Path(state["structure_root"])),
        "custom_context": str(archive / "00-input" / state["custom_index"]),
        "custom_root": state["custom_root"],
        "approved_inputs": state.get("approved", {}),
        "write_scope": (
            "approved_repo_scope_and_artifact" if stage in {"implementation", "test_execution"}
            else "structure_and_artifact" if stage in {"structure_analysis", "technical_design", "code_plan", "structure_refresh"}
            else "artifact_only"
        ),
        "rules": [
            "只执行当前 stage/version，不执行状态机命令或人工审批",
            "读取经验复用上下文并记录采用或不适用的经验",
            "开始当前环节前读取项目自定义上下文，遵守 user.md 约束并复用 self.md 经验",
            "优先读取 structure 记录；涉及设计时先与需求相关代码核对，不一致则先更新 structure",
            "summary 环节必须根据澄清、审核反馈和 custom 更新提炼用户反馈经验",
            "不得执行其他环节的工作，不得复用本次子 Agent 身份",
        ],
    }
    runs = archive / "agent-runs"
    order_path = runs / f"{stage}_v{version:03d}_{run_id}_work-order.json"
    order_path.write_text(json.dumps(work_order, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lease = runs / "active.lease"
    try:
        with lease.open("x", encoding="utf-8") as f:
            json.dump(work_order, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except FileExistsError as exc:
        order_path.unlink(missing_ok=True)
        raise SystemExit("已有子 Agent 租约，拒绝并发派发") from exc
    state["active_agent"] = {"run_id": run_id, "agent_id": a.agent_id, "work_order": str(order_path.relative_to(archive)), "started_at": now(), "structure_before": work_order["structure_before"]}
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
    keys = ["iteration_id", "requirement", "prd_source_type", "stage", "version", "status", "test_cycles", "active_agent"]
    payload = {k: state.get(k) for k in keys}
    payload["next_action"] = {
        "awaiting_dispatch": "spawn_fresh_subagent_then_dispatch",
        "subagent_working": "monitor_subagent",
        "ready_for_submit": "orchestrator_submit",
        "awaiting_user_clarification": "ask_user_then_clarify",
        "awaiting_prd_review": "human_review",
        "awaiting_human_review": "human_review",
        "complete": "none",
    }.get(state["status"], "inspect_state")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if state["status"] != "complete":
        print(f"产物: {artifact_path(archive, state)}")


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
    if stage in {"structure_analysis", "technical_design", "code_plan", "structure_refresh"}:
        state["structure_index"] = create_structure_context(archive, state, f"{stage}-v{state['version']:03d}")
        event["structure_snapshot"] = state["structure_index"]
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
            state["stage"] = "implementation"
            state["version"] = state["stage_versions"].get("implementation", 0) + 1
            state["stage_versions"]["implementation"] = state["version"]
            state["status"] = "awaiting_dispatch"
        else:
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
    if a.decision == "reject" and not a.feedback.strip():
        raise SystemExit("驳回必须提供可执行的 --feedback")
    stage, version, path = state["stage"], state["version"], artifact_path(archive, state)
    record = {"at": now(), "reviewer": a.reviewer, "decision": a.decision, "stage": stage, "version": version, "artifact": str(path.relative_to(archive)), "sha256": digest(path), "feedback": a.feedback.strip()}
    if stage in {"technical_design", "code_plan"} and "PRESENTATION_FORMAT: HTML" in path.read_text(encoding="utf-8"):
        html = path.with_suffix(".html")
        record["html_sidecar"] = {"artifact": str(html.relative_to(archive)), "sha256": digest(html)}
    review_path = archive / "reviews" / f"{stage}_v{version:03d}_{a.decision}_{dt.datetime.now():%Y%m%d%H%M%S}.json"
    review_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state["history"].append({**record, "action": "human_review", "record": str(review_path.relative_to(archive))})
    if a.decision == "approve":
        state["approved"][stage] = {"version": version, "artifact": str(path.relative_to(archive)), "sha256": digest(path)}
        if "html_sidecar" in record:
            state["approved"][stage]["html_sidecar"] = record["html_sidecar"]
        if stage == "prd_intake":
            state["prd_snapshot"] = path.name
            state["prd_sha256"] = digest(path)
            create_requirement_baseline(archive, state)
        advance(state)
    else:
        state["version"] += 1
        state["stage_versions"][stage] = state["version"]
        state["status"] = "awaiting_dispatch"
    target = artifact_path(archive, state)
    if state["status"] == "awaiting_dispatch" and not target.exists():
        if stage == "prd_intake" and a.decision == "reject":
            revised = path.read_text(encoding="utf-8").replace("PRD_STATUS: READY", "PRD_STATUS: NEEDS_CLARIFICATION")
            revised += f"\n\n## PRD 审核反馈（待处理）\n\n- 审核人：{a.reviewer}\n- 反馈：{a.feedback.strip()}\n"
            target.write_text(revised, encoding="utf-8")
        else:
            target.write_text(template(state, state["stage"], state["version"]), encoding="utf-8")
    save(archive, state)
    cmd_status(argparse.Namespace(archive=str(archive)))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="人工闸门驱动的研发迭代状态机")
    sub = p.add_subparsers(dest="command", required=True)
    default_repo, default_archive, default_improve, default_structure, default_custom, default_home = project_defaults()
    x = sub.add_parser("init")
    x.add_argument("--iteration-id", required=True); x.add_argument("--requirement", required=True)
    source = x.add_mutually_exclusive_group(required=True)
    source.add_argument("--prd"); source.add_argument("--description"); source.add_argument("--description-file")
    x.add_argument("--repo", default=default_repo); x.add_argument("--root", default=default_archive)
    x.add_argument("--improve-root", default=default_improve); x.add_argument("--structure-root", default=default_structure); x.add_argument("--custom-root", default=default_custom)
    x.add_argument("--home", default=default_home, help=argparse.SUPPRESS); x.set_defaults(func=cmd_init)
    x = sub.add_parser("status"); x.add_argument("--archive", required=True); x.set_defaults(func=cmd_status)
    x = sub.add_parser("dispatch"); x.add_argument("--archive", required=True); x.add_argument("--agent-id", required=True); x.add_argument("--orchestrator", required=True); x.set_defaults(func=cmd_dispatch)
    x = sub.add_parser("agent-complete"); x.add_argument("--archive", required=True); x.add_argument("--run-id", required=True); x.add_argument("--result", required=True, choices=["succeeded", "failed"]); x.add_argument("--evidence", required=True); x.set_defaults(func=cmd_agent_complete)
    x = sub.add_parser("abandon"); x.add_argument("--archive", required=True); x.add_argument("--run-id", required=True); x.add_argument("--reason", required=True); x.set_defaults(func=cmd_abandon)
    x = sub.add_parser("submit"); x.add_argument("--archive", required=True); x.add_argument("--result", choices=["needs-clarification", "ready", "passed", "failed"]); x.set_defaults(func=cmd_submit)
    x = sub.add_parser("clarify"); x.add_argument("--archive", required=True); x.add_argument("--responder", required=True)
    response = x.add_mutually_exclusive_group(required=True); response.add_argument("--response"); response.add_argument("--response-file"); x.set_defaults(func=cmd_clarify)
    x = sub.add_parser("customize"); x.add_argument("--archive", required=True); x.add_argument("--target", choices=["user", "self"], default="user"); x.add_argument("--mode", choices=["append", "replace"], default="append"); x.add_argument("--actor", required=True)
    custom_content = x.add_mutually_exclusive_group(required=True); custom_content.add_argument("--content"); custom_content.add_argument("--content-file"); x.set_defaults(func=cmd_customize)
    x = sub.add_parser("review"); x.add_argument("--archive", required=True); x.add_argument("--decision", required=True, choices=["approve", "reject"]); x.add_argument("--reviewer", required=True); x.add_argument("--feedback", default=""); x.set_defaults(func=cmd_review)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)
