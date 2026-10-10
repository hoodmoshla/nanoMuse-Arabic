"""The Arabic resources of the standalone edition, and the identity that keeps it standalone.

`scripts/check-arabic-resources.py` is the tool the Android side of this repository never had: a
guard for upstream's `values-ar/strings.xml`, which `NmStringsParityTest` does not look at. These
tests run that tool over the real tree, and then feed it the mistakes it exists to catch, so a
future edit that breaks the checker is caught here rather than in the quiet English fallback of a
phone nobody is looking at.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-arabic-resources.py"


def _load_checker():
    """The tool, loaded from its path: `scripts/` is not an importable package.

    It is registered in `sys.modules` first because the module defines a dataclass, and the
    dataclass machinery looks its own module up by name while the class body is being built.
    """
    name = "check_arabic_resources"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def checker():
    module = _load_checker()
    module.problems.clear()
    module.notices.clear()
    yield module
    module.problems.clear()
    module.notices.clear()


def _parse(module, path: Path):
    resources, errors = module.parse_resources(path)
    assert errors == [], f"{path.name}: {errors}"
    assert resources is not None
    return resources


def _write(directory: Path, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "strings.xml"
    path.write_text(f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n{body}\n</resources>\n')
    return path


EN = """    <string name="greeting">Hello %1$s</string>
    <string name="count">%1$d files</string>
    <plurals name="items">
        <item quantity="one">One item</item>
        <item quantity="other">%1$d items</item>
    </plurals>
    <string-array name="days">
        <item>Monday</item>
        <item>Tuesday</item>
    </string-array>
"""

AR_OK = """    <string name="greeting">مرحبًا %1$s</string>
    <string name="count">%1$d ملف</string>
    <plurals name="items">
        <item quantity="zero">لا عناصر</item>
        <item quantity="one">عنصر واحد</item>
        <item quantity="two">عنصران</item>
        <item quantity="few">%1$d عناصر</item>
        <item quantity="many">%1$d عنصرًا</item>
        <item quantity="other">%1$d عنصر</item>
    </plurals>
    <string-array name="days">
        <item>الاثنين</item>
        <item>الثلاثاء</item>
    </string-array>
"""


# --- the repository as it stands ------------------------------------------------------------


def test_the_arabic_resources_of_this_repository_are_clean(checker):
    assert checker.run(strict_locales=False) == 0, checker.problems


def test_the_other_locales_drift_is_reported_and_not_fatal(checker):
    checker.run(strict_locales=False)
    assert checker.problems == []
    assert all("key(s) missing" in message for message in checker.notices)


def test_the_strict_mode_counts_the_other_locales(checker):
    assert checker.run(strict_locales=True) == 1
    assert any("key(s) missing" in problem for problem in checker.problems)


def test_every_proper_noun_entry_still_exists(checker):
    reference = _parse(checker, checker.RES / "values" / "strings.xml")
    stale = sorted(key for key in checker.PROPER_NOUNS if key not in reference)
    assert stale == [], f"PROPER_NOUNS names keys that are gone: {stale}"


def test_the_application_id_is_the_standalone_one(checker):
    checker.check_identity()
    assert checker.problems == [], checker.problems


def test_the_label_of_this_edition_is_in_every_locale(checker):
    checker.check_label()
    assert checker.problems == [], checker.problems


def test_the_two_arrays_upstream_localises_are_localised_here(checker):
    """Every other locale translates the week list and the name pool; Arabic must too."""
    arabic = _parse(checker, checker.RES / "values-ar" / "nm_strings.xml")
    for name in ("nm_weekdays", "nm_name_suggestions"):
        for index, value in enumerate(arabic[name].values):
            assert checker.ARABIC_LETTER.search(value), f"{name}[{index}] is not Arabic: {value!r}"


# --- the mistakes the tool exists to catch --------------------------------------------------


def test_a_dropped_key_is_an_error(checker, tmp_path):
    en = _parse(checker, _write(tmp_path / "values", EN))
    ar = _parse(
        checker,
        _write(
            tmp_path / "values-ar",
            AR_OK.replace('    <string name="count">%1$d ملف</string>\n', ""),
        ),
    )
    checker.check_keys(en, ar, "values-ar/strings.xml")
    assert any("count" in problem for problem in checker.problems)


def test_a_key_english_does_not_have_is_an_error(checker, tmp_path):
    en = _parse(checker, _write(tmp_path / "values", EN))
    ar = _parse(
        checker, _write(tmp_path / "values-ar", AR_OK + '    <string name="extra">زائد</string>\n')
    )
    checker.check_keys(en, ar, "values-ar/strings.xml")
    assert any("extra" in problem for problem in checker.problems)


def test_a_changed_placeholder_is_an_error(checker, tmp_path):
    en = _parse(checker, _write(tmp_path / "values", EN))
    ar = _parse(checker, _write(tmp_path / "values-ar", AR_OK.replace("%1$d ملف", "ملف")))
    checker.check_format(en, ar, "values-ar/strings.xml")
    assert any("count" in problem for problem in checker.problems)


def test_a_placeholder_without_the_length_modifier_is_an_error(checker, tmp_path):
    en = _parse(checker, _write(tmp_path / "values", EN))
    ar = _parse(checker, _write(tmp_path / "values-ar", AR_OK.replace("مرحبًا %1$s", "مرحبًا %s")))
    checker.check_format(en, ar, "values-ar/strings.xml")
    assert any("greeting" in problem for problem in checker.problems)


def test_a_plural_that_lost_its_other_form_is_an_error(checker, tmp_path, capsys):
    en = _parse(checker, _write(tmp_path / "values", EN))
    ar = _parse(checker, _write(tmp_path / "values-ar", AR_OK))
    checker.check_format(en, ar, "values-ar/strings.xml")
    assert checker.problems == []

    missing_other = AR_OK.replace(
        '<item quantity="other">%1$d عنصر</item>', '<item quantity="many">%1$d عنصر</item>'
    )
    _, errors = checker.parse_resources(_write(tmp_path / "values-ar2", missing_other))
    assert any("must all be six" in error or "other" in error for error in errors), errors


def test_arabic_plurals_missing_a_category_are_reported(checker, tmp_path):
    short = AR_OK.replace('        <item quantity="two">عنصران</item>\n', "")
    _, errors = checker.parse_resources(_write(tmp_path / "values-ar", short))
    assert any("Arabic plurals" in error for error in errors), errors


def test_a_bad_quantity_name_is_reported(checker, tmp_path):
    bad = AR_OK.replace('quantity="few"', 'quantity="several"')
    _, errors = checker.parse_resources(_write(tmp_path / "values-ar", bad))
    assert any("CLDR" in error for error in errors), errors


def test_english_left_in_one_item_of_an_array_is_an_error(checker, tmp_path):
    en = _parse(checker, _write(tmp_path / "values", EN))
    ar = _parse(
        checker,
        _write(
            tmp_path / "values-ar", AR_OK.replace("<item>الثلاثاء</item>", "<item>Tuesday</item>")
        ),
    )
    checker.check_copy(ar, (tmp_path / "values-ar" / "strings.xml").read_text(), "values-ar")
    assert any("days" in problem for problem in checker.problems)
    checker.check_keys(en, ar, "values-ar/strings.xml")
    assert checker.problems


def test_a_persian_letter_is_an_error(checker, tmp_path):
    ar = _parse(checker, _write(tmp_path / "values-ar", AR_OK.replace("ملف", "فايل\u06cc")))
    checker.check_copy(ar, (tmp_path / "values-ar" / "strings.xml").read_text(), "values-ar")
    assert any("Persian" in problem for problem in checker.problems)


def test_an_empty_value_is_an_error(checker, tmp_path):
    ar = _parse(checker, _write(tmp_path / "values-ar", AR_OK.replace("مرحبًا %1$s", "")))
    checker.check_copy(ar, (tmp_path / "values-ar" / "strings.xml").read_text(), "values-ar")
    assert any("empty" in problem for problem in checker.problems)


def test_an_exclamation_mark_is_an_error(checker, tmp_path):
    ar = _parse(checker, _write(tmp_path / "values-ar", AR_OK.replace("ملف", "ملف!")))
    checker.check_copy(ar, (tmp_path / "values-ar" / "strings.xml").read_text(), "values-ar")
    assert any("exclamation" in problem for problem in checker.problems)


def test_an_em_dash_is_an_error(checker, tmp_path):
    ar = _parse(checker, _write(tmp_path / "values-ar", AR_OK.replace("ملف", "ملف \u2014 ملف")))
    checker.check_copy(ar, (tmp_path / "values-ar" / "strings.xml").read_text(), "values-ar")
    assert any("em dash" in problem for problem in checker.problems)


def test_a_duplicate_key_is_an_error(checker, tmp_path):
    doubled = AR_OK + '    <string name="count">مرة أخرى</string>\n'
    _, errors = checker.parse_resources(_write(tmp_path / "values-ar", doubled))
    assert any("duplicate" in error for error in errors), errors


def test_an_invalid_resource_name_is_an_error(checker, tmp_path):
    bad = AR_OK + '    <string name="Not_A_Name">x</string>\n'
    _, errors = checker.parse_resources(_write(tmp_path / "values-ar", bad))
    assert any("valid Android name" in error for error in errors), errors


def test_malformed_xml_is_an_error(checker, tmp_path):
    path = tmp_path / "values-ar" / "strings.xml"
    path.parent.mkdir(parents=True)
    path.write_text("<resources><string name='a'>unclosed</resources>")
    resources, errors = checker.parse_resources(path)
    assert resources is None
    assert any("well-formed" in error for error in errors), errors


def test_a_stale_proper_noun_entry_is_an_error(checker, tmp_path):
    reference = _parse(checker, _write(tmp_path / "values", EN))
    checker.check_reference_labels(reference)
    assert checker.problems


# --- the small decisions the checks rest on -------------------------------------------------


@pytest.mark.parametrize(
    ("text", "translatable"),
    [
        ("Hello", True),
        ("JSON", True),
        ("%1$s · %2$s", False),
        ("%1$s %2$s", False),
        ("~ %1$s", False),
        ("مرحبا", False),
        ("1234", False),
        ("", False),
        ("%1$d ملف", False),
        ("nanoMuse", True),
    ],
)
def test_what_counts_as_a_translatable_value(checker, text, translatable):
    assert checker.is_translatable(text) is translatable


def test_the_placeholders_of_a_string_ignore_their_letters(checker, tmp_path):
    en = _parse(checker, _write(tmp_path / "values", EN))
    assert en["count"].placeholders == {"%1$d"}
    assert en["greeting"].placeholders == {"%1$s"}


def test_the_other_form_of_a_plural_is_read_back(checker, tmp_path):
    en = _parse(checker, _write(tmp_path / "values", EN))
    assert en["items"].placeholders_of("other") == {"%1$d"}
    # English spells its own singular out, with no placeholder at all — that is a shape, not a
    # missing value, and the element-wide comparison is what keeps it from being an error.
    assert en["items"].placeholders_of("one") == set()
    assert en["items"].placeholders_of("few") is None
