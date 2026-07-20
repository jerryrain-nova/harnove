#!/usr/bin/env python3
"""End-to-end tests for intake, subagent isolation, diagrams, and experience reuse."""

from __future__ import annotations

import argparse
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import harnove


def ns_init(root: Path, iteration: str, requirement: str, **source: object) -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root / "iterations"), improve_root=str(root / "improve"), home=str(root),
        repo=str(root), iteration_id=iteration, requirement=requirement,
        prd=source.get("prd"), description=source.get("description"),
        description_file=source.get("description_file"),
    )


def fill_current(archive: Path) -> None:
    state = harnove.load(archive)
    path = harnove.artifact_path(archive, state)
    text = path.read_text(encoding="utf-8").replace(
        harnove.PLACEHOLDER,
        "REQ-001：依据已批准 PRD。本节记录结论、边界、历史经验采用情况与预期结果。",
    )
    text = text.replace("待细化输入", "需求输入").replace("待细化处理", "方案处理").replace("待细化输出", "可验证输出")
    if state["stage"] in {"technical_design", "code_plan"}:
        text += "\nDIAGRAM_STATUS: INCLUDED\n\n```mermaid\nflowchart LR\n  A[输入] --> B[处理]\n  B --> C[输出]\n```\n"
    text += "\n" + ("REQ-001 的范围证据、实现约束与验证说明。" * 40) + "\n"
    path.write_text(text, encoding="utf-8")


def run_subagent(archive: Path, writer=None) -> str:
    before = harnove.load(archive)
    agent_id = f"agent-{before['stage']}-v{before['version']}-{len(before.get('used_agent_ids', [])) + 1}"
    harnove.cmd_dispatch(argparse.Namespace(archive=str(archive), agent_id=agent_id, orchestrator="smoke-main"))
    state = harnove.load(archive)
    run_id = state["active_agent"]["run_id"]
    (writer or fill_current)(archive)
    harnove.cmd_agent_complete(argparse.Namespace(
        archive=str(archive), run_id=run_id, result="succeeded", evidence="子 Agent 已完成当前环节产物并返回证据。"
    ))
    return run_id


def submit(archive: Path, result: str | None = None) -> None:
    run_subagent(archive)
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=result))


def review(archive: Path, decision: str, feedback: str = "") -> None:
    harnove.cmd_review(argparse.Namespace(
        archive=str(archive), decision=decision, reviewer="smoke-human", feedback=feedback
    ))


def write_intake_file(path: Path, status: str, questions: str, supplement: str = "暂无。") -> None:
    detail = "用户需要批量导出订单；所有未明确能力均不进入本次范围。" * 25
    path.write_text(f"""# 候选 PRD

- 状态标记：`PRD_STATUS: {status}`

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
        write_intake_file(harnove.artifact_path(archive, state), status, questions, supplement)
    return write


def test_existing_prd(root: Path) -> Path:
    prd = root / "prd.md"
    prd.write_text("# PRD\n\nREQ-001：只实现明确范围。\n", encoding="utf-8")
    harnove.cmd_init(ns_init(root, "SMOKE-001", "state-machine", prd=str(prd)))
    archive = next((root / "iterations").glob("*_SMOKE-001_state-machine"))
    state = harnove.load(archive)
    assert state["status"] == "awaiting_dispatch"
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
    review(archive, "reject", "补充批量导出的范围依据")
    assert harnove.load(archive)["status"] == "awaiting_dispatch"
    run_subagent(archive, intake_writer("READY", "无（边界已确认）", "已按审核意见补充。"))
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    review(archive, "approve")

    # Diagram contract accepts a real Mermaid block and rejects a content-free N/A escape.
    fill_current(archive)
    design_path = harnove.artifact_path(archive, harnove.load(archive))
    valid_design = design_path.read_text(encoding="utf-8")
    assert not harnove.validate_artifact(design_path, "technical_design")
    design_path.write_text(valid_design.replace("DIAGRAM_STATUS: INCLUDED", "DIAGRAM_STATUS: NOT_APPLICABLE").replace("```mermaid", "```text"), encoding="utf-8")
    assert any("NOT_APPLICABLE" in error for error in harnove.validate_artifact(design_path, "technical_design"))
    design_path.write_text(valid_design, encoding="utf-8")

    submit(archive); review(archive, "reject", "补充回滚证据")
    submit(archive); review(archive, "approve")
    submit(archive); review(archive, "approve")
    submit(archive); review(archive, "approve")
    submit(archive)
    submit(archive, "failed")
    assert harnove.load(archive)["stage"] == "implementation"
    submit(archive)
    submit(archive, "passed")
    submit(archive)
    state = harnove.load(archive)
    assert state["status"] == "complete"
    assert state["test_cycles"] == 2
    assert len(state["used_agent_ids"]) == len(set(state["used_agent_ids"]))
    assert len(list((archive / "agent-runs").glob("*_work-order.json"))) == len(state["used_agent_ids"])
    improvement = Path(state["improvement_record"]["path"])
    assert improvement.is_file() and improvement.parent == root / "improve"
    return improvement


def test_natural_language_reuses_experience(root: Path, improvement: Path) -> None:
    harnove.cmd_init(ns_init(
        root, "SMOKE-002", "order-export",
        description="给订单页增加批量导出，但格式和数量上限还没确定。",
    ))
    archive = next((root / "iterations").glob("*_SMOKE-002_order-export"))
    context = archive / "00-input" / harnove.load(archive)["improvement_index"]
    assert improvement.name in context.read_text(encoding="utf-8")
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


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="harnove-") as tmp, redirect_stdout(StringIO()):
        root = Path(tmp)
        improvement = test_existing_prd(root)
        test_natural_language_reuses_experience(root, improvement)
    print("self-test passed")


if __name__ == "__main__":
    main()
