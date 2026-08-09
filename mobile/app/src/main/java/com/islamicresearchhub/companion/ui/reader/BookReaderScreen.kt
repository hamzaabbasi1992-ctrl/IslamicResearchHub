package com.islamicresearchhub.companion.ui.reader

import android.content.Context
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.data.local.PageEntity
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch

private const val PREFS_NAME = "reader_prefs"
private fun getSavedPageKey(bookId: Int) = "last_read_page_$bookId"

/**
 * Phase 18 Offline Reader Screen:
 * Renders page contents in RTL for Arabic/Urdu, remembers last read position per book,
 * provides jump-to-page dialog, and displays page X of Y header indicator.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookReaderScreen(bookId: Int, startPageNo: Int?) {
    val context = LocalContext.current
    var bookMetadata by remember { mutableStateOf<BookEntity?>(null) }
    var pages by remember { mutableStateOf<List<PageEntity>>(emptyList()) }
    var showJumpDialog by remember { mutableStateOf(false) }
    var jumpInput by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    LaunchedEffect(bookId) {
        if (BookPackageDatabase.isImported(context, bookId)) {
            val db = BookPackageDatabase.openExisting(context, bookId)
            val dao = db.pageDao()
            bookMetadata = dao.getBook()
            pages = dao.listPages()
        }
    }

    // Restore page scroll position
    LaunchedEffect(pages, startPageNo) {
        if (pages.isEmpty()) return@LaunchedEffect

        if (startPageNo != null) {
            val index = pages.indexOfFirst { it.pageNo == startPageNo }
            if (index >= 0) {
                listState.scrollToItem(index)
            }
        } else {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val savedPageNo = prefs.getInt(getSavedPageKey(bookId), -1)
            if (savedPageNo != -1) {
                val index = pages.indexOfFirst { it.pageNo == savedPageNo }
                if (index >= 0) {
                    listState.scrollToItem(index)
                }
            }
        }
    }

    // Save last read position as user scrolls
    LaunchedEffect(listState, pages) {
        snapshotFlow { listState.firstVisibleItemIndex }
            .distinctUntilChanged()
            .collect { firstIndex ->
                if (pages.isNotEmpty() && firstIndex in pages.indices) {
                    val currentPg = pages[firstIndex].pageNo ?: (firstIndex + 1)
                    val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    prefs.edit().putInt(getSavedPageKey(bookId), currentPg).apply()
                }
            }
    }

    val currentVisibleIndex = listState.firstVisibleItemIndex
    val currentPageNo = if (pages.isNotEmpty() && currentVisibleIndex in pages.indices) {
        pages[currentVisibleIndex].pageNo ?: (currentVisibleIndex + 1)
    } else {
        1
    }
    val totalPages = pages.size

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            bookMetadata?.title ?: "Reader",
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1
                        )
                        if (totalPages > 0) {
                            Text(
                                "Page $currentPageNo of $totalPages",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                actions = {
                    if (totalPages > 0) {
                        IconButton(onClick = {
                            jumpInput = currentPageNo.toString()
                            showJumpDialog = true
                        }) {
                            Icon(Icons.AutoMirrored.Filled.List, contentDescription = "Jump to page")
                        }
                    }
                }
            )
        }
    ) { padding ->
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            if (pages.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        "No pages available in this book package.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                ) {
                    itemsIndexed(pages, key = { index, _ -> index }) { index, page ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp, vertical = 6.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "Page ${page.pageNo ?: (index + 1)}",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                    if (page.hadeesNumber != null) {
                                        Text(
                                            text = " • Hadith #${page.hadeesNumber}",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.secondary
                                        )
                                    }
                                    if (page.ayahNumber != null) {
                                        Text(
                                            text = " • Ayah #${page.ayahNumber}",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.tertiary
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Text(
                                    text = page.content ?: "",
                                    style = MaterialTheme.typography.bodyLarge.copy(
                                        lineHeight = 32.sp,
                                        fontSize = 18.sp
                                    )
                                )
                            }
                        }
                        HorizontalDivider()
                    }
                }
            }
        }
    }

    if (showJumpDialog) {
        AlertDialog(
            onDismissRequest = { showJumpDialog = false },
            title = { Text("Jump to Page") },
            text = {
                OutlinedTextField(
                    value = jumpInput,
                    onValueChange = { jumpInput = it.filter { char -> char.isDigit() } },
                    label = { Text("Page number (1 - $totalPages)") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    val targetPage = jumpInput.toIntOrNull()
                    if (targetPage != null) {
                        val targetIndex = pages.indexOfFirst { it.pageNo == targetPage }
                        if (targetIndex >= 0) {
                            scope.launch { listState.scrollToItem(targetIndex) }
                        }
                    }
                    showJumpDialog = false
                }) {
                    Text("Go")
                }
            },
            dismissButton = {
                TextButton(onClick = { showJumpDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}
