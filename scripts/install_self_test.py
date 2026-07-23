#!/usr/bin/env python3
"""Smoke-test project installation, idempotency, config defaults, and conflict safety."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args: str, cwd: Path | None = None, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, *args], cwd=cwd, text=True, encoding="utf-8",
        errors="replace", capture_output=True, timeout=30,
    )
    if ok and result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return result


def main() -> None:
    plugin = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="harnove-install-") as temp:
        project = Path(temp) / "sample-project"
        project.mkdir()
        prd = project / "prd.md"
        prd.write_text("# PRD\n\nREQ-001：实现明确范围。\n", encoding="utf-8")

        run(str(plugin / "init.py"), "--project", str(project))
        config = json.loads((project / ".harnove" / "config.json").read_text(encoding="utf-8"))
        assert config["archive_root"] == "iterations"
        assert config["improve_root"] == "improve"
        assert config["structure_root"] == "structure"
        assert config["custom_root"] == "custom"
        assert config["default_branch_pattern"] == "tmp/{iteration_name}-{implementation_version}"
        assert (project / ".harnove" / "iterations").is_dir()
        assert (project / ".harnove" / "improve").is_dir()
        assert (project / ".harnove" / "structure").is_dir()
        assert (project / ".harnove" / "custom" / "user.md").is_file()
        assert (project / ".harnove" / "custom" / "self.md").is_file()
        assert not (project / "iterations").exists()
        assert not (project / "improve").exists()
        assert not (project / "structure").exists()
        assert not (project / "custom").exists()
        assert (project / ".harnove" / "README.md").is_file()
        assert (project / ".harnove" / "skill" / "harnove" / "SKILL.md").is_file()
        assert (project / ".harnove" / "runtime" / "harnove.py").is_file()
        assert (project / ".agents" / "skills" / "harnove" / "SKILL.md").is_file()
        assert (project / ".claude" / "skills" / "harnove" / "SKILL.md").is_file()
        assert (project / ".cursor" / "commands" / "harnove.md").is_file()
        assert not (project / "docs").exists()

        # Reinstallation is idempotent and project-local config remains owner-managed.
        custom_user = project / ".harnove" / "custom" / "user.md"
        custom_user.write_text("# 用户个性化诉求\n\n保留此项目规则。\n", encoding="utf-8")
        config["archive_root"] = "iteration-records"
        (project / ".harnove" / "config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        run(str(plugin / "init.py"), "--project", str(project))
        assert json.loads((project / ".harnove" / "config.json").read_text(encoding="utf-8"))["archive_root"] == "iteration-records"
        assert "保留此项目规则" in custom_user.read_text(encoding="utf-8")

        # Installed runtime discovers config from its own location, independent of cwd.
        runtime = project / ".harnove" / "runtime" / "harnove.py"
        missing_name = run(str(runtime), "init", "--iteration-id", "ITER-MISSING-NAME", "--requirement", "portable",
            "--prd", str(prd), cwd=Path(temp), ok=False)
        assert missing_name.returncode != 0 and "--iteration-name" in (missing_name.stdout + missing_name.stderr)
        run(str(runtime), "init", "--iteration-id", "ITER-001", "--iteration-name", "portable", "--requirement", "portable",
            "--prd", str(prd), cwd=Path(temp))
        archives = list((project / ".harnove" / "iteration-records").glob("*_ITER-001_portable"))
        assert len(archives) == 1

        # A user-modified managed file blocks an update unless force is explicit.
        installed_skill = project / ".harnove" / "skill" / "harnove" / "SKILL.md"
        modified = installed_skill.read_text(encoding="utf-8") + "\nuser change\n"
        installed_skill.write_text(modified, encoding="utf-8")
        result = run(str(plugin / "init.py"), "--project", str(project), ok=False)
        assert result.returncode != 0
        assert installed_skill.read_text(encoding="utf-8") == modified
        assert "--force-managed-files" in (result.stdout + result.stderr)

        # Primary distribution mode: copy the plugin folder into a project and initialize in place.
        copied_project = Path(temp) / "copied-project"
        copied_project.mkdir()
        copied_plugin = copied_project / "harnove"
        shutil.copytree(plugin, copied_plugin, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        run(str(copied_plugin / "init.py"), "--project", str(copied_project))
        assert (copied_plugin / "config.json").is_file()
        assert (copied_plugin / "README.md").is_file()
        assert (copied_plugin / "runtime" / "harnove.py").is_file()
        assert (copied_plugin / "skill" / "harnove" / "SKILL.md").is_file()
        assert (copied_plugin / "iterations").is_dir()
        assert (copied_plugin / "improve").is_dir()
        assert (copied_plugin / "structure").is_dir()
        assert (copied_plugin / "custom" / "user.md").is_file()
        assert (copied_plugin / "custom" / "self.md").is_file()
        assert not (copied_project / ".harnove").exists()
        assert (copied_project / ".agents" / "skills" / "harnove" / "SKILL.md").is_file()
        assert (copied_project / ".claude" / "skills" / "harnove" / "SKILL.md").is_file()
        assert (copied_project / ".cursor" / "commands" / "harnove.md").is_file()
        assert not (copied_project / "docs").exists()
        copied_prd = copied_project / "copied-prd.md"
        copied_prd.write_text("# PRD\n\nREQ-001：原位安装归档验证。\n", encoding="utf-8")
        run(str(copied_plugin / "runtime" / "harnove.py"), "init", "--iteration-id", "ITER-INPLACE",
            "--iteration-name", "archive-location", "--requirement", "archive-location", "--prd", str(copied_prd), cwd=copied_project)
        assert len(list((copied_plugin / "iterations").glob("*_ITER-INPLACE_archive-location"))) == 1
        assert not (copied_project / "iterations").exists()
        assert not (copied_project / "improve").exists()
        assert not (copied_project / "structure").exists()
        assert not (copied_project / "custom").exists()

        # Unsafe owner configuration fails closed instead of writing outside Harnove.
        bad_config = json.loads((copied_plugin / "config.json").read_text(encoding="utf-8"))
        bad_config["archive_root"] = "../outside-iterations"
        (copied_plugin / "config.json").write_text(json.dumps(bad_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = run(str(copied_plugin / "runtime" / "harnove.py"), "status", "--archive", "missing", cwd=copied_project, ok=False)
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "archive_root" in output and "improve_root" in output and "structure_root" in output and "custom_root" in output, output
    print("install self-test passed")


if __name__ == "__main__":
    main()
