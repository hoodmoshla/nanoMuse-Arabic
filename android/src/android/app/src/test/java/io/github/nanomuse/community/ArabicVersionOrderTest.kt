package io.github.nanomuse.community

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * nanoMuse-Arabic: the edition's own version line, held in place where it is read.
 *
 * `scripts/arabic-release-apk.sh` names a release `<upstream version>.<revision>` — 1.0.1.1,
 * 1.0.1.2 — and a dash in there would break the whole update path silently:
 * `UpdateChecker.normalizeTag` cuts a version at its first `-` (that is how upstream sorts
 * `1.2.3-rc1` below `1.2.3`), so `1.0.1-ar.2` and the release tag for it would both read back as
 * `1.0.1`, equal to the installed build, and the About page's *App Update* — the path that
 * downloads and installs — would call it up to date for ever.
 *
 * A numeric fourth component survives that untouched and still sorts above the base it sits on,
 * which is what these four assertions pin. They do not read `BuildConfig.VERSION_NAME`: the
 * released version is written at build time and never committed, so the committed value is the
 * upstream base these are compared against.
 */
class ArabicVersionOrderTest {

    @Test
    fun `a revision is newer than the one before it`() {
        assertTrue(UpdateCheck.isNewer("1.0.1.2", "1.0.1.1"))
        assertFalse(UpdateCheck.isNewer("1.0.1.1", "1.0.1.1"))
        assertFalse(UpdateCheck.isNewer("1.0.1.1", "1.0.1.2"))
    }

    @Test
    fun `a revision is newer than the base it sits on`() {
        assertTrue(UpdateCheck.isNewer("1.0.1.1", "1.0.1"))
        assertFalse(UpdateCheck.isNewer("1.0.1", "1.0.1.1"))
    }

    @Test
    fun `the next base wins over any revision of the last one`() {
        assertTrue(UpdateCheck.isNewer("1.0.2.1", "1.0.1.9"))
        assertFalse(UpdateCheck.isNewer("1.0.1.9", "1.0.2.1"))
    }

    @Test
    fun `the tag of a release reads back as its version`() {
        // The row compares a tag with a versionName; `/releases/latest` answers with the tag.
        for (version in listOf("1.0.1.1", "1.0.1.2", "1.0.2.3")) {
            assertFalse("v$version must not read as newer than $version", UpdateCheck.isNewer("v$version", version))
            assertTrue("v$version is newer than the base it sits on", UpdateCheck.isNewer("v$version", "1.0.0"))
        }
    }
}
