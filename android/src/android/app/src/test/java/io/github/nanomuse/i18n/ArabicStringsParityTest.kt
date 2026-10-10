package io.github.nanomuse.i18n

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * nanoMuse-Arabic: the half of the Arabic translation that [NmStringsParityTest] cannot see.
 *
 * That test guards `nm_strings.xml` — our own strings, one file per locale. Upstream's
 * `strings.xml` is a different story: 1755 keys translated once into Arabic and then never
 * checked again, in a file an upstream pull rewrites. A key dropped there falls back to English
 * on the device, silently, one screen at a time, which is exactly the failure an Arabic edition
 * exists to avoid.
 *
 * Only Arabic is held to this: eight of upstream's other locales already sit two keys short of
 * English, and enforcing the rule everywhere would mean failing the build over files this
 * edition does not own. `scripts/check-arabic-resources.py` runs the same checks from the Python
 * side, with the plural quantities and the copy rules on top; this test is the one that runs in
 * the Android job, beside the code it protects.
 *
 * Runs from the module directory, as unit tests do.
 */
class ArabicStringsParityTest {

    private val res: File = listOf("src/main/res", "app/src/main/res").map(::File).first { it.isDirectory }
    private val app: File = generateSequence(res) { it.parentFile }.first { File(it, "build.gradle.kts").isFile }
    private val english = File(res, "values/strings.xml")
    private val arabic = File(res, "values-ar/strings.xml")
    private val englishNaming = File(res, "values/nm_strings.xml")
    private val arabicNaming = File(res, "values-ar/nm_strings.xml")

    /** One named resource and the values it holds: one for a string, one per item otherwise. */
    private data class Res(val tag: String, val values: List<String>, val quantities: List<String>) {
        val placeholders: Set<String> get() = values.flatMap { placeholderRx.findAll(it).map(MatchResult::value) }.toSet()
        fun placeholdersOf(quantity: String): Set<String>? =
            quantities.indexOf(quantity).takeIf { it >= 0 }?.let { index ->
                placeholderRx.findAll(values[index]).map(MatchResult::value).toSet()
            }
    }

    private fun load(file: File): Map<String, Res> =
        elementRx.findAll(file.readText()).associate { match ->
            val body = match.groupValues[3]
            val items = itemRx.findAll(body).toList()
            val name = match.groupValues[2]
            name to Res(
                tag = match.groupValues[1],
                values = items.map { it.groupValues[2] }.ifEmpty { listOf(body.trim()) },
                quantities = items.map { it.groupValues[1] },
            )
        }

    @Test
    fun `Arabic carries every key of the English strings file`() {
        val en = load(english).keys
        val ar = load(arabic).keys
        assertTrue("the English file looks wrong: ${en.size} keys", en.size > 1500)
        val missing = en - ar
        val extra = ar - en
        assertEquals(
            "values-ar/strings.xml lacks ${missing.size} key(s): ${missing.sorted().take(8)}",
            emptySet<String>(),
            missing,
        )
        assertEquals(
            "values-ar/strings.xml has ${extra.size} key(s) English does not: ${extra.sorted().take(8)}",
            emptySet<String>(),
            extra,
        )
    }

    @Test
    fun `the format placeholders of the English string are the Arabic ones`() {
        val en = load(english)
        val ar = load(arabic)
        val wrong = en.filter { (name, theirs) -> ar[name]?.placeholders?.let { it != theirs.placeholders } ?: false }
        assertEquals(
            "placeholders differ from English in ${wrong.keys.sorted().take(8)}",
            emptyMap<String, Res>(),
            wrong,
        )
    }

    /**
     * The `other` form is the one every locale has and the one a wrong plural damages, so it is
     * compared on its own as well — the element-wide comparison above would hide a placeholder
     * dropped from it while another quantity kept it.
     */
    @Test
    fun `the other form of a plural keeps the English placeholders`() {
        val en = load(english)
        val ar = load(arabic)
        for ((name, theirs) in en) {
            if (theirs.tag != "plurals") continue
            val mine = ar[name] ?: continue
            val expected = theirs.placeholdersOf("other") ?: continue
            assertEquals("$name (other) differs from English", expected, mine.placeholdersOf("other"))
        }
    }

    /** Arabic counts with six CLDR categories; a file with one/other renders eleven cases wrong. */
    @Test
    fun `Arabic plurals carry all six categories`() {
        val want = setOf("zero", "one", "two", "few", "many", "other")
        val plurals = load(arabic).filterValues { it.tag == "plurals" }
        assertTrue("the Arabic file has no plurals at all", plurals.isNotEmpty())
        for ((name, res) in plurals) {
            assertEquals("$name wants all six Arabic categories", want, res.quantities.toSet())
        }
    }

    @Test
    fun `every item of every array and plural is Arabic`() {
        for (file in listOf(arabic, arabicNaming)) {
            val untranslated = load(file).filterKeys { it !in PROPER_NOUNS }.flatMap { (name, res) ->
                res.values.mapIndexedNotNull { index, value ->
                    val where = if (res.tag == "string") name else "$name[$index]"
                    if (isTranslatable(value)) where else null
                }
            }
            assertEquals("${file.parentFile.name}: ${untranslated.take(8)}", emptyList<String>(), untranslated)
        }
    }

    @Test
    fun `the standalone edition keeps its own identity`() {
        val gradle = File(app, "build.gradle.kts").readText()
        val appId = Regex("applicationId\\s*=\\s*\"([^\"]+)\"").find(gradle)?.groupValues?.get(1)
        assertTrue("no applicationId in ${app.canonicalPath}", appId != null)
        assertTrue("the Arabic edition shares the official application id: $appId", appId!!.endsWith(".arabic"))
        val shortcuts = File(res, "xml/shortcuts.xml").readText()
        val targeted = Regex("android:targetPackage=\"([^\"]+)\"").findAll(shortcuts).map { it.groupValues[1] }.toSet()
        assertEquals("shortcuts.xml does not target the application id", setOf(appId), targeted)
        val manifest = File(app, "src/main/AndroidManifest.xml").readText()
        assertTrue("the manifest does not set supportsRtl", manifest.contains("android:supportsRtl=\"true\""))
        assertTrue("the manifest does not point at locales_config", manifest.contains("@xml/locales_config"))
        val locales = File(res, "xml/locales_config.xml").readText()
        assertTrue("locales_config does not offer Arabic", locales.contains("<locale android:name=\"ar\"/>"))
    }

    /** `%1$s · %2$s` is punctuation and two placeholders; the letters inside `%s` are not words. */
    private fun isTranslatable(text: String): Boolean =
        !arabicRx.containsMatchIn(text) && latinRx.containsMatchIn(placeholderRx.replace(text, ""))

    private companion object {
        val elementRx = Regex("""<(string|plurals|string-array)\s+name="([^"]+)"[^>]*>(.*?)</\1>""", RegexOption.DOT_MATCHES_ALL)
        val itemRx = Regex("""<item(?:\s+quantity="([^"]+)")?[^>]*>(.*?)</item>""", RegexOption.DOT_MATCHES_ALL)
        val placeholderRx = Regex("""%(?:\d+\$)?[sd]""")
        val latinRx = Regex("""[A-Za-z]""")
        val arabicRx = Regex("""[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]""")

        /** Values a translator is right to leave in Latin script; the reasons are in the checker. */
        val PROPER_NOUNS = setOf(
            "app_name",
            "mcp_transport_http",
            "mcp_transport_sse",
            "mcp_transport_stdio",
            "mcp_form_url_placeholder",
            "mcp_form_command_placeholder",
            "mcp_form_args_placeholder",
            "mcp_import_placeholder",
            "export_summary_format_value_json",
            "skill_import_tab_url",
            "skill_import_url_label",
            "skill_detail_source_url",
        )
    }
}
