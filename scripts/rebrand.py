#!/usr/bin/env python3
"""Turn the OpenMinis tree in android/ into nanoMuse. Idempotent; re-run after every
upstream pull (CONTRIBUTING.md), then scripts/gen-android-icons.py.

What it changes, and only this:

- Gradle: applicationId, versionCode / versionName (the Kotlin package and namespace stay).
- The places that hard-code the package id (shortcuts, the accessibility service id).
- The product name: "Minis" -> "nanoMuse" in the 17 strings.xml and in Kotlin string
  literals (never in identifiers, paths such as /var/minis, or MinisSkills).
- The label the standalone Arabic edition shows (LABEL, below): app_name in every
  strings.xml, so a phone with both apps tells them apart.
- The Soul defaults (agent name and header emoji).
- Links: update source, GitHub repository, issues, privacy policy.
- Colours: the iOS blues and the teal Material scheme -> the brand palette (docs/brand.md).
- Notification small icons: the launcher icon -> the flat status-bar mark; every
  notification also carries the agent's face as its large icon (Muse: the agent
  is the sender).
- "<name> is browsing": the browser banner string takes the Soul name (%1$s).
- A handful of first-run / notification strings reworded in nanoMuse's voice
  (COPY below, en + zh + zh-rTW; the other locales keep the upstream text).

- iOS (android/src/ios, when present): the bundle ids (com.openminis.app* → io.github.nanomuse.arabic*,
  including the app group and iCloud container), the display names, MARKETING_VERSION /
  CURRENT_PROJECT_VERSION, "Minis" -> "nanoMuse" in Swift string literals and in
  Localizable.xcstrings (keys renamed, every translation updated), the About links, the
  Soul emoji, the accent colour. Icons: scripts/gen-ios-icons.py.

Anything else is a hand edit marked `// nanoMuse:` in the file.

    python scripts/rebrand.py            # apply, then report what is still upstream's
    python scripts/rebrand.py --check    # report only, write nothing
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android" / "src" / "android"
APP = ANDROID / "app"
MAIN = APP / "src" / "main"
JAVA = MAIN / "java" / "com" / "openminis" / "app"
# nanoMuse's own tree, where the Arabic edition's identity and update source live.
NM_JAVA = MAIN / "java" / "io" / "github" / "nanomuse"
RES = MAIN / "res"
IOS = ROOT / "android" / "src" / "ios"

# nanoMuse-Arabic: the standalone Arabic edition. It installs BESIDE the official
# app, so it carries an application id, a launcher label and a release feed of its
# own; the Kotlin package and the Gradle namespace stay com.openminis.app, as
# CONTRIBUTING.md asks, so upstream merges keep landing.
APP_ID = "io.github.nanomuse.arabic"
NAME = "nanoMuse"
LABEL = "nanoMuse-Arabic"
VERSION_NAME = "1.0.6"
VERSION_CODE = 49
# This edition's repository: the update check reads it and the About rows link to
# it. Never upstream's — that feed carries the English app, signed with a key this
# build does not share.
REPO = "hoodmoshla/nanoMuse-Arabic"
REPO_URL = f"https://github.com/{REPO}"
# Upstream, for attribution only (the source this edition is built on).
UPSTREAM_URL = "https://github.com/nano-muse/nanoMuse"
PRIVACY_URL = f"{UPSTREAM_URL}/blob/main/docs/privacy.md"

# X-Minis-Token is a protocol header; MinisSkills is a path. The tail is an ASCII
# lookahead rather than \b so that "Minis가" (Korean particle) is still caught.
WORD = re.compile(r"(?<!X-)\bMinis(?!Skills)(?![A-Za-z0-9_])")
changed: list[str] = []


def edit(path: Path, subs: list[tuple[str, str]], count: int = 0) -> None:
    text = path.read_text(encoding="utf-8")
    new = text
    for pattern, repl in subs:
        new = re.sub(pattern, repl, new, count=count, flags=re.M)
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))


def gradle() -> None:
    edit(
        APP / "build.gradle.kts",
        [
            (r'applicationId = "[^"]+"', f'applicationId = "{APP_ID}"'),
            (r"versionCode = \d+", f"versionCode = {VERSION_CODE}"),
            (r'versionName = "[^"]+"', f'versionName = "{VERSION_NAME}"'),
        ],
    )


def package_ids() -> None:
    edit(
        RES / "xml" / "shortcuts.xml",
        [
            (r'android:targetPackage="[^"]+"', f'android:targetPackage="{APP_ID}"'),
        ],
    )
    a11y = JAVA / "accessibility" / "MinisAccessibilityService.kt"
    edit(
        a11y,
        [
            (
                r'const val SERVICE_ID = "com\.openminis\.app/\.accessibility\.MinisAccessibilityService"',
                'val SERVICE_ID = "${BuildConfig.APPLICATION_ID}/com.openminis.app.accessibility.'
                'MinisAccessibilityService" // nanoMuse: the applicationId is not the package',
            ),
        ],
    )
    text = a11y.read_text(encoding="utf-8")
    if "import com.openminis.app.BuildConfig" not in text:
        text = text.replace("\nimport ", "\nimport com.openminis.app.BuildConfig\nimport ", 1)
        a11y.write_text(text, encoding="utf-8")


def product_name() -> None:
    for path in sorted(RES.glob("values*/strings.xml")):
        text = path.read_text(encoding="utf-8")
        new = WORD.sub(NAME, text)
        if new != text:
            ET.fromstring(new.encode("utf-8"))
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))
    literal = re.compile(r'"""[\s\S]*?"""|"(?:[^"\\\n]|\\.)*"')
    for path in sorted(JAVA.rglob("*.kt")):
        text = path.read_text(encoding="utf-8")
        new = literal.sub(lambda m: WORD.sub(NAME, m.group(0)), text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))


def soul_defaults() -> None:
    edit(
        JAVA / "agent" / "SoulStore.kt",
        [
            (r'const val DISPLAY_EMOJI = "✨"', 'const val DISPLAY_EMOJI = "🐾"'),
        ],
    )
    # The default-name round-trip follows DEFAULT; explicit stored-name fixtures stay intact.
    test = APP / "src" / "test" / "java" / "com" / "openminis" / "app" / "agent"
    test /= "SoulIconConfigEdgeTest.kt"
    if test.is_file():
        edit(
            test,
            [
                (
                    r'^([ \t]*)assertEquals\("Minis", back\.metadata\.name\)$',
                    r"\1// nanoMuse: round-trip the rebranded default name.\n"
                    r"\1assertEquals(SoulMetadata.DEFAULT.name, back.metadata.name)",
                ),
            ],
        )


def links() -> None:
    owner, repo_name = REPO.split("/")
    edit(
        JAVA / "data" / "UpdateChecker.kt",
        [
            (r'private const val OWNER = "[^"]+"', f'private const val OWNER = "{owner}"'),
            (r'private const val REPO = "[^"]+"', f'private const val REPO = "{repo_name}"'),
            (
                r'const val RELEASES_URL: String = "[^"]+"',
                f'const val RELEASES_URL: String = "{REPO_URL}/releases"',
            ),
        ],
    )
    # nanoMuse-Arabic: the Version row's source. Upstream's download index
    # (nanomuse.cn) and the GitHub feed it falls back to both carry the ENGLISH
    # app, signed with a key this build does not share, so the row must read this
    # edition's releases only — and say so plainly while it has none.
    edit(
        NM_JAVA / "community" / "UpdateCheck.kt",
        [
            (r'[ \t]*const val INDEX_URL: String = "[^"]+"\n', ""),
            (
                r'const val DOWNLOAD_URL = "[^"]+"',
                f'const val DOWNLOAD_URL = "{REPO_URL}/releases"',
            ),
            (
                r'const val GITHUB_LATEST_URL = "[^"]+"',
                f'const val GITHUB_LATEST_URL = "https://api.github.com/repos/{REPO}/releases/latest"',
            ),
        ],
    )
    edit(
        JAVA / "ui" / "settings" / "AboutScreen.kt",
        [
            (r'"https://github\.com/OpenMinis/OpenMinis"\)', f'"{REPO_URL}")'),
        ],
    )
    edit(
        JAVA / "ui" / "settings" / "SettingsScreen.kt",
        [
            (r'"https://openminis\.github\.io/privacy-policy\.html"', f'"{PRIVACY_URL}"'),
            (r'"https://github\.com/OpenMinis/OpenMinis/issues/new"', f'{REPO_URL}/issues/new"'),
        ],
    )


def arabic_edition() -> None:
    """nanoMuse-Arabic: the label the launcher, the task switcher and the
    notifications show.

    The product name itself stays nanoMuse: it is what the strings, the docs and
    the agent's own voice call this thing. The label is what tells the two apps
    apart on a phone that has both, which is the whole point of a standalone
    edition. One line per locale, and only that line — the rest of upstream's
    strings.xml is not ours to edit.
    """
    for path in sorted(RES.glob("values*/strings.xml")):
        edit(
            path,
            [(r'(<string name="app_name">)[^<]+(</string>)', rf"\g<1>{LABEL}\g<2>")],
        )


SYSTEM_SCHEME = (
    "nanomuse-arabic"  # what the system knows this edition by; inside, links stay minis://
)


def schemes() -> None:
    """The scheme this edition registers with the system.

    Upstream registers `nanomuse`; this edition registers `nanomuse-arabic` instead, because the
    phone it exists for already has the official app on it, and two apps claiming one scheme means
    a chooser every time a link, a shortcut or an automation arrives. The in-app vocabulary
    (`minis://…`: the sandbox, the model, every saved conversation) does not change, and
    [OwnScheme] reads both names, so a link in either form still lands here. The rule matches
    upstream's `minis` as well, so it is idempotent on a fresh upstream tree and on this one.
    """
    edit(
        MAIN / "AndroidManifest.xml",
        [
            (
                r'<data android:scheme="(?:minis|nanomuse)" />',
                f'<data android:scheme="{SYSTEM_SCHEME}" />',
            )
        ],
    )
    edit(
        NM_JAVA / "deeplink" / "OwnScheme.kt",
        [(r'const val SYSTEM = "[^"]+"', f'const val SYSTEM = "{SYSTEM_SCHEME}"')],
    )


# (pattern, replacement); applied to Theme.kt only.
THEME_MAP = [
    ("0xFF528AD2", "0xFF015CFB"),  # primary
    ("0xFFB2DFDB", "0xFFE5F0FF"),  # primaryContainer
    ("0xFF00332F", "0xFF012F80"),  # onPrimaryContainer
    ("0xFF4A6360", "0xFF4F5B6E"),  # secondary
    ("0xFFCCE8E4", "0xFFDCE6F5"),  # secondaryContainer
    ("0xFF05201D", "0xFF101C2E"),  # onSecondaryContainer
    ("0xFFF5FAFA", "0xFFF2F2F7"),  # background / surface (overridden by the neutrals)
    ("0xFF171D1C", "0xFF1C1C1E"),  # onBackground / onSurface
    ("0xFFDAE5E2", "0xFFE5E5EA"),  # surfaceVariant
    ("0xFF3F4947", "0xFF3C3C43"),  # onSurfaceVariant (light) / surfaceVariant (dark)
    ("0xFF6F7977", "0xFF6E6E73"),  # outline
    ("0xFF6A94CE", "0xFF58A6FF"),  # dark primary
    ("0xFF003737", "0xFF00224D"),  # dark onPrimary
    ("0xFF1A6B6B", "0xFF1A2B4A"),  # dark primaryContainer
    ("0xFFB1CCC8", "0xFFB8C6DA"),  # dark secondary
    ("0xFF1C3532", "0xFF22304A"),  # dark onSecondary
    ("0xFF334B48", "0xFF334159"),  # dark secondaryContainer
    ("0xFF0E1514", "0xFF000000"),  # dark background / surface
    ("0xFFDEE4E2", "0xFFE5E5EA"),  # dark onBackground / onSurface
    ("0xFFBEC9C6", "0xFFC7C7CC"),  # dark onSurfaceVariant
    ("0xFF899390", "0xFF8E8E93"),  # dark outline
]

# Applied to ChatColors.kt only; light palette first, then dark. The user's own
# message is a black pill in the light theme and a white one in the dark theme
# (docs/design.md); the send button keeps upstream's black / white, so no entry.
CHAT_MAP = [
    ("userBubble = Color(0x1E787880)", "userBubble = Color(0xFF000000)"),
    ("codeBlockText = Color(0xFF34C759)", "codeBlockText = Color(0xFFE5E5EA)"),
    ("inlineCodeText = Color(0xFFFF9500)", "inlineCodeText = Color(0xFF015CFB)"),
    ("blockquoteBar = Color(0x80FF9500)", "blockquoteBar = Color(0x80015CFB)"),
    ("fabAccent = Color(0xFFB7AF96)", "fabAccent = Color(0xFF015CFB)"),
    ("userBubble = Color(0xFF2F3A5C)", "userBubble = Color(0xFFFFFFFF)"),
    ("codeBlockText = Color(0xFF8CF38C)", "codeBlockText = Color(0xFFE5E5EA)"),
    ("inlineCodeText = Color(0xFFFF9F0A)", "inlineCodeText = Color(0xFF58A6FF)"),
    ("blockquoteBar = Color(0x80FF9F0A)", "blockquoteBar = Color(0x8058A6FF)"),
    ("fabAccent = Color(0xFF504C42)", "fabAccent = Color(0xFF58A6FF)"),
]

# The iOS system blues, wherever they are hard-coded (any alpha).
GLOBAL_MAP = [
    (r"0x([0-9A-Fa-f]{2})007AFF", r"0x\g<1>015CFB"),
    (r"0x([0-9A-Fa-f]{2})0A84FF", r"0x\g<1>58A6FF"),
    (r"#007AFF\b", "#015CFB"),
    (r"#0A84FF\b", "#58A6FF"),
]


def colours() -> None:
    edit(JAVA / "ui" / "theme" / "Theme.kt", [(re.escape(a), b) for a, b in THEME_MAP])
    edit(JAVA / "ui" / "theme" / "ChatColors.kt", [(re.escape(a), b) for a, b in CHAT_MAP], count=1)
    for path in sorted(JAVA.rglob("*.kt")) + sorted(RES.rglob("*.xml")):
        edit(path, GLOBAL_MAP)
    edit(RES / "values" / "colors.xml", [(r'(<color name="seed">)#[0-9A-Fa-f]+', r"\g<1>#015CFB")])


def notification_icons() -> None:
    for path in sorted(JAVA.rglob("*.kt")):
        edit(
            path,
            [
                (
                    r"setSmallIcon\(R\.mipmap\.ic_launcher\)",
                    "setSmallIcon(R.drawable.ic_stat_nanomuse) // nanoMuse: flat status-bar mark",
                ),
            ],
        )


FACE = re.compile(
    r"(Notification(?:Compat)?\.Builder\((\w+), [^\n]*\)\n(\s*)\.setSmallIcon\([^\n]*\n)"
    r"(?!\s*\.setLargeIcon)"
)


def notification_faces() -> None:
    """Every notification the agent sends shows its face as the large icon."""

    def add(m: re.Match[str]) -> str:
        ctx, indent = m.group(2), m.group(3)
        return (
            f"{m.group(1)}{indent}.setLargeIcon(io.github.nanomuse.identity.NanoMuseIdentity"
            f".face({ctx})) // nanoMuse: the agent is the sender\n"
        )

    for path in sorted(JAVA.rglob("*.kt")):
        text = path.read_text(encoding="utf-8")
        new = FACE.sub(add, text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))


# Reworded in nanoMuse's voice. Locale dir -> string name -> text.
COPY: dict[str, dict[str, str]] = {
    "values": {
        "sessionlist_welcome_subtitle": "Three steps, and you have an assistant that lives on your phone.",
        "about_minis_tagline": "An open-source personal agent for every device you own. On this phone today; everything runs here, with your own model.",
        "onboarding_welcome_subtitle": "An AI assistant with its own terminal and browser, running on this phone.",
        "bg_service_notification_title": "nanoMuse is working",
    },
    "values-zh": {
        "sessionlist_welcome_subtitle": "三步之后，你就有一个住在手机里的助理。",
        "about_minis_tagline": "一个开源的个人智能体，面向你的所有设备。目前在这台手机上：一切都在本机运行，模型由你自己带。",
        "onboarding_welcome_subtitle": "有自己的终端和浏览器、能用这台手机的 AI 助理。",
        "bg_service_notification_title": "nanoMuse 正在工作",
    },
    "values-zh-rTW": {
        "sessionlist_welcome_subtitle": "三步之後，你就有一個住在手機裡的助理。",
        "about_minis_tagline": "一個開源的個人智慧體，面向你的所有裝置。目前在這支手機上：一切都在本機執行，模型由你自己帶。",
        "onboarding_welcome_subtitle": "有自己的終端機和瀏覽器、能用這支手機的 AI 助理。",
        "bg_service_notification_title": "nanoMuse 正在工作",
    },
}


def reword() -> None:
    for folder, strings in COPY.items():
        subs = [
            (rf'(<string name="{name}">)[^<]*(</string>)', rf"\g<1>{text}\g<2>")
            for name, text in strings.items()
        ]
        edit(RES / folder / "strings.xml", subs)
    # "<name> is browsing": the product name becomes a placeholder in every locale.
    for path in sorted(RES.glob("values*/strings.xml")):
        edit(
            path,
            [
                (
                    rf'(<string name="browser_minis_browsing">[^<]*?){NAME}([^<]*</string>)',
                    r"\g<1>%1$s\g<2>",
                )
            ],
        )


# --- iOS -------------------------------------------------------------------------------------

IOS_ID_RULES = [
    (r"com\.openminis\.app", APP_ID),
    (r"com\.openminis\.MinisTests", "io.github.nanomuse.MinisTests"),
    (r"com\.openminis\.MinisUITests", "io.github.nanomuse.MinisUITests"),
]


def ios_files(*suffixes: str) -> list[Path]:
    out: list[Path] = []
    for path in sorted(IOS.rglob("*")):
        if path.is_file() and path.suffix in suffixes and "Vendor" not in path.parts:
            out.append(path)
    return out


def ios_ids() -> None:
    """Bundle ids, app group, iCloud container, BGTask / URL-scheme / keychain ids: the iOS side
    has no fixed package name, so the whole family moves to ours."""
    for path in ios_files(
        ".swift", ".plist", ".entitlements", ".pbxproj", ".xcscheme", ".xcprivacy"
    ):
        edit(path, IOS_ID_RULES)
    # Stale File Provider domains are matched by prefix; ours now start with our id.
    edit(
        IOS / "MinisApp.swift",
        [(r'contains\("com\.openminis"\)', 'contains("io.github.nanomuse")')],
    )


def ios_schemes() -> None:
    """Same as `schemes()` for the phone's other half: Info.plist registers `nanomuse` and
    `nanomuse-mcp`, the share extension opens `nanomuse://share`; `minis://` stays in-app."""
    edit(
        IOS / "Info.plist",
        [
            (r"<string>minis</string>", f"<string>{SYSTEM_SCHEME}</string>"),
            (r"<string>minis-mcp</string>", f"<string>{SYSTEM_SCHEME}-mcp</string>"),
        ],
    )
    edit(
        IOS / "ShareExtension" / "ShareViewController.swift",
        [(r"minis://share", f"{SYSTEM_SCHEME}://share")],
    )


def ios_project() -> None:
    pbx = IOS / "Minis.xcodeproj" / "project.pbxproj"
    edit(
        pbx,
        [
            # upstream's `1.13` and every version of ours before this one
            (r"MARKETING_VERSION = \d+(?:\.\d+)+;", f"MARKETING_VERSION = {VERSION_NAME};"),
            (r"CURRENT_PROJECT_VERSION = \d+;", f"CURRENT_PROJECT_VERSION = {VERSION_CODE};"),
            (
                r'INFOPLIST_KEY_CFBundleDisplayName = "Share to Minis";',
                f'INFOPLIST_KEY_CFBundleDisplayName = "Share to {NAME}";',
            ),
            (
                r'INFOPLIST_KEY_CFBundleDisplayName = "Minis Files";',
                f'INFOPLIST_KEY_CFBundleDisplayName = "{NAME} Files";',
            ),
            # The app target has no display name of its own (PRODUCT_NAME is the target, "Minis").
            (
                r'(INFOPLIST_FILE = "\$\(SRCROOT\)/Info\.plist";\n)(?!\t*INFOPLIST_KEY_CFBundleDisplayName)',
                f"\\g<1>\t\t\t\tINFOPLIST_KEY_CFBundleDisplayName = {NAME};\n",
            ),
            # The launch screen: upstream's "Open Minis — … is starting" storyboard is left in
            # place; the app shows NanoMuse/NanoMuseLaunch.storyboard (the mark, no words).
            (
                r'INFOPLIST_KEY_UILaunchStoryboardName = "Launch Screen";',
                "INFOPLIST_KEY_UILaunchStoryboardName = NanoMuseLaunch;",
            ),
        ],
    )


def ios_product_name() -> None:
    literal = re.compile(r'"""[\s\S]*?"""|"(?:[^"\\\n]|\\.)*"')
    for path in ios_files(".swift"):
        if "MinisTests" in path.parts or "MinisUITests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        new = literal.sub(lambda m: WORD.sub(NAME, m.group(0)), text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))
    # Info.plist usage descriptions ("Minis uses HealthKit so…") and their per-language
    # InfoPlist.strings / AppShortcuts.strings; the ids in the plists were handled by ios_ids.
    for path in ios_files(".plist", ".strings"):
        if "Vendor" in path.parts or path.name == "PrivacyInfo.xcprivacy":
            continue
        text = path.read_text(encoding="utf-8")
        new = WORD.sub(NAME, text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))
    # Localizable.xcstrings: the English text is the key, so keys move with the literals and
    # every translation's "Minis" moves too (the other languages keep their wording).
    xc = IOS / "Localizable.xcstrings"
    if not xc.exists():
        return
    raw = xc.read_text(encoding="utf-8")
    data = json.loads(raw)

    def walk(node: object) -> object:
        if isinstance(node, dict):
            return {
                k: (WORD.sub(NAME, v) if k == "value" and isinstance(v, str) else walk(v))
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    strings = data.get("strings", {})
    renamed: dict[str, object] = {}
    for key, entry in strings.items():
        new_key = WORD.sub(NAME, key)
        if new_key in renamed and new_key != key:
            continue  # upstream already has the nanoMuse spelling; keep theirs
        renamed[new_key] = walk(entry)
    if renamed != strings:
        data["strings"] = renamed
        xc.write_text(xcstrings_dumps(data, raw), encoding="utf-8")
        changed.append(str(xc.relative_to(ROOT)))


def xcstrings_dumps(data: object, like: str) -> str:
    """Xcode's own layout (2-space indent, ` : `, empty objects spread over three lines, trailing
    newline only if the file had one), keys in the order they were read, so the diff stays at the
    renamed entries."""
    out = json.dumps(data, ensure_ascii=False, indent=2, separators=(",", " : "))
    out = re.sub(
        r"^([ ]*)(.*)\{\}",
        lambda m: f"{m.group(1)}{m.group(2)}{{\n\n{m.group(1)}}}",
        out,
        flags=re.M,
    )
    return out + ("\n" if like.endswith("\n") else "")


def ios_links() -> None:
    edit(
        IOS / "Views" / "Settings" / "AboutView.swift",
        [
            (r'"https://github\.com/OpenMinis"\)', f'"{REPO_URL}")'),
            (r'"https://github\.com/OpenMinis/OpenMinis/issues"\)', f'"{REPO_URL}/issues")'),
            (
                r'"(?:(?:Minis|nanoMuse) is Your Fully Local, Fully Private On-Device Agent'
                r'|A fully open-source, Muse-style personal agent for every device you own)\."',
                '"An open-source personal agent for every device you own."',
            ),
        ],
    )
    edit(
        IOS / "Views" / "ContentView.swift",
        [
            (r'"https://openminis\.github\.io/privacy-policy\.html"', f'"{PRIVACY_URL}"'),
            (r'"https://github\.com/OpenMinis/OpenMinis/issues/new"', f'"{REPO_URL}/issues/new"'),
        ],
    )
    edit(
        IOS / "Views" / "Providers" / "AddProviderView.swift",
        [(r'"https://openminis\.github\.io/privacy-policy\.html"', f'"{PRIVACY_URL}"')],
    )


def ios_soul_defaults() -> None:
    edit(
        IOS / "Agent" / "Session" / "SoulStore.swift",
        [(r'var displayEmoji: String \{ "✨" \}', 'var displayEmoji: String { "🐾" }')],
    )


def ios_colours() -> None:
    """AccentColor: the iOS system blues -> the brand blue (light) and its dark-mode tint."""
    path = IOS / "Assets.xcassets" / "AccentColor.colorset" / "Contents.json"
    if not path.exists():
        return
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    want = {
        None: ("0.004", "0.361", "0.984"),  # #015CFB
        "dark": ("0.345", "0.651", "1.000"),  # #58A6FF
    }
    touched = False
    for entry in data.get("colors", []):
        appearance = None
        for a in entry.get("appearances", []):
            if a.get("appearance") == "luminosity":
                appearance = a.get("value")
        r, g, b = want.get(appearance, want[None])
        comps = entry.setdefault("color", {}).setdefault("components", {})
        new = {"red": r, "green": g, "blue": b, "alpha": comps.get("alpha", "1.000")}
        if comps != new:
            comps.clear()
            comps.update(new)
            touched = True
    if touched:
        path.write_text(xcstrings_dumps(data, raw), encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))


def ios() -> None:
    if not IOS.is_dir():
        return
    ios_ids()
    ios_schemes()
    ios_project()
    ios_product_name()
    ios_links()
    ios_soul_defaults()
    ios_colours()


def ios_check() -> int:
    if not IOS.is_dir():
        return 0
    problems = 0
    leftovers = re.compile(
        r"com\.openminis\.(app|Minis)|openminis\.github\.io|MARKETING_VERSION = (?!"
        + re.escape(VERSION_NAME)
        + r";)"
    )
    for path in ios_files(".swift", ".plist", ".entitlements", ".pbxproj"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if leftovers.search(line):
                print(f"  ! {path.relative_to(ROOT)}:{i}: {line.strip()[:80]}")
                problems += 1
    for path in ios_files(".plist", ".strings"):
        if path.name != "PrivacyInfo.xcprivacy" and WORD.search(path.read_text(encoding="utf-8")):
            print(f"  ! Minis left in {path.relative_to(ROOT)}")
            problems += 1
    plist = (IOS / "Info.plist").read_text(encoding="utf-8")
    if re.search(r"<string>minis(-mcp)?</string>", plist):
        print("  ! Info.plist still registers upstream's URL scheme")
        problems += 1
    share = (IOS / "ShareExtension" / "ShareViewController.swift").read_text(encoding="utf-8")
    if "minis://share" in share:
        print("  ! the share extension still opens minis://share")
        problems += 1
    return problems


def check() -> int:
    problems = 0
    # nanoMuse-Arabic: the identity this edition lives by. The application id in
    # Gradle and in shortcuts.xml must be APP_ID and the label must be LABEL — a
    # miss here is what makes the two apps collide on the same phone, or makes the
    # Arabic one silently update itself to the English one.
    gradle_text = (APP / "build.gradle.kts").read_text(encoding="utf-8")
    for want in (
        f'applicationId = "{APP_ID}"',
        f"versionCode = {VERSION_CODE}",
        f'versionName = "{VERSION_NAME}"',
    ):
        if want not in gradle_text:
            print(f"  ! app/build.gradle.kts lacks {want}")
            problems += 1
    shortcuts = (RES / "xml" / "shortcuts.xml").read_text(encoding="utf-8")
    if f'android:targetPackage="{APP_ID}"' not in shortcuts:
        print(f"  ! shortcuts.xml does not target {APP_ID}")
        problems += 1
    if (NM_JAVA / "community" / "UpdateCheck.kt").exists():
        feed = (NM_JAVA / "community" / "UpdateCheck.kt").read_text(encoding="utf-8")
        if REPO not in feed:
            print(f"  ! UpdateCheck.kt does not read {REPO}")
            problems += 1
        # A mention inside a comment explaining why the feed is ours is fine;
        # an actual URL or repo path in code is the update reading the wrong app.
        feed_code = "\n".join(
            line for line in feed.splitlines() if not line.lstrip().startswith(("*", "//"))
        )
        if "nanomuse.cn" in feed_code or "nano-muse/nanoMuse" in feed_code:
            print("  ! UpdateCheck.kt still points at upstream's release feed")
            problems += 1
    for path in sorted(RES.glob("values*/strings.xml")):
        text = path.read_text(encoding="utf-8")
        if f'<string name="app_name">{LABEL}</string>' not in text:
            print(f"  ! app_name is not {LABEL} in {path.relative_to(ROOT)}")
            problems += 1
        if WORD.search(text):
            print(f"  ! Minis left in {path.relative_to(ROOT)}")
            problems += 1
    leftovers = re.compile(
        r"0x[0-9A-Fa-f]{2}(007AFF|0A84FF|528AD2|6A94CE)|#007AFF|#0A84FF|nanoMuseSkills"
    )
    for path in sorted(JAVA.rglob("*.kt")) + sorted(RES.rglob("*.xml")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if leftovers.search(line):
                print(f"  ! {path.relative_to(ROOT)}:{i}: {line.strip()[:80]}")
                problems += 1
    if 'android:scheme="minis"' in (MAIN / "AndroidManifest.xml").read_text(encoding="utf-8"):
        print("  ! AndroidManifest.xml still registers upstream's URL scheme")
        problems += 1
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    if args not in ([], ["--check"]):
        print(f"usage: {sys.argv[0]} [--check]  (unknown: {' '.join(args)})", file=sys.stderr)
        return 2
    if not APP.is_dir():
        sys.exit(f"{APP} not found")
    if args == ["--check"]:
        problems = check() + ios_check()
        print("clean" if problems == 0 else f"{problems} leftovers")
        return 1 if problems else 0
    gradle()
    package_ids()
    arabic_edition()
    product_name()
    soul_defaults()
    links()
    schemes()
    colours()
    notification_icons()
    notification_faces()
    reword()
    ios()
    for path in sorted(set(changed)):
        print(f"  edited {path}")
    print(f"{len(set(changed))} files changed")
    problems = check() + ios_check()
    print("clean" if problems == 0 else f"{problems} leftovers")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
