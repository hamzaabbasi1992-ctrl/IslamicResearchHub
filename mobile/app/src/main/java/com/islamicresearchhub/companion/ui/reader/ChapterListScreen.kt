package com.islamicresearchhub.companion.ui.reader

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.data.local.ChapterEntity

/**
 * Real table of contents for one already-imported book package.
 * Computes nested indentation levels based on `parentChapterId` depth
 * and displays starting page numbers for quick jump navigation.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChapterListScreen(bookId: Int, onChapterClick: (Int) -> Unit) {
    val context = LocalContext.current
    var chapters by remember { mutableStateOf<List<ChapterEntity>>(emptyList()) }

    LaunchedEffect(bookId) {
        if (BookPackageDatabase.isImported(context, bookId)) {
            chapters = BookPackageDatabase.openExisting(context, bookId).pageDao().listChapters()
        }
    }

    // Build map of chapter depth for nested visual hierarchy
    val depthMap = remember(chapters) {
        val depths = mutableMapOf<Int, Int>()
        val byId = chapters.associateBy { it.chapterId }

        fun getDepth(chapterId: Int): Int {
            depths[chapterId]?.let { return it }
            val chapter = byId[chapterId] ?: return 0
            val parentId = chapter.parentChapterId
            val d = if (parentId != null && parentId != 0 && parentId in byId) {
                1 + getDepth(parentId)
            } else {
                0
            }
            depths[chapterId] = d
            return d
        }

        chapters.forEach { getDepth(it.chapterId) }
        depths
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Chapters") }) }) { padding ->
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            if (chapters.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        "No chapter index available for this book.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                LazyColumn(modifier = Modifier.fillMaxSize().padding(padding)) {
                    items(chapters, key = { it.chapterId }) { chapter ->
                        val depth = depthMap[chapter.chapterId] ?: 0
                        val indentPadding = (depth * 16).dp

                        ListItem(
                            headlineContent = {
                                Text(
                                    chapter.title ?: "Untitled chapter",
                                    style = if (depth == 0) MaterialTheme.typography.titleMedium else MaterialTheme.typography.bodyMedium
                                )
                            },
                            supportingContent = {
                                chapter.pageNo?.let { page ->
                                    Text(
                                        "Page $page",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            },
                            modifier = Modifier
                                .padding(start = indentPadding)
                                .clickable { onChapterClick(chapter.pageNo ?: 1) },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}
