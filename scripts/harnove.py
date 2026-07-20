#!/usr/bin/env python3
"""Deterministic, dependency-free state machine for PRD-driven development iterations."""

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

STAGES = ["technical_design", "code_plan", "test_design", "implementation", "test_execution", "summary"]
GATED = {"technical_design", "code_plan", "test_design"}
DIRS = {
    "technical_design": "01-technical-design",
    "code_plan": "02-code-plan",
    "test_design": "03-test-design",
    "implementation": "04-implementation",
    "test_execution": "05-test-execution",
    "summary": "06-summary",
}
CN_NAMES = {
    "technical_design": "技术方案",
    "code_plan": "代码修改方案",
    "test_design": "测试方案",
    "implementation": "代码变更记录",
    "test_execution": "测试报告",
    "summary": "迭代总结",
}
REQUIRED_SECTIONS = {
    "technical_design": ["需求依据", "目标与非目标", "现状分析", "技术方案", "风险", "回滚", "追溯矩阵"],
    "code_plan": ["需求依据", "改动范围", "改动细则", "改动原因", "禁止改动", "追溯矩阵"],
    "test_design": ["需求依据", "覆盖策略", "测试用例", "测试目的", "覆盖矩阵"],
    "implementation": ["需求依据", "批准基线", "实际改动", "Git 证据", "方案偏差"],
    "test_execution": ["需求依据", "实际变更审查", "可执行测试", "执行结果", "结论"],
    "summary": ["需求背景", "迭代内容", "测试结论", "追溯矩阵", "环节评分", "亮点", "缺点", "改进项"],
}


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
    """Find the nearest initialized project and return absolute repo/archive defaults."""
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
            harnove_home = config_path.parent
            project = (harnove_home / config.get("project_root", "..")).resolve()
            repo = (project / config.get("repo_root", ".")).resolve()
            archive = (harnove_home / config.get("archive_root", "iterations")).resolve()
            return str(repo), str(archive)
    return ".", "iterations"


def load(archive: Path) -> dict:
    state_path = archive / "state.json"
    if not state_path.is_file():
        raise SystemExit(f"找不到状态文件: {state_path}")
    return json.loads(state_path.read_text(encoding="utf-8"))


def save(archive: Path, state: dict) -> None:
    tmp = archive / "state.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(archive / "state.json")


def git(repo: Path, *args: str) -> str | None:
    try:
        p = subprocess.run(["git", "-C", str(repo), *args], text=True, encoding="utf-8",
                           errors="replace", capture_output=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def capture_git_evidence(archive: Path, state: dict) -> list[str]:
    """Capture immutable implementation evidence for the current implementation version."""
    repo = Path(state["repo"])
    folder = archive / DIRS["implementation"]
    version = state["version"]
    commands = {
        f"git-head-v{version:03d}.txt": ("rev-parse", "HEAD"),
        f"git-status-v{version:03d}.txt": ("status", "--short"),
        f"git-diff-stat-v{version:03d}.txt": ("diff", "--stat", "--", "."),
        f"git-diff-v{version:03d}.patch": ("diff", "--binary", "--", "."),
    }
    written = []
    unavailable = False
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
        target.write_text(
            f"captured_at={now()}\nrepo={repo}\nreason=Git command unavailable or repository invalid\n",
            encoding="utf-8",
        )
        written.append(str(target.relative_to(archive)))
    return written


def artifact_name(state: dict, stage: str, version: int) -> str:
    return f"{state['iteration_id']}_{state['requirement']}_{CN_NAMES[stage]}_v{version:03d}.md"


def artifact_path(archive: Path, state: dict) -> Path:
    return archive / DIRS[state["stage"]] / artifact_name(state, state["stage"], state["version"])


def template(state: dict, stage: str, version: int) -> str:
    lines = [
        f"# {state['iteration_id']} {state['requirement']} - {CN_NAMES[stage]}", "",
        f"- 迭代编号：{state['iteration_id']}", f"- 需求名称：{state['requirement']}",
        f"- 文档版本：v{version:03d}", f"- 角色：{CN_NAMES[stage]}", "- 状态：草稿",
        f"- PRD 快照：`00-input/{state['prd_snapshot']}`", f"- PRD SHA-256：`{state['prd_sha256']}`",
        f"- 仓库基线：`{state.get('git_baseline') or 'GIT_UNAVAILABLE'}`", "",
    ]
    for section in REQUIRED_SECTIONS[stage]:
        lines += [f"## {section}", "", "<!-- 待填写；所有判断须引用 REQ-xxx 或代码证据。 -->", ""]
    return "\n".join(lines)


def validate_artifact(path: Path, stage: str) -> list[str]:
    if not path.is_file():
        return [f"缺少产物: {path}"]
    text = path.read_text(encoding="utf-8")
    errors = [f"缺少章节: {s}" for s in REQUIRED_SECTIONS[stage] if f"## {s}" not in text]
    if "REQ-" not in text:
        errors.append("未引用任何稳定需求 ID（REQ-xxx）")
    if "<!-- 待填写" in text:
        errors.append("仍存在未填写的模板占位符")
    if len(text.strip()) < 500:
        errors.append("产物内容过短，无法形成可审核证据")
    return errors


def advance(state: dict) -> None:
    state["stage"] = STAGES[STAGES.index(state["stage"]) + 1]
    state["version"] = state["stage_versions"].get(state["stage"], 0) + 1
    state["stage_versions"][state["stage"]] = state["version"]
    state["status"] = "drafting"


def cmd_init(a: argparse.Namespace) -> None:
    root, prd, repo = Path(a.root).resolve(), Path(a.prd).resolve(), Path(a.repo).resolve()
    if not prd.is_file():
        raise SystemExit(f"PRD 不存在: {prd}")
    ident, req = safe_name(a.iteration_id), safe_name(a.requirement)
    archive = root / f"{dt.date.today():%Y%m%d}_{ident}_{req}"
    if archive.exists():
        raise SystemExit(f"归档目录已存在: {archive}")
    for folder in ["00-input", *DIRS.values(), "reviews"]:
        (archive / folder).mkdir(parents=True, exist_ok=True)
    snap = f"{ident}_{req}_PRD{prd.suffix or '.md'}"
    shutil.copy2(prd, archive / "00-input" / snap)
    baseline = git(repo, "rev-parse", "HEAD")
    state = {
        "schema_version": 1, "iteration_id": ident, "requirement": req,
        "archive": str(archive), "repo": str(repo), "prd_source": str(prd),
        "prd_snapshot": snap, "prd_sha256": digest(archive / "00-input" / snap),
        "git_baseline": baseline, "stage": "technical_design", "version": 1,
        "status": "drafting", "created_at": now(), "history": [], "approved": {},
        "test_cycles": 0, "stage_versions": {stage: (1 if stage == "technical_design" else 0) for stage in STAGES},
    }
    baseline_doc = archive / "00-input" / f"{ident}_{req}_需求基线.md"
    baseline_doc.write_text(
        f"# {ident} {req} - 需求基线\n\n- PRD：`{snap}`\n- SHA-256：`{state['prd_sha256']}`\n\n"
        "## 需求清单\n\n| ID | PRD 原文位置 | 需求原意摘要 | 验收标准 | 状态 |\n"
        "| --- | --- | --- | --- | --- |\n| REQ-001 | 待定位 | 待按原意摘录 | 待明确 | 待确认 |\n\n"
        "不得增加 PRD 未表达的业务范围；歧义进入待确认项。\n", encoding="utf-8")
    target = artifact_path(archive, state)
    target.write_text(template(state, state["stage"], 1), encoding="utf-8")
    save(archive, state)
    print(archive)
    print(f"下一步: 填写 {target}")


def cmd_status(a: argparse.Namespace) -> None:
    archive = Path(a.archive).resolve(); state = load(archive)
    print(json.dumps({k: state[k] for k in ["iteration_id", "requirement", "stage", "version", "status", "test_cycles"]}, ensure_ascii=False, indent=2))
    if state["status"] != "complete":
        print(f"产物: {artifact_path(archive, state)}")


def cmd_submit(a: argparse.Namespace) -> None:
    archive = Path(a.archive).resolve(); state = load(archive)
    if state["status"] != "drafting":
        raise SystemExit(f"当前状态 {state['status']} 不允许提交")
    stage, path = state["stage"], artifact_path(archive, state)
    errors = validate_artifact(path, stage)
    if errors:
        raise SystemExit("提交校验失败:\n- " + "\n- ".join(errors))
    event = {"at": now(), "action": "submit", "stage": stage, "version": state["version"], "artifact": str(path.relative_to(archive)), "sha256": digest(path)}
    if stage == "implementation":
        event["git_evidence"] = capture_git_evidence(archive, state)
    state["history"].append(event)
    if stage in GATED:
        state["status"] = "awaiting_human_review"
    elif stage == "test_execution":
        if a.result not in {"passed", "failed"}:
            raise SystemExit("测试执行提交必须提供 --result passed|failed")
        event["result"] = a.result; state["test_cycles"] += 1
        if a.result == "failed":
            state["stage"] = "implementation"
            state["version"] = state["stage_versions"].get("implementation", 0) + 1
            state["stage_versions"]["implementation"] = state["version"]
            state["status"] = "drafting"
        else:
            advance(state)
    elif stage == "summary":
        state["status"] = "complete"; state["completed_at"] = now()
    else:
        advance(state)
    if state["status"] == "drafting":
        nxt = artifact_path(archive, state)
        if not nxt.exists(): nxt.write_text(template(state, state["stage"], state["version"]), encoding="utf-8")
    save(archive, state); cmd_status(argparse.Namespace(archive=str(archive)))


def cmd_review(a: argparse.Namespace) -> None:
    archive = Path(a.archive).resolve(); state = load(archive)
    if state["status"] != "awaiting_human_review" or state["stage"] not in GATED:
        raise SystemExit("当前没有等待人工审核的闸门")
    if a.decision == "reject" and not a.feedback.strip():
        raise SystemExit("驳回必须提供可执行的 --feedback")
    stage, version, path = state["stage"], state["version"], artifact_path(archive, state)
    record = {
        "at": now(), "reviewer": a.reviewer, "decision": a.decision,
        "stage": stage, "version": version, "artifact": str(path.relative_to(archive)),
        "sha256": digest(path), "feedback": a.feedback.strip(),
    }
    review_path = archive / "reviews" / f"{stage}_v{version:03d}_{a.decision}_{dt.datetime.now():%Y%m%d%H%M%S}.json"
    review_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state["history"].append({**record, "action": "human_review", "record": str(review_path.relative_to(archive))})
    if a.decision == "approve":
        state["approved"][stage] = {"version": version, "artifact": str(path.relative_to(archive)), "sha256": digest(path)}
        advance(state)
    else:
        state["version"] += 1
        state["stage_versions"][stage] = state["version"]
        state["status"] = "drafting"
    nxt = artifact_path(archive, state)
    if state["status"] == "drafting" and not nxt.exists():
        nxt.write_text(template(state, state["stage"], state["version"]), encoding="utf-8")
    save(archive, state); cmd_status(argparse.Namespace(archive=str(archive)))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="人工闸门驱动的研发迭代状态机")
    sub = p.add_subparsers(dest="command", required=True)
    default_repo, default_archive = project_defaults()
    x = sub.add_parser("init"); x.add_argument("--iteration-id", required=True); x.add_argument("--requirement", required=True); x.add_argument("--prd", required=True); x.add_argument("--repo", default=default_repo); x.add_argument("--root", default=default_archive); x.set_defaults(func=cmd_init)
    x = sub.add_parser("status"); x.add_argument("--archive", required=True); x.set_defaults(func=cmd_status)
    x = sub.add_parser("submit"); x.add_argument("--archive", required=True); x.add_argument("--result", choices=["passed", "failed"]); x.set_defaults(func=cmd_submit)
    x = sub.add_parser("review"); x.add_argument("--archive", required=True); x.add_argument("--decision", required=True, choices=["approve", "reject"]); x.add_argument("--reviewer", required=True); x.add_argument("--feedback", default=""); x.set_defaults(func=cmd_review)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    try: args.func(args)
    except KeyboardInterrupt: sys.exit(130)
