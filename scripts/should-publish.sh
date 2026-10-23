#!/usr/bin/env bash
# Should this run publish the release? Prints `true` or `false`.
#
#   scripts/should-publish.sh <event-name> [<publish-input>]
#
#   workflow_dispatch true    → true    a dispatch that asked for it
#   workflow_dispatch false   → false   a dispatch that asked to build and verify only
#   workflow_dispatch ""      → false   a dispatch with the input unset
#   pull_request true|false|  → false   a pull request never publishes, even when
#                                        the input asks and even when it is absent
#
# A pull request used to publish unconditionally. That is how a verify-only run on
# codex/upstream-full-sync created tag v1.0.6.1 and a public release, although the
# command line never passed --publish. The event name is not a request to publish.
# A release after a merge is a workflow_dispatch, or a later job whose event is not
# pull_request, and it still has to pass `true` on purpose.
#
# Why this is a script and not a GitHub expression, which is where it went wrong:
#
#   publish="${{ github.event_name == 'pull_request' || inputs.publish == 'true' }}"
#
# `publish` is declared `type: boolean`, so `inputs.publish` is a **boolean**, and comparing a
# boolean with the string `'true'` does not do what it reads like. The expression engine coerces
# mismatched types to numbers — `true` becomes 1, `'true'` becomes NaN — and `1 == NaN` is false.
# The release then built, signed, verified the pinned certificate of a real APK, kept it as an
# artifact and published nothing, with `publish=false` in the log and no tag to show for it.
#
# Here the comparison is a shell `case`, on a value lower-cased first, so it is the same for
# `true`, `True` and an empty input, and it can be tested without a runner.
set -uo pipefail

event="${1:-}"
input="$(printf '%s' "${2:-}" | tr '[:upper:]' '[:lower:]')"

case "$event:$input" in
  pull_request:*) echo false ;;
  *:true) echo true ;;
  *) echo false ;;
esac
