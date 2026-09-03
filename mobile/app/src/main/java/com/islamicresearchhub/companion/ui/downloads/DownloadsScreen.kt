package com.islamicresearchhub.companion.ui.downloads

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.DownloadDone
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.ui.common.BookListCard
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurface
import com.islamicresearchhub.companion.ui.theme.DarkGreenTopBar
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal

private val BOOK_PACKAGE_FILE_NAME = Regex("""^book_(\d+)\.db$""")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DownloadsScreen(onBookClick: (Int) -> Unit) {
    val context = LocalContext.current
    var books by remember { mutableStateOf<List<BookEntity>>(emptyList()) }
    val snackbarHostState = remember { SnackbarHostState() }

    suspend fun reload() {
        try {
            books = loadDownloadedBooks(context)
        } catch (e: Exception) {
            snackbarHostState.showSnackbar("Error loading downloads: ${e.localizedMessage}")
        }
    }

    LaunchedEffect(Unit) { reload() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Download, contentDescription = null, tint = EmeraldTeal, modifier = Modifier.size(24.dp))
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text("Downloads", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = DarkGreenLightText)
                            Text("${books.size} Offline Book Packages", fontSize = 12.sp, color = DarkGreenSubText)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar),
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        if (books.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = DarkGreenSurface),
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Surface(
                            modifier = Modifier.size(56.dp),
                            shape = RoundedCornerShape(14.dp),
                            color = EmeraldTeal.copy(alpha = 0.15f),
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    Icons.Default.DownloadDone,
                                    contentDescription = null,
                                    tint = EmeraldTeal,
                                    modifier = Modifier.size(32.dp),
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            "No Offline Books Downloaded",
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = DarkGreenLightText,
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            "Import a book package file (.db) from the Library or Book Detail screen to read offline without internet.",
                            fontSize = 13.sp,
                            color = DarkGreenSubText,
                            lineHeight = 18.sp,
                        )
                    }
                }
            }
        } else {
            LazyColumn(
                contentPadding = PaddingValues(
                    top = padding.calculateTopPadding() + 8.dp,
                    start = 16.dp, end = 16.dp, bottom = 24.dp,
                ),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(books, key = { it.bookId }) { book ->
                    BookListCard(
                        book = book,
                        onClick = { onBookClick(book.bookId) },
                    )
                }
            }
        }
    }
}

private suspend fun loadDownloadedBooks(context: Context): List<BookEntity> {
    val dbNames = context.databaseList().toMutableSet()
    try {
        context.assets.list("sample_books")?.forEach { name ->
            if (BOOK_PACKAGE_FILE_NAME.matches(name)) {
                dbNames.add(name)
            }
        }
    } catch (_: Exception) {}

    val bookIds = dbNames
        .mapNotNull { name -> BOOK_PACKAGE_FILE_NAME.find(name)?.groupValues?.get(1)?.toIntOrNull() }
    if (bookIds.isEmpty() || !CatalogDatabase.isImported(context)) return emptyList()

    val catalogDao = CatalogDatabase.openExisting(context).catalogDao()
    return bookIds.mapNotNull { catalogDao.getBook(it) }.sortedBy { it.title }
}
