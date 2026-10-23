package io.github.nanomuse.community

import android.content.Context
import com.openminis.app.BuildConfig
import com.openminis.app.logging.AppLogger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * The installed version and the latest one, side by side (shared contract C2). The latest
 * comes from this edition's own GitHub releases; it is
 * looked up at most once a day and the answer kept, with a "check now" for a stale or failed
 * check. Only the two lines of the Version row live on this; the in-app APK download on the
 * About page is the [com.openminis.app.data.UpdateChecker], which reads the same repository.
 *
 * nanoMuse-Arabic: it reads the standalone edition's feed and nothing else. Upstream's
 * download index (nanomuse.cn) and upstream's GitHub releases both carry the ENGLISH app,
 * signed with a key this build does not share, so showing one of their versions here would
 * offer an update that can never install. [State.noRelease] is the third answer — the feed
 * was read and holds no release of this edition yet — so the row can say that plainly
 * instead of calling it a failure.
 */
object UpdateCheck {
    private const val TAG = "UpdateCheck"
    private const val PREFS = "nm.update"
    private const val KEY_LATEST = "latest"
    private const val KEY_CHECKED_AT = "checked_at"
    private const val KEY_FAILED = "failed"
    private const val KEY_NO_RELEASE = "no_release"
    private const val KEY_ACK_VERSION = "ack_version"
    private const val KEY_ACK_AT = "ack_at"

    /** Where "Update" goes: this edition's releases, never upstream's download page. */
    const val DOWNLOAD_URL = "https://github.com/hoodmoshla/nanoMuse-Arabic/releases"
    const val GITHUB_LATEST_URL = "https://api.github.com/repos/hoodmoshla/nanoMuse-Arabic/releases/latest"

    /** A check is repeated at most this often on its own. */
    const val FRESH_MS = 24L * 60 * 60 * 1000

    data class State(
        /** The newest release known, without the `v` (null = never found out). */
        val latest: String? = null,
        /** When the last check ran, epoch ms (0 = never). */
        val checkedAt: Long = 0L,
        /** No source could be reached. */
        val failed: Boolean = false,
        /** A source was reached and this edition has published no release yet. */
        val noRelease: Boolean = false,
        val checking: Boolean = false,
    ) {
        /** The latest is newer than this build. */
        val newer: Boolean get() = latest != null && isNewer(latest, BuildConfig.VERSION_NAME)

        /**
         * A newer release the person has not been told about in the last day. Settings can
         * still show the version; this only decides the notice.
         */
        fun shouldNotify(acknowledgedVersion: String?, acknowledgedAt: Long, now: Long): Boolean =
            UpdateNoticePolicy.shouldShow(latest, newer, acknowledgedVersion, acknowledgedAt, now)
    }

    /** What the feed had to say. The three answers are not the same answer. */
    internal sealed interface Feed {
        /** A release of this edition is published; its tag, normalised. */
        data class Version(val latest: String) : Feed

        /** The repository answered and carries no release yet. GitHub says 404 for that. */
        data object Empty : Feed

        /** Nothing answered, or the answer was not one we understand. */
        data object Unreachable : Feed
    }

    private val _state = MutableStateFlow<State?>(null)

    /** The state as the screens follow it; [load] fills it from the prefs first. */
    val state: StateFlow<State?> = _state.asStateFlow()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val checking = AtomicBoolean(false)
    private val http: OkHttpClient by lazy {
        OkHttpClient.Builder().connectTimeout(5, TimeUnit.SECONDS).readTimeout(5, TimeUnit.SECONDS).build()
    }

    private fun prefs(context: Context) = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** "0.1.35 (36)" — the build the person has. */
    fun installed(): String = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})"

    /** The kept state, read from prefs the first time. */
    fun load(context: Context): State {
        _state.value?.let { return it }
        val p = prefs(context)
        val s = State(
            latest = p.getString(KEY_LATEST, null),
            checkedAt = p.getLong(KEY_CHECKED_AT, 0L),
            failed = p.getBoolean(KEY_FAILED, false),
            noRelease = p.getBoolean(KEY_NO_RELEASE, false),
        )
        _state.value = s
        return s
    }

    /** A check when the last one is older than a day, or did not get through and is older than an hour. */
    fun refreshIfStale(context: Context) {
        val s = load(context)
        val age = System.currentTimeMillis() - s.checkedAt
        if (age < if (s.failed) RETRY_MS else FRESH_MS) return
        checkNow(context)
    }

    private const val RETRY_MS = 60L * 60 * 1000

    /** A check right now (the row's tap). */
    fun checkNow(context: Context) {
        if (!checking.compareAndSet(false, true)) return
        val app = context.applicationContext
        _state.value = load(app).copy(checking = true)
        scope.launch {
            try {
                val feed = fetchLatest()
                val now = System.currentTimeMillis()
                val p = prefs(app)
                val kept = p.getString(KEY_LATEST, null)
                val latest = (feed as? Feed.Version)?.latest ?: kept
                val failed = feed is Feed.Unreachable
                val noRelease = feed is Feed.Empty
                p.edit()
                    .putString(KEY_LATEST, latest)
                    .putLong(KEY_CHECKED_AT, now)
                    .putBoolean(KEY_FAILED, failed)
                    .putBoolean(KEY_NO_RELEASE, noRelease)
                    .apply()
                _state.value = State(latest = latest, checkedAt = now, failed = failed, noRelease = noRelease)
            } finally {
                checking.set(false)
            }
        }
    }

    /** The person has seen the notice for this version; do not repeat it until the quiet period ends. */
    fun acknowledge(context: Context, version: String, now: Long = System.currentTimeMillis()) {
        prefs(context).edit().putString(KEY_ACK_VERSION, version).putLong(KEY_ACK_AT, now).apply()
    }

    /** Whether the launch notice should appear, given what was last acknowledged. */
    fun shouldNotify(context: Context, state: State, now: Long = System.currentTimeMillis()): Boolean {
        val p = prefs(context)
        return state.shouldNotify(p.getString(KEY_ACK_VERSION, null), p.getLong(KEY_ACK_AT, 0L), now)
    }

    /**
     * This edition's releases, and only those.
     *
     * Upstream's download index on nanomuse.cn is deliberately not read any more: every tag on
     * it names the English app, so a version read from there would be shown as an update that
     * can never install. The GitHub endpoint below is the one source, and it answers 404 while
     * no release of this edition is published — an answer, not a failure, which is why
     * [Feed.Empty] and [Feed.Unreachable] are told apart.
     */
    internal fun fetchLatest(): Feed {
        val response = get(GITHUB_LATEST_URL) ?: return Feed.Unreachable
        if (response.code == 404) return Feed.Empty
        if (response.code !in 200..299) return Feed.Unreachable
        val latest = parseGitHubLatest(response.body.orEmpty())
        return if (latest != null) Feed.Version(latest) else Feed.Empty
    }

    /** One GET, with its status code kept: "404" and "no connection" are not the same answer. */
    private class Response(val code: Int, val body: String?)

    private fun get(url: String): Response? = try {
        val req = Request.Builder().url(url).get()
            .header("User-Agent", "nanoMuse-Arabic-Android/${BuildConfig.VERSION_NAME}")
            .header("Accept", "application/json")
            .build()
        http.newCall(req).execute().use { r ->
            Response(r.code, if (r.isSuccessful) r.body?.string() else null)
        }
    } catch (e: Exception) {
        AppLogger.info(TAG, "GET $url failed: ${e.javaClass.simpleName}")
        null
    }

    /**
     * `{"releases":[{"tag":"v0.1.34",…},…]}`, newest first → "0.1.34".
     *
     * nanoMuse-Arabic reads GitHub directly and has no index of its own yet, so nothing calls
     * this today. It is kept, with its test, because the shape is the cheapest thing to serve
     * from a mirror the day this edition wants one.
     */
    fun parseIndex(text: String): String? {
        val o = runCatching { JSONObject(text) }.getOrNull() ?: return null
        val releases = o.optJSONArray("releases") ?: return null
        for (i in 0 until releases.length()) {
            val tag = releases.optJSONObject(i)?.optString("tag")?.let(::normalize) ?: continue
            if (tag.isNotEmpty()) return tag
        }
        return null
    }

    /** GitHub's `/releases/latest` → its `tag_name`, normalised. */
    fun parseGitHubLatest(text: String): String? {
        val o = runCatching { JSONObject(text) }.getOrNull() ?: return null
        return normalize(o.optString("tag_name")).takeIf { it.isNotEmpty() }
    }

    /** "v0.1.35" → "0.1.35"; a stray space or newline goes. */
    fun normalize(tag: String): String = tag.trim().removePrefix("v").removePrefix("V").trim()

    /**
     * Semver-ish: numeric parts compared as numbers, a missing part is 0, and a pre-release
     * label ("0.1.35-rc1") sorts below the plain version it precedes.
     */
    fun compare(a: String, b: String): Int {
        fun split(v: String): Pair<List<Int>, String> {
            val core = v.substringBefore('-')
            val label = v.substringAfter('-', "")
            return core.split('.').map { it.filter(Char::isDigit).toIntOrNull() ?: 0 } to label
        }
        val (an, al) = split(normalize(a))
        val (bn, bl) = split(normalize(b))
        for (i in 0 until maxOf(an.size, bn.size)) {
            val c = (an.getOrNull(i) ?: 0).compareTo(bn.getOrNull(i) ?: 0)
            if (c != 0) return c
        }
        return when {
            al == bl -> 0
            al.isEmpty() -> 1
            bl.isEmpty() -> -1
            else -> al.compareTo(bl)
        }
    }

    fun isNewer(latest: String, installed: String): Boolean = compare(latest, installed) > 0
}
