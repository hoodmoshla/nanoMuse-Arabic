#!/usr/bin/env bash
# Create the permanent signing key of the standalone Arabic edition — once — and wire it into this
# repository's secrets and variables. Run it on the machine that will keep the key.
#
#   bash scripts/arabic-signing-setup.sh [--repo OWNER/NAME] [--key PATH] [--check]
#
# It is safe to run more than once: an existing key is REUSED, never replaced, and the only thing
# a second run does is re-read its fingerprint and re-set the secrets. Replacing the key would
# make every installed copy of the app permanent: an APK under a new key cannot install over one
# signed with the old key, so the two secrets and the fingerprint are the app's identity.
#
# What it never does:
#   * print the keystore, the password, or the base64 blob;
#   * put the password in the command line (every keytool call reads it from the environment with
#     -storepass:env, so it never appears in `ps` or in a shell history);
#   * write the key inside the repository, or touch Git at all;
#   * create a key when one already exists at --key.
#
# The password is typed once, with the terminal echo off. It goes to three places only: the
# keystore file, the ARABIC_KEYSTORE_PASSWORD secret, and the summary you must keep with your
# backup. Nothing else on this machine remembers it.
set -euo pipefail

REPO="hoodmoshla/nanoMuse-Arabic"
KEY_FILE="$HOME/nanomuse-arabic-release.jks"
ALIAS="nanomuse-arabic"
DNAME="CN=nanoMuse-Arabic, OU=standalone Arabic edition, O=nanoMuse-Arabic"
CHECK_ONLY=0
PASSWORD_ENV="NM_ARABIC_KEYSTORE_PASSWORD"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="${2:-}"; shift ;;
    --key) KEY_FILE="${2:-}"; shift ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# The password lives in the environment and nowhere else, and this unsets it on every exit path.
trap 'unset "$PASSWORD_ENV" 2>/dev/null || true' EXIT

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---- 1. the repository, and the right to write its secrets ---------------------
say "== repository $REPO"
command -v gh >/dev/null || die "gh is not installed (https://cli.github.com)"
gh auth status >/dev/null 2>&1 || die "gh is not signed in — run: gh auth login"
admin="$(gh api "repos/$REPO" --jq '.permissions.admin' 2>/dev/null || echo false)"
[ "$admin" = "true" ] || die "this token is not an admin of $REPO; secrets and variables need that"
say "   signed in, with admin rights"

# ---- 2. the key file is outside the repository --------------------------------
case "$(cd "$(dirname "$KEY_FILE")" 2>/dev/null && pwd || echo "$KEY_FILE")/$(basename "$KEY_FILE")" in
  "$REPO_ROOT"/*) die "refusing to keep the key inside the repository ($KEY_FILE)" ;;
esac

if [ "$CHECK_ONLY" = 1 ]; then
  say "== --check: nothing is created, nothing is written"
  [ -f "$KEY_FILE" ] && say "   key: $KEY_FILE (present)" || say "   key: $KEY_FILE (NOT there yet — run without --check to create it)"
  say "   secrets: $(gh secret list --repo "$REPO" --json name --jq '[.[].name] | join(", ")' 2>/dev/null || echo '?')"
  say "   variables: $(gh variable list --repo "$REPO" --json name,value --jq '[.[] | .name] | join(", ")' 2>/dev/null || echo '?')"
  exit 0
fi

# ---- 3. the password, typed once, never echoed --------------------------------
command -v keytool >/dev/null || die "keytool is not on PATH — install a JDK 17+"
if [ -f "$KEY_FILE" ]; then
  say "== an existing key is used as it is: $KEY_FILE"
else
  say "== a new key will be created: $KEY_FILE"
fi
printf 'keystore password (typing is hidden): ' >&2
read -rs "$PASSWORD_ENV" || die "no password given"
printf '\n' >&2
[ -n "${!PASSWORD_ENV}" ] || die "the password is empty"
export "$PASSWORD_ENV"

# ---- 4. the key, once ---------------------------------------------------------
if [ ! -f "$KEY_FILE" ]; then
  umask 077
  # -storepass:env keeps the password out of the process arguments; PKCS12 keeps one password for
  # the store and the key, which is what the release workflow assumes.
  keytool -genkeypair -v \
    -keystore "$KEY_FILE" \
    -alias "$ALIAS" \
    -keyalg RSA -keysize 4096 -validity 10000 \
    -storetype PKCS12 \
    -dname "$DNAME" \
    -storepass:env "$PASSWORD_ENV" >/dev/null || die "keytool could not create the key"
  chmod 600 "$KEY_FILE"
  say "   created, alias $ALIAS, 4096-bit RSA, valid 27 years"
else
  keytool -list -keystore "$KEY_FILE" -alias "$ALIAS" -storepass:env "$PASSWORD_ENV" >/dev/null 2>&1 \
    || die "the key at $KEY_FILE has no private key under the alias '$ALIAS'"
  say "   reused, alias $ALIAS (never replaced)"
fi

# ---- 5. the fingerprint, as the release script will compare it ----------------
fingerprint="$(keytool -list -v -keystore "$KEY_FILE" -alias "$ALIAS" \
  -storepass:env "$PASSWORD_ENV" 2>/dev/null \
  | sed -nE 's/.*SHA256: //p' | head -1 | tr -d ':' | tr 'A-F' 'a-f' | tr -d '[:space:]')"
[ -n "$fingerprint" ] || die "could not read the certificate fingerprint"
say "== certificate SHA-256: $fingerprint"

# ---- 6. the two secrets and the pinned fingerprint ---------------------------
b64() { # a single line of base64, GNU or BSD
  if openssl base64 -A -in "$1" 2>/dev/null; then return 0; fi
  if base64 -w0 "$1" 2>/dev/null; then return 0; fi
  base64 -i "$1"
}
say "== secrets"
b64 "$KEY_FILE" | gh secret set ARABIC_KEYSTORE_BASE64 --repo "$REPO"
printf '%s' "${!PASSWORD_ENV}" | gh secret set ARABIC_KEYSTORE_PASSWORD --repo "$REPO"
say "   ARABIC_KEYSTORE_BASE64, ARABIC_KEYSTORE_PASSWORD"
gh variable set ARABIC_CERT_SHA256 --body "$fingerprint" --repo "$REPO"
say "   ARABIC_CERT_SHA256 = $fingerprint"

# ---- 7. what is now true -----------------------------------------------------
say
say "Secrets now on $REPO:"
gh secret list --repo "$REPO" | sed 's/^/   /'
say "Variables now on $REPO:"
gh variable list --repo "$REPO" | sed 's/^/   /'
cat <<EOF

Keep these two things together, offline, and never regenerate the key:
  * a copy of $KEY_FILE (two copies, on two machines or two drives)
  * the password you just typed

Then release, once, from anywhere:

  gh workflow run "Arabic release" -f revision=1 -f publish=true --repo $REPO

and from then on every merged sync pull request publishes the next revision by itself.
EOF
