package com.islamicresearchhub.companion.ui.catalog

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
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
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.data.local.copyPickedFileToCache
import kotlinx.coroutines.launch

/**
 * Phase 18 Catalog Browse & Search Screen:
 * Pre-loaded 36,249 Master Catalog books with instant search, category chips,
 * dark mode emerald design system, and custom catalog file importer.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CatalogListScreen(onBookClick: (Int) -> Unit) {
    val context = LocalContext.current
    var books by remember { mutableStateOf<List<BookEntity>>(emptyList()) }
    var searchQuery by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf("All") }
    var imported by remember { mutableStateOf(true) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    val categories = listOf("All", "Hadith", "Tafseer", "Fiqh", "Seerah", "Aqeedah", "English")

    suspend fun loadBooks(query: String, category: String) {
        try {
            val dao = CatalogDatabase.openExisting(context).catalogDao()
            val rawList = if (query.isBlank()) {
                dao.listAll()
            } else {
                dao.search(query.trim())
            }

            books = if (category == "All") {
                rawList
            } else {
                rawList.filter { it.category?.contains(category, ignoreCase = true) == true || it.title?.contains(category, ignoreCase = true) == true }
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

    LaunchedEffect(Unit) {
        loadBooks("", "All")
    }

    LaunchedEffect(searchQuery, selectedCategory) {
        loadBooks(searchQuery, selectedCategory)
    }

    val accentTeal = MaterialTheme.colorScheme.primary
    val cardBg = MaterialTheme.colorScheme.surface
    val lightText = MaterialTheme.colorScheme.onSurface
    val subText = MaterialTheme.colorScheme.onSurfaceVariant
    val outlineColor = MaterialTheme.colorScheme.outline

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Book, contentDescription = null, tint = accentTeal, modifier = Modifier.size(28.dp))
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text("Islamic Research Hub", color = lightText, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                            Text("Master Library Companion", color = subText, fontSize = 12.sp)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            // Header stats and Custom Import Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "${books.size} Books Available",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = accentTeal
                )
                Button(
                    onClick = { importLauncher.launch(arrayOf("*/*")) },
                    colors = ButtonDefaults.buttonColors(containerColor = cardBg, contentColor = lightText),
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                ) {
                    Icon(Icons.Default.FolderOpen, contentDescription = null, modifier = Modifier.size(16.dp), tint = accentTeal)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Custom DB", fontSize = 12.sp)
                }
            }

            // Search Bar
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                placeholder = { Text("Search 36,249 books by title or author...", color = subText) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = "Search", tint = accentTeal) },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = "" }) {
                            Icon(Icons.Default.Clear, contentDescription = "Clear search", tint = subText)
                        }
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = cardBg,
                    unfocusedContainerColor = cardBg,
                    focusedBorderColor = accentTeal,
                    unfocusedBorderColor = outlineColor,
                    focusedTextColor = lightText,
                    unfocusedTextColor = lightText
                )
            )

            // Category Filter Chips
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(categories) { cat ->
                    val isSelected = selectedCategory == cat
                    FilterChip(
                        selected = isSelected,
                        onClick = { selectedCategory = cat },
                        label = { Text(cat, fontSize = 13.sp) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = accentTeal,
                            selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
                            containerColor = cardBg,
                            labelColor = subText
                        ),
                        border = FilterChipDefaults.filterChipBorder(
                            borderColor = if (isSelected) accentTeal else outlineColor,
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
                        text = if (searchQuery.isNotEmpty()) "No books matching '$searchQuery'." else "No books found.",
                        color = subText,
                        fontSize = 15.sp
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(books, key = { it.bookId }) { book ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onBookClick(book.bookId) },
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(containerColor = cardBg)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Surface(
                                    modifier = Modifier.size(44.dp),
                                    shape = RoundedCornerShape(8.dp),
                                    color = accentTeal.copy(alpha = 0.2f)
                                ) {
                                    Box(contentAlignment = Alignment.Center) {
                                        Icon(Icons.Default.Book, contentDescription = null, tint = accentTeal, modifier = Modifier.size(22.dp))
                                    }
                                }
                                Spacer(modifier = Modifier.width(14.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = book.title ?: "Untitled",
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 15.sp,
                                        color = lightText
                                    )
                                    Spacer(modifier = Modifier.height(2.dp))
                                    Text(
                                        text = book.author?.takeIf { it.isNotBlank() } ?: "Unknown Author",
                                        fontSize = 13.sp,
                                        color = subText
                                    )
                                    if (!book.category.isNullOrBlank()) {
                                        Spacer(modifier = Modifier.height(4.dp))
                                        Surface(
                                            shape = RoundedCornerShape(4.dp),
                                            color = outlineColor
                                        ) {
                                            Text(
                                                text = book.category,
                                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                                fontSize = 11.sp,
                                                color = accentTeal
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
