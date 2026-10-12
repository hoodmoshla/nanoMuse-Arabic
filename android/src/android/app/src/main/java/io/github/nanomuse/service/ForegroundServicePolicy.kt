package io.github.nanomuse.service

/**
 * nanoMuse-Arabic: the one place that decides whether the agent's foreground service runs.
 *
 * The service exists for a single reason — to keep the process alive while the agent has work to
 * do — and it should be running exactly then. Before this file, the answer was
 *
 *     activeSessions.isNotEmpty() || presentSessions.isNotEmpty()
 *
 * where `presentSessions` marked "the user is sitting on a chat screen". That made the service
 * outlive the work by design: pressing Home from a chat left the marker set, so the service and
 * its permanent notification stayed for as long as the process lived, with nothing to do. The
 * marker was added to hold the process at adj=200 across a brief absence; what it actually held
 * was a notification the user could not get rid of except by swiping the app away.
 *
 * Two rules follow, and they are the whole policy:
 *
 *  - **The work decides.** Anything that needs the process alive — a running turn, a tool, a
 *    scheduled task about to start — is a reason to run; nothing else is.
 *  - **The UI is not work.** The screen being visible is not a reason to run the service (the
 *    process is already in the foreground), and the screen going away is not a reason to stop one
 *    that has work. Visibility is only a *moment to ask the question again*, which is why
 *    [shouldRun] has no such parameter: an event cannot change its answer, only re-ask it.
 *
 * [shouldRun] is pure, so the six cases that matter are unit-tested in
 * `ForegroundServicePolicyTest` rather than described: leaving the app with nothing to do, leaving
 * with a task running, the last task finishing, a task being cancelled, several tasks where only
 * the last one matters, and coming back to the app.
 */
object ForegroundServicePolicy {

    /**
     * Whether the foreground service should be running, given what the agent has to do.
     *
     * @param activeTasks turns in flight right now (an LLM call, a tool, a sandbox command).
     * @param pendingTasks work accepted but not started yet — a scheduled task, a queued turn.
     *   It counts because the window it covers is exactly the one where the process must not be
     *   reclaimed: between "this will run" and "this is running".
     */
    fun shouldRun(activeTasks: Int, pendingTasks: Int): Boolean =
        activeTasks > 0 || pendingTasks > 0

    /** Why the answer is what it is, for the log line at every transition. */
    fun describe(activeTasks: Int, pendingTasks: Int): String = when {
        activeTasks > 0 && pendingTasks > 0 -> "$activeTasks running, $pendingTasks pending"
        activeTasks > 0 -> "$activeTasks running"
        pendingTasks > 0 -> "$pendingTasks pending"
        else -> "nothing to do"
    }
}
