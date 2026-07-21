#!/usr/bin/env python3
"""Export a clean Harnove distribution using an explicit core-file allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def safe_relative(value: str) -> Path:
    posix = PurePosixPath(value)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise SystemExit(f"核心文件路径不安全: {value}")
    return Path(*posix.parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="导出不含任何项目内容的 Harnove 核心发行包")
    parser.add_argument("--source", default=str(Path(__file__).resolve().parent.parent), help="Harnove 源目录")
    parser.add_argument("--output", required=True, help="干净发行包输出目录，必须不存在或为空")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    manifest_path = source / "harnove-package.json"
    if not manifest_path.is_file():
        raise SystemExit(f"缺少核心清单: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"输出目录必须不存在或为空: {output}")
    output.mkdir(parents=True, exist_ok=True)

    exported = {}
    for item in manifest.get("core_files", []):
        relative = safe_relative(item)
        src = source / relative
        if not src.is_file():
            raise SystemExit(f"核心清单中的文件不存在: {src}")
        dst = output / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        exported[relative.as_posix()] = sha256(dst)

    forbidden = []
    for item in manifest.get("project_owned_paths", []):
        if (output / safe_relative(item.rstrip("/"))).exists():
            forbidden.append(item)
    if forbidden:
        raise SystemExit("发行包意外包含项目资产: " + ", ".join(forbidden))

    build = {
        "name": manifest["name"],
        "version": manifest["version"],
        "config_schema_version": manifest["config_schema_version"],
        "version_policy": manifest.get("version_policy", {}),
        "files": exported,
    }
    (output / "package-build.json").write_text(
        json.dumps(build, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"干净 Harnove 发行包已生成: {output}")
    print(f"版本: {manifest['version']}; 核心文件: {len(exported)}")


if __name__ == "__main__":
    main()
