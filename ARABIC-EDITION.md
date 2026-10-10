# nanoMuse-Arabic: the standalone Arabic edition

This repository is a fork of [nano-muse/nanoMuse](https://github.com/nano-muse/nanoMuse), released
as an app of its own: **nanoMuse-Arabic**, tracking upstream **1.0.1**. It installs *beside* the official nanoMuse on the same
phone, keeps its own data, its own key and its own updates, and neither app can touch the other.

Everything upstream's README, `CONTRIBUTING.md` and `AGENTS.md` say about the project is still
true here — this file only adds what is different about this edition.

---

## What is different, and only this

| | official nanoMuse | nanoMuse-Arabic |
|---|---|---|
| Android `applicationId` | `io.github.nanomuse.app` | **`io.github.nanomuse.arabic`** |
| Launcher label | nanoMuse | **nanoMuse-Arabic** |
| Signing key | the project's | **one of this edition's own** |
| Update feed | `nano-muse/nanoMuse` releases | **`hoodmoshla/nanoMuse-Arabic` releases** |
| Issue tracker | upstream's | upstream's, for anything that is not this fork |
| Arabic UI | not shipped | `values-ar/strings.xml` and `values-ar/nm_strings.xml` |

The Kotlin package (`com.openminis.app`) and the Gradle `namespace` are **unchanged**, exactly as
`CONTRIBUTING.md` asks: upstream merges keep landing, and only the identity Android cares about
moves. Everything the platform derives from it — `${applicationId}.permission.ALARM`, the Shizuku
authority `<applicationId>.shizuku`, the FileProvider authority `<applicationId>.fileprovider`,
the accessibility service id `"$applicationId/com.openminis.app.accessibility.MinisAccessibilityService"`
— follows the one line in `app/build.gradle.kts` on its own. `res/xml/shortcuts.xml` is the single
file that hardcodes the id and cannot be templated; `scripts/rebrand.py` writes it, and
`scripts/check-arabic-resources.py` fails the build if the two ever disagree.

The URL scheme registered with the system is **`nanomuse-arabic`**, not upstream's `nanomuse`
and not `minis`. The phone this edition exists for already runs the official nanoMuse, which
claims `nanomuse://`; two apps claiming one scheme is a chooser every time a link, a shortcut or
an automation arrives. Inside the app nothing changes: the links the model writes, the sandbox
and every saved conversation keep their `minis://` form, `OwnScheme` reads all three names, and a
link the app opens on itself is addressed to its own activity by name rather than through the
system's resolution of a scheme. `scripts/rebrand.py` writes both the manifest line and
`OwnScheme.SYSTEM`.

---

## The Arabic translation

Two files, and they are not the same kind of thing:

| file | what it is | who checks it |
|---|---|---|
| `res/values-ar/nm_strings.xml` | our own strings (the `nm_` keys) | `NmStringsParityTest`, `ArabicStringsParityTest` |
| `res/values-ar/strings.xml` | upstream's strings, translated | `ArabicStringsParityTest`, `scripts/check-arabic-resources.py` |

```sh
python3 scripts/check-arabic-resources.py                  # Arabic, strict
python3 scripts/check-arabic-resources.py --strict-locales  # and the other locales' drift
```

It checks key parity, duplicate and invalid names, format placeholders (`%s`, `%1$d` …), the six
CLDR plural categories Arabic counts with, empty values, em dashes, exclamation marks, Persian
letters from the wrong keyboard, and any value still in English with no entry in its
`PROPER_NOUNS` list. Every item of every array and plural is checked on its own, so a week list
half in English cannot hide behind its Arabic neighbours — which is how `nm_weekdays` and
`nm_name_suggestions` were found, untranslated here while every other locale had them.

**Only Arabic is held to the key rule.** Eight of upstream's other locales already sit two keys
short of English; failing the build over files this edition does not own would be noise. They are
reported as notes, and fail the run only under `--strict-locales`.

---

## The signing key: read this once

Debug builds need no key and never will. A **release** build is signed with the key named by
`android/keystore-arabic.properties`, or by the file `$NM_KEYSTORE_PROPERTIES` points at, falling
back to upstream's `android/keystore.properties` and then to the debug key. What is tracked in
this repository is `android/keystore-arabic.properties.example` — never a real key.

Create it **once**, keep two backups of the `.jks` off the machine, and never regenerate it: a
release signed with a different key cannot install over the last one.

```sh
keytool -genkeypair -v \
  -keystore /absolute/path/to/nanomuse-arabic-release.jks \
  -alias nanomuse-arabic -keyalg RSA -keysize 4096 -validity 10000 -storetype PKCS12

keytool -list -v -keystore /absolute/path/to/nanomuse-arabic-release.jks \
  -alias nanomuse-arabic | grep -E "SHA256|SHA-256"   # keep this next to the backup

cp android/keystore-arabic.properties.example android/keystore-arabic.properties
# fill in storeFile / storePassword / keyAlias / keyPassword, then:
```

`scripts/release-apk.sh <version>` builds, **verifies the signature**, and refuses a build signed
with `CN=Android Debug` unless `--allow-debug-key` says this one is only a local test. Release
builds stay on a developer machine: they need this key, and the native artifacts take half an
hour, which is upstream's model and is not changed here.

`android/keystore-arabic.properties` is in `.gitignore`. Do not put a key, a password or a
fingerprint anywhere else in this repository.

---

## Updates

Two places check for one, and both read this edition's releases only:

- **Settings → About → App Update** (`com.openminis.app.data.UpdateChecker`) reads
  `api.github.com/repos/hoodmoshla/nanoMuse-Arabic/releases`. A repository with no release yet
  answers `404`, which the UI already shows as *No release published yet.*
- **Settings → About → the Version row** (`io.github.nanomuse.community.UpdateCheck`) reads
  `/releases/latest` and tells three answers apart: a version (show it), `404` (this edition has
  published nothing yet), and anything else (a check that failed). Before, both of the last two
  said *Could not check*, which sent people looking for a network problem that did not exist.

Upstream's download index on `nanomuse.cn` is deliberately **not** read any more: every tag on it
names the English app, signed with a key this build does not carry, so a version read from there
can only ever offer an update that cannot install.

Before anything is handed to the system installer, `UpdateChecker.installApk` reads the signing
certificate out of the downloaded APK (`io.github.nanomuse.update.ApkSignerIdentity`) and compares
it with the installed app's. An APK from another key can never install over this app — the system
refuses it with `INSTALL_FAILED_UPDATE_INCOMPATIBLE` after the download and the permission dance —
so the mismatch is caught first, logged, and shown as one plain sentence.

**There is no release yet.** Until one is published, the update row says so, and that is the
correct answer rather than a fabricated one. `## Releases` below is the pipeline that changes it.

---

## Releases, and the numbers in them

The Arabic edition carries a version of its own, and it has no dash in it:

```
versionName  = <the upstream versionName in build.gradle.kts> . <revision>   →  1.0.1.1, 1.0.1.2
versionCode  = <the upstream versionCode> * 1000 + <revision>               →  44001, 44002
```

The dash matters. `UpdateChecker.normalizeTag` cuts a version at its first `-`, because that is
how upstream sorts `1.2.3-rc1` below `1.2.3`; a version spelled `1.0.1-ar.1`, and the tag for it,
would both read back as `1.0.1` — equal to the installed build — and the update would never
appear in the app. A numeric fourth component survives that untouched and still compares greater
than the base it sits on. `scripts/arabic-release-apk.sh --check-only --revision N` prints what a
revision would be called and writes nothing.

### One-time setup, then one button

Copy this whole block once, on the machine that will keep the key. It creates the key, sets the
two secrets the workflow reads, and pins the certificate's fingerprint — after it, every release
is one command.

```sh
# 1. The key. Made ONCE and never again: a release signed with a different key cannot install
#    over the last one. Keep two backups of the .jks file next to the fingerprint printed below.
keytool -genkeypair -v -keystore ~/nanomuse-arabic-release.jks \
  -alias nanomuse-arabic -keyalg RSA -keysize 4096 -validity 10000 -storetype PKCS12

# 2. The two secrets. The alias is `nanomuse-arabic` and PKCS12 keeps one password for the store
#    and the key, so the workflow needs nothing else.
base64 -w0 ~/nanomuse-arabic-release.jks | gh secret set ARABIC_KEYSTORE_BASE64
gh secret set ARABIC_KEYSTORE_PASSWORD          # the password you just chose

# 3. The fingerprint, pinned on purpose. It is public information (it ships inside every APK), it
#    lives in a repository variable so no commit is needed, and every later release is measured
#    against it.
gh variable set ARABIC_CERT_SHA256 --body "$(keytool -list -v -keystore ~/nanomuse-arabic-release.jks \
  | sed -nE 's/.*SHA256: //p' | tr -d ':' | tr 'A-F' 'a-f')"
```

Run it with `bash`, not `sh`, and answer the two password prompts. `gh` needs to be signed in to
this repository (`gh auth status`).

**Then, for this release:**

```sh
gh workflow run "Arabic release" -f revision=1 -f publish=true
```

`revision=1` builds `nanoMuse-Arabic-1.0.1.1-arm64.apk` at `versionCode 44001`; the next release is
`revision=2`, and so on. Add `--repo hoodmoshla/nanoMuse-Arabic` if you are not in the clone. This
is the same as **Actions → Arabic release → Run workflow**.

Until the fingerprint is pinned, a release build stops **after** signing and prints the fingerprint
instead of publishing. That is deliberate: an APK under a key nobody chose can never install over
the copies already on people's phones, and a build that "just works" with a new key is the failure
this pipeline exists to prevent.

| the run refuses to publish when | because |
|---|---|
| a secret is missing | it stops before the build, naming which one |
| the Arabic checks or the unit tests fail | the steps are sequential |
| the APK's package is not `io.github.nanomuse.arabic`, or its version is not the one being released | a release under the wrong identity is somebody else's app |
| a native payload is missing (`libproot-loader.so`, `libpty_bridge.so`, the Alpine rootfs …) | it would install and then fail on the first shell command |
| the APK is signed with the debug key | `android/keystore-arabic.properties` was not read |
| the signature is not the pinned one | the key is not this edition's permanent key |
| the revision does not beat the version in the file | an update that is not newer is not an update |

It publishes `v<versionName>` marked **Latest** with `nanoMuse-Arabic-<versionName>-arm64.apk` and
its `.sha256`. Latest matters: `/releases/latest` is what the Version row reads, and a prerelease
is excluded from it by GitHub.

### What the app then does

`Settings → About → the Version row` reads
`api.github.com/repos/hoodmoshla/nanoMuse-Arabic/releases/latest`, compares the tag with its own
`versionName`, and offers *Update* when the tag is newer. `App Update` under it reads the release
list and can download and install the APK itself. Two things make the install work, and both are
checked before publishing:

- **the application id never moves** (`io.github.nanomuse.arabic`), so it is an update of the same
  app and not a second copy;
- **the signing key never moves** (the pinned fingerprint), which is what Android demands before
  it will replace an installed app — and it is what keeps the person's data.

A downloaded APK is additionally checked on the phone, in
`io.github.nanomuse.update.ApkSignerIdentity`: whatever the feed answered with, nothing reaches
the system installer unless its certificate is this app's.

## Following upstream

```sh
git remote add upstream https://github.com/nano-muse/nanoMuse   # once
git fetch upstream main
python3 scripts/upstream-gap.py                                 # what changed, what Arabic owes
```

`.github/workflows/upstream.yml` runs that report weekly, and — when upstream publishes a
**release** we do not have — fetches the tag, merges it into `upstream/<tag>`, lists the conflicts
and the files of ours it touches, and opens one pull request. It never merges the Arabic branch,
never pushes upstream and never publishes. The pull request is where the build happens:
`android.yml` runs on it, builds the debug APK and runs the unit tests, `ArabicStringsParityTest`
and `NmStringsParityTest` among them, so a merge that brought new strings and no Arabic for them
fails there rather than on a phone.

The merge itself is done by hand, on a branch, in this order:

1. **Look at what upstream touched under `android/src/android/app/src/main/res`.** Three files
   here are ours: `values-ar/` entirely, one line of `values/xml/locales_config.xml`, and one line
   of `AppearanceScreen.kt`. A merge that drops any of them silently un-ships the Arabic.
2. `git merge --no-commit upstream/main` on a branch — never on `main`, never by a robot.
3. **Add upstream's new strings to both** the English-locale reference file *and* `values-ar/`.
   Missing this is what turns `ArabicStringsParityTest` red and the Arabic UI back into English.
4. `python3 scripts/rebrand.py` — it re-applies the application id, the label and the update
   source, and prints `clean` when nothing was left behind.
5. `python3 scripts/check-arabic-resources.py --strict-locales`, then build the debug APK. A merge
   that compiles is the only merge worth reviewing.

### The keys upstream added since this fork's base

Applied. Upstream 1.0.1 added three `nm_` keys in every one of its locales; the same three are
in `values-ar/nm_strings.xml` here, so `NmStringsParityTest` and
`scripts/check-arabic-resources.py` both pass on the merged tree:

```xml
<string name="nm_chat_no_model">لا يوجد نموذج يمكنه الإجابة الآن. اختر واحدًا من الإعدادات › النماذج.</string>
<string name="nm_cloud_err_content_rejected">رفض فحص المحتوى لدى مزوّد النموذج هذا الطلب. جرّب كلمات مختلفة، أو ابدأ محادثة جديدة إن تكرّر الأمر: فقد تكون الكلمات التي يعترض عليها في جزء سابق من المحادثة.</string>
<string name="nm_models_cloud_off_refused">أضف مزوّدًا خاصًا بك أولًا؛ فمع إغلاق nanoMuse Cloud لن يجيب أي شيء آخر.</string>
```

That is what the order above is for: a merge that brings new keys and no Arabic for them turns
the parity test red on the next run, which is the point of having it.

---

## Building

```sh
bash scripts/android/build-natives.sh          # 30-60 min the first time; the artifacts are gitignored
cd android/src/android
./gradlew :app:assembleDebug                   # no key needed
./gradlew :app:testDebugUnitTest --tests 'io.github.nanomuse.*'
```

JDK 21, NDK r27c, Go 1.26, CMake 3.22.1, `compileSdk 36`, `minSdk 26`, arm64-v8a only — the same
toolchain as upstream's `.github/workflows/android.yml`, which builds the debug APK and runs those
unit tests (including `ArabicStringsParityTest`) on every push and pull request.

A release build is `scripts/release-apk.sh <version>` with the key in place. Nothing in CI signs
or publishes anything: there is no keystore in the repository and no secret in the workflows.

---

## What this edition does not do

- **No iOS.** `android/src/ios` is untouched, in English, and builds with upstream's own bundle
  ids. Rebranding would follow `APP_ID` if `scripts/rebrand.py` ever ran over it, but nobody
  builds it here.
- **No desktop, web or relay changes.** The relay this app signs in to is upstream's service,
  unchanged, so `cloud.nanomuse.cn` and the sign-in flow stay exactly as upstream wrote them.
- **No separate release channel for the runtime.** This is the phone app; the Python runtime, the
  console and the desktop app are upstream's.
