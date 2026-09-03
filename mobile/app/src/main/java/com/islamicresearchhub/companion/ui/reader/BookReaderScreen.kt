package com.islamicresearchhub.companion.ui.reader

import android.content.Context
import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
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
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.AppStateDatabase
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.data.local.PageEntity
import com.islamicresearchhub.companion.data.local.RecentlyOpenedEntity
import com.islamicresearchhub.companion.ui.theme.DarkGreenBorder
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurface
import com.islamicresearchhub.companion.ui.theme.DarkGreenTopBar
import com.islamicresearchhub.companion.ui.theme.EmeraldGold
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch

private const val PREFS_NAME = "reader_prefs"
private fun getSavedPageKey(bookId: Int) = "last_read_page_$bookId"

fun parseRichUrduTextWithSearch(rawContent: String, searchQuery: String): AnnotatedString {
    if (rawContent.isBlank()) return AnnotatedString("")

    val headingRegex = Regex("""<urh([1-6])>(.*?)</urh\1>""", RegexOption.DOT_MATCHES_ALL)
    val headings = headingRegex.findAll(rawContent).map { match ->
        val level = match.groupValues[1].toIntOrNull() ?: 1
        val titleText = match.groupValues[2].replace(Regex("""</?[a-zA-Z0-9]+[^>]*>"""), "").trim()
        Pair(level, titleText)
    }.filter { it.second.isNotEmpty() }.toList()

    val prepared = rawContent
        .replace(Regex("""</urh[1-6]>""", RegexOption.IGNORE_CASE), "\n\n")
        .replace(Regex("""<urh[1-6]>""", RegexOption.IGNORE_CASE), "\n\n")
        .replace(Regex("""<br\s*/?>""", RegexOption.IGNORE_CASE), "\n")
        .replace(Regex("""</?p>""", RegexOption.IGNORE_CASE), "\n\n")

    val cleanedText = prepared.replace(Regex("""</?[a-zA-Z0-9]+[^>]*>"""), "").trim()

    return buildAnnotatedString {
        append(cleanedText)

        for ((level, titleText) in headings) {
            var start = 0
            while (start < cleanedText.length) {
                val foundIndex = cleanedText.indexOf(titleText, start)
                if (foundIndex == -1) break

                val headingFontSize = when (level) {
                    1 -> 21.sp
                    2 -> 20.sp
                    else -> 19.sp
                }

                addStyle(
                    style = SpanStyle(
                        color = EmeraldGold,
                        fontWeight = FontWeight.ExtraBold,
                        fontSize = headingFontSize,
                    ),
                    start = foundIndex,
                    end = foundIndex + titleText.length,
                )
                start = foundIndex + titleText.length
            }
        }

        // Highlight matching search query text
        if (searchQuery.isNotBlank()) {
            var searchStart = 0
            while (searchStart < cleanedText.length) {
                val matchIdx = cleanedText.indexOf(searchQuery, searchStart, ignoreCase = true)
                if (matchIdx == -1) break

                addStyle(
                    style = SpanStyle(
                        background = EmeraldGold,
                        color = DarkGreenTopBar,
                        fontWeight = FontWeight.Bold
                    ),
                    start = matchIdx,
                    end = matchIdx + searchQuery.length
                )
                searchStart = matchIdx + searchQuery.length
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookReaderScreen(bookId: Int, startPageNo: Int?) {
    val context = LocalContext.current
    var bookMetadata by remember { mutableStateOf<BookEntity?>(null) }
    var pages by remember { mutableStateOf<List<PageEntity>>(emptyList()) }
    var showJumpDialog by remember { mutableStateOf(false) }
    var jumpInput by remember { mutableStateOf("") }
    var isBookmarked by remember { mutableStateOf(false) }
    
    // In-Book Search state
    var isSearchActive by remember { mutableStateOf(false) }
    var inBookSearchQuery by remember { mutableStateOf("") }
    var matchingPageIndices by remember { mutableStateOf<List<Int>>(emptyList()) }
    var currentMatchPointer by remember { mutableStateOf(0) }

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

    LaunchedEffect(bookMetadata, pages) {
        val metadata = bookMetadata ?: return@LaunchedEffect
        if (pages.isEmpty()) return@LaunchedEffect
        val resumePage = startPageNo ?: run {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.getInt(getSavedPageKey(bookId), pages.first().pageNo ?: 1)
        }
        AppStateDatabase.get(context).appStateDao().recordOpened(
            RecentlyOpenedEntity(
                bookId = bookId,
                title = metadata.title ?: "Untitled",
                author = metadata.author,
                lastPageNo = resumePage,
                openedAtEpochMillis = System.currentTimeMillis(),
            )
        )
    }

    // Update in-book search matching indices
    LaunchedEffect(inBookSearchQuery, pages) {
        if (inBookSearchQuery.isBlank() || pages.isEmpty()) {
            matchingPageIndices = emptyList()
            currentMatchPointer = 0
        } else {
            val matches = mutableListOf<Int>()
            pages.forEachIndexed { index, page ->
                if (page.content?.contains(inBookSearchQuery, ignoreCase = true) == true) {
                    matches.add(index)
                }
            }
            matchingPageIndices = matches
            currentMatchPointer = 0
            if (matches.isNotEmpty()) {
                listState.scrollToItem(matches.first())
            }
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
                    if (isSearchActive) {
                        OutlinedTextField(
                            value = inBookSearchQuery,
                            onValueChange = { inBookSearchQuery = it },
                            placeholder = { Text("Search in book...", color = DarkGreenSubText) },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth().height(48.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = DarkGreenSurface,
                                unfocusedContainerColor = DarkGreenSurface,
                                focusedBorderColor = EmeraldTeal,
                                unfocusedBorderColor = DarkGreenBorder,
                                focusedTextColor = DarkGreenLightText,
                                unfocusedTextColor = DarkGreenLightText
                            ),
                            shape = RoundedCornerShape(8.dp)
                        )
                    } else {
                        Column {
                            Text(
                                bookMetadata?.title ?: "Reader",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = DarkGreenLightText,
                                maxLines = 1
                            )
                            if (totalPages > 0) {
                                Text(
                                    "Page $currentPageNo of $totalPages",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = DarkGreenSubText
                                )
                            }
                        }
                    }
                },
                actions = {
                    if (isSearchActive) {
                        if (matchingPageIndices.isNotEmpty()) {
                            Text(
                                text = "${currentMatchPointer + 1}/${matchingPageIndices.size}",
                                color = EmeraldGold,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold
                            )
                            IconButton(onClick = {
                                if (currentMatchPointer > 0) {
                                    currentMatchPointer--
                                    scope.launch { listState.scrollToItem(matchingPageIndices[currentMatchPointer]) }
                                }
                            }) {
                                Icon(Icons.Default.ChevronLeft, contentDescription = "Prev", tint = EmeraldTeal)
                            }
                            IconButton(onClick = {
                                if (currentMatchPointer < matchingPageIndices.size - 1) {
                                    currentMatchPointer++
                                    scope.launch { listState.scrollToItem(matchingPageIndices[currentMatchPointer]) }
                                }
                            }) {
                                Icon(Icons.Default.ChevronRight, contentDescription = "Next", tint = EmeraldTeal)
                            }
                        }
                        IconButton(onClick = {
                            isSearchActive = false
                            inBookSearchQuery = ""
                        }) {
                            Icon(Icons.Default.Close, contentDescription = "Close Search", tint = DarkGreenSubText)
                        }
                    } else {
                        IconButton(onClick = { isSearchActive = true }) {
                            Icon(Icons.Default.Search, contentDescription = "Search in book", tint = EmeraldTeal)
                        }
                        if (totalPages > 0) {
                            IconButton(onClick = {
                                jumpInput = currentPageNo.toString()
                                showJumpDialog = true
                            }) {
                                Icon(Icons.AutoMirrored.Filled.List, contentDescription = "Jump to page", tint = EmeraldTeal)
                            }
                        }
                        IconButton(onClick = { isBookmarked = !isBookmarked }) {
                            Icon(
                                imageVector = if (isBookmarked) Icons.Default.Bookmark else Icons.Outlined.BookmarkBorder,
                                contentDescription = "Bookmark Page",
                                tint = if (isBookmarked) EmeraldGold else EmeraldTeal
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar)
            )
        },
        containerColor = MaterialTheme.colorScheme.background
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
                        color = DarkGreenSubText
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
                                .padding(horizontal = 12.dp, vertical = 6.dp),
                            colors = CardDefaults.cardColors(containerColor = DarkGreenSurface),
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "Page ${page.pageNo ?: (index + 1)}",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = EmeraldTeal,
                                        fontWeight = FontWeight.Bold
                                    )
                                    if (page.hadeesNumber != null) {
                                        Text(
                                            text = " • Hadith #${page.hadeesNumber}",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = EmeraldGold
                                        )
                                    }
                                    if (page.ayahNumber != null) {
                                        Text(
                                            text = " • Ayah #${page.ayahNumber}",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = EmeraldTeal
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(10.dp))

                                val formattedContent = remember(page.content, inBookSearchQuery) {
                                    parseRichUrduTextWithSearch(page.content ?: "", inBookSearchQuery)
                                }

                                Text(
                                    text = formattedContent,
                                    color = DarkGreenLightText,
                                    style = MaterialTheme.typography.bodyLarge.copy(
                                        lineHeight = 34.sp,
                                        fontSize = 18.sp
                                    )
                                )
                            }
                        }
                        HorizontalDivider(color = DarkGreenTopBar)
                    }
                }
            }
        }
    }

    if (showJumpDialog) {
        val parsedPage = jumpInput.toIntOrNull()
        val isInputError = parsedPage != null && totalPages > 0 && (parsedPage < 1 || parsedPage > totalPages)

        AlertDialog(
            onDismissRequest = { showJumpDialog = false },
            title = { Text("Jump to Page", color = DarkGreenLightText) },
            text = {
                Column {
                    OutlinedTextField(
                        value = jumpInput,
                        onValueChange = { jumpInput = it.filter { char -> char.isDigit() } },
                        label = { Text("Page number (1 - $totalPages)", color = DarkGreenSubText) },
                        singleLine = true,
                        isError = isInputError,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = EmeraldTeal,
                            unfocusedBorderColor = DarkGreenBorder,
                            focusedLabelColor = EmeraldTeal,
                            cursorColor = EmeraldTeal
                        )
                    )
                    if (isInputError) {
                        Text(
                            text = "Please enter a page between 1 and $totalPages",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                }
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
                    Text("Go", color = EmeraldTeal)
                }
            },
            dismissButton = {
                TextButton(onClick = { showJumpDialog = false }) {
                    Text("Cancel", color = DarkGreenSubText)
                }
            },
            containerColor = DarkGreenSurface,
        )
    }
}
