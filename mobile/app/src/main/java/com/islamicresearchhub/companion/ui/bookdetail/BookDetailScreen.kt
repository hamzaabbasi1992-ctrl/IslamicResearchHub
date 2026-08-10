package com.islamicresearchhub.companion.ui.bookdetail

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Book
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
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
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.data.local.copyPickedFileToCache
import kotlinx.coroutines.launch

/**
 * Phase 18 Book Detail & Import Screen:
 * Displays rich book metadata, handles offline book package import with error feedback,
 * and allows launching the offline reader or chapter index.
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
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    LaunchedEffect(bookId) {
        if (CatalogDatabase.isImported(context)) {
            book = CatalogDatabase.openExisting(context).catalogDao().getBook(bookId)
        }
    }

    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val tempFile = copyPickedFileToCache(context, uri, "import_book_$bookId.db")
                BookPackageDatabase.open(context, bookId, tempFile)
                packageImported = true
                snackbarHostState.showSnackbar("Book package imported successfully!")
            } catch (e: Exception) {
                snackbarHostState.showSnackbar("Failed to import book package: ${e.localizedMessage ?: "Invalid file"}")
            }
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text(book?.title ?: "Book Detail") }) },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(56.dp),
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            Icons.Default.Book,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(28.dp)
                        )
                    }
                }
                Spacer(modifier = Modifier.width(14.dp))
                Column {
                    Text(book?.title ?: "Untitled Book", style = MaterialTheme.typography.headlineSmall)
                    Text(
                        book?.author ?: "Unknown Author",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.AutoMirrored.Filled.MenuBook,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Metadata Overview",
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                    HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

                    MetadataRow("Category", book?.category)
                    MetadataRow("Language", book?.language)
                    MetadataRow("Publisher", book?.publisher)
                    MetadataRow("Publish Year", book?.publishYear)
                    MetadataRow("Page Count", book?.pageCount?.let { "$it pages" })
                    MetadataRow("Chapter Count", book?.chapterCount?.let { "$it chapters" })
                    if (book?.seriesId != null) {
                        MetadataRow("Series ID", book?.seriesId.toString())
                    }
                    if (book?.volumeNumber != null) {
                        MetadataRow("Volume Number", book?.volumeNumber.toString())
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            if (packageImported) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Button(
                        onClick = { onReadClick(bookId) },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Read Book")
                    }
                    OutlinedButton(
                        onClick = { onChaptersClick(bookId) },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Chapters")
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                OutlinedButton(
                    onClick = { importLauncher.launch(arrayOf("*/*")) },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Re-import Book Package")
                }
            } else {
                Text(
                    "This book package is not imported on this device yet. Import the 'book_$bookId.db' file to enable offline reading.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = { importLauncher.launch(arrayOf("*/*")) },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Import Book Package")
                }
            }
        }
    }
}

@Composable
private fun MetadataRow(label: String, value: String?) {
    if (value.isNullOrBlank()) return
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall
        )
    }
}
