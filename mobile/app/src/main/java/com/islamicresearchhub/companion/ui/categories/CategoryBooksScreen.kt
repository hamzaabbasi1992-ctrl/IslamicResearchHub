package com.islamicresearchhub.companion.ui.categories

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.ui.common.BookListCard

/** Real books carrying one real category (tapped from `CategoriesScreen`). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CategoryBooksScreen(mjcn: Int, categoryName: String, onBookClick: (Int) -> Unit) {
    val context = LocalContext.current
    var books by remember { mutableStateOf<List<BookEntity>>(emptyList()) }

    LaunchedEffect(mjcn) {
        if (CatalogDatabase.isImported(context)) {
            books = CatalogDatabase.openExisting(context).catalogDao().listByCategory(mjcn)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(categoryName, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold) },
                colors = androidx.compose.material3.TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        if (books.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Text("No books found in this category.", color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                    BookListCard(book = book, badge = book.category, onClick = { onBookClick(book.bookId) })
                }
            }
        }
    }
}
