#!/usr/bin/env bash
# Print the SHA-256 of the signer certificate from `apksigner verify --print-certs` output.
#
#   "$ANDROID_HOME"/build-tools/*/apksigner verify --print-certs app.apk \
#     | scripts/apksigner-fingerprint.sh
#
# Prints 64 lower-case hex characters and exits 0, or prints nothing and exits 1.
#
# Why this is a file of its own: the text it reads has changed shape between build-tools releases.
# The long-standing one names the signer
#
#   Signer #1 certificate SHA-256 digest: 9802a6008e5aefad9e2847a4006a9ed189025170cd4c0558c4c16c0e18a12a5b
#
# and others print the scheme the signature was verified with instead
#
#   V2 Signer: certificate SHA-256 digest: 9802a6008e5aefad9e2847a4006a9ed189025170cd4c0558c4c16c0e18a12a5b
#
# A reader that matches one prefix stops working the day the runner's build-tools are updated, and
# the failure it produces ("could not read the signing certificate") says nothing about why. So
# this one looks for a line that mentions SHA-256 and takes the digest off it, whatever is written
# in front — and the digest is the certificate's own, not a value from anywhere else.
#
# `keytool -list -v` prints the same digest as `SHA256: AB:CD:…`, which is why the colons are
# stripped too: one normalisation, one comparison, whatever produced the line.
set -uo pipefail

digest="$(
  grep -iE '(^|[^0-9a-z])sha-?256([^0-9a-z]|$)' 2>/dev/null \
    | grep -oE '([0-9a-fA-F]{2}:){31}[0-9a-fA-F]{2}|[0-9a-fA-F]{64}' 2>/dev/null \
    | head -1 \
    | tr -d ':' \
    | tr 'A-F' 'a-f'
)"

# A digest and nothing else: anything shorter or longer is not a SHA-256 fingerprint.
if ! printf '%s' "$digest" | grep -qE '^[0-9a-f]{64}$'; then
  exit 1
fi
printf '%s\n' "$digest"
