package io.github.nanomuse.service

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The six cases the foreground service's life depends on.
 *
 * Each one is a state the agent can be in when something asks the question again — a task started,
 * a task settled, the UI went away or came back. The policy is pure, so these run everywhere with
 * no device and no service, which is the point of having the decision in one testable place: the
 * bug this replaces (`presentSessions` keeping the service alive with nothing to do) was a
 * decision nobody could test without a phone in hand.
 */
class ForegroundServicePolicyTest {

    /** Nothing running, nothing queued: the app is idle. */
    @Test
    fun `leaving the app with no work stops the service`() {
        assertFalse(ForegroundServicePolicy.shouldRun(activeTasks = 0, pendingTasks = 0))
        assertEquals("nothing to do", ForegroundServicePolicy.describe(0, 0))
    }

    /** The user started a turn and pressed Home while it runs. */
    @Test
    fun `a task started before leaving keeps the service running`() {
        assertTrue(ForegroundServicePolicy.shouldRun(activeTasks = 1, pendingTasks = 0))
        assertEquals("1 running", ForegroundServicePolicy.describe(1, 0))
    }

    /** The work was accepted but has not begun — a scheduled task, a queued turn. */
    @Test
    fun `work that is queued but not started keeps the service running`() {
        assertTrue(ForegroundServicePolicy.shouldRun(activeTasks = 0, pendingTasks = 1))
        assertTrue(ForegroundServicePolicy.shouldRun(activeTasks = 1, pendingTasks = 2))
        assertEquals("1 running, 2 pending", ForegroundServicePolicy.describe(1, 2))
    }

    /** The last turn finished: nothing is left for the service to keep alive. */
    @Test
    fun `the last task finishing stops the service`() {
        assertTrue(ForegroundServicePolicy.shouldRun(1, 0))
        assertFalse(ForegroundServicePolicy.shouldRun(0, 0))
    }

    /** A cancelled task is a finished one: it stops being a reason to run. */
    @Test
    fun `a cancelled task stops being a reason to run`() {
        assertTrue(ForegroundServicePolicy.shouldRun(activeTasks = 1, pendingTasks = 0))
        val afterCancel = 1 - 1
        assertFalse(ForegroundServicePolicy.shouldRun(afterCancel, 0))
    }

    /** Several tasks at once: only the last one to settle may stop the service. */
    @Test
    fun `several tasks keep the service until the last one ends`() {
        assertTrue("three running", ForegroundServicePolicy.shouldRun(3, 0))
        assertTrue("two left", ForegroundServicePolicy.shouldRun(2, 0))
        assertTrue("one left", ForegroundServicePolicy.shouldRun(1, 0))
        assertFalse("none left", ForegroundServicePolicy.shouldRun(0, 0))
    }

    /**
     * Coming back to the app is not a reason to start the service: nothing is running, so there is
     * nothing to keep alive, and the visible app is already in the foreground. This is the half of
     * the old behaviour that put a permanent notification on screen for a user who was looking at
     * the app anyway.
     */
    @Test
    fun `coming back to the app does not start the service by itself`() {
        assertFalse(ForegroundServicePolicy.shouldRun(activeTasks = 0, pendingTasks = 0))
    }

    /** And the UI going away never stops work that is still on its way. */
    @Test
    fun `the ui going away cannot stop work in flight`() {
        for (active in 1..3) {
            assertTrue(ForegroundServicePolicy.shouldRun(active, 0))
        }
    }

    /** A process restart with no remembered work does not revive the notification. */
    @Test
    fun `a restart with no work does not keep the service`() {
        assertFalse(ForegroundServicePolicy.shouldRun(activeTasks = 0, pendingTasks = 0))
    }

    /**
     * A task accepted from another device is pending work, not a reason to leave the service
     * running after it ends. HubService is a separate connection and is not decided here.
     */
    @Test
    fun `a task from another device keeps the service only while it is pending`() {
        assertTrue(ForegroundServicePolicy.shouldRun(activeTasks = 0, pendingTasks = 1))
        assertFalse(ForegroundServicePolicy.shouldRun(activeTasks = 0, pendingTasks = 0))
    }
}
