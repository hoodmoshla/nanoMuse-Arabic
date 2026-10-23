"""The foreground service is started and stopped in exactly one place — and these say so.

What the service should do is tested where it can be: `ForegroundServicePolicyTest` (Kotlin, run by
the Android job) covers the six states, because the policy is pure. What that cannot see is whether
the pieces are still wired to it, and the bug this replaces was exactly a wiring bug: the service
was kept alive by `presentSessions`, a marker for "the user is looking at the app", so it and its
permanent notification outlived every task. Nobody could test that without a phone.

These are structural guards, and they are cheap: a file that starts announcing the service on its
own, or a service that the system is allowed to revive with nothing to do, would put the
notification back on screen and no assertion anywhere else would notice.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "android/src/android/app/src/main/java"
TRACKER = MAIN / "com/openminis/app/service/SessionActivityTracker.kt"
SERVICE = MAIN / "com/openminis/app/service/AgentForegroundService.kt"
RUNNER = MAIN / "com/openminis/app/scheduled/ScheduledAgentRunner.kt"
APP = MAIN / "com/openminis/app/MinisApp.kt"
POLICY = MAIN / "io/github/nanomuse/service/ForegroundServicePolicy.kt"


def test_the_policy_is_the_only_thing_that_decides() -> None:
    tracker = TRACKER.read_text(encoding="utf-8")
    assert "ForegroundServicePolicy.shouldRun" in tracker, "the tracker decides on its own again"
    # The old rule, in one line, is what kept a notification on screen for a user who was merely
    # reading a chat. It must not come back. (Presence is still read for the notification's copy,
    # which is why this matches the decision's own shape rather than the name.)
    assert (
        "_activeSessions.value.isNotEmpty() || _presentSessions.value.isNotEmpty()" not in tracker
    ), "presence is deciding whether the service runs again"
    assert tracker.count("private fun reconcileService()") == 1


def test_only_the_tracker_starts_the_service() -> None:
    starters = [
        path.relative_to(ROOT).as_posix()
        for path in MAIN.rglob("*.kt")
        if "AgentForegroundService.startService(" in path.read_text(encoding="utf-8")
    ]
    assert starters == [
        "android/src/android/app/src/main/java/com/openminis/app/service/SessionActivityTracker.kt"
    ], f"more than one place starts the service: {starters}"


def test_scheduled_work_registers_itself_instead_of_starting_the_service() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    assert "SessionActivityTracker.setPending(" in runner, (
        "a scheduled run does not register as work"
    )
    assert "pendingId" in runner
    # Once on the background scope, the run owns the registration: releasing it when the function
    # returns would stop the service while the agent is still working.
    assert "handedToBackground" in runner


def test_the_service_cannot_be_revived_with_nothing_to_do() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    assert "return START_NOT_STICKY" in service
    assert "return START_STICKY" not in service, (
        "a sticky service is restarted by the system after the process dies, with no work"
    )


def test_the_notification_goes_with_the_service() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    destroy = service.index("override fun onDestroy()")
    body = service[destroy : destroy + 900]
    assert "NOTIFICATION_ID)" in body, "onDestroy does not cancel the permanent notification"
    assert "stopForeground" in body


def test_the_ui_tells_the_tracker_it_came_and_went() -> None:
    app = APP.read_text(encoding="utf-8")
    assert "SessionActivityTracker.onUiHidden()" in app, (
        "leaving the app does not re-ask the question"
    )
    assert "SessionActivityTracker.onUiShown()" in app
    # Leaving the UI must not stop a run: the callback re-asks, and only the policy answers. The
    # one place the app does stop the service is the foreground-service-timeout handler, which
    # exists to drop a notification the system is about to tear down anyway.
    stopped = app.index("override fun onActivityStopped")
    callback = app[stopped : stopped + 900]
    assert "onUiHidden()" in callback
    assert "stopService" not in callback, "leaving the app stops the service instead of re-asking"


def test_the_policy_file_has_no_android_dependency() -> None:
    """It has to stay pure: that is what makes the six cases testable without a device."""
    policy = POLICY.read_text(encoding="utf-8")
    assert "import android" not in policy
    assert "import androidx" not in policy
