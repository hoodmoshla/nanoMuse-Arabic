"""The two halves of the signing setup have to agree, and nothing at runtime would notice if they
stopped.

`scripts/arabic-signing-setup.sh` writes a repository's secrets and variables;
`.github/workflows/arabic-release.yml` reads them. A name that changes in one file and not the
other is a release that fails on a runner, at the last step, with a message about an empty
variable — or worse, a release that quietly builds with no key and falls back to the debug one.
These tests read both files and hold the contract: the names, the alias, and the shape of the
fingerprint.

Nothing here needs a key, a runner or a network; it is a check on the wiring, which is what can be
checked before either exists.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "arabic-signing-setup.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "arabic-release.yml"
RELEASE_SCRIPT = ROOT / "scripts" / "arabic-release-apk.sh"
EXAMPLE = ROOT / "android" / "keystore-arabic.properties.example"
PIN_FILE = ROOT / "android" / "arabic-cert.sha256"

# The two without which no signed APK can exist — the setup script must set both — and the two
# that only exist so a key made another way can be described.
REQUIRED_SECRETS = ("ARABIC_KEYSTORE_BASE64", "ARABIC_KEYSTORE_PASSWORD")
OPTIONAL_SECRETS = ("ARABIC_KEY_ALIAS", "ARABIC_KEY_PASSWORD")
PIN_VARIABLE = "ARABIC_CERT_SHA256"
ALIAS = "nanomuse-arabic"


def test_the_files_are_where_this_test_says() -> None:
    for path in (SETUP, WORKFLOW, RELEASE_SCRIPT, EXAMPLE, PIN_FILE):
        assert path.is_file(), f"missing {path.relative_to(ROOT)}"


def test_the_workflow_reads_the_names_the_setup_writes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")

    read_secrets = set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", workflow))
    read_vars = set(re.findall(r"vars\.([A-Z][A-Z0-9_]*)", workflow))
    written_secrets = set(re.findall(r"gh secret set ([A-Z][A-Z0-9_]*)", setup))
    written_vars = set(re.findall(r"gh variable set ([A-Z][A-Z0-9_]*)", setup))

    # GITHUB_TOKEN is handed to every run by GitHub itself; the rest are this edition's.
    assert read_secrets - {"GITHUB_TOKEN"} == set(REQUIRED_SECRETS) | set(OPTIONAL_SECRETS), (
        read_secrets
    )
    assert set(REQUIRED_SECRETS) <= written_secrets, (
        f"the setup does not set {set(REQUIRED_SECRETS) - written_secrets}"
    )
    assert "GITHUB_TOKEN" not in written_secrets, "the setup tries to set the token GitHub provides"
    assert read_vars == {PIN_VARIABLE}, read_vars
    assert PIN_VARIABLE in written_vars


def test_the_alias_is_the_same_in_all_three_places() -> None:
    setup = SETUP.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    example = EXAMPLE.read_text(encoding="utf-8")

    assert re.search(rf'^ALIAS="{ALIAS}"$', setup, re.M), (
        "the setup creates a key under another alias"
    )
    assert (
        f"${{{{ secrets.ARABIC_KEY_ALIAS }}}}:-{ALIAS}" in workflow or f":-{ALIAS}" in workflow
    ), "the workflow's default alias is not the one the setup creates"
    assert re.search(rf"^keyAlias={ALIAS}$", example, re.M), "the example file names another alias"


def test_the_fingerprint_is_normalised_the_same_way_on_both_sides() -> None:
    """apksigner prints it with colons or not, keytool prints it with colons and upper case; the
    comparison only works if both sides are lower case hex with nothing between the bytes."""
    setup = SETUP.read_text(encoding="utf-8")
    release = RELEASE_SCRIPT.read_text(encoding="utf-8")
    for name, text in (("setup", setup), ("release", release)):
        assert "tr -d ':'" in text or "tr -d '[:space:]:'" in text, (
            f"{name}: colons are not stripped"
        )
        assert "tr 'A-F' 'a-f'" in text, f"{name}: the fingerprint is not lower-cased"


def test_the_release_script_reads_the_pin_and_refuses_an_empty_one() -> None:
    release = RELEASE_SCRIPT.read_text(encoding="utf-8")
    assert "ARABIC_CERT_SHA256" in release, "the pinned variable is not read"
    assert "arabic-cert.sha256" in release, "the tracked pin file is not read"
    assert "is not pinned" in release, "nothing refuses an unpinned key"
    assert "CN=Android Debug" in release, "nothing refuses the debug key"


def test_the_pin_file_is_tracked_and_empty_on_purpose() -> None:
    """An empty pin is what makes the first release stop and print the fingerprint instead of
    publishing it; a value here without the key it belongs to would pin the wrong thing."""
    body = [
        line
        for line in PIN_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert body == [], (
        f"the pin file carries {body}, but the key it belongs to is not in this repository"
    )
