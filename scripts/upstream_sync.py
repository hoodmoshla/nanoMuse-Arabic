#!/usr/bin/env python3
"""Decide what a nanoMuse-Arabic upstream sync may do. It never merges or publishes.

The workflow calls this before it opens a branch and again before it asks the release workflow
to publish. A repeated release, a conflict, or a failed check stops here; only a clean, new,
tested tree is allowed to continue. The tests in tests/test_upstream_sync.py cover those gates
without a GitHub runner.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

STABLE = re.compile(r"^v\d+\.\d+\.\d+$")


class Decision:
    def __init__(self, action: str, reason: str) -> None:
        self.action = action
        self.reason = reason

    def __str__(self) -> str:
        return f"{self.action}: {self.reason}"


def stable_release(tag: str, draft: bool = False, prerelease: bool = False) -> bool:
    """A stable upstream release is a final vX.Y.Z tag, never a draft or a pre-release."""
    return bool(STABLE.fullmatch(tag)) and not draft and not prerelease


def already_synced(tag: str, merged_tags: set[str], open_branches: set[str]) -> bool:
    """The same upstream tag is not prepared twice, and an open review branch is left alone."""
    return tag in merged_tags or f"upstream/{tag}" in open_branches


def decide(
    tag: str,
    *,
    merged_tags: set[str] | None = None,
    open_branches: set[str] | None = None,
    conflicts: list[str] | None = None,
    checks_passed: bool = False,
    draft: bool = False,
    prerelease: bool = False,
) -> Decision:
    """The one gate between an upstream release and a nanoMuse-Arabic release."""
    if not stable_release(tag, draft, prerelease):
        return Decision("skip", f"{tag} is not a stable upstream release")
    if already_synced(tag, merged_tags or set(), open_branches or set()):
        return Decision("skip", f"{tag} was already prepared or is still waiting for review")
    if conflicts:
        return Decision("review", "conflicts need a person: " + ", ".join(conflicts))
    if not checks_passed:
        return Decision("stop", "a check failed, so nothing is published")
    return Decision("publish", f"{tag} is new, clean, and every check passed")


def _split(value: str) -> set[str]:
    return {item for item in value.split(",") if item}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--merged", default="")
    parser.add_argument("--open-branches", default="")
    parser.add_argument("--conflicts", default="")
    parser.add_argument("--checks-passed", action="store_true")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--prerelease", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    decision = decide(
        args.tag,
        merged_tags=_split(args.merged),
        open_branches=_split(args.open_branches),
        conflicts=[item for item in args.conflicts.split(",") if item],
        checks_passed=args.checks_passed,
        draft=args.draft,
        prerelease=args.prerelease,
    )
    text = str(decision)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if decision.action != "stop" else 1


if __name__ == "__main__":
    raise SystemExit(main())
