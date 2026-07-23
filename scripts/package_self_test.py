#!/usr/bin/env python3
"""Verify that exported packages contain no project data and remain installable."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args: str) -> None:
    result = subprocess.run(
        [sys.executable, *args], text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def main() -> None:
    source = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="harnove-package-") as temp:
        root = Path(temp)
        used_harnove = root / "used-project" / "harnove"
        used_harnove.parent.mkdir()
        shutil.copytree(source, used_harnove, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        run(str(used_harnove / "init.py"), "--project", str(used_harnove.parent))
        # Add unmistakable project-owned content after a real in-place initialization.
        marker = used_harnove / "iterations" / "PROJECT-DATA-MUST-NOT-EXPORT.txt"
        marker.write_text("project-only", encoding="utf-8")
        improve_marker = used_harnove / "improve" / "EXPERIENCE-MUST-NOT-EXPORT.md"
        improve_marker.write_text("project-only experience", encoding="utf-8")
        structure_marker = used_harnove / "structure" / "PROJECT-STRUCTURE-MUST-NOT-EXPORT.md"
        structure_marker.write_text("project-only structure", encoding="utf-8")
        custom_marker = used_harnove / "custom" / "user.md"
        custom_marker.write_text("project-only custom preference", encoding="utf-8")
        project_config = json.loads((used_harnove / "config.json").read_text(encoding="utf-8"))
        project_config["project_only_marker"] = True
        (used_harnove / "config.json").write_text(
            json.dumps(project_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        assert (used_harnove / "runtime").is_dir()
        assert (used_harnove / "skill").is_dir()
        exported = root / "exported"
        run(str(used_harnove / "scripts" / "export_package.py"), "--source", str(used_harnove), "--output", str(exported))
        assert not (exported / "iterations").exists()
        assert not (exported / "improve").exists()
        assert not (exported / "structure").exists()
        assert not (exported / "custom").exists()
        assert not (exported / "config.json").exists()
        assert not (exported / "runtime").exists()
        assert not (exported / "skill").exists()
        assert (exported / "README.md").is_file()
        build = json.loads((exported / "package-build.json").read_text(encoding="utf-8"))
        assert build["version"] == json.loads((source / "harnove-package.json").read_text(encoding="utf-8"))["version"]
        assert build["version_policy"]["new_feature"] == "increment_minor_b"

        target = root / "target-project"
        target.mkdir()
        run(str(exported / "init.py"), "--project", str(target))
        assert (target / ".harnove" / "config.json").is_file()
        assert (target / ".harnove" / "README.md").is_file()
        assert (target / ".harnove" / "runtime" / "harnove.py").is_file()
        assert (target / ".harnove" / "iterations").is_dir()
        assert (target / ".harnove" / "improve").is_dir()
        assert (target / ".harnove" / "structure").is_dir()
        assert (target / ".harnove" / "custom" / "user.md").is_file()
        assert (target / ".harnove" / "custom" / "self.md").is_file()
        assert (target / ".agents" / "skills" / "harnove" / "SKILL.md").is_file()
        assert (target / ".claude" / "skills" / "harnove" / "SKILL.md").is_file()
        assert (target / ".cursor" / "commands" / "harnove.md").is_file()
    print("package self-test passed")


if __name__ == "__main__":
    main()
