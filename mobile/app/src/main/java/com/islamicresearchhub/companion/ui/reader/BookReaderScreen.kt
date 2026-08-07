package com.islamicresearchhub.companion.ui.reader

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.data.local.PageEntity

/**
 * The real offline reader: every real page of an already-imported book
 * package, in order, entirely from local Room (must work with the
 * device's network fully disabled - there is no network call anywhere
 * in this screen). Real Arabic/Urdu text reads right-to-left, matching
 * the desktop app's own reader (`viewer_screen.py`'s `RTL_TEXT_STYLE`).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookReaderScreen(bookId: Int, startPageNo: Int?) {
    val context = LocalContext.current
    var pages by remember { mutableStateOf<List<PageEntity>>(emptyList()) }
    val listState = rememberLazyListState()

    LaunchedEffect(bookId) {
        pages = BookPackageDatabase.openExisting(context, bookId).pageDao().listPages()
    }

    LaunchedEffect(pages, startPageNo) {
        if (startPageNo != null) {
            val index = pages.indexOfFirst { it.pageNo == startPageNo }
            if (index >= 0) {
                listState.scrollToItem(index)
            }
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Reader") }) }) { padding ->
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize().padding(padding),
            ) {
                items(pages) { page ->
                    Text(
                        page.content ?: "",
                        modifier = Modifier.padding(16.dp),
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}
