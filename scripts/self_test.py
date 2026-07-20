#!/usr/bin/env python3
"""End-to-end smoke test for harnove.py using only temporary files."""

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
        "<!-- 待填写；所有判断须引用 REQ-xxx 或代码证据。 -->",
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


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="harnove-") as tmp, redirect_stdout(StringIO()):
        root = Path(tmp)
        prd = root / "prd.md"
        prd.write_text("# PRD\n\nREQ-001：只实现明确范围。\n", encoding="utf-8")
        harnove.cmd_init(argparse.Namespace(
            root=str(root / "iterations"), prd=str(prd), repo=str(root),
            iteration_id="SMOKE-001", requirement="state-machine",
        ))
        archive = next((root / "iterations").iterdir())

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
        assert len(list((archive / "reviews").glob("*.json"))) == 4
    print("self-test passed")


if __name__ == "__main__":
    main()

