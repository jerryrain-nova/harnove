#!/usr/bin/env python3
"""Install or safely update Harnove inside a target project."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

SKILL_NAME = "harnove"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def relative_or_absolute(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def install_file(source: Path, target: Path, old_hash: str | None, force: bool) -> str:
    if source.resolve() == target.resolve():
        return sha256(source)
    if target.exists():
        current = sha256(target)
        incoming = sha256(source)
        if current == incoming:
            return current
        if not force and (not old_hash or current != old_hash):
            raise RuntimeError(
                f"检测到人工修改，拒绝覆盖: {target}\n"
                "如确认用插件版本覆盖，请重新执行并添加 --force-managed-files。"
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return sha256(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="将研发迭代 Harnove 初始化到目标代码项目")
    parser.add_argument("--project", default=".", help="目标项目根目录，默认当前目录")
    parser.add_argument("--archive-dir", "--archive-root", dest="archive_dir", default="iterations", help="Harnove 目录内的迭代归档子目录")
    parser.add_argument("--force-managed-files", action="store_true", help="覆盖被人工修改的插件托管文件")
    args = parser.parse_args()

    source_root = Path(__file__).resolve().parent
    package_manifest_path = source_root / "harnove-package.json"
    if not package_manifest_path.is_file():
        raise SystemExit(f"缺少 Harnove 核心清单: {package_manifest_path}")
    package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))
    plugin_version = package_manifest["version"]
    project = Path(args.project).resolve()
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在: {project}")
    try:
        source_root.relative_to(project)
        install_root = source_root
    except ValueError:
        install_root = project / ".harnove"
    manifest_path = install_root / "install-manifest.json"
    config_path = install_root / "config.json"
    old_manifest = {}
    if manifest_path.is_file():
        old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_files = old_manifest.get("managed_files", {})

    sources = []
    for item in package_manifest.get("core_files", []):
        relative = Path(*item.split("/"))
        sources.append((source_root / relative, install_root / relative))
    sources.extend([
        (source_root / "scripts" / "harnove.py", install_root / "runtime" / "harnove.py"),
        (source_root / "SKILL.md", install_root / "skill" / SKILL_NAME / "SKILL.md"),
        (source_root / "agents" / "openai.yaml", install_root / "skill" / SKILL_NAME / "agents" / "openai.yaml"),
        (source_root / "references" / "artifact-contracts.md", install_root / "skill" / SKILL_NAME / "references" / "artifact-contracts.md"),
        (source_root / "SKILL.md", project / ".agents" / "skills" / SKILL_NAME / "SKILL.md"),
        (source_root / "agents" / "openai.yaml", project / ".agents" / "skills" / SKILL_NAME / "agents" / "openai.yaml"),
        (source_root / "references" / "artifact-contracts.md", project / ".agents" / "skills" / SKILL_NAME / "references" / "artifact-contracts.md"),
        (source_root / "SKILL.md", project / ".claude" / "skills" / SKILL_NAME / "SKILL.md"),
        (source_root / "references" / "artifact-contracts.md", project / ".claude" / "skills" / SKILL_NAME / "references" / "artifact-contracts.md"),
        (source_root / "adapters" / "cursor" / "harnove.md", project / ".cursor" / "commands" / "harnove.md"),
    ])
    conflicts = []
    for source, target in sources:
        key = relative_or_absolute(target, project)
        if not target.exists() or sha256(target) == sha256(source) or args.force_managed_files:
            continue
        if not old_files.get(key) or sha256(target) != old_files[key]:
            conflicts.append(str(target))
    if conflicts:
        raise SystemExit(
            "以下目标文件不是本插件已知的托管版本，初始化未执行:\n- "
            + "\n- ".join(conflicts)
            + "\n如确认覆盖，请添加 --force-managed-files。"
        )
    managed = {}
    try:
        for source, target in sources:
            key = relative_or_absolute(target, project)
            managed[key] = install_file(source, target, old_files.get(key), args.force_managed_files)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    config_changed = False
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if "improve_root" not in config:
            config["improve_root"] = "improve"
            config_changed = True
        if "structure_root" not in config:
            config["structure_root"] = "structure"
            config_changed = True
        if "custom_root" not in config:
            config["custom_root"] = "custom"
            config_changed = True
        if "default_branch_pattern" not in config:
            config["default_branch_pattern"] = "tmp/{iteration_name}-{implementation_version}"
            config_changed = True
        gates = config.setdefault("required_human_gates", [])
        if "prd_intake" not in gates:
            gates.insert(0, "prd_intake")
            config_changed = True
        if config.get("schema_version", 1) < 5:
            config["schema_version"] = 5
            config_changed = True
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "schema_version": 5,
            "project_root": relative_or_absolute(project, install_root),
            "repo_root": ".",
            "archive_root": args.archive_dir,
            "improve_root": "improve",
            "structure_root": "structure",
            "custom_root": "custom",
            "default_branch_pattern": "tmp/{iteration_name}-{implementation_version}",
            "skill": f"skill/{SKILL_NAME}",
            "platform_entrypoints": {
                "codex": f".agents/skills/{SKILL_NAME}",
                "cursor": ".cursor/commands/harnove.md",
                "claude_code": f".claude/skills/{SKILL_NAME}",
            },
            "scope_policy": "prd_only",
            "test_pass_policy": "all_mandatory_cases_pass",
            "required_human_gates": ["prd_intake", "technical_design", "code_plan", "test_design"],
        }
        config_changed = True

    archive_root = (install_root / config.get("archive_root", "iterations")).resolve()
    improve_root = (install_root / config.get("improve_root", "improve")).resolve()
    structure_root = (install_root / config.get("structure_root", "structure")).resolve()
    custom_root = (install_root / config.get("custom_root", "custom")).resolve()
    for label, managed_root in [("archive_root", archive_root), ("improve_root", improve_root), ("structure_root", structure_root), ("custom_root", custom_root)]:
        try:
            managed_root.relative_to(install_root)
        except ValueError as exc:
            raise SystemExit(f"{label} 必须位于 Harnove 统一目录内") from exc
        managed_root.mkdir(parents=True, exist_ok=True)
        if label != "custom_root":
            (managed_root / ".gitkeep").touch(exist_ok=True)
    custom_defaults = {
        "user.md": "# 用户个性化诉求\n\n暂无。用户对本项目的长期约束、偏好和额外诉求记录在此。\n",
        "self.md": "# Harnove 项目经验\n\n暂无。Harnove 将在需求完成后追加从用户反馈中提炼的可复用经验。\n",
    }
    for name, content in custom_defaults.items():
        target = custom_root / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")
    if config_changed:
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "plugin_version": plugin_version,
        "plugin_source": relative_or_absolute(source_root, install_root),
        "installed_at": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "managed_files": managed,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Harnove 初始化完成: {project}")
    print(f"Harnove 统一目录: {install_root}")
    print(f"项目配置: {config_path}")
    print(f"项目 Skill: {install_root / 'skill' / SKILL_NAME}")
    print("平台入口: Claude Code /harnove; Cursor /harnove; Codex $harnove 或 /skills")
    print(f"迭代归档: {archive_root}")
    print(f"经验沉淀: {improve_root}")
    print(f"项目结构知识: {structure_root}")
    print(f"自适应超时策略: {install_root / 'timeout-policy.json'}（首次真实超时后创建）")
    print(f"项目自定义上下文: {custom_root}")
    print(f"使用文档: {install_root / 'USAGE.md'}")
    print("下一步: 先由 Agent 建议迭代名称并由用户确认。")
    print(f"确认后运行: {install_root / 'run.ps1'} init --iteration-id <ID> --iteration-name <用户确认名称> --requirement <需求标识> (--prd <路径> | --description <描述>)")
    print("运行后由主 Agent 为每个环节派发全新的隔离子 Agent。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
