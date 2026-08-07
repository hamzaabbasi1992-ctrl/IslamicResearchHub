package com.islamicresearchhub.companion.ui.reader

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.runtime.setValue
import androidx.compose.foundation.clickable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.runtime.CompositionLocalProvider
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.data.local.ChapterEntity

/**
 * Real table of contents for one already-imported book package - a
 * flat list for this real first version (real parent/child nesting via
 * `ParentChapterID` is a genuine "nice to have," not required for
 * tapping a chapter to jump the reader to its real page).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChapterListScreen(bookId: Int, onChapterClick: (Int) -> Unit) {
    val context = LocalContext.current
    var chapters by remember { mutableStateOf<List<ChapterEntity>>(emptyList()) }

    LaunchedEffect(bookId) {
        chapters = BookPackageDatabase.openExisting(context, bookId).pageDao().listChapters()
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Chapters") }) }) { padding ->
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            LazyColumn(modifier = Modifier.fillMaxSize().padding(padding)) {
                items(chapters) { chapter ->
                    ListItem(
                        headlineContent = { Text(chapter.title ?: "Untitled chapter") },
                        modifier = Modifier.clickable { onChapterClick(chapter.pageNo ?: 1) },
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}
