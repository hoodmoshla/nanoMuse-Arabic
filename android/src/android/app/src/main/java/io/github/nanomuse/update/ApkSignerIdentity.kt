package io.github.nanomuse.update

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import androidx.core.content.pm.PackageInfoCompat
import com.openminis.app.logging.AppLogger
import java.io.File
import java.security.MessageDigest

/**
 * nanoMuse-Arabic: is this APK signed with the key this app is signed with?
 *
 * The standalone Arabic edition installs BESIDE the official nanoMuse, with an
 * application id of its own, and it is signed with a key of its own. Two things
 * follow, and this object is where both are settled:
 *
 *  - An APK signed with another key can never install over this app. Android
 *    refuses it with `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, after the user has
 *    already been walked through "install unknown apps" and a download. Asking
 *    the archive first turns that dead end into one log line and one honest
 *    message.
 *  - A release feed answers with whatever is published on it. The one thing that
 *    tells an update of *this* edition from the English app — or from anything
 *    else someone put on the internet and called an update — is the signing
 *    certificate. Everything else (the file name, the tag, the repository) is a
 *    claim; the certificate is proof.
 *
 * `versionCode` and `applicationId` are still enforced by the platform: a lower
 * `versionCode` is refused, and a different package is simply a different app.
 * This check is the third leg, and the only one the platform cannot check for us
 * before the download is spent.
 *
 * The pure half — [fingerprint] — is unit-tested; the rest needs a real
 * PackageManager and is exercised on a device.
 */
object ApkSignerIdentity {

    private const val TAG = "ApkSignerIdentity"

    /**
     * Both certificate flags, always.
     *
     * `GET_SIGNING_CERTIFICATES` is API 28+ and `GET_SIGNATURES` is what fills `signatures` below
     * it — and this app's `minSdk` is 26, where the signing block does not exist yet and the
     * unknown flag is simply ignored. Asking for `GET_SIGNING_CERTIFICATES` alone reads nothing at
     * all on Android 8.0 and 8.1, `PackageInfoCompat` then finds no certificates, and every
     * update would be refused on those two versions with a "cannot read the certificate" line.
     * Passing both is what androidx itself documents for a caller that spans the boundary.
     */
    @Suppress("DEPRECATION")
    private const val CERTIFICATE_FLAGS =
        PackageManager.GET_SIGNING_CERTIFICATES or PackageManager.GET_SIGNATURES

    /** Lowercase hex SHA-256 of one signing certificate's encoded bytes. */
    fun fingerprint(certificate: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(certificate).joinToString("") { "%02x".format(it) }

    /**
     * The SHA-256 fingerprints of this app's own signing certificates — one entry in practice,
     * more only during a key rotation.
     */
    fun installedFingerprints(context: Context): Set<String> =
        fingerprints(context.packageManager) { pm ->
            pm.getPackageInfo(context.packageName, CERTIFICATE_FLAGS)
        }

    /**
     * True when [apk] carries exactly the signing certificates this app carries.
     *
     * False for an unreadable or unsigned archive, and false when either side's certificate
     * cannot be read at all: an update the app cannot vouch for is not an update this app
     * installs.
     */
    fun isSignedLikeInstalledApp(context: Context, apk: File): Boolean {
        val mine = installedFingerprints(context)
        if (mine.isEmpty()) {
            AppLogger.warning(TAG, "this app's signing certificate could not be read; refusing ${apk.name}")
            return false
        }
        val theirs = fingerprints(context.packageManager) { pm ->
            pm.getPackageArchiveInfo(apk.absolutePath, CERTIFICATE_FLAGS)
        }
        if (theirs.isEmpty()) {
            AppLogger.warning(TAG, "${apk.name}: no signing certificate could be read from the archive")
            return false
        }
        val same = theirs == mine
        if (!same) {
            AppLogger.warning(
                TAG,
                "${apk.name} is signed with ${theirs.joinToString()}, this app with ${mine.joinToString()}",
            )
        }
        return same
    }

    private fun fingerprints(
        pm: PackageManager,
        load: (PackageManager) -> PackageInfo?,
    ): Set<String> = runCatching {
        val info = load(pm) ?: return emptySet<String>()
        PackageInfoCompat.getSignatures(info).map { fingerprint(it.toByteArray()) }.toSet()
    }.getOrElse { e ->
        AppLogger.warning(TAG, "reading a signing certificate failed: ${e.javaClass.simpleName}")
        emptySet()
    }
}
