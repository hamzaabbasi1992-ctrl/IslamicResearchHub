package com.islamicresearchhub.companion.ui.catalog

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.data.local.copyPickedFileToCache
import kotlinx.coroutines.launch

/**
 * Phase 18 Catalog Browse & Search Screen:
 * Import catalog.db, search books by title/author with live FTS/like query,
 * view book counts, and handle import errors safely.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CatalogListScreen(onBookClick: (Int) -> Unit) {
    val context = LocalContext.current
    var books by remember { mutableStateOf<List<BookEntity>>(emptyList()) }
    var searchQuery by remember { mutableStateOf("") }
    var imported by remember { mutableStateOf(CatalogDatabase.isImported(context)) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    suspend fun loadBooks(query: String) {
        if (!CatalogDatabase.isImported(context)) return
        try {
            val dao = CatalogDatabase.openExisting(context).catalogDao()
            books = if (query.isBlank()) {
                dao.listAll()
            } else {
                dao.search(query.trim())
            }
        } catch (e: Exception) {
            snackbarHostState.showSnackbar("Error loading books: ${e.localizedMessage}")
        }
    }

    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val tempFile = copyPickedFileToCache(context, uri, "import_catalog.db")
                val database = CatalogDatabase.open(context, tempFile)
                books = database.catalogDao().listAll()
                imported = true
                searchQuery = ""
                snackbarHostState.showSnackbar("Catalog imported successfully!")
            } catch (e: Exception) {
                snackbarHostState.showSnackbar("Failed to import catalog: ${e.localizedMessage ?: "Invalid file"}")
            }
        }
    }

    LaunchedEffect(imported) {
        if (imported) {
            loadBooks("")
        }
    }

    LaunchedEffect(searchQuery) {
        if (imported) {
            loadBooks(searchQuery)
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Islamic Research Hub") }) },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Button(
                    onClick = { importLauncher.launch(arrayOf("*/*")) },
                ) {
                    Text(if (imported) "Re-import catalog" else "Import catalog")
                }
                if (imported) {
                    Text(
                        text = "${books.size} ${if (books.size == 1) "book" else "books"}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            if (imported) {
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 4.dp),
                    placeholder = { Text("Search title or author...") },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = "Search") },
                    trailingIcon = {
                        if (searchQuery.isNotEmpty()) {
                            IconButton(onClick = { searchQuery = "" }) {
                                Icon(Icons.Default.Clear, contentDescription = "Clear search")
                            }
                        }
                    },
                    singleLine = true
                )
            }

            if (books.isEmpty()) {
                val emptyMessage = when {
                    !imported -> "No catalog imported yet. Tap 'Import catalog' to load your library."
                    searchQuery.isNotEmpty() -> "No books found matching '$searchQuery'."
                    else -> "No real books in this catalog."
                }
                Text(
                    text = emptyMessage,
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                LazyColumn {
                    items(books, key = { it.bookId }) { book ->
                        val details = buildList {
                            book.author?.takeIf { it.isNotBlank() }?.let { add(it) }
                            book.category?.takeIf { it.isNotBlank() }?.let { add(it) }
                            book.pageCount?.let { add("$it pages") }
                        }.joinToString(" • ")

                        ListItem(
                            headlineContent = { Text(book.title ?: "Untitled") },
                            supportingContent = {
                                if (details.isNotEmpty()) {
                                    Text(details)
                                }
                            },
                            modifier = Modifier.clickable { onBookClick(book.bookId) },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
