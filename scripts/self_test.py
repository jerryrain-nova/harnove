#!/usr/bin/env python3
"""End-to-end smoke tests for file-PRD and natural-language intake flows."""

from __future__ import annotations

import argparse
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import harnove


def fill_current(archive: Path) -> None:
    state = harnove.load(archive)
    path = harnove.artifact_path(archive, state)
    text = path.read_text(encoding="utf-8").replace(
        harnove.PLACEHOLDER,
        "REQ-001：依据 PRD 第一节。本节记录可审核结论、边界、证据与预期结果。",
    )
    text += "\n" + ("REQ-001 的范围证据、实现约束与验证说明。" * 40) + "\n"
    path.write_text(text, encoding="utf-8")


def submit(archive: Path, result: str | None = None) -> None:
    fill_current(archive)
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result=result))


def review(archive: Path, decision: str, feedback: str = "") -> None:
    harnove.cmd_review(argparse.Namespace(
        archive=str(archive), decision=decision, reviewer="smoke-human", feedback=feedback
    ))


def test_existing_prd(root: Path) -> None:
    prd = root / "prd.md"
    prd.write_text("# PRD\n\nREQ-001：只实现明确范围。\n", encoding="utf-8")
    harnove.cmd_init(argparse.Namespace(
        root=str(root / "iterations-file"), prd=str(prd), description=None,
        description_file=None, repo=str(root), iteration_id="SMOKE-001",
        requirement="state-machine",
    ))
    archive = next((root / "iterations-file").iterdir())
    state = harnove.load(archive)
    assert state["stage"] == "prd_intake"
    original = archive / "00-input" / state["original_input_snapshot"]
    assert original.read_text(encoding="utf-8") == prd.read_text(encoding="utf-8")
    assert harnove.artifact_path(archive, state) != original

    write_intake(harnove.artifact_path(archive, state), "READY", "无（边界已确认）")
    original.write_text("tampered\n", encoding="utf-8")
    try:
        harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
        raise AssertionError("tampered original input was accepted")
    except SystemExit as exc:
        assert "原始输入副本" in str(exc)
    original.write_text(prd.read_text(encoding="utf-8"), encoding="utf-8")
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    assert harnove.load(archive)["status"] == "awaiting_prd_review"
    review(archive, "reject", "补充批量导出的范围依据")
    state = harnove.load(archive)
    assert state["stage"] == "prd_intake" and state["version"] == 2
    assert "PRD 审核反馈" in harnove.artifact_path(archive, state).read_text(encoding="utf-8")
    write_intake(harnove.artifact_path(archive, state), "READY", "无（边界已确认）", "已按审核意见补充范围依据。")
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    review(archive, "approve")
    assert harnove.load(archive)["stage"] == "technical_design"
    assert original.read_text(encoding="utf-8") == prd.read_text(encoding="utf-8")

    submit(archive); review(archive, "reject", "补充回滚证据")
    submit(archive); review(archive, "approve")
    submit(archive); review(archive, "approve")
    submit(archive); review(archive, "approve")
    submit(archive)
    submit(archive, "failed")
    assert harnove.load(archive)["stage"] == "implementation"
    assert harnove.load(archive)["version"] == 2
    submit(archive)
    assert harnove.load(archive)["stage"] == "test_execution"
    assert harnove.load(archive)["version"] == 2
    submit(archive, "passed")
    submit(archive)
    state = harnove.load(archive)
    assert state["status"] == "complete"
    assert state["test_cycles"] == 2
    assert len(list((archive / "reviews").glob("*.json"))) == 6


def write_intake(path: Path, status: str, questions: str, supplement: str = "暂无。") -> None:
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


def test_natural_language(root: Path) -> None:
    harnove.cmd_init(argparse.Namespace(
        root=str(root / "iterations-natural"), prd=None,
        description="给订单页增加批量导出，但格式和数量上限还没确定。",
        description_file=None, repo=str(root), iteration_id="SMOKE-002",
        requirement="order-export",
    ))
    archive = next((root / "iterations-natural").iterdir())
    state = harnove.load(archive)
    assert state["stage"] == "prd_intake"
    assert state["prd_source_type"] == "natural_language"

    write_intake(harnove.artifact_path(archive, state), "NEEDS_CLARIFICATION", "1. 导出格式是 CSV 还是 XLSX？\n2. 单次导出数量上限是多少？")
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="needs-clarification"))
    assert harnove.load(archive)["status"] == "awaiting_user_clarification"

    harnove.cmd_clarify(argparse.Namespace(
        archive=str(archive), responder="product-owner",
        response="使用 CSV；单次最多 10,000 条。", response_file=None,
    ))
    state = harnove.load(archive)
    assert state["version"] == 2 and state["status"] == "drafting"
    write_intake(harnove.artifact_path(archive, state), "READY", "无（边界已确认）", "用户确认：CSV，最多 10,000 条。")
    harnove.cmd_submit(argparse.Namespace(archive=str(archive), result="ready"))
    assert harnove.load(archive)["status"] == "awaiting_prd_review"
    review(archive, "approve")
    state = harnove.load(archive)
    assert state["stage"] == "technical_design"
    assert state["prd_snapshot"].endswith("候选PRD_v002.md")
    assert len(list((archive / "00-input").glob("*候选PRD_v*.md"))) == 2
    assert len(list((archive / "00-input" / "clarifications").glob("*.json"))) == 1
    assert (archive / "00-input" / f"{state['iteration_id']}_{state['requirement']}_需求基线.md").is_file()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="harnove-") as tmp, redirect_stdout(StringIO()):
        root = Path(tmp)
        test_existing_prd(root)
        test_natural_language(root)
    print("self-test passed")


if __name__ == "__main__":
    main()
