package com.islamicresearchhub.companion.ui.catalog

import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.data.local.bulkImportBookFiles
import com.islamicresearchhub.companion.data.local.copyPickedFileToCache
import com.islamicresearchhub.companion.ui.common.BookListCard
import com.islamicresearchhub.companion.ui.theme.DarkGreenBorder
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurface
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurfaceVariant
import com.islamicresearchhub.companion.ui.theme.DarkGreenTopBar
import com.islamicresearchhub.companion.ui.theme.EmeraldGold
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal
import kotlinx.coroutines.launch

private val BOOK_PACKAGE_FILE_NAME = Regex("""^book_(\d+)\.db$""")

private fun getInstalledBookIds(context: Context): Set<Int> {
    val set = mutableSetOf<Int>()
    context.databaseList().forEach { name ->
        BOOK_PACKAGE_FILE_NAME.find(name)?.groupValues?.get(1)?.toIntOrNull()?.let { set.add(it) }
    }
    try {
        context.assets.list("sample_books")?.forEach { name ->
            BOOK_PACKAGE_FILE_NAME.find(name)?.groupValues?.get(1)?.toIntOrNull()?.let { set.add(it) }
        }
    } catch (_: Exception) {}
    return set
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CatalogListScreen(onBookClick: (Int) -> Unit) {
    val context = LocalContext.current
    var books by remember { mutableStateOf<List<BookEntity>>(emptyList()) }
    var searchQuery by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf("All") }
    var showOnlyInstalled by remember { mutableStateOf(true) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    val categories = listOf("All", "Khutbat", "Tib", "Hadith", "Tafseer", "Fiqh", "Seerah", "Aqeedah", "English")

    suspend fun loadBooks(query: String, category: String, installedOnly: Boolean) {
        try {
            val dao = CatalogDatabase.openExisting(context).catalogDao()
            val installedIds = getInstalledBookIds(context)
            
            val rawList = if (query.isBlank()) {
                dao.listAll()
            } else {
                dao.search(query.trim())
            }

            var filtered = if (category == "All") {
                rawList
            } else {
                when (category) {
                    "Khutbat" -> rawList.filter {
                        it.title?.contains("khutb", ignoreCase = true) == true ||
                        it.title?.contains("خطب", ignoreCase = true) == true ||
                        it.category?.contains("khutb", ignoreCase = true) == true
                    }
                    "Tib" -> rawList.filter {
                        it.title?.contains("tib", ignoreCase = true) == true ||
                        it.title?.contains("طب", ignoreCase = true) == true ||
                        it.title?.contains("حکمت", ignoreCase = true) == true ||
                        it.title?.contains("علاج", ignoreCase = true) == true ||
                        it.category?.contains("tib", ignoreCase = true) == true
                    }
                    else -> rawList.filter {
                        it.category?.contains(category, ignoreCase = true) == true ||
                        it.title?.contains(category, ignoreCase = true) == true
                    }
                }
            }

            if (installedOnly) {
                filtered = filtered.filter { installedIds.contains(it.bookId) }
            }

            books = filtered
        } catch (e: Exception) {
            snackbarHostState.showSnackbar("Error loading books: ${e.localizedMessage}")
        }
    }

    val bulkImportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                snackbarHostState.showSnackbar("Bulk importing ${uris.size} book files...")
                val importedCount = bulkImportBookFiles(context, uris)
                loadBooks(searchQuery, selectedCategory, showOnlyInstalled)
                snackbarHostState.showSnackbar("Successfully imported $importedCount books at once!")
            } catch (e: Exception) {
                snackbarHostState.showSnackbar("Bulk import completed with errors: ${e.localizedMessage}")
            }
        }
    }

    LaunchedEffect(Unit) {
        loadBooks("", "All", true)
    }

    LaunchedEffect(searchQuery, selectedCategory, showOnlyInstalled) {
        loadBooks(searchQuery, selectedCategory, showOnlyInstalled)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Book, contentDescription = null, tint = EmeraldTeal, modifier = Modifier.size(26.dp))
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text("Library", color = DarkGreenLightText, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                            Text(
                                if (showOnlyInstalled) "Installed Offline Books" else "Full Master Corpus (36k)",
                                color = DarkGreenSubText,
                                fontSize = 12.sp
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar),
                actions = {
                    Button(
                        onClick = { bulkImportLauncher.launch(arrayOf("*/*")) },
                        colors = ButtonDefaults.buttonColors(containerColor = EmeraldTeal, contentColor = Color.White),
                        shape = RoundedCornerShape(8.dp),
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                        modifier = Modifier.padding(end = 8.dp)
                    ) {
                        Icon(Icons.Default.FolderOpen, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("تمام کتب اکٹھا امپورٹ کریں", fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            // Mode Segment Control Bar (Installed vs Full Catalog)
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 6.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .border(width = 1.dp, color = DarkGreenBorder, shape = RoundedCornerShape(12.dp)),
                color = DarkGreenSurface,
            ) {
                Row(modifier = Modifier.fillMaxWidth().padding(4.dp)) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (showOnlyInstalled) EmeraldTeal else DarkGreenSurface)
                            .clickable { showOnlyInstalled = true }
                            .padding(vertical = 8.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = null,
                                tint = if (showOnlyInstalled) DarkGreenLightText else DarkGreenSubText,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Installed Books",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (showOnlyInstalled) DarkGreenLightText else DarkGreenSubText,
                            )
                        }
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (!showOnlyInstalled) EmeraldTeal else DarkGreenSurface)
                            .clickable { showOnlyInstalled = false }
                            .padding(vertical = 8.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = "All Catalog (36k)",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (!showOnlyInstalled) DarkGreenLightText else DarkGreenSubText,
                        )
                    }
                }
            }

            // Header stats and Custom Import Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = if (showOnlyInstalled) "${books.size} Installed Books Ready" else "${books.size} Catalog Books",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = EmeraldTeal
                )
                Button(
                    onClick = { bulkImportLauncher.launch(arrayOf("*/*")) },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkGreenSurface, contentColor = DarkGreenLightText),
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                ) {
                    Icon(Icons.Default.FolderOpen, contentDescription = null, modifier = Modifier.size(16.dp), tint = EmeraldTeal)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Bulk Import Books", fontSize = 12.sp)
                }
            }

            // Search Bar
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                placeholder = {
                    Text(
                        if (showOnlyInstalled) "Search installed books..." else "Search 36k corpus books...",
                        color = DarkGreenSubText
                    )
                },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = "Search", tint = EmeraldTeal) },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = "" }) {
                            Icon(Icons.Default.Clear, contentDescription = "Clear search", tint = DarkGreenSubText)
                        }
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = DarkGreenSurface,
                    unfocusedContainerColor = DarkGreenSurface,
                    focusedBorderColor = EmeraldTeal,
                    unfocusedBorderColor = DarkGreenBorder,
                    focusedTextColor = DarkGreenLightText,
                    unfocusedTextColor = DarkGreenLightText
                )
            )

            // Category Filter Chips
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(categories) { cat ->
                    val isSelected = selectedCategory == cat
                    FilterChip(
                        selected = isSelected,
                        onClick = { selectedCategory = cat },
                        label = { Text(cat, fontSize = 13.sp) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = EmeraldTeal,
                            selectedLabelColor = DarkGreenLightText,
                            containerColor = DarkGreenSurface,
                            labelColor = DarkGreenSubText
                        ),
                        border = FilterChipDefaults.filterChipBorder(
                            borderColor = if (isSelected) EmeraldTeal else DarkGreenBorder,
                            enabled = true,
                            selected = isSelected
                        )
                    )
                }
            }

            Spacer(modifier = Modifier.height(4.dp))

            if (books.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (showOnlyInstalled) "No installed books found matching filter. Tap 'Import DB' or switch to 'All Catalog (36k)'." else "No books found matching search.",
                        color = DarkGreenSubText,
                        fontSize = 14.sp,
                        modifier = Modifier.padding(24.dp)
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(books, key = { it.bookId }) { book ->
                        BookListCard(
                            book = book,
                            onClick = { onBookClick(book.bookId) }
                        )
                    }
                }
            }
        }
    }
}
