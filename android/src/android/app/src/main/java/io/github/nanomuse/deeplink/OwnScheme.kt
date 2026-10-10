package io.github.nanomuse.deeplink

import android.content.Context
import android.content.Intent
import android.net.Uri

/**
 * The two names of the app's own links.
 *
 * Inside the app a link is `minis://…`: that is upstream's vocabulary, shared with the sandbox
 * and with the model (`minis://attachments/x.png`, `minis://settings/soul`, the system prompt,
 * every saved conversation), and it stays. What the app registers with Android is
 * `nanomuse-arabic` (`AndroidManifest.xml`): upstream's `nanomuse` would be claimed by the
 * official app on this phone as well, which is a chooser every time a link arrives, and
 * `minis` is OpenMinis's. A `nanomuse-arabic://…` link coming in from outside means the same as
 * its `minis://…` form; a link the app opens on itself goes to its own activity by name, never
 * through the system's resolution of a scheme.
 */
object OwnScheme {
    /** What the manifest registers: the name other apps and web pages can address. */
    const val SYSTEM = "nanomuse-arabic"

    /**
     * Upstream's system scheme, still read.
     *
     * This phone also runs the official app, so this edition registers `nanomuse-arabic` instead
     * of claiming the same name; a `nanomuse://…` link written before that rename (a saved
     * conversation, a bookmark, a Shortcut, an automation) still means what it meant.
     */
    const val UPSTREAM_SYSTEM = "nanomuse"

    /** Upstream's in-app vocabulary; never registered with the system. */
    const val INTERNAL = "minis"

    /** The activity that takes every deep link, named so no scheme resolution is involved. */
    const val ACTIVITY = "com.openminis.app.MainActivity"

    /** Whether [scheme] is one of the app's own names. */
    fun isOwn(scheme: String?): Boolean {
        val s = scheme?.lowercase() ?: return false
        return s == INTERNAL || s == SYSTEM || s == UPSTREAM_SYSTEM
    }

    /** `nanomuse-arabic://x` (or `nanomuse://x`) read as `minis://x`; any other scheme as written. */
    fun internal(scheme: String?): String? {
        val s = scheme?.lowercase() ?: return null
        return if (s == SYSTEM || s == UPSTREAM_SYSTEM) INTERNAL else scheme
    }

    /** The `minis://…` form of [url] when it is one of the app's system links; else [url]. */
    fun internalUrl(url: String): String {
        for (scheme in listOf(SYSTEM, UPSTREAM_SYSTEM)) {
            val prefix = "$scheme://"
            if (url.regionMatches(0, prefix, 0, prefix.length, ignoreCase = true)) {
                return "$INTERNAL://" + url.substring(prefix.length)
            }
        }
        return url
    }

    /** A VIEW intent for [uri] addressed to the app's own activity; [flags] as the caller needs. */
    fun intent(context: Context, uri: Uri, flags: Int = Intent.FLAG_ACTIVITY_NEW_TASK): Intent =
        Intent(Intent.ACTION_VIEW, uri).apply {
            setClassName(context.packageName, ACTIVITY)
            addFlags(flags)
        }
}
