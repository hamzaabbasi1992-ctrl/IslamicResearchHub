package com.islamicresearchhub.companion.data.local

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Copy a real file the user picked via the system file picker into cache.
 */
fun copyPickedFileToCache(context: Context, uri: Uri, cacheFileName: String): File {
    val tempFile = File(context.cacheDir, cacheFileName)
    context.contentResolver.openInputStream(uri)?.use { input ->
        tempFile.outputStream().use { output -> input.copyTo(output) }
    }
    return tempFile
}

/**
 * Bulk copy multiple picked database files (book_*.db or catalog.db) directly into the app's databases folder.
 */
suspend fun bulkImportBookFiles(context: Context, uris: List<Uri>): Int = withContext(Dispatchers.IO) {
    var count = 0
    uris.forEach { uri ->
        try {
            val fileName = getFileNameFromUri(context, uri) ?: "book_${System.currentTimeMillis()}.db"
            val targetFile = context.getDatabasePath(fileName)
            targetFile.parentFile?.mkdirs()
            context.contentResolver.openInputStream(uri)?.use { input ->
                targetFile.outputStream().use { output -> input.copyTo(output) }
            }
            count++
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
    return@withContext count
}

fun getFileNameFromUri(context: Context, uri: Uri): String? {
    var result: String? = null
    if (uri.scheme == "content") {
        val cursor = context.contentResolver.query(uri, null, null, null, null)
        cursor?.use {
            if (it.moveToFirst()) {
                val index = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index != -1) {
                    result = it.getString(index)
                }
            }
        }
    }
    if (result == null) {
        result = uri.path
        val cut = result?.lastIndexOf('/') ?: -1
        if (cut != -1) {
            result = result?.substring(cut + 1)
        }
    }
    return result
}
