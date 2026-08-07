package com.islamicresearchhub.companion.ui.bookdetail

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.data.local.copyPickedFileToCache
import kotlinx.coroutines.launch

/**
 * One real book's metadata (from the already-imported catalog), plus
 * the real "import this specific book to read it offline" flow - a
 * separate, smaller file from the catalog (`book_<id>.db`, produced by
 * the desktop's `book_package_export_cli.py`) the user picks via the
 * system file picker, same real SAF pattern as the catalog import.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookDetailScreen(
    bookId: Int,
    onReadClick: (Int) -> Unit,
    onChaptersClick: (Int) -> Unit,
) {
    val context = LocalContext.current
    var book by remember { mutableStateOf<BookEntity?>(null) }
    var packageImported by remember { mutableStateOf(BookPackageDatabase.isImported(context, bookId)) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(bookId) {
        book = CatalogDatabase.openExisting(context).catalogDao().getBook(bookId)
    }

    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val tempFile = copyPickedFileToCache(context, uri, "import_book_$bookId.db")
            BookPackageDatabase.open(context, bookId, tempFile)
            packageImported = true
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text(book?.title ?: "Book") }) }
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            Text(book?.title ?: "Untitled", style = MaterialTheme.typography.titleLarge)
            Text(book?.author ?: "Unknown author", style = MaterialTheme.typography.bodyMedium)
            if (packageImported) {
                Button(
                    onClick = { onReadClick(bookId) },
                    modifier = Modifier.padding(top = 16.dp),
                ) {
                    Text("Read")
                }
                Button(
                    onClick = { onChaptersClick(bookId) },
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Text("Chapters")
                }
            } else {
                Text(
                    "This book isn't downloaded to this device yet.",
                    modifier = Modifier.padding(top = 16.dp),
                )
                Button(
                    onClick = { importLauncher.launch(arrayOf("*/*")) },
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Text("Import this book")
                }
            }
        }
    }
}
