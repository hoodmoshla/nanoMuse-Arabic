#!/usr/bin/env python3
"""Check the Arabic resources of nanoMuse-Arabic — and the identity that keeps it standalone.

Run it from the repository root:

    python3 scripts/check-arabic-resources.py
    python3 scripts/check-arabic-resources.py --strict-locales   # every locale, not just Arabic

Why this exists: `NmStringsParityTest` already guards `nm_strings.xml` on the Android side, but
nothing guarded upstream's `values-ar/strings.xml` — 1755 keys a translator wrote once, which a
later upstream pull could quietly drop back to English one key at a time. The other locales can
keep drifting (upstream ships eight of them two keys short of English); Arabic may not, because a
missing key there is the whole point of this edition failing silently on a device.

It is stdlib-only on purpose: it runs wherever Python 3.11 does, with no test dependencies, so CI
can run it as its own step and print the reason in one screen. Exit code 0 means clean, 1 means
something above is wrong.

What it checks:

  identity   applicationId and the shortcuts' targetPackage agree, app_name carries the label of
             this edition, the manifest keeps `supportsRtl`, and the locale list offers Arabic.
  keys       every key of `values/` present in `values-ar/` (and nothing extra), no duplicate
             names, resource names that are valid Android names.
  format     `%s`, `%d`, `%1$s`, `%1$d` sets identical to English — a mismatch is a crash or a
             half-written sentence on the device.
  plurals    valid CLDR quantity names, `other` always present, and for Arabic all six of its own
             categories, because Arabic counts with all six.
  copy       Arabic that is genuinely Arabic: no empty values, no em dash, no exclamation mark, no
             Persian letters, and no English left behind — every item of an array and every plural
             form counted on its own, so a half-translated week list cannot hide behind its
             neighbours. Only PROPER_NOUNS below may stay in Latin script.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "android" / "src" / "android" / "app"
MAIN = APP / "src" / "main"
RES = MAIN / "res"
APP_GRADLE = APP / "build.gradle.kts"
MANIFEST = MAIN / "AndroidManifest.xml"
SHORTCUTS = RES / "xml" / "shortcuts.xml"
LOCALES_CONFIG = RES / "xml" / "locales_config.xml"

REFERENCE = "values"
TARGET = "values-ar"
TARGET_LANG = "ar"
FILES = ("strings.xml", "nm_strings.xml")
LABEL = "nanoMuse-Arabic"

PLACEHOLDER = re.compile(r"%(?:\d+\$)?[sd]")
RESOURCE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
STRING_VALUE = re.compile(r"<string\s+name=\"([^\"]+)\"[^>]*>(.*?)</string>", re.DOTALL)
LATIN = re.compile(r"[A-Za-z]")

# The plural categories Android's CLDR data uses. Arabic counts with all six; a file carrying
# only one/other renders "0 items" and "3 items" correctly and the eleven other cases wrong.
PLURAL_CATEGORIES = {"zero", "one", "two", "few", "many", "other"}
ARABIC_CATEGORIES = {"zero", "one", "two", "few", "many", "other"}

# Arabic script, including the supplement and the presentation forms.
ARABIC_LETTER = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
# Persian/Urdu letters that are NOT Arabic: a translation tool that reached for the wrong
# keyboard produces kaf as U+06A9 and yeh as U+06CC, which reads as broken to an Arabic speaker.
NON_ARABIC_LETTERS = "\u06a9\u06cc\u06af\u067e\u0686"

# Whole resources that are deliberately not Arabic: names, protocols, file names and code. Each
# entry is a key whose value a translator is RIGHT to leave in Latin script, with the reason it
# is there — so that a new English value nobody translated still fails the run.
PROPER_NOUNS: dict[str, str] = {
    "app_name": "the product name",
    "mcp_transport_http": "the protocol's own name",
    "mcp_transport_sse": "the protocol's own name",
    "mcp_transport_stdio": "the protocol's own name",
    "mcp_form_url_placeholder": "an example URL",
    "mcp_form_command_placeholder": "an example command line",
    "mcp_form_args_placeholder": "an example argument list",
    "mcp_import_placeholder": "an example JSON document",
    "export_summary_format_value_json": "a file format's name",
    "skill_import_tab_url": "a URL field's label in a technical form",
    "skill_import_url_label": "a URL field's label in a technical form",
    "skill_detail_source_url": "a URL field's label in a technical form",
}

problems: list[str] = []
notices: list[str] = []


@dataclass
class Resource:
    """One named resource: a string, a string-array, or a plurals with its quantities."""

    tag: str
    values: list[str]
    quantities: list[str]
    translatable: bool = True

    @property
    def placeholders(self) -> set[str]:
        return {match for value in self.values for match in PLACEHOLDER.findall(value)}

    def placeholders_of(self, quantity: str) -> set[str] | None:
        for index, name in enumerate(self.quantities):
            if name == quantity:
                return set(PLACEHOLDER.findall(self.values[index]))
        return None


def fail(where: str, message: str) -> None:
    problems.append(f"{where}: {message}")


def note(message: str) -> None:
    notices.append(message)


def locale_dirs() -> list[str]:
    return sorted(d.name for d in RES.glob("values-*") if d.is_dir())


def parse_resources(path: Path) -> tuple[dict[str, Resource] | None, list[str]]:
    """Every named resource of one file. Returns (resources, errors)."""
    errors: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return None, [f"not well-formed XML ({exc})"]
    resources: dict[str, Resource] = {}
    for child in root:
        name = child.get("name")
        if not name:
            errors.append(f"a <{child.tag}> without a name")
            continue
        if not RESOURCE_NAME.match(name):
            errors.append(f"resource name {name!r} is not a valid Android name")
        if name in resources:
            errors.append(f"duplicate resource {name!r}")
        if child.tag == "string":
            resources[name] = Resource(
                child.tag,
                [child.text or ""],
                [],
                child.get("translatable", "true") != "false",
            )
            continue
        values = [item.text or "" for item in child]
        quantities = [item.get("quantity") or "" for item in child]
        resources[name] = Resource(child.tag, values, quantities)
        if child.tag == "plurals":
            bad = [q for q in quantities if q not in PLURAL_CATEGORIES]
            if bad:
                errors.append(f"{name}: plural quantit(ies) {bad} are not CLDR categories")
            if "other" not in quantities:
                errors.append(f"{name}: a <plurals> without the required 'other'")
            if path.parent.name == TARGET and set(quantities) != ARABIC_CATEGORIES:
                missing = sorted(ARABIC_CATEGORIES - set(quantities))
                extra = sorted(set(quantities) - ARABIC_CATEGORIES)
                errors.append(
                    f"{name}: Arabic plurals want all six categories, "
                    f"missing {missing} extra {extra}"
                )
    return resources, errors


def check_keys(reference: dict[str, Resource], target: dict[str, Resource], label: str) -> None:
    # Upstream marks some strings `translatable="false"`. NmStringsParityTest then fails if a
    # locale copies them, so Arabic must not carry them either.
    required = {name for name, res in reference.items() if res.translatable}
    missing = sorted(required - set(target))
    forbidden = sorted(
        name for name, res in reference.items() if not res.translatable and name in target
    )
    extra = sorted(set(target) - set(reference))
    if missing:
        fail(label, f"{len(missing)} key(s) English has and Arabic does not: {missing[:12]}")
    if forbidden:
        fail(
            label,
            f"{len(forbidden)} key(s) English marks translatable=false but Arabic copies: {forbidden[:12]}",
        )
    if extra:
        fail(label, f"{len(extra)} key(s) Arabic has and English does not: {extra[:12]}")


def check_format(reference: dict[str, Resource], target: dict[str, Resource], label: str) -> None:
    """The placeholders of a key are its shape; a missing one drops a number from the sentence.

    Compiled plurals are compared loosely on purpose: a locale spells its own singular out
    ("Checks every hour") where English has no placeholder at all, so the union over the whole
    element is what must match — plus the `other` form, which every locale has and which is the
    one a wrong plural almost always damages.
    """
    wrong: list[str] = []
    for name, mine in target.items():
        theirs = reference.get(name)
        if theirs is None:
            continue
        if mine.placeholders != theirs.placeholders:
            wrong.append(
                f"{name}: Arabic {sorted(mine.placeholders)} vs English {sorted(theirs.placeholders)}"
            )
            continue
        if mine.tag == "plurals":
            theirs_other = theirs.placeholders_of("other")
            mine_other = mine.placeholders_of("other")
            if theirs_other is not None and mine_other is not None and theirs_other != mine_other:
                wrong.append(
                    f"{name} (other): Arabic {sorted(mine_other)} vs English {sorted(theirs_other)}"
                )
    if wrong:
        fail(
            label,
            f"{len(wrong)} string(s) whose format placeholders differ from English: {wrong[:8]}",
        )


def is_translatable(text: str) -> bool:
    """True when a value is something a translator must put words into.

    `%1$s · %2$s` is not: it is punctuation and two placeholders. Neither is `123`. The letters
    inside a placeholder (`%s`, `%d`) do not count, which is how `%1$s` stops looking English.
    """
    if ARABIC_LETTER.search(text):
        return False
    return bool(LATIN.search(PLACEHOLDER.sub("", text)))


def check_copy(target: dict[str, Resource], raw: str, label: str) -> None:
    empty = sorted(name for name, res in target.items() if not any(v.strip() for v in res.values))
    if empty:
        fail(label, f"{len(empty)} empty value(s): {empty[:12]}")

    body = COMMENT.sub("", raw)
    if "\u2014" in body:
        dashed = [name for name, text in STRING_VALUE.findall(body) if "\u2014" in text]
        fail(label, f"em dash(es) in {dashed[:8] or 'a plural or array item'}")
    shouting = sorted(
        name for name, text in STRING_VALUE.findall(body) if "!" in text or "\uff01" in text
    )
    if shouting:
        fail(label, f"exclamation mark(s) in {shouting[:8]}")

    for name, res in sorted(target.items()):
        for value in res.values:
            hit = sorted(set(value) & set(NON_ARABIC_LETTERS))
            if hit:
                fail(label, f"{name}: non-Arabic letter(s) {' '.join(hit)} (Persian/Urdu keyboard)")
                break

    # Every item on its own: an array is translated item by item, and a week list left in English
    # next to one Arabic entry is exactly the gap this check is for.
    untranslated: list[str] = []
    for name, res in sorted(target.items()):
        if name in PROPER_NOUNS:
            continue
        for index, value in enumerate(res.values):
            if not is_translatable(value):
                continue
            where = name if res.tag == "string" else f"{name}[{index}]"
            untranslated.append(f"{where}={value!r}")
    if untranslated:
        fail(
            label,
            f"{len(untranslated)} value(s) with no Arabic and no entry in PROPER_NOUNS "
            f"(translate it, or add the key with its reason): {untranslated[:8]}",
        )


def check_reference_labels(reference: dict[str, Resource]) -> None:
    """A PROPER_NOUNS entry that no longer exists is a rule that quietly stopped applying."""
    stale = sorted(key for key in PROPER_NOUNS if key not in reference)
    if stale:
        fail("PROPER_NOUNS", f"entries for keys that no longer exist: {stale}")


def check_identity() -> None:
    if not APP_GRADLE.is_file():
        fail("identity", f"{APP_GRADLE.relative_to(ROOT)} not found")
        return
    match = re.search(r'applicationId\s*=\s*"([^"]+)"', APP_GRADLE.read_text(encoding="utf-8"))
    if match is None:
        fail("identity", "no applicationId in app/build.gradle.kts")
        return
    app_id = match.group(1)
    if not app_id.endswith(".arabic"):
        fail(
            "identity",
            f"applicationId is {app_id}: the standalone edition must not share the official id, "
            "or it cannot install beside it",
        )
    shortcuts = SHORTCUTS.read_text(encoding="utf-8")
    wrong = sorted(set(re.findall(r'android:targetPackage="([^"]+)"', shortcuts)) - {app_id})
    if wrong:
        fail("identity", f"shortcuts.xml targets {wrong}, not the applicationId {app_id}")
    manifest = MANIFEST.read_text(encoding="utf-8")
    if "${applicationId}" not in manifest:
        note("the manifest derives nothing from ${applicationId} any more — check the authorities")
    if 'android:supportsRtl="true"' not in manifest:
        fail("rtl", "the manifest does not set android:supportsRtl")
    if 'android:localeConfig="@xml/locales_config"' not in manifest:
        fail("rtl", "the manifest does not point at locales_config")
    if f'<locale android:name="{TARGET_LANG}"' not in LOCALES_CONFIG.read_text(encoding="utf-8"):
        fail("rtl", f"locales_config.xml does not offer {TARGET_LANG}")


def check_label() -> None:
    for path in sorted(RES.glob("values*/strings.xml")):
        if f'<string name="app_name">{LABEL}</string>' not in path.read_text(encoding="utf-8"):
            fail("label", f"{path.parent.name}/strings.xml does not carry app_name {LABEL}")


def run(strict_locales: bool) -> int:
    reference: dict[str, dict[str, Resource]] = {}
    for filename in FILES:
        parsed, errors = parse_resources(RES / REFERENCE / filename)
        for error in errors:
            fail(f"{REFERENCE}/{filename}", error)
        reference[filename] = parsed or {}

    for filename in FILES:
        path = RES / TARGET / filename
        if not path.is_file():
            fail("arabic", f"{path.relative_to(ROOT)} is missing")
            continue
        resources, errors = parse_resources(path)
        for error in errors:
            fail(f"{TARGET}/{filename}", error)
        resources = resources or {}
        check_keys(reference[filename], resources, f"{TARGET}/{filename}")
        check_format(reference[filename], resources, f"{TARGET}/{filename}")
        check_copy(resources, path.read_text(encoding="utf-8"), f"{TARGET}/{filename}")

    check_reference_labels(reference["strings.xml"])

    # The other locales are upstream's and drift on purpose (eight of them are two keys short of
    # English today). They are reported, never fatal, unless --strict-locales is asked for.
    def other_locale(locale: str, filename: str, message: str) -> None:
        if strict_locales:
            fail(f"{locale}/{filename}", message)
        else:
            note(f"{locale}/{filename}: {message}")

    for locale in locale_dirs():
        if locale in (REFERENCE, TARGET):
            continue
        for filename in FILES:
            path = RES / locale / filename
            if not path.is_file():
                continue
            resources, errors = parse_resources(path)
            if errors:
                other_locale(locale, filename, "; ".join(errors))
                continue
            missing = sorted(set(reference[filename]) - set(resources or {}))
            extra = sorted(set(resources or {}) - set(reference[filename]))
            if missing or extra:
                other_locale(
                    locale,
                    filename,
                    f"{len(missing)} key(s) missing, {len(extra)} extra {missing[:4]}",
                )

    check_identity()
    check_label()
    return report()


def report() -> int:
    for message in notices:
        print(f"note  {message}")
    for message in problems:
        print(f"FAIL  {message}")
    if problems:
        print(f"\n{len(problems)} problem(s) in the Arabic resources")
        return 1
    print("\nArabic resources: clean")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--strict-locales",
        action="store_true",
        help="fail on the other locales' key drift as well (upstream ships eight of them short)",
    )
    return run(parser.parse_args().strict_locales)


if __name__ == "__main__":
    sys.exit(main())
