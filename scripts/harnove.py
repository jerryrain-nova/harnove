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
from pathlib import Path

STAGES = ["prd_intake", "technical_design", "code_plan", "test_design", "implementation", "test_execution", "summary"]
GATED = {"technical_design", "code_plan", "test_design"}
REVIEW_GATED = GATED | {"prd_intake"}
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
    "prd_intake": ["原始需求描述", "目标与背景", "用户与场景", "功能需求", "非功能需求", "范围内", "范围外", "验收标准", "约束与依赖", "信息补充记录", "待确认问题", "用户补充记录"],
    "technical_design": ["需求依据", "目标与非目标", "现状分析", "技术方案", "风险", "回滚", "追溯矩阵"],
    "code_plan": ["需求依据", "改动范围", "改动细则", "改动原因", "禁止改动", "追溯矩阵"],
    "test_design": ["需求依据", "覆盖策略", "测试用例", "测试目的", "覆盖矩阵"],
    "implementation": ["需求依据", "批准基线", "实际改动", "Git 证据", "方案偏差"],
    "test_execution": ["需求依据", "实际变更审查", "可执行测试", "执行结果", "结论"],
    "summary": ["需求背景", "迭代内容", "测试结论", "追溯矩阵", "环节评分", "亮点", "缺点", "改进项"],
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


def project_defaults() -> tuple[str, str]:
    starts = [Path.cwd().resolve(), Path(__file__).resolve().parent]
    seen = set()
    for start in starts:
        for candidate in [start, *start.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            config_path = candidate / ".harnove" / "config.json"
            if not config_path.is_file():
                continue
            config = json.loads(config_path.read_text(encoding="utf-8"))
            home = config_path.parent
            project = (home / config.get("project_root", "..")).resolve()
            return str((project / config.get("repo_root", ".")).resolve()), str((home / config.get("archive_root", "iterations")).resolve())
    return ".", "iterations"


def load(archive: Path) -> dict:
    path = archive / "state.json"
    if not path.is_file():
        raise SystemExit(f"找不到状态文件: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


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
    commands = {
        f"git-head-v{version:03d}.txt": ("rev-parse", "HEAD"),
        f"git-status-v{version:03d}.txt": ("status", "--short"),
        f"git-diff-stat-v{version:03d}.txt": ("diff", "--stat", "--", "."),
        f"git-diff-v{version:03d}.patch": ("diff", "--binary", "--", "."),
    }
    written, unavailable = [], False
    for name, args in commands.items():
        value = git(Path(state["repo"]), *args)
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
        f"- 仓库基线：`{state.get('git_baseline') or 'GIT_UNAVAILABLE'}`", "",
    ]
    for section in REQUIRED_SECTIONS[stage]:
        lines += [f"## {section}", "", PLACEHOLDER, ""]
    return "\n".join(lines)


def validate_artifact(path: Path, stage: str) -> list[str]:
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
    state["status"] = "drafting"


def cmd_init(a: argparse.Namespace) -> None:
    root, repo = Path(a.root).resolve(), Path(a.repo).resolve()
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
    for folder in sorted(set(DIRS.values())) + ["reviews", "00-input/clarifications"]:
        (archive / folder).mkdir(parents=True, exist_ok=True)
    baseline = git(repo, "rev-parse", "HEAD")
    state = {
        "schema_version": 3, "iteration_id": ident, "requirement": req,
        "archive": str(archive), "repo": str(repo), "git_baseline": baseline,
        "created_at": now(), "history": [], "approved": {}, "test_cycles": 0,
        "stage_versions": {stage: 0 for stage in STAGES},
    }

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
            "version": 1, "status": "drafting",
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
            "prd_sha256": None, "stage": "prd_intake", "version": 1, "status": "drafting",
        })
        state["stage_versions"]["prd_intake"] = 1
        target = artifact_path(archive, state)
        target.write_text(prd_template(state, description, 1), encoding="utf-8")
    save(archive, state)
    print(archive)
    print(f"下一步: 填写 {target}")


def cmd_status(a: argparse.Namespace) -> None:
    archive, state = Path(a.archive).resolve(), load(Path(a.archive).resolve())
    keys = ["iteration_id", "requirement", "prd_source_type", "stage", "version", "status", "test_cycles"]
    print(json.dumps({k: state.get(k) for k in keys}, ensure_ascii=False, indent=2))
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
    if state["status"] != "drafting":
        raise SystemExit(f"当前状态 {state['status']} 不允许提交")
    stage, path = state["stage"], artifact_path(archive, state)
    if stage == "prd_intake":
        validate_original_input(archive, state)
    errors = validate_artifact(path, stage)
    if errors:
        raise SystemExit("提交校验失败:\n- " + "\n- ".join(errors))
    if stage == "prd_intake":
        submit_prd_intake(archive, state, path, getattr(a, "result", None))
        save(archive, state)
        cmd_status(argparse.Namespace(archive=str(archive)))
        return
    event = {"at": now(), "action": "submit", "stage": stage, "version": state["version"], "artifact": str(path.relative_to(archive)), "sha256": digest(path)}
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
            state["status"] = "drafting"
        else:
            advance(state)
    elif stage == "summary":
        state["status"], state["completed_at"] = "complete", now()
    else:
        advance(state)
    if state["status"] == "drafting":
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
    state["status"] = "drafting"
    target = artifact_path(archive, state)
    content = previous.read_text(encoding="utf-8")
    content += f"\n\n### 用户补充 {record['at']}（{a.responder}）\n\n{response.strip()}\n"
    target.write_text(content, encoding="utf-8")
    state["history"].append({**record, "action": "user_clarification", "record": str(record_path.relative_to(archive)), "to_version": state["version"]})
    save(archive, state)
    print(f"已保留澄清记录并创建新版本: {target}")
    print("请依据回复修订候选 PRD；仍有关键歧义可再次提交 needs-clarification，否则标记 READY 后提交。")


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
    review_path = archive / "reviews" / f"{stage}_v{version:03d}_{a.decision}_{dt.datetime.now():%Y%m%d%H%M%S}.json"
    review_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state["history"].append({**record, "action": "human_review", "record": str(review_path.relative_to(archive))})
    if a.decision == "approve":
        state["approved"][stage] = {"version": version, "artifact": str(path.relative_to(archive)), "sha256": digest(path)}
        if stage == "prd_intake":
            state["prd_snapshot"] = path.name
            state["prd_sha256"] = digest(path)
            create_requirement_baseline(archive, state)
        advance(state)
    else:
        state["version"] += 1
        state["stage_versions"][stage] = state["version"]
        state["status"] = "drafting"
    target = artifact_path(archive, state)
    if state["status"] == "drafting" and not target.exists():
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
    default_repo, default_archive = project_defaults()
    x = sub.add_parser("init")
    x.add_argument("--iteration-id", required=True); x.add_argument("--requirement", required=True)
    source = x.add_mutually_exclusive_group(required=True)
    source.add_argument("--prd"); source.add_argument("--description"); source.add_argument("--description-file")
    x.add_argument("--repo", default=default_repo); x.add_argument("--root", default=default_archive); x.set_defaults(func=cmd_init)
    x = sub.add_parser("status"); x.add_argument("--archive", required=True); x.set_defaults(func=cmd_status)
    x = sub.add_parser("submit"); x.add_argument("--archive", required=True); x.add_argument("--result", choices=["needs-clarification", "ready", "passed", "failed"]); x.set_defaults(func=cmd_submit)
    x = sub.add_parser("clarify"); x.add_argument("--archive", required=True); x.add_argument("--responder", required=True)
    response = x.add_mutually_exclusive_group(required=True); response.add_argument("--response"); response.add_argument("--response-file"); x.set_defaults(func=cmd_clarify)
    x = sub.add_parser("review"); x.add_argument("--archive", required=True); x.add_argument("--decision", required=True, choices=["approve", "reject"]); x.add_argument("--reviewer", required=True); x.add_argument("--feedback", default=""); x.set_defaults(func=cmd_review)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)
