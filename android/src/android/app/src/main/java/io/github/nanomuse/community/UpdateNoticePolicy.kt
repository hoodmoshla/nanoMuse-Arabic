package io.github.nanomuse.community

/**
 * nanoMuse-Arabic: whether the update notice should appear again.
 *
 * Finding a newer release is not a reason to announce it on every launch. The notice is shown
 * once for a version, then stays quiet for [QUIET_MS] unless the person asks from Settings.
 * A different newer version is a new fact, so it is announced on its own.
 *
 * Pure on purpose: the screen stores the pair this returns, and [UpdateNoticePolicyTest] covers
 * the cases without a device.
 */
object UpdateNoticePolicy {
    /** A day. Long enough not to nag, short enough that a person who dismissed it still hears once. */
    const val QUIET_MS = 24L * 60 * 60 * 1000

    fun shouldShow(
        latest: String?,
        newer: Boolean,
        acknowledgedVersion: String?,
        acknowledgedAt: Long,
        now: Long,
    ): Boolean {
        if (!newer || latest.isNullOrBlank()) return false
        if (acknowledgedVersion != latest) return true
        return now - acknowledgedAt >= QUIET_MS
    }
}
