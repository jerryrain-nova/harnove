#!/usr/bin/env python3
"""End-to-end tests for intake, subagent isolation, diagrams, and experience reuse."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import harnove
import version_policy


def ns_init(root: Path, iteration: str, requirement: str, **source: object) -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root / "iterations"), improve_root=str(root / "improve"), structure_root=str(root / "structure"), custom_root=str(root / "custom"), home=str(root),
        repo=str(root), iteration_id=iteration, iteration_name=requirement, requirement=requirement,
        mode=source.get("mode", "expert"),
        prd=source.get("prd"), description=source.get("description"),
        description_file=source.get("description_file"),
    )


def fill_current(archive: Path) -> None:
    state = harnove.load(archive)
    path = harnove.artifact_path(archive, state)
    text = path.read_text(encoding="utf-8").replace(
        harnove.PLACEHOLDER,
        "REQ-001：依据已批准 PRD。本节优先记录目标、范围、关键决策、验收或风险重点，并补充边界、历史经验采用情况、代码证据与预期结果。",
    )
    if state["stage"] in harnove.VERSIONED_DOCUMENT_STAGES:
        difference = (
            "首版文档，无上一版本；本版建立目标、范围、关键决策和审核基线。" if state["version"] == 1 else
            "相对上一版，本版根据已批准的变更影响预览补充回滚证据、收紧方案边界，并记录修改原因；其余已批准决策保持不变。"
        )
        text = re.sub(r"(^## 版本核心差异\s*$\n)[\s\S]*?(?=^## )", rf"\1\n{difference}\n\n", text, count=1, flags=re.MULTILINE)
        evolution = "\n".join(
            f"- v{value:03d}：" + ("建立首版阶段基线，归纳目标、范围和关键决策。" if value == 1 else f"落实第 {value - 1} 轮已批准反馈，归纳受影响章节和关键决策变化。")
            for value in range(state["version"], 0, -1)
        )
        if state["version"] > 1:
            if "## 版本演进摘要" in text:
                text = re.sub(r"(^## 版本演进摘要\s*$\n)[\s\S]*?(?=^## )", rf"\1\n{evolution}\n\n", text, count=1, flags=re.MULTILINE)
            else:
                text = re.sub(
                    r"(^## 版本核心差异\s*$\n[\s\S]*?)(?=^## )",
                    lambda match: match.group(1).rstrip() + "\n\n## 版本演进摘要\n\n" + evolution + "\n\n",
                    text, count=1, flags=re.MULTILINE,
                )
    text = text.replace("待细化输入", "需求输入").replace("待细化处理", "方案处理").replace("待细化输出", "可验证输出")
    text = text.replace("待细化变更一", "订单导出功能").replace("待细化变更二", "权限与数量边界")
    structure_file = Path(state["structure_root"]) / "project-structure.md"
    if state["stage"] == "summary":
        structure_file.write_text(
            f"# 项目结构解读\n\n- 最近迭代：{state['iteration_id']}\n\n## 功能模块\n\n订单模块负责查询与导出。\n\n"
            "## 代码框架\n\n采用分层服务结构。\n\n## 结构定义和关系\n\n控制器调用服务，服务访问仓储。\n\n"
            "## 代码证据\n\n依据当前仓库中的 prd.md 与已完成迭代 Git diff 抽象。\n",
            encoding="utf-8",
        )
    if state["stage"] in {"technical_design", "code_plan"}:
        text += "\nDIAGRAM_STATUS: INCLUDED\n\n```mermaid\nflowchart LR\n  A[输入] --> B[处理]\n  B --> C[输出]\n```\n"
    if state["stage"] == "code_plan":
        agile = state.get("workflow_mode") == "agile"
        text = text.replace("DESIGN_MODE: UNDECIDED", "DESIGN_MODE: SEPARATE")
        text = text.replace("CHANGE_SCOPE: UNDECIDED", "CHANGE_SCOPE: REGULAR")
        text = text.replace(
            "## 改动规模判断\n\n",
            "## 改动规模判断\n\n"
            + (
                "AFFECTED_FILES: 2\nAFFECTED_MODULES: 1\nCROSS_BOUNDARY_CHANGE: NO\n\n"
                "敏捷模式依据实时文件与符号检查记录范围，本阶段只输出代码改动方案，不修改实际代码。\n\n"
                if agile else
                "AFFECTED_FILES: 5\nAFFECTED_MODULES: 2\nCROSS_BOUNDARY_CHANGE: YES\n\n"
                "依据实时文件与符号检查，本次变更跨越多个模块，代码方案与测试方案保持独立审核。\n\n"
            ),
        )
    text += "\n" + ("REQ-001 的范围证据、实现约束与验证说明。" * 40) + "\n"
    path.write_text(text, encoding="utf-8")


def fill_combined_code_plan(archive: Path) -> None:
    fill_current(archive)
    state = harnove.load(archive)
    assert state["stage"] == "code_plan"
    path = harnove.artifact_path(archive, state)
    text = path.read_text(encoding="utf-8")
    text = text.replace("DESIGN_MODE: SEPARATE", "DESIGN_MODE: COMBINED")
    text = text.replace("CHANGE_SCOPE: REGULAR", "CHANGE_SCOPE: SMALL")
    text = text.replace("AFFECTED_FILES: 5", "AFFECTED_FILES: 2")
    text = text.replace("AFFECTED_MODULES: 2", "AFFECTED_MODULES: 1")
    text = text.replace("CROSS_BOUNDARY_CHANGE: YES", "CROSS_BOUNDARY_CHANGE: NO")
    text = text.replace(
        "依据实时文件与符号检查，本次变更跨越多个模块，代码方案与测试方案保持独立审核。",
        "依据实时文件与符号检查，本次只改动同一模块内两个文件，不改变公共契约、数据结构或跨模块边界，适合合并设计与审核。",
    )
    text += """
## 测试总览

REQ-001：测试集中验证同一模块内两个文件的局部行为，覆盖正常、边界与失败路径，并复用现有测试入口。

## 测试方案

REQ-001：使用现有单元测试与模块级集成测试验证改动，不引入跨模块环境；失败时保留日志并打回同一实现分支修复，所有强制用例必须通过。

## 覆盖策略

REQ-001：覆盖主要输入、空输入、权限拒绝和依赖异常，确认未改动的公共接口行为保持稳定。

## 测试用例

REQ-001：用例一验证正常结果；用例二验证边界；用例三验证依赖失败时返回既有错误语义。

## 测试目的

REQ-001：证明局部实现满足需求且不会越过批准范围或破坏同模块既有行为。

## 覆盖矩阵

| 需求 | 代码范围 | 用例 | 预期 |
| --- | --- | --- | --- |
| REQ-001 | 同模块两个文件 | 正常/边界/失败 | 全部强制用例通过 |
"""
    path.write_text(text, encoding="utf-8")


def run_subagent(archive: Path, writer=None, branch: str | None = None) -> str:
    before = harnove.load(archive)
    agent_id = f"agent-{before['stage']}-v{before['version']}-{len(before.get('used_agent_ids', [])) + 1}"
    harnove.cmd_dispatch(argparse.Namespace(archive=str(archive), agent_id=agent_id, orchestrator="smoke-main", branch=branch))
    state = harnove.load(archive)
    run_id = state["active_agent"]["run_id"]
    target = harnove.artifact_path(archive, state)
    if not target.exists():
        target.write_text(harnove.template(state, state["stage"], state["version"]), encoding="utf-8")
    (writer or fill_current)(archive)
    harnove.cmd_agent_complete(argparse.Namespace(
        archive=str(archive), run_id=run_id, result="succeeded", evidence="子 Agent 已完成当前环节产物并返回证据。"
    ))
    return run_id


def submit(archive: Path, result: str | None = None, branch: str | None = None) -> None:
    run_subagent(archive, branch=branch)
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=result))


def review(
    archive: Path, decision: str, feedback: str = "", human_confirmation: str | None = None,
) -> None:
    harnove.cmd_review(argparse.Namespace(
        archive=str(archive), decision=decision, reviewer="smoke-human", feedback=feedback,
        human_confirmation=(
            human_confirmation if human_confirmation is not None
            else "人工明确批准当前完整文档" if decision == "approve" else ""
        ),
    ))


def decide_repair_branch(archive: Path, strategy: str, branch: str | None = None) -> None:
    harnove.cmd_repair_branch_decision(argparse.Namespace(
        archive=str(archive), strategy=strategy, responder="smoke-human", branch=branch,
    ))


def approve_document_change(archive: Path, feedback: str, revise_feedback: str = "") -> None:
    before = harnove.load(archive)
    source_path = harnove.artifact_path(archive, before)
    source_bytes = source_path.read_bytes()
    next_state = dict(before)
    next_state["version"] = before["version"] + 1
    next_path = harnove.artifact_path(archive, next_state)
    review(archive, "reject", feedback)
    state = harnove.load(archive)
    assert state["status"] == "awaiting_change_preview" and state["version"] == before["version"]
    assert not next_path.exists()
    preview_sections = {
        "prd_intake": "范围内,验收标准,约束与依赖",
        "technical_design": "技术方案,风险,回滚",
        "code_plan": "改动范围,改动细则,禁止改动",
        "test_design": "覆盖策略,测试用例,覆盖矩阵",
    }[state["stage"]]
    harnove.cmd_change_preview(argparse.Namespace(
        archive=str(archive), orchestrator="smoke-main", sections=preview_sections,
        summary="根据用户反馈，范围、验收标准和风险章节将调整；保留未受影响的已批准边界，并在新版本中归纳记录修改原因。", summary_file=None,
    ))
    assert harnove.load(archive)["status"] == "awaiting_change_confirmation"
    if revise_feedback:
        harnove.cmd_change_decision(argparse.Namespace(
            archive=str(archive), decision="revise", reviewer="smoke-human", feedback=revise_feedback,
        ))
        state = harnove.load(archive)
        assert state["status"] == "awaiting_change_preview" and state["version"] == before["version"]
        assert not next_path.exists()
        harnove.cmd_change_preview(argparse.Namespace(
            archive=str(archive), orchestrator="smoke-main", sections=preview_sections,
            summary="结合追加反馈，范围、验收标准、权限边界和风险章节将变化；不扩展其他业务能力，并在新版本中保留精简的累计版本摘要。", summary_file=None,
        ))
    harnove.cmd_change_decision(argparse.Namespace(
        archive=str(archive), decision="approve", reviewer="smoke-human", feedback="",
    ))
    state = harnove.load(archive)
    assert state["status"] == "awaiting_dispatch" and state["version"] == before["version"] + 1
    assert next_path.is_file()
    assert source_path.read_bytes() == source_bytes
    if before["version"] == 1:
        assert "## 版本演进摘要" not in next_path.read_text(encoding="utf-8")
    context = state["approved_change_preview"]
    assert context["from_version"] == before["version"] and context["to_version"] == before["version"] + 1


def write_intake_file(
    path: Path, status: str, questions: str, supplement: str, iteration_name: str,
    version: int, workflow_mode: str = "expert",
) -> None:
    detail = "用户需要批量导出订单；所有未明确能力均不进入本次范围。" * 25
    difference = "首版候选文档，无上一版本；本版建立需求和验收基线。" if version == 1 else "相对上一版，本版落实已批准反馈，调整范围依据、权限约束与验收决策，同时保留其他已确认边界和不变项。"
    evolution = "\n".join(
        f"- v{value:03d}：" + ("建立首版需求基线，归纳目标、范围和验收边界。" if value == 1 else f"落实第 {value - 1} 轮反馈，归纳范围、验收和关键决策变化。")
        for value in range(version, 0, -1)
    )
    evolution_section = f"\n## 版本演进摘要\n\n{evolution}\n" if version > 1 else ""
    path.write_text(f"""# 候选 PRD

- 文档版本：v{version:03d}
- 状态标记：`PRD_STATUS: {status}`
- 迭代名称：{iteration_name}
- 工作流模式：`{workflow_mode.upper()}`

## 文档总览

REQ-001：目标是在订单页提供受现有权限边界约束的批量导出；范围只包含列表入口与结果，关键验收聚焦格式、数量上限和无权限处理，不引入定时任务或新权限体系。

## 版本核心差异

{difference}
{evolution_section}

## 原始需求描述

给订单页增加批量导出。{detail}

## 目标与背景

REQ-001：减少逐条整理订单的人工成本。

## 用户与场景

运营人员在订单列表选择记录后发起导出。

## 功能需求

REQ-001：按当前筛选条件导出订单。

## 非功能需求

未提出，由现有系统约束决定。

## 范围内

订单列表导出入口与导出结果。

## 范围外

定时导出、邮件投递及新权限体系。

## 验收标准

REQ-001：满足已确认格式和数量边界时生成可下载文件。

## 约束与依赖

复用现有登录态与订单查询条件。

## 信息补充记录

| 补充项 | 补充内容 | 依据 | 补充原因 | 确认状态 |
| --- | --- | --- | --- | --- |
| 导出边界 | CSV，最多 10,000 条 | 用户确认 | 形成可验收边界 | 已确认 |

## 待确认问题

{questions}

## 用户补充记录

{supplement}
""", encoding="utf-8")


def intake_writer(status: str, questions: str, supplement: str = "暂无。"):
    def write(archive: Path) -> None:
        state = harnove.load(archive)
        write_intake_file(
            harnove.artifact_path(archive, state), status, questions, supplement,
            state["iteration_name"], state["version"], state.get("workflow_mode", "expert"),
        )
    return write


def test_existing_prd(root: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    prd = root / "prd.md"
    prd.write_text("# PRD\n\nREQ-001：只实现明确范围。\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "prd.md"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Harnove Test", "-c", "user.email=harnove@example.invalid", "commit", "-qm", "baseline"], check=True)
    harnove.cmd_init(ns_init(root, "SMOKE-001", "state-machine", prd=str(prd)))
    archive = next((root / "iterations").glob("*_SMOKE-001_state-machine"))
    state = harnove.load(archive)
    assert state["status"] == "awaiting_dispatch"
    assert {path.name for path in archive.iterdir() if path.is_dir()} == {
        "00-input", "01-technical-design", "02-code-plan", "03-test-design",
        "04-implementation", "05-test-execution", "06-summary", "reviews", "agent-runs",
    }
    assert state["timeout_profile"]["project_scale"]["scale"] == "unknown"
    assert state["timeout_profile"]["stage_minutes"] == harnove.DEFAULT_STAGE_TIMEOUT_MINUTES
    assert (root / "custom" / "user.md").is_file()
    assert (root / "custom" / "self.md").is_file()
    initial_custom = archive / "00-input" / state["custom_index"]
    assert "user.md" in initial_custom.read_text(encoding="utf-8") and "self.md" in initial_custom.read_text(encoding="utf-8")
    harnove.cmd_customize(argparse.Namespace(
        archive=str(archive), target="user", mode="append", actor="smoke-human",
        content="所有导出能力必须沿用当前权限边界，并在方案中显式说明。", content_file=None,
    ))
    state = harnove.load(archive)
    assert "权限边界" in (root / "custom" / "user.md").read_text(encoding="utf-8")
    assert "权限边界" in (archive / "00-input" / state["custom_index"]).read_text(encoding="utf-8")
    original = archive / "00-input" / state["original_input_snapshot"]
    assert original.read_text(encoding="utf-8") == prd.read_text(encoding="utf-8")

    run_subagent(archive, intake_writer("READY", "无（边界已确认）"))
    original.write_text("tampered\n", encoding="utf-8")
    try:
        harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
        raise AssertionError("tampered original input was accepted")
    except SystemExit as exc:
        assert "原始输入副本" in str(exc)
    original.write_text(prd.read_text(encoding="utf-8"), encoding="utf-8")
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    approve_document_change(archive, "补充批量导出的范围依据", "权限边界也应纳入变更影响说明")
    run_subagent(archive, intake_writer("READY", "无（边界已确认）", "已按审核意见补充。"))
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    before_human_approval = harnove.load(archive)
    try:
        harnove.cmd_review(argparse.Namespace(
            archive=str(archive), decision="approve", reviewer="smoke-human",
            feedback="", human_confirmation="",
        ))
        raise AssertionError("document advanced without explicit human approval evidence")
    except SystemExit as exc:
        assert "--human-confirmation" in str(exc)
    after_missing_confirmation = harnove.load(archive)
    assert after_missing_confirmation["stage"] == before_human_approval["stage"]
    assert after_missing_confirmation["version"] == before_human_approval["version"]
    assert after_missing_confirmation["status"] == before_human_approval["status"]
    review(archive, "approve")

    assert harnove.load(archive)["stage"] == "technical_design"

    # Diagram contract accepts a real Mermaid block and rejects a content-free N/A escape.
    run_subagent(archive)
    design_path = harnove.artifact_path(archive, harnove.load(archive))
    valid_design = design_path.read_text(encoding="utf-8")
    assert not harnove.validate_artifact(design_path, "technical_design", harnove.load(archive))
    design_path.write_text(valid_design.replace("DIAGRAM_STATUS: INCLUDED", "DIAGRAM_STATUS: NOT_APPLICABLE").replace("```mermaid", "```text"), encoding="utf-8")
    assert any("NOT_APPLICABLE" in error for error in harnove.validate_artifact(design_path, "technical_design"))
    design_path.write_text(valid_design, encoding="utf-8")
    html_design = valid_design.replace("PRESENTATION_FORMAT: MD", "PRESENTATION_FORMAT: HTML")
    design_path.write_text(html_design, encoding="utf-8")
    html_path = design_path.with_suffix(".html")
    html_path.write_text("<html><body>" + ("结构关系可视化说明" * 80) + "</body></html>", encoding="utf-8")
    assert not harnove.validate_artifact(design_path, "technical_design", harnove.load(archive))
    html_path.unlink()
    design_path.write_text(valid_design, encoding="utf-8")

    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=None)); approve_document_change(archive, "补充回滚证据")
    run_subagent(archive)
    design_v2 = harnove.artifact_path(archive, harnove.load(archive))
    design_v2_text = design_v2.read_text(encoding="utf-8")
    reversed_history = design_v2_text.replace(
        "- v002：落实第 1 轮已批准反馈，归纳受影响章节和关键决策变化。\n- v001：建立首版阶段基线，归纳目标、范围和关键决策。",
        "- v001：建立首版阶段基线，归纳目标、范围和关键决策。\n- v002：落实第 1 轮已批准反馈，归纳受影响章节和关键决策变化。",
    )
    design_v2.write_text(reversed_history, encoding="utf-8")
    assert any("当前版本到初代版本" in error for error in harnove.validate_artifact(design_v2, "technical_design", harnove.load(archive)))
    design_v2.write_text(design_v2_text, encoding="utf-8")
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=None)); review(archive, "approve")
    submit(archive); review(archive, "approve")
    submit(archive); review(archive, "approve")
    reviewed_state = harnove.load(archive)
    assert set(harnove.REVIEW_GATED) <= set(reviewed_state["approved"])
    for reviewed_stage in harnove.REVIEW_GATED:
        approval = reviewed_state["approved"][reviewed_stage]
        assert approval["reviewer"] == "smoke-human"
        assert approval["human_confirmation"] == "人工明确批准当前完整文档"
        review_record = archive / approval["review_record"]
        assert review_record.is_file()
        review_payload = json.loads(review_record.read_text(encoding="utf-8"))
        assert review_payload["human_confirmation"] == "人工明确批准当前完整文档"
    assert not harnove.structure_files(Path(harnove.load(archive)["structure_root"]))
    submit(archive)
    implementation_state = harnove.load(archive)
    first_branch = implementation_state["implementation_branches"][-1]["name"]
    assert first_branch == "tmp/state-machine-1"
    (root / "implementation-marker.txt").write_text("initial implementation\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "implementation-marker.txt"], check=True)
    subprocess.run([
        "git", "-C", str(root), "-c", "user.name=Harnove Test", "-c", "user.email=harnove@example.invalid",
        "commit", "-qm", "initial implementation marker",
    ], check=True)
    original_branch = implementation_state["implementation_branch"]["previous_branch"]
    subprocess.run(["git", "-C", str(root), "switch", original_branch], check=True, capture_output=True)
    submit(archive, "failed")
    assert harnove.git(root, "branch", "--show-current") == first_branch
    pending_state = harnove.load(archive)
    assert pending_state["status"] == "awaiting_repair_branch_decision"
    assert pending_state["pending_repair_branch_decision"]["current_branch"] == first_branch
    assert pending_state["pending_repair_branch_decision"]["suggested_new_branch"] == "tmp/state-machine-2"
    try:
        harnove.cmd_dispatch(argparse.Namespace(
            archive=str(archive), agent_id="premature-fix-agent", orchestrator="smoke-main", branch=None,
        ))
        raise AssertionError("repair dispatched before user selected a branch strategy")
    except SystemExit as exc:
        assert "不允许派发" in str(exc)
    decide_repair_branch(archive, "reuse")
    try:
        harnove.cmd_dispatch(argparse.Namespace(
            archive=str(archive), agent_id="wrong-fix-branch-agent", orchestrator="smoke-main",
            branch="feature/state-machine-fix-round-2",
        ))
        raise AssertionError("test fix was allowed to switch implementation branches")
    except SystemExit as exc:
        assert "选择复用原有分支" in str(exc)
    submit(archive)
    second_branch = harnove.load(archive)["implementation_branches"][-1]["name"]
    assert second_branch == first_branch
    assert len({item["name"] for item in harnove.load(archive)["implementation_branches"]}) == 1
    (root / "repair-marker.txt").write_text("repair on original branch\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "repair-marker.txt"], check=True)
    subprocess.run([
        "git", "-C", str(root), "-c", "user.name=Harnove Test", "-c", "user.email=harnove@example.invalid",
        "commit", "-qm", "repair marker",
    ], check=True)
    reused_branch_head = harnove.git(root, "rev-parse", "HEAD")
    submit(archive, "failed")
    assert harnove.load(archive)["status"] == "awaiting_repair_branch_decision"
    try:
        decide_repair_branch(archive, "new", first_branch)
        raise AssertionError("new repair branch decision accepted the current implementation branch")
    except SystemExit as exc:
        assert "必须不同于当前实现分支" in str(exc)
    new_fix_branch = "tmp/state-machine-3"
    decide_repair_branch(archive, "new")
    subprocess.run(["git", "-C", str(root), "switch", original_branch], check=True, capture_output=True)
    submit(archive)
    third_branch = harnove.load(archive)["implementation_branches"][-1]["name"]
    assert third_branch == new_fix_branch
    assert harnove.git(root, "branch", "--show-current") == new_fix_branch
    assert subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", reused_branch_head, new_fix_branch],
        check=False,
    ).returncode == 0
    submit(archive, "passed")
    assert harnove.load(archive)["stage"] == "summary"
    submit(archive)
    state = harnove.load(archive)
    assert state["status"] == "complete"
    assert state["test_cycles"] == 3
    assert state["initial_implementation_branch"]["name"] == first_branch
    assert state["implementation_branch"]["name"] == new_fix_branch
    assert state["delivery_branch"]["name"] == new_fix_branch
    assert [item["strategy"] for item in state["repair_branch_decisions"]] == ["reuse", "new"]
    assert harnove.git(root, "branch", "--show-current") == new_fix_branch
    assert len(state["used_agent_ids"]) == len(set(state["used_agent_ids"]))
    assert len(list((archive / "agent-runs").glob("*_work-order.json"))) == len(state["used_agent_ids"])
    improvement = Path(state["improvement_record"]["path"])
    assert improvement.is_file() and improvement.parent.resolve() == (root / "improve").resolve()
    custom_experience = Path(state["custom_experience_record"]["path"])
    assert custom_experience.resolve() == (root / "custom" / "self.md").resolve()
    assert "FEEDBACK_EXPERIENCE_STATUS: CAPTURED" in custom_experience.read_text(encoding="utf-8")
    return improvement


def test_natural_language_reuses_experience(root: Path, improvement: Path) -> None:
    structure_root = root / "structure"
    (structure_root / "modules.md").write_text(
        "# 模块补充\n\n" + "\n".join(f"- 模块 {index}：职责与依赖关系" for index in range(8)),
        encoding="utf-8",
    )
    (structure_root / "relations.md").write_text(
        "# 关系补充\n\n" + "\n".join(f"- 关系 {index}：模块调用与数据流" for index in range(8)),
        encoding="utf-8",
    )
    harnove.cmd_init(ns_init(
        root, "SMOKE-002", "order-export",
        description="给订单页增加批量导出，但格式和数量上限还没确定。",
    ))
    archive = next((root / "iterations").glob("*_SMOKE-002_order-export"))
    initial_timeout_profile = harnove.load(archive)["timeout_profile"]
    assert initial_timeout_profile["project_scale"]["scale"] == "non_simple"
    assert initial_timeout_profile["stage_minutes"]["technical_design"] == 68
    context = archive / "00-input" / harnove.load(archive)["improvement_index"]
    assert improvement.name in context.read_text(encoding="utf-8")
    custom_context = archive / "00-input" / harnove.load(archive)["custom_index"]
    custom_text = custom_context.read_text(encoding="utf-8")
    assert "user.md" in custom_text and "self.md" in custom_text and "权限边界" in custom_text
    try:
        harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="needs-clarification"))
        raise AssertionError("orchestrator bypassed subagent dispatch")
    except SystemExit as exc:
        assert "不允许提交" in str(exc)

    run_subagent(archive, intake_writer("NEEDS_CLARIFICATION", "1. 导出格式是什么？\n2. 数量上限是多少？"))
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="needs-clarification"))
    harnove.cmd_clarify(argparse.Namespace(
        archive=str(archive), responder="product-owner", response="CSV，最多 10,000 条。", response_file=None,
    ))
    assert harnove.load(archive)["status"] == "awaiting_dispatch"
    run_subagent(archive, intake_writer("READY", "无（边界已确认）", "用户确认：CSV，最多 10,000 条。"))
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    review(archive, "approve")
    state = harnove.load(archive)
    assert state["stage"] == "technical_design" and state["status"] == "awaiting_dispatch"
    harnove.cmd_dispatch(argparse.Namespace(archive=str(archive), agent_id="live-code-design", orchestrator="smoke-main", branch=None))
    dispatched_state = harnove.load(archive)
    work_order = json.loads((archive / dispatched_state["active_agent"]["work_order"]).read_text(encoding="utf-8"))
    assert "structure_context" not in work_order
    assert work_order["timeout_minutes"] == 68 and work_order["expires_at"]
    try:
        harnove.cmd_abandon(argparse.Namespace(
            archive=str(archive), run_id=dispatched_state["active_agent"]["run_id"],
            reason="尚未过期", timed_out=True,
        ))
        raise AssertionError("active lease was incorrectly recorded as timed out")
    except SystemExit as exc:
        assert "尚未到期" in str(exc)
    dispatched_state["active_agent"]["expires_at"] = "2000-01-01T00:00:00+00:00"
    harnove.save(archive, dispatched_state)
    try:
        harnove.cmd_agent_complete(argparse.Namespace(
            archive=str(archive), run_id=dispatched_state["active_agent"]["run_id"],
            result="succeeded", evidence="迟到完成不应被接受。",
        ))
        raise AssertionError("expired subagent completion was accepted")
    except SystemExit as exc:
        assert "租约已过期" in str(exc)
    harnove.cmd_abandon(argparse.Namespace(
        archive=str(archive), run_id=dispatched_state["active_agent"]["run_id"],
        reason="子 Agent 达到租约时间", timed_out=True,
    ))
    expanded = harnove.load(archive)["timeout_profile"]
    assert expanded["timeout_count"] == 1
    assert expanded["learned_multiplier"] == 1.5
    assert expanded["stage_minutes"]["technical_design"] == 101
    policy = json.loads((root / "timeout-policy.json").read_text(encoding="utf-8"))
    assert policy["history"][-1]["increase_rate"] == 0.5

    harnove.cmd_init(ns_init(
        root, "SMOKE-003", "timeout-reuse",
        description="验证后续迭代复用已经扩大的子 Agent 超时阈值。",
    ))
    reused_archive = next((root / "iterations").glob("*_SMOKE-003_timeout-reuse"))
    reused_profile = harnove.load(reused_archive)["timeout_profile"]
    assert reused_profile["timeout_count"] == 1
    assert reused_profile["stage_minutes"]["technical_design"] == 101


def test_combined_code_and_test_design(root: Path) -> None:
    harnove.cmd_init(ns_init(
        root, "SMOKE-004", "combined-design",
        description="在单一模块内调整两个文件的局部校验逻辑，不改变公共接口或数据结构。",
    ))
    archive = next((root / "iterations").glob("*_SMOKE-004_combined-design"))
    run_subagent(archive, intake_writer("READY", "无（边界已确认）", "范围已明确。"))
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    review(archive, "approve")
    submit(archive)
    review(archive, "approve")
    run_subagent(archive, fill_combined_code_plan)
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=None))
    state = harnove.load(archive)
    assert state["stage"] == "code_plan" and state["design_mode"] == "combined"
    combined_path = harnove.artifact_path(archive, state)
    combined_sha = harnove.digest(combined_path)
    review(archive, "approve")
    state = harnove.load(archive)
    assert state["stage"] == "implementation" and state["status"] == "awaiting_dispatch"
    assert state["stage_versions"]["test_design"] == 0
    assert state["approved"]["code_plan"]["artifact"] == state["approved"]["test_design"]["artifact"]
    assert state["approved"]["code_plan"]["sha256"] == combined_sha
    assert state["approved"]["test_design"]["combined_with"] == "code_plan"
    assert state["skipped_stages"][-1]["stage"] == "test_design"


def test_agile_mode_is_independent(root: Path) -> None:
    harnove.cmd_init(ns_init(
        root, "SMOKE-005", "agile-flow", mode="agile",
        description="在订单模块中调整两个文件的局部校验逻辑，但错误提示是否沿用现状尚未确认。",
    ))
    archive = next((root / "iterations").glob("*_SMOKE-005_agile-flow"))
    state = harnove.load(archive)
    assert state["workflow_mode"] == "agile"
    assert harnove.workflow_stages(state) == ["prd_intake", "code_plan", "implementation", "summary"]
    assert {path.name for path in archive.iterdir() if path.is_dir()} == {
        "00-input", "02-code-plan", "04-implementation", "06-summary", "reviews", "agent-runs",
    }
    assert (archive / "00-input" / "clarifications").is_dir()
    assert not any((archive / folder).exists() for folder in [
        "01-technical-design", "03-test-design", "05-test-execution",
    ])
    original_state = json.loads(json.dumps(state))
    state["stage"] = "technical_design"
    harnove.save(archive, state)
    try:
        harnove.load(archive)
        raise AssertionError("agile state accepted an expert-only stage")
    except SystemExit as exc:
        assert "拒绝跨模式推进" in str(exc)
    harnove.save(archive, original_state)

    run_subagent(archive, intake_writer("NEEDS_CLARIFICATION", "1. 错误提示是否沿用当前系统文案？"))
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="needs-clarification"))
    harnove.cmd_clarify(argparse.Namespace(
        archive=str(archive), responder="product-owner",
        response="沿用当前系统错误提示，不新增提示类型。", response_file=None,
    ))
    run_subagent(
        archive,
        intake_writer("READY", "无（边界已确认）", "用户确认：沿用当前系统错误提示。"),
    )
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    review(archive, "approve", human_confirmation="批准当前PRD")
    state = harnove.load(archive)
    assert state["stage"] == "code_plan"
    assert state["agile_requirements_confirmation"]["human_confirmation"] == "批准当前PRD"
    assert state["agile_requirements_confirmation"]["no_pending_clarification"] is True
    assert state["agile_requirements_confirmation"]["approval_effect"] == (
        "approved_ready_prd_implies_no_pending_clarification"
    )
    assert state["stage_versions"]["technical_design"] == 0

    run_subagent(archive)
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=None))
    assert harnove.load(archive)["design_mode"] == "agile"
    approve_document_change(archive, "补充错误分支的具体代码改动点和不变边界")
    run_subagent(archive)
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=None))
    review(archive, "approve")
    state = harnove.load(archive)
    assert state["stage"] == "implementation" and state["status"] == "awaiting_dispatch"
    assert set(state["approved"]) == {"prd_intake", "code_plan"}
    assert state["stage_versions"]["test_design"] == 0

    submit(archive)
    state = harnove.load(archive)
    assert state["stage"] == "summary"
    assert state["stage_versions"]["test_execution"] == 0
    assert state["delivery_branch"]["name"] == state["implementation_branch"]["name"]
    submit(archive)
    state = harnove.load(archive)
    assert state["status"] == "complete" and state["test_cycles"] == 0
    summary = harnove.artifact_path(archive, state)
    assert "## 代码改动点" in summary.read_text(encoding="utf-8")


def test_schema8_branch_migration(root: Path) -> None:
    archive = root / "schema8-migration"
    archive.mkdir()
    state = {
        "schema_version": 8, "stage": "summary", "version": 1, "status": "complete",
        "requirement": "migration", "iteration_name": "migration", "history": [],
        "used_agent_ids": [], "improvement_index": "existing.md", "custom_index": "existing.md",
        "implementation_branches": [
            {"stage_version": 1, "name": "feature/original", "previous_branch": "main", "source": "user_or_custom"},
            {"stage_version": 2, "name": "feature/old-fix", "previous_branch": "feature/original", "source": "user_or_custom"},
        ],
    }
    (archive / "state.json").write_text(json.dumps(state), encoding="utf-8")
    migrated = harnove.load(archive)
    assert migrated["schema_version"] == 12
    assert migrated["workflow_mode"] == "expert"
    assert migrated["initial_implementation_branch"]["name"] == "feature/original"
    assert migrated["implementation_branch"]["name"] == "feature/old-fix"
    assert migrated["repair_branch_decisions"] == []


def main() -> None:
    package = json.loads((Path(__file__).resolve().parent.parent / "harnove-package.json").read_text(encoding="utf-8"))
    assert version_policy.expected(version_policy.parse("5.3.0"), "feature") == version_policy.parse(package["version"])
    assert [harnove.timeout_increase_rate(index) for index in range(1, 9)] == [
        0.5, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
    ]
    with tempfile.TemporaryDirectory(prefix="harnove-") as tmp, redirect_stdout(StringIO()):
        root = Path(tmp)
        improvement = test_existing_prd(root)
        test_natural_language_reuses_experience(root, improvement)
        test_combined_code_and_test_design(root)
        test_agile_mode_is_independent(root)
        test_schema8_branch_migration(root)
    print("self-test passed")


if __name__ == "__main__":
    main()
