package com.islamicresearchhub.companion.ui.catalog

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
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
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.data.local.copyPickedFileToCache
import kotlinx.coroutines.launch

/**
 * Milestone 2's first real screen (Phase 18): import a real catalog.db
 * (produced by the desktop's `catalog_export_cli.py`) via the system
 * file picker, then browse its real books entirely offline. Tapping a
 * book navigates to `BookDetailScreen`, which handles the separate
 * real book-package import for actually reading it.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CatalogListScreen(onBookClick: (Int) -> Unit) {
    val context = LocalContext.current
    var books by remember { mutableStateOf<List<BookEntity>>(emptyList()) }
    var imported by remember { mutableStateOf(CatalogDatabase.isImported(context)) }
    val scope = rememberCoroutineScope()

    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val tempFile = copyPickedFileToCache(context, uri, "import_catalog.db")
            val database = CatalogDatabase.open(context, tempFile)
            books = database.catalogDao().listAll()
            imported = true
        }
    }

    LaunchedEffect(Unit) {
        if (imported) {
            books = CatalogDatabase.openExisting(context).catalogDao().listAll()
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Islamic Research Hub") }) }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Button(
                onClick = { importLauncher.launch(arrayOf("*/*")) },
                modifier = Modifier.padding(16.dp),
            ) {
                Text(if (imported) "Re-import catalog" else "Import catalog")
            }
            if (books.isEmpty()) {
                Text(
                    if (imported) "No real books in this catalog." else "No catalog imported yet.",
                    modifier = Modifier.padding(16.dp),
                )
            } else {
                LazyColumn {
                    items(books) { book ->
                        ListItem(
                            headlineContent = { Text(book.title ?: "Untitled") },
                            supportingContent = { Text(book.author ?: "") },
                            modifier = Modifier.clickable { onBookClick(book.bookId) },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
