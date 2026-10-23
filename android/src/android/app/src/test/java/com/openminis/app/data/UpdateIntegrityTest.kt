package com.openminis.app.data

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class UpdateIntegrityTest {
    @Test fun numericComparisonBeatsTextOrder() {
        assertTrue(UpdateChecker.compareVersions("1.0.5.1", "1.0.1.2") > 0)
        assertTrue(UpdateChecker.compareVersions("1.0.10", "1.0.9") > 0)
        assertEquals(0, UpdateChecker.compareVersions("v1.0.5", "1.0.5"))
        assertTrue(UpdateChecker.compareVersions("1.0.5", "1.0.5.1") < 0)
    }

    @Test fun onlyThisEditionHttpsReleaseIsTrusted() {
        assertTrue(
            UpdateChecker.isTrustedDownloadUrl(
                "https://github.com/hoodmoshla/nanoMuse-Arabic/releases/download/v1.0.5.1/app.apk",
            ),
        )
        assertFalse(
            UpdateChecker.isTrustedDownloadUrl(
                "https://github.com/nano-muse/nanoMuse/releases/download/v1.0.5/app.apk",
            ),
        )
        assertFalse(UpdateChecker.isTrustedDownloadUrl("http://github.com/hoodmoshla/nanoMuse-Arabic/releases/download/v1/app.apk"))
        assertFalse(UpdateChecker.isTrustedDownloadUrl("https://example.com/hoodmoshla/nanoMuse-Arabic/releases/download/v1/app.apk"))
    }

    @Test fun publishedDigestIsReadAndNormalised() {
        val digest = "A".repeat(64)
        val assets = JSONArray().put(
            JSONObject().put("name", "app.apk.sha256").put("digest_text", "sha256:$digest  app.apk"),
        )
        assertEquals(digest.lowercase(), UpdateChecker.publishedSha256(assets, "app.apk"))
        assertNull(UpdateChecker.publishedSha256(assets, "other.apk"))
        assertNull(UpdateChecker.normalizeSha256("not a digest"))
    }

    @Test fun fileDigestMatchesKnownBytes() {
        val file = File.createTempFile("update-integrity", ".bin")
        file.writeBytes("nanoMuse-Arabic".toByteArray())
        assertEquals(64, UpdateChecker.sha256(file).length)
        assertEquals(UpdateChecker.sha256(file), UpdateChecker.sha256(file))
        file.delete()
    }
}
