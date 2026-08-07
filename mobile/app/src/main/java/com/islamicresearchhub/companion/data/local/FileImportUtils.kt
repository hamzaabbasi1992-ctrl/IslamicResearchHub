package com.islamicresearchhub.companion.data.local

import android.content.Context
import android.net.Uri
import java.io.File

/**
 * Copy a real file the user picked via the system file picker (Storage
 * Access Framework) into this app's own cache, so Room's
 * `createFromFile()` has a real, directly-readable local `File` to
 * import from - `content://` URIs aren't real filesystem paths Room
 * can open directly. Shared by both the catalog import (`CatalogListScreen`)
 * and book-package import (`BookDetailScreen`) flows.
 */
fun copyPickedFileToCache(context: Context, uri: Uri, cacheFileName: String): File {
    val tempFile = File(context.cacheDir, cacheFileName)
    context.contentResolver.openInputStream(uri)?.use { input ->
        tempFile.outputStream().use { output -> input.copyTo(output) }
    }
    return tempFile
}
