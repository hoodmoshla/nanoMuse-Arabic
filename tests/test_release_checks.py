"""The bits of `scripts/arabic-release-apk.sh` that read something and could read it wrongly.

Two things there decide whether a release is published, and both were wrong once:

* the signer certificate's SHA-256, taken from `apksigner verify --print-certs`. The reader looked
  for one prefix, `Signer #1 certificate SHA-256 digest:`, and the run that produced this file
  printed `V2 Signer: certificate SHA-256 digest: …` instead — so the release stopped with "could
  not read the signing certificate", which says nothing about which of the two was wrong;
* the Alpine asset, which aapt2 may ship as `alpine-minirootfs.tar.gz` or as the `.tar` it
  unpacked it into. Checking for one of the two names is checking the wrong thing twice: the entry
  that matters is the one whose *bytes* are a gzip or a tar.

The reader is a script of its own precisely so it can be run here, on the real shapes, instead of
being asserted to contain the right grep.

The digest below is not a secret: it is the certificate fingerprint of a public APK, and it is
already what `ARABIC_CERT_SHA256` carries.
"""

from __future__ import annotations

import gzip
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def posix_bash() -> str | None:
    """A path to a shell that behaves like bash, or None when this machine has none.

    The release scripts are run by the Linux job. On a bare `windows-latest` runner `bash` is the
    Windows Subsystem for Linux stub, which answers with a UTF-16 message about a missing
    distribution instead of running anything, so there is nothing here to test there. Asked rather
    than assumed from the platform name, because Git for Windows does ship a real bash.
    """
    if sys.platform == "win32":
        return None
    try:
        result = subprocess.run(["bash", "-c", "echo ok"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or b"ok" in result.stdout is False:
        return None
    # Answering `echo ok` is not enough: the reader leans on grep/tr/head behaving the way POSIX
    # says, and the shell on a Windows runner is a portability layer over the Win32 API rather than
    # a POSIX one. The release runs these scripts on Linux, and the Linux job is where they are
    # covered; the Windows job is `experimental` upstream for the same reason ("the shell tool
    # assumes a POSIX shell", ci.yml).
    return "bash"


BASH = posix_bash()
needs_bash = pytest.mark.skipif(
    BASH is None,
    reason="no POSIX bash here; scripts/arabic-release-apk.sh is run by the Linux job",
)
READER = ROOT / "scripts" / "apksigner-fingerprint.sh"
RELEASE = ROOT / "scripts" / "arabic-release-apk.sh"
DECIDER = ROOT / "scripts" / "should-publish.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "arabic-release.yml"
DIGEST = "9802a6008e5aefad9e2847a4006a9ed189025170cd4c0558c4c16c0e18a12a5b"
COLONS = ":".join(DIGEST[i : i + 2] for i in range(0, 64, 2)).upper()


def read(text: str) -> tuple[int, str]:
    """Run the reader on [text] the way the release script does, through a pipe."""
    result = subprocess.run(
        [BASH or "bash", str(READER)], input=text, capture_output=True, text=True, check=False
    )
    return result.returncode, result.stdout.strip()


def first_bytes(path: Path) -> bytes:
    """The first 512 bytes of a file, the way the release script reads the APK entry."""
    with path.open("rb") as handle:
        return handle.read(512)


def magic_of(path: Path) -> str:
    return "".join(f"{byte:02x}" for byte in first_bytes(path)[:2])


def ustar_of(path: Path) -> str:
    return first_bytes(path)[257:262].decode("ascii", "replace")


# The long-standing output of `apksigner verify --print-certs`.
CLASSIC = f"""Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Number of signers: 1
Signer #1 certificate DN: CN=nanoMuse-Arabic, OU=standalone Arabic edition, O=nanoMuse-Arabic
Signer #1 certificate SHA-256 digest: {DIGEST}
Signer #1 certificate SHA-1 digest: 0123456789abcdef0123456789abcdef01234567
Signer #1 certificate MD5 digest: 0123456789abcdef0123456789abcdef
"""

# What a newer build-tools printed, and what stopped the release.
SCHEME_PREFIXED = (
    f"V2 Signer: certificate SHA-256 digest: {DIGEST}\nSigner #1 certificate DN: CN=x\n"
)
V3_PREFIXED = f"V3 Signer: certificate SHA-256 digest: {DIGEST}\n"

# `keytool -list -v`, which names the same certificate the same way with colons and capitals.
KEYTOOL = f"Certificate fingerprint (SHA-256): {COLONS}\n"

# No DN line, no scheme line, nothing but the digest on a line that mentions SHA-256.
BARE = f"SHA-256: {DIGEST}\n"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("classic", CLASSIC),
        ("v2 signer", SCHEME_PREFIXED),
        ("v3 signer", V3_PREFIXED),
        ("keytool", KEYTOOL),
        ("bare", BARE),
    ],
)
@needs_bash
def test_the_reader_takes_the_digest_from_every_shape_apksigner_prints(
    name: str, text: str
) -> None:
    code, out = read(text)
    assert code == 0, f"{name}: the reader refused output it should read"
    assert out == DIGEST, f"{name}: read {out!r}"


@needs_bash
def test_the_reader_takes_the_sha256_and_not_the_sha1_beside_it() -> None:
    """A SHA-1 digest is 40 hex characters; a reader that took the first long hex on any line
    would pin the wrong certificate, and the release would refuse a key that is correct."""
    code, out = read(CLASSIC)
    assert (code, out) == (0, DIGEST)
    assert "0123456789abcdef0123456789abcdef01234567" not in out


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Verifies\nNumber of signers: 1\n",
        "Signer #1 certificate SHA-256 digest: not-hex-at-all\n",
        "Signer #1 certificate SHA-256 digest: 9802a600\n",  # half a digest is not a digest
        "Signer #1 certificate SHA-1 digest: 0123456789abcdef0123456789abcdef01234567\n",
    ],
)
@needs_bash
def test_the_reader_prints_nothing_rather_than_a_wrong_digest(text: str) -> None:
    code, out = read(text)
    assert code == 1, f"expected a refusal for {text!r}"
    assert out == ""


def test_the_alpine_detection_tells_a_gzip_from_a_tar(tmp_path: Path) -> None:
    """The two byte tests the release script applies, run on files this test builds itself: a
    gzip starts `1f8b`, a POSIX tar carries `ustar` at offset 257. If either drifted, the check
    would either pass a broken asset or refuse a good one, and both are silent failures on a
    phone — the sandbox extracts garbage and every command returns "Shell not running"."""
    tar = tmp_path / "rootfs.tar"
    with tarfile.open(tar, "w") as archive:
        payload = b"hello\n"
        entry = tarfile.TarInfo("etc/motd")
        entry.size = len(payload)
        archive.addfile(entry, io.BytesIO(payload))
    gz = tmp_path / "rootfs.tar.gz"
    gz.write_bytes(gzip.compress(tar.read_bytes()))

    assert magic_of(gz) == "1f8b", "a gzip no longer starts 1f8b"
    assert magic_of(tar) != "1f8b", "a tar is being read as a gzip"
    assert ustar_of(tar) == "ustar", "a tar no longer carries ustar at offset 257"
    assert ustar_of(gz) != "ustar", "a gzip is being read as a tar"


@pytest.mark.parametrize(
    ("event", "value", "expected"),
    [
        ("workflow_dispatch", "true", "true"),
        ("workflow_dispatch", "True", "true"),
        ("workflow_dispatch", "false", "false"),
        ("workflow_dispatch", "", "false"),
        ("pull_request", "", "false"),
        ("pull_request", "false", "false"),
        ("pull_request", "true", "false"),
        ("pull_request", "True", "false"),
    ],
)
@needs_bash
def test_the_publish_decision(event: str, value: str, expected: str) -> None:
    """A pull request never publishes, even when the input says true or is empty.

    A verify run on a pull request created tag v1.0.6.1 because this decision used
    to treat every `pull_request` event as a request to publish, and the absent
    `--publish` flag never reached the script. An empty input and an explicit
    `true` are both refused here so that path cannot return.
    """
    result = subprocess.run(
        [BASH or "bash", str(DECIDER), event, value], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected, f"{event}/{value!r} → {result.stdout.strip()!r}"


def test_the_workflow_asks_that_script_and_shows_what_it_decided() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "should-publish.sh" in text, "the publish decision is a GitHub expression again"
    assert "inputs.publish == 'true'" not in text, (
        "a boolean dispatch input is being compared with the string 'true'"
    )
    assert "pull_request:" not in text.split("on:", 1)[1].split("jobs:", 1)[0], (
        "a pull_request event can start the Arabic release workflow"
    )
    assert "github.event.pull_request" not in text, (
        "a closed pull request can still reach the release job"
    )
    assert "github.ref == 'refs/heads/main'" in text, "a dispatch can publish from another branch"
    assert "ref: main" in text, "the release checkout can build a pull request commit"
    commands = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "github.sha" not in commands, "the release checkout follows the event commit"
    # The summary must read the value the build actually used, not the input again, or it can
    # report a publication that did not happen.
    assert "steps.release.outputs.publish" in text


def test_the_release_script_says_when_it_did_not_publish() -> None:
    """The other half of the same confusion: `--publish` was also gated on the runner's
    environment, so a local run with it would build, sign and stay silent."""
    script = RELEASE.read_text(encoding="utf-8")
    assert 'if [ "$publish" = 1 ]; then' in script
    assert "built and verified only" in script, "nothing says why a signed APK was not released"
    assert 'echo "publish=$publish_flag"' in script


def test_the_annotated_tag_carries_a_tagger(tmp_path: Path) -> None:
    """`git tag -a` needs an identity and a CI runner has none, so the release built, signed,
    verified the pinned certificate and then died on the tag with "Committer identity unknown".

    Both halves are run here: the command without an identity, which has to fail so the reason is
    not imaginary, and the one the script uses, in a repository with no identity anywhere."""
    repo = tmp_path / "repo"
    repo.mkdir()
    blank = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    blank["HOME"] = str(tmp_path)  # no ~/.gitconfig to fall back on
    blank["XDG_CONFIG_HOME"] = str(tmp_path)
    # A CI runner often carries an identity in the system config (the macOS runner does), which is
    # precisely what the real runner does not have — hence the whole bug. Both are closed off so
    # the test asks the question the runner asks.
    blank["GIT_CONFIG_NOSYSTEM"] = "1"
    blank["GIT_CONFIG_GLOBAL"] = str(tmp_path / "no-such-gitconfig")

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=blank)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=a",
            "-c",
            "user.email=a@b",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        cwd=repo,
        check=True,
        env=blank,
    )

    without = subprocess.run(
        ["git", "tag", "-a", "v9.9.9.1", "-m", "x"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=blank,
        check=False,
    )
    # On a machine with an identity configured this one succeeds, which is why the script cannot
    # rely on it; when it fails, the message is the one the run died with.
    if without.returncode != 0:
        assert "identity" in (without.stderr + without.stdout).lower()

    # A different name: whether the bare command succeeded or not, this one must.
    with_identity = subprocess.run(
        [
            "git",
            "-c",
            "user.name=nanoMuse-Arabic",
            "-c",
            "user.email=noreply@github.com",
            "tag",
            "-a",
            "v9.9.9.2",
            "-m",
            "x",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        env=blank,
        check=False,
    )
    assert with_identity.returncode == 0, with_identity.stderr

    script = RELEASE.read_text(encoding="utf-8")
    assert 'git -c user.name="nanoMuse-Arabic"' in script, (
        "the release script tags without an identity again"
    )


def test_the_release_script_reads_the_certificate_through_this_reader() -> None:
    script = RELEASE.read_text(encoding="utf-8")
    assert "apksigner-fingerprint.sh" in script, "the release script reads the digest itself again"
    assert "Signer #1 certificate SHA-256 digest:" not in script, (
        "the release script is back to matching one apksigner prefix"
    )
    # The pin is still compared, and the debug key is still refused.
    assert "ARABIC_CERT_SHA256" in script
    assert "CN=Android Debug" in script


def test_the_release_script_accepts_either_alpine_name_and_checks_the_bytes() -> None:
    script = RELEASE.read_text(encoding="utf-8")
    assert "assets/alpine-minirootfs.tar.gz" in script
    assert "assets/alpine-minirootfs.tar" in script, "the unpacked name is not accepted"
    # The contents, not just the name: a gzip starts 1f8b, a tar carries ustar at offset 257.
    assert "1f8b" in script, "nothing checks that the asset is really a gzip"
    assert "ustar" in script, "nothing checks that the asset is really a tar"
    assert "unzip -p" in script, "the asset is not opened, only listed"


def test_no_check_in_the_release_script_was_removed_to_make_it_pass() -> None:
    """The gates, named one by one. A release script that drops one of these still builds an APK;
    it just stops meaning anything."""
    script = RELEASE.read_text(encoding="utf-8")
    for gate in (
        "is not pinned",  # an unpinned key is refused
        "is not the permanent one",  # a different key is refused
        "application-debuggable",  # a debuggable release is refused
        "the launcher label is",  # the wrong label is refused
        "is not newer",  # a revision that does not beat the file
        "did not produce",  # the natives are checked before Gradle runs
    ):
        assert gate in script, f"the release script no longer refuses: {gate}"
