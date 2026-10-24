#!/usr/bin/env python3
"""Compute the next SemVer for a push to main.

Rules:
- No existing v* tags → 0.1.0 (bootstrap).
- Otherwise bump from the latest vX.Y.Z tag using conventional commits:
  - BREAKING CHANGE footer or type! → major
  - feat → minor
  - anything else (fix, chore, unclear, …) → patch
- If there are no meaningful commits since the latest tag → print SKIP.
"""

from __future__ import annotations

import re
import subprocess
import sys

RELEASE_COMMIT_RE = re.compile(r"^chore\(release\):", re.MULTILINE)
BREAKING_FOOTER_RE = re.compile(r"^BREAKING CHANGE:", re.MULTILINE)
BREAKING_TYPE_RE = re.compile(r"^[a-z]+(?:\([^)]*\))?!:", re.MULTILINE)
FEAT_RE = re.compile(r"^feat(?:\([^)]*\))?:", re.MULTILINE)
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def run(args: list[str]) -> str:
    return subprocess.check_output(
        args, text=True, stderr=subprocess.DEVNULL
    ).strip()


def latest_tag() -> str | None:
    try:
        return run(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"]
        )
    except subprocess.CalledProcessError:
        return None


def commits_since(tag: str | None) -> list[str]:
    rng = f"{tag}..HEAD" if tag else "HEAD"
    raw = subprocess.check_output(
        ["git", "log", rng, "--pretty=%B%x00"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    return [c.strip() for c in raw.split("\0") if c.strip()]


def is_release_commit(message: str) -> bool:
    first = message.splitlines()[0] if message else ""
    return bool(RELEASE_COMMIT_RE.match(first))


def classify(messages: list[str]) -> str:
    bump = "patch"
    for message in messages:
        if BREAKING_FOOTER_RE.search(message) or BREAKING_TYPE_RE.search(
            message
        ):
            return "major"
        if FEAT_RE.search(message):
            bump = "minor"
    return bump


def bump_version(version: str, kind: str) -> str:
    major, minor, patch = (int(p) for p in version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main() -> int:
    tag = latest_tag()
    if tag is None:
        print("0.1.0")
        return 0

    match = TAG_RE.match(tag)
    if not match:
        print(f"Unsupported tag format: {tag}", file=sys.stderr)
        return 1

    base = f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
    messages = [m for m in commits_since(tag) if not is_release_commit(m)]
    if not messages:
        print("SKIP")
        return 0

    print(bump_version(base, classify(messages)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
