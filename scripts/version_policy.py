#!/usr/bin/env python3
"""Validate Harnove semantic version increments against the declared change type."""

from __future__ import annotations

import argparse
import re


def parse(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise SystemExit(f"版本号必须为 a.b.c: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def expected(previous: tuple[int, int, int], change_type: str) -> tuple[int, int, int]:
    major, minor, patch = previous
    if change_type == "fix":
        return major, minor, patch + 1
    if change_type == "feature":
        return major, minor + 1, 0
    return major + 1, 0, 0


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 Harnove 版本号递增规则")
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--change-type", required=True, choices=["fix", "feature", "architecture"])
    args = parser.parse_args()
    actual = parse(args.current)
    wanted = expected(parse(args.previous), args.change_type)
    if actual != wanted:
        raise SystemExit(f"版本号不符合 {args.change_type} 规则: 期望 {wanted[0]}.{wanted[1]}.{wanted[2]}，实际 {args.current}")
    print(f"version policy passed: {args.previous} -> {args.current} ({args.change_type})")


if __name__ == "__main__":
    main()
