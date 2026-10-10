#!/usr/bin/env bash
# Build, verify and name a signed nanoMuse-Arabic release APK.
#
#   scripts/arabic-release-apk.sh --revision N [--check-only] [--allow-debug-key]
#   scripts/arabic-release-apk.sh --revision N --publish [--notes FILE]
#
# The version story, and why it has no dash in it:
#
#   versionName = <upstream versionName in build.gradle.kts> . N   →  1.0.1.1, 1.0.1.2, …
#   versionCode = <upstream versionCode in build.gradle.kts> * 1000 + N   →  44001, 44002, …
#
# `UpdateChecker.normalizeTag` cuts a version at its first `-` (that is how `1.2.3-rc1` sorts
# below `1.2.3`), so a version spelled `1.0.1-ar.1` and its release tag both read back as `1.0.1`
# — equal to the installed build, and the in-app update would never appear. A numeric fourth
# component survives that untouched and still compares greater than the base it sits on.
#
# What it refuses to do, in order:
#
#   * publish a revision whose versionCode does not beat the one in the file,
#   * build a release signed with the debug key (unless --allow-debug-key, for a local test),
#   * treat an unpinned key as good: the signer's SHA-256 must equal `android/arabic-cert.sha256`
#     or $ARABIC_CERT_SHA256, and a first run against an unpinned key stops with the fingerprint
#     printed so someone pins it on purpose. Without that, a re-generated key would silently
#     ship an APK no installed copy can ever update.
#
# It never commits the version it writes: the release tag is what fixes it.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/android/env.sh"

revision="" check_only=0 allow_debug=0 publish=0 notes=""
while [ $# -gt 0 ]; do
  case "$1" in
    --revision) revision="${2:-}"; shift ;;
    --check-only) check_only=1 ;;
    --allow-debug-key) allow_debug=1 ;;
    --publish) publish=1 ;;
    --notes) notes="${2:-}"; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done
case "$revision" in ''|*[!0-9]*) [ -z "$revision" ] || { echo "--revision must be a positive integer, got '$revision'" >&2; exit 2; } ;; esac

gradle_file="$NM_GRADLE_DIR/app/build.gradle.kts"
[ -f "$gradle_file" ] || { echo "not found: $gradle_file" >&2; exit 1; }

APP_ID="$(sed -nE 's/.*applicationId = "([^"]+)".*/\1/p' "$gradle_file" | head -1)"
[ -n "$APP_ID" ] || { echo "no applicationId in $gradle_file" >&2; exit 1; }

# ---- the two numbers ---------------------------------------------------------
# The base is read back from the file, so this is idempotent: a file a previous run already
# wrote (`1.0.1.2` / `44002`) yields the same base as a fresh upstream tree (`1.0.1` / `44`).
current_name="$(sed -nE 's/.*versionName = "([^"]+)".*/\1/p' "$gradle_file" | head -1)"
current_code="$(sed -nE 's/.*versionCode = ([0-9]+).*/\1/p' "$gradle_file" | head -1)"
[ -n "$current_name" ] && [ -n "$current_code" ] || { echo "no versionName/versionCode in $gradle_file" >&2; exit 1; }

base_name="$current_name"
case "$current_name" in
  *.*.*.*) base_name="${current_name%.*}" ;; # 1.0.1.3 → 1.0.1
esac
base_code="$current_code"
if [ "$current_code" -ge 1000 ]; then base_code=$((current_code / 1000)); fi # 44003 → 44

# No --revision: the next one, read from the tags that already exist. This is what lets the
# release run on its own when a sync pull request is merged, without anyone choosing a number.
if [ -z "$revision" ]; then
  highest="$(git -C "$NM_ROOT" tag -l "v$base_name.*" 2>/dev/null \
    | sed -nE "s/^v$base_name\.([0-9]+)$/\1/p" | sort -n | tail -1)"
  revision=$(( ${highest:-0} + 1 ))
  echo "== no --revision given: $revision (this base has ${highest:-no} release(s) tagged)"
fi
[ "$revision" -ge 1 ] || { echo "--revision must be a positive integer" >&2; exit 2; }

version_name="$base_name.$revision"
version_code=$((base_code * 1000 + revision))

if [ "$version_code" -le "$current_code" ]; then
  echo "revision $revision is not newer: versionCode would be $version_code, the file carries $current_code" >&2
  echo "raise --revision, or reset the file's version to the upstream base first." >&2
  exit 1
fi

tag="v$version_name"
out="$NM_ROOT/dist/nanoMuse-Arabic-$version_name-arm64.apk"
echo "== nanoMuse-Arabic $version_name (versionCode $version_code)"
echo "== from $current_name (versionCode $current_code), tag $tag"

if [ "$check_only" = 1 ]; then
  echo "== --check-only: nothing written, nothing built"
  exit 0
fi

# ---- the version, written but never committed --------------------------------
sed -i.bak -E "s/versionCode = [0-9]+/versionCode = $version_code/" "$gradle_file"
sed -i.bak -E "s/versionName = \"[^\"]+\"/versionName = \"$version_name\"/" "$gradle_file"
rm -f "$gradle_file.bak"
grep -qE "versionName = \"$version_name\"" "$gradle_file" || { echo "could not write versionName" >&2; exit 1; }
grep -qE "versionCode = $version_code" "$gradle_file" || { echo "could not write versionCode" >&2; exit 1; }

# ---- checks, then the two builds --------------------------------------------
python3 "$NM_ROOT/scripts/check-arabic-resources.py"
bash "$NM_ROOT/scripts/android/build-natives.sh"

# Gradle reads `rclone.aar` out of `app/libs` while it resolves the module's classpath, before it
# compiles anything: without it the failure is "Could not find :rclone:." and nothing in the
# message says a build step had to run first. Naming the missing file is cheaper than that.
for f in "$NM_GRADLE_DIR/app/libs/rclone.aar" \
  "$NM_APP_MAIN/assets/proot-aarch64" \
  "$NM_APP_MAIN/assets/alpine-minirootfs.tar.gz" \
  "$NM_APP_MAIN/jniLibs/arm64-v8a/libproot-loader.so"; do
  [ -s "$f" ] || { echo "build-natives.sh did not produce $f" >&2; exit 1; }
done

echo "== unit tests"
( cd "$NM_GRADLE_DIR" && ./gradlew :app:testDebugUnitTest --tests 'io.github.nanomuse.*' --console=plain --no-daemon )

echo "== assembleRelease"
( cd "$NM_GRADLE_DIR" && ./gradlew :app:assembleRelease --console=plain --no-daemon )

apk="$NM_GRADLE_DIR/app/build/outputs/apk/release/app-release.apk"
[ -f "$apk" ] || { echo "no APK at $apk" >&2; exit 1; }

# ---- the signature -----------------------------------------------------------
build_tools="$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)"
certs="$("$build_tools/apksigner" verify --print-certs "$apk" 2>&1)"
echo "$certs" | grep -iE "certificate (DN|SHA-256 digest)" || true
if echo "$certs" | grep -q "CN=Android Debug" && [ "$allow_debug" = 0 ]; then
  echo "signed with the debug key — android/keystore-arabic.properties is missing or unreadable" >&2
  exit 1
fi

# ---- it is this app, at this version, with its sandbox inside ------------------
# A release that installs and then fails on the first shell command is worse than one that fails
# to build, because the phone is where you find out. The badging is read back rather than assumed,
# and the native payload is listed: the Linux sandbox is proot plus two ELF loaders, the hands and
# the editor need the JNI libraries, and the backup destinations are a Go library that only exists
# as a .so. A packaging regression shows up here, not on someone's phone.
badging="$("$build_tools/aapt" dump badging "$apk")"
case "$badging" in
  *"name='$APP_ID'"*) echo "== package $APP_ID" ;;
  *)
    echo "the APK is not the standalone Arabic edition:" >&2
    grep -m1 '^package:' <<<"$badging" >&2 || true
    exit 1
    ;;
esac
grep -q "versionName='$version_name'" <<<"$badging" || { echo "the APK is not $version_name" >&2; exit 1; }
grep -q "versionCode='$version_code'" <<<"$badging" || { echo "the APK is not versionCode $version_code" >&2; exit 1; }

# A release that is still debuggable is a debug build wearing a release name: anyone can attach a
# debugger to it and read the vault. proguard-android-optimize.txt does not set the flag, and a
# manifest edit could; it costs one line to be sure.
if grep -q '^application-debuggable' <<<"$badging"; then
  echo "the release APK is debuggable (application-debuggable is set)" >&2
  exit 1
fi
label="$(sed -nE "s/^application-label:'([^']*)'.*/\1/p" <<<"$badging" | head -1)"
echo "== label: $label"
[ "$label" = "nanoMuse-Arabic" ] || {
  echo "the launcher label is '$label', not 'nanoMuse-Arabic'" >&2
  exit 1
}
grep -E '^(sdkVersion|targetSdkVersion|native-code)' <<<"$badging" | sed 's/^/     /' || true

# Read exact ZIP entry paths from the central directory.
entries="$(unzip -Z1 "$apk")"
missing=""
for entry in \
  lib/arm64-v8a/libproot-loader.so \
  lib/arm64-v8a/libproot-loader32.so \
  lib/arm64-v8a/libpty_bridge.so \
  lib/arm64-v8a/libjieba_jni.so \
  assets/proot-aarch64
do
  grep -Fxq "$entry" <<<"$entries" || missing="$missing $entry"
done
# The Alpine asset is the one entry whose *contents* have to be right, not only its name. aapt2
# unpacks a `.gz` asset on the way into the APK — upstream's own RootfsManager says so and opens
# whichever of the two names it finds — so which name and which contents survive depends on the
# build tools. A `.tar.gz` holding a plain tar, or a `.tar` holding a gzip, would install and then
# fail on the first shell command. The bytes are read, not the name.
alpine=""
for candidate in assets/alpine-minirootfs.tar.gz assets/alpine-minirootfs.tar; do
  if grep -Fxq "$candidate" <<<"$entries"; then
    alpine="$candidate"
    break
  fi
done
if [ -z "$alpine" ]; then
  missing="$missing assets/alpine-minirootfs.tar.gz (or assets/alpine-minirootfs.tar)"
fi
if [ -n "$missing" ]; then
  echo "the release APK is missing:$missing" >&2
  echo "APK assets:" >&2
  unzip -Z1 "$apk" | grep '^assets/' | head -200 >&2 || true
  echo "Merged asset files:" >&2
  find "$NM_GRADLE_DIR/app/build/intermediates/merged_assets" -type f \
    \( -name 'alpine-minirootfs.tar.gz' -o -name 'alpine-minirootfs.tar' -o -name 'proot-aarch64' \) \
    -printf '%p (%s bytes)\n' 2>/dev/null >&2 || true
  echo "the sandbox cannot start without those, and the app would install and then fail." >&2
  exit 1
fi

head_bytes="$(mktemp)"
unzip -p "$apk" "$alpine" 2>/dev/null | head -c 512 >"$head_bytes" || true
magic="$(head -c 2 "$head_bytes" | od -An -tx1 | tr -d ' \n')"
ustar="$(dd if="$head_bytes" bs=1 skip=257 count=5 2>/dev/null || true)"
rm -f "$head_bytes"
case "$magic:$ustar" in
  1f8b:*) echo "== $alpine: a gzip" ;;
  *:ustar) echo "== $alpine: a tar (the gzip was unpacked on the way in; the app reads either)" ;;
  *)
    echo "the Alpine asset in the APK is neither a gzip nor a tar:" >&2
    echo "  entry: $alpine" >&2
    echo "  first two bytes: '$magic' (a gzip starts 1f8b)" >&2
    echo "  tar ustar field at offset 257: '$ustar'" >&2
    exit 1
    ;;
esac
libs="$(grep -c '^lib/arm64-v8a/.*\.so$' <<<"$entries" || true)"
if [ "${libs:-0}" -lt 6 ]; then
  echo "only ${libs:-0} native libraries are packaged; the sandbox and the JNI code need at least" >&2
  echo "six (two proot loaders, pty_bridge, jieba_jni, the rclone binding, the VAD payload)." >&2
  exit 1
fi
echo "== $libs native libraries, $(grep -c '^assets/' <<<"$entries" || true) assets"
grep '^lib/arm64-v8a/.*\.so$' <<<"$entries" | sed 's/^/     /'

fingerprint="$(printf '%s\n' "$certs" | bash "$NM_ROOT/scripts/apksigner-fingerprint.sh" || true)"
if [ -z "$fingerprint" ]; then
  echo "could not read the signing certificate; apksigner output follows:" >&2
  printf '%s\n' "$certs" >&2
  exit 1
fi
echo "== signer certificate SHA-256: $fingerprint"

# The permanent key, pinned on purpose. Public information (it is in every APK), so it lives in
# the repository; $ARABIC_CERT_SHA256 overrides it for a machine that keeps it elsewhere. The
# file's comment lines explain how to fill it; only what follows a '#' is thrown away here.
pinned="$(sed -E 's/#.*//' "$NM_ROOT/android/arabic-cert.sha256" 2>/dev/null | tr -d '[:space:]:' | tr 'A-F' 'a-f')"
if [ -n "${ARABIC_CERT_SHA256:-}" ]; then
  pinned="$(printf '%s' "$ARABIC_CERT_SHA256" | tr -d '[:space:]:' | tr 'A-F' 'a-f')"
fi

if [ -z "$pinned" ]; then
  cat >&2 <<EOF
::error::this APK is signed, but its key is not pinned, so nothing vouches for it.

  fingerprint: $fingerprint

Pin it once, on the machine that owns the key, or in the repository's variables:

  printf '${fingerprint}\n' > android/arabic-cert.sha256      # tracked; it is public information
  gh variable set ARABIC_CERT_SHA256 --body '$fingerprint'    # or keep it in the repository

Every later release is then checked against it, which is what makes an update of an installed
copy possible at all: a different key cannot install over the last one.
EOF
  exit 1
fi
if [ "$fingerprint" != "$pinned" ]; then
  cat >&2 <<EOF
::error::this APK is signed with a key that is not the permanent one.

  fingerprint: $fingerprint
  pinned:      $pinned

Refusing to publish: an APK under a new key can never install over the copies already on
people's phones. Either the key in android/keystore-arabic.properties is not the permanent one,
or the pin is stale and must be changed on purpose, never to make a build pass.
EOF
  exit 1
fi

mkdir -p "$NM_ROOT/dist"
cp "$apk" "$out"
( cd "$NM_ROOT/dist" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256" && cat "$(basename "$out").sha256" )
ls -la "$out"

publish_flag=false
if [ "$publish" = 1 ]; then publish_flag=true; fi

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "version=$version_name"
    echo "version_code=$version_code"
    echo "tag=$tag"
    echo "apk=$out"
    echo "sha256=$out.sha256"
    echo "cert=$fingerprint"
    echo "publish=$publish_flag"
  } >>"$GITHUB_OUTPUT"
fi

# ---- the release -------------------------------------------------------------
# Note the condition: whether to publish is `--publish`, not whether a runner happens to be there.
# Tying it to $GITHUB_OUTPUT as well meant a `--publish` run outside Actions built, signed and
# then kept quiet about not releasing anything.
if [ "$publish" = 1 ]; then
  echo "== publishing $tag"
  if [ -z "$notes" ]; then
    notes="$RUNNER_TEMP/arabic-notes.md"
    cat >"$notes" <<EOF
nanoMuse-Arabic $version_name, built on nanoMuse $base_name.

The Arabic edition of the app, in Arabic, beside the official one: the same agent, browser,
hands, sandbox and MCP, with an application id and a signing key of its own, so it installs next
to nanoMuse and neither app touches the other's data.

- \`versionCode $version_code\` — an older nanoMuse-Arabic updates in place, and keeps its data.
- Signed with the permanent key of this edition (SHA-256 \`$fingerprint\`).
- Arabic resources checked before the build: key parity, format placeholders, the six plural
  categories, every array item, and the copy rules.
EOF
  fi
  [ -f "$notes" ] || { echo "release notes not found: $notes" >&2; exit 1; }
  # A runner has no git identity and `git tag -a` needs one — the annotated tag carries a tagger.
  # Without this the release builds, signs, verifies the pinned certificate and dies on the tag
  # with "Committer identity unknown", which is where the first run that reached this line stopped.
  git -c user.name="nanoMuse-Arabic" -c user.email="noreply@github.com" \
    tag -a "$tag" -m "nanoMuse-Arabic $version_name"
  git push origin "$tag"
  gh release create "$tag" --latest --title "nanoMuse-Arabic $version_name" \
    --notes-file "$notes" "$out" "$out.sha256"
else
  echo "== built and verified only: no --publish, so no tag and no release"
  echo "   the signed APK is at $out"
fi

echo "== done: $version_name ($tag)"
