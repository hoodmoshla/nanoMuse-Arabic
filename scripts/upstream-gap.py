#!/usr/bin/env python3
"""What nano-muse/nanoMuse has that this fork does not, and what that means for Arabic.

    git remote add upstream https://github.com/nano-muse/nanoMuse   # once
    git fetch upstream main
    python3 scripts/upstream-gap.py                                 # report to stdout
    python3 scripts/upstream-gap.py --out upstream-gap.md           # and to a file

It only reads. It never merges, never pushes and never opens a release: merging upstream is a
hand decision, with a review of the four files this fork owns (see ARABIC-EDITION.md). What it
does is make that decision cheap to take: how far behind we are, which trees upstream touched,
the strings the Arabic translation will owe once we merge, and whether upstream has meanwhile
shipped an Arabic locale of its own that would collide with ours.

Exit code is 0 whether or not there is anything to do — this is a report, not a gate. The
workflow that calls it decides what to do with the answer.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = "android/src/android/app/src/main/res"
LOCALE_FILES = ("nm_strings.xml", "strings.xml")
NAME = re.compile(r"<(string|plurals|string-array)\s+name=\"([^\"]+)\"")
APP_GRADLE = "android/src/android/app/build.gradle.kts"
AREAS = (
    "nanomuse/",
    "cloud/",
    "web/",
    "harness/",
    "android/",
    "docs/",
    "scripts/",
    "tests/",
    ".github/",
    "website/",
)


def git(*args: str, repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def show(repo: Path, ref: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def keys(text: str) -> set[str]:
    return {f"{tag}:{name}" for tag, name in NAME.findall(text)}


def local(path: str) -> str | None:
    file = ROOT / path
    return file.read_text(encoding="utf-8") if file.is_file() else None


def version(text: str) -> tuple[str, str]:
    code = re.search(r"versionCode\s*=\s*(\d+)", text)
    name = re.search(r'versionName\s*=\s*"([^"]+)"', text)
    return (code.group(1) if code else "?", name.group(1) if name else "?")


def report(repo: Path, ours: str, theirs: str) -> str:
    out: list[str] = []
    behind = git("rev-list", "--count", f"{ours}..{theirs}", repo=repo).strip()
    ahead = git("rev-list", "--count", f"{theirs}..{ours}", repo=repo).strip()
    out.append("# nanoMuse-Arabic: where upstream is\n")
    out.append(f"- `{ours}` is **{behind} commit(s) behind** `{theirs}`, and {ahead} ahead.\n")

    changed = git("diff", "--name-only", f"{ours}..{theirs}", repo=repo).splitlines()
    out.append(f"- {len(changed)} file(s) differ.\n")
    out.append("\n## What upstream touched, by tree\n")
    out.append("| tree | files |\n|---|---|")
    for area in AREAS:
        count = sum(1 for path in changed if path.startswith(area))
        if count:
            out.append(f"| `{area}` | {count} |")
    left = [p for p in changed if not p.startswith(AREAS)]
    if left:
        out.append(f"| (other) | {len(left)} |")

    # The Android resources: the one tree where this fork has additions of its own that a merge
    # must not drop (values-ar/ and the label in every strings.xml).
    res_changed = sorted(p for p in changed if p.startswith(RES))
    out.append("\n## Android resources upstream changed\n")
    out.append("\n".join(f"- `{p[len(RES) + 1 :]}`" for p in res_changed) or "- none")

    out.append("\n## The strings Arabic will owe after a merge\n")
    out.append("| file | keys upstream added | keys upstream removed |\n|---|---|---|")
    owed_total = 0
    for filename in LOCALE_FILES:
        theirs_text = show(repo, theirs, f"{RES}/values/{filename}")
        mine_text = local(f"{RES}/values/{filename}")
        if theirs_text is None or mine_text is None:
            continue
        added = sorted(keys(theirs_text) - keys(mine_text))
        removed = sorted(keys(mine_text) - keys(theirs_text))
        owed_total += len(added)
        out.append(f"| `values/{filename}` | {len(added)} | {len(removed)} |")
        if added:
            out.append(
                f"| | {', '.join('`' + key + '`' for key in added[:12])} | {', '.join(removed[:12])} |"
            )
    if owed_total == 0:
        out.append("\nNothing new to translate: our English reference already matches upstream's.")
    else:
        out.append(
            f"\n**{owed_total} new key(s)**: each one needs its line in `values/nm_strings.xml` (or"
            " `values/strings.xml`) **and** in `values-ar/`, or `ArabicStringsParityTest` fails"
            " and the Arabic app quietly falls back to English on that screen."
        )

    # A collision, if upstream ever adds Arabic itself.
    upstream_arabic = show(repo, theirs, f"{RES}/values-ar/nm_strings.xml") is not None
    out.append("\n## Overlaps with this fork's own additions\n")
    if upstream_arabic:
        out.append(
            "- **Upstream now ships an Arabic locale.** `values-ar/` here is ours; merging theirs"
            " over it is a conflict to settle by hand, line by line, kept in one file."
        )
    else:
        out.append(
            "- Upstream still ships no `values-ar/`: the Arabic translation here is additive."
        )

    ours_version = version(git("show", f"{ours}:{APP_GRADLE}", repo=repo))
    theirs_version = version(show(repo, theirs, APP_GRADLE) or "")
    out.append("\n## Version\n")
    out.append(f"- this fork: `versionCode {ours_version[0]}` / `versionName {ours_version[1]}`")
    out.append(f"- upstream: `versionCode {theirs_version[0]}` / `versionName {theirs_version[1]}`")

    out.append(
        "\n## What to do with this\n"
        "\n1. Read the Android resource diff above before anything else: `locales_config.xml` and"
        " `AppearanceScreen.kt` are one line each of ours, and `values-ar/` is ours entirely.\n"
        "2. `git merge --no-commit <upstream>` on a branch, never on `main`, never by a robot.\n"
        "3. Add the new keys to `values-ar/` in the same commit, then run"
        " `python3 scripts/check-arabic-resources.py` and `python3 scripts/check-arabic-resources.py"
        " --strict-locales`.\n"
        "4. Run `python3 scripts/rebrand.py`: it re-applies this edition's application id, label"
        " and update source, and prints `clean` when nothing was left behind.\n"
        "5. Build the debug APK before pushing: a merge that compiles is the only merge worth"
        " reviewing.\n"
    )
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--upstream-repo", type=Path, default=ROOT, help="a checkout with upstream fetched"
    )
    parser.add_argument("--ours", default="HEAD")
    parser.add_argument("--theirs", default="upstream/main")
    parser.add_argument("--out", type=Path, help="also write the report here")
    args = parser.parse_args()
    text = report(args.upstream_repo, args.ours, args.theirs)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
