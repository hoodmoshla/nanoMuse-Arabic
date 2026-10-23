package io.github.nanomuse.community

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateNoticePolicyTest {
    private val now = 1_700_000_000_000L

    @Test fun noNewerReleaseIsQuiet() {
        assertFalse(UpdateNoticePolicy.shouldShow("1.0.5.1", false, null, 0L, now))
        assertFalse(UpdateNoticePolicy.shouldShow(null, true, null, 0L, now))
    }

    @Test fun aNewVersionIsAnnouncedOnce() {
        assertTrue(UpdateNoticePolicy.shouldShow("1.0.5.1", true, null, 0L, now))
        assertTrue(UpdateNoticePolicy.shouldShow("1.0.5.1", true, "1.0.5.0", now, now))
    }

    @Test fun theSameVersionStaysQuietForADay() {
        assertFalse(
            UpdateNoticePolicy.shouldShow("1.0.5.1", true, "1.0.5.1", now - 60_000L, now),
        )
        assertTrue(
            UpdateNoticePolicy.shouldShow(
                "1.0.5.1",
                true,
                "1.0.5.1",
                now - UpdateNoticePolicy.QUIET_MS,
                now,
            ),
        )
    }
}
