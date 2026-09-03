package com.islamicresearchhub.companion.ui.waqiat

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.SharedPreferences
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.InputStream
import java.util.Locale

data class WaqiatItem(
    val id: Int,
    val bookId: Int,
    val bookTitle: String,
    val title: String,
    val pageNo: Int,
    val subject: String,
    val excerpt: String,
    val citation: String,
    val keyFigures: List<String> = emptyList()
)

suspend fun loadAssetWaqiat(context: Context): List<WaqiatItem> = withContext(Dispatchers.IO) {
    val items = mutableListOf<WaqiatItem>()
    try {
        val stream: InputStream = context.assets.open("waqiat_database.json")
        val jsonString = stream.bufferedReader().use { it.readText() }
        val array = JSONArray(jsonString)
        for (i in 0 until array.length()) {
            val obj = array.getJSONObject(i)
            val figsArray = obj.optJSONArray("key_figures")
            val figures = mutableListOf<String>()
            if (figsArray != null) {
                for (j in 0 until figsArray.length()) {
                    figures.add(figsArray.getString(j))
                }
            }

            items.add(
                WaqiatItem(
                    id = obj.optInt("id", i + 1),
                    bookId = obj.optInt("book_id", 0),
                    bookTitle = obj.optString("book_title", ""),
                    title = obj.optString("title", "واقعہ"),
                    pageNo = obj.optInt("page", 1),
                    subject = obj.optString("subject", "اخلاق و موعظت"),
                    excerpt = obj.optString("text", ""),
                    citation = obj.optString("citation", ""),
                    keyFigures = figures
                )
            )
        }
    } catch (e: Exception) {
        e.printStackTrace()
    }
    return@withContext items
}

/**
 * Helper to build highlighted text spans with theme-matched contrast
 */
fun buildHighlightedText(text: String, query: String, palette: WaqiatThemeColors): AnnotatedString {
    if (query.isBlank()) return AnnotatedString(text)

    val cleanQuery = query.trim().lowercase(Locale.ROOT)
    val lowerText = text.lowercase(Locale.ROOT)
    val tokens = cleanQuery.split("\\s+".toRegex()).filter { it.isNotEmpty() }

    return buildAnnotatedString {
        append(text)
        tokens.forEach { token ->
            var startIndex = lowerText.indexOf(token)
            while (startIndex >= 0) {
                val endIndex = startIndex + token.length
                addStyle(
                    style = SpanStyle(
                        background = palette.highlightBg,
                        color = palette.highlightText,
                        fontWeight = FontWeight.Bold
                    ),
                    start = startIndex,
                    end = endIndex
                )
                startIndex = lowerText.indexOf(token, endIndex)
            }
        }
    }
}

/**
 * Waqiat Encyclopedia Screen with Live Themes (Dark Green, Off White, Sunny),
 * Font Size/Weight Controls, Word Highlighting, Multi-Filters & Top/Bottom Navigation.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WaqiatScreen(
    onOpenBookPage: (Int, Int) -> Unit = { _, _ -> }
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()

    val prefs: SharedPreferences = remember { context.getSharedPreferences("waqiat_prefs", Context.MODE_PRIVATE) }

    // Theme & Display Preferences
    var currentThemeMode by remember {
        val savedTheme = prefs.getString("theme_mode", AppThemeMode.DARK_GREEN.name) ?: AppThemeMode.DARK_GREEN.name
        mutableStateOf(try { AppThemeMode.valueOf(savedTheme) } catch (e: Exception) { AppThemeMode.DARK_GREEN })
    }
    var fontSizeSp by remember { mutableStateOf(prefs.getInt("font_size", 17)) }
    var isBoldText by remember { mutableStateOf(prefs.getBoolean("is_bold", false)) }
    var showSettingsSheet by remember { mutableStateOf(false) }

    val palette = remember(currentThemeMode) { getThemePalette(currentThemeMode) }

    var allWaqiat by remember { mutableStateOf<List<WaqiatItem>>(emptyList()) }
    var searchQuery by remember { mutableStateOf("") }
    var selectedBook by remember { mutableStateOf("تمام کتب") }
    var selectedCategory by remember { mutableStateOf("تمام") }
    var selectedSortOrder by remember { mutableStateOf("مطابقت") }
    var bookmarkedIds by remember { mutableStateOf(setOf<Int>()) }
    var showOnlyBookmarked by remember { mutableStateOf(false) }

    // Launcher for Bulk Importing additional Waqiat JSON/DB files
    val bulkWaqiatLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                Toast.makeText(context, "${uris.size} واقعات فائلیں امپورٹ ہو رہی ہیں...", Toast.LENGTH_SHORT).show()
                var importedCount = 0
                val newItems = mutableListOf<WaqiatItem>()
                uris.forEach { uri ->
                    context.contentResolver.openInputStream(uri)?.use { stream ->
                        val jsonString = stream.bufferedReader().use { it.readText() }
                        val array = JSONArray(jsonString)
                        for (i in 0 until array.length()) {
                            val obj = array.getJSONObject(i)
                            newItems.add(
                                WaqiatItem(
                                    id = obj.optInt("id", allWaqiat.size + importedCount + 1),
                                    bookId = obj.optInt("book_id", 0),
                                    bookTitle = obj.optString("book_title", ""),
                                    title = obj.optString("title", "واقعہ"),
                                    pageNo = obj.optInt("page", 1),
                                    subject = obj.optString("subject", "اخلاق و موعظت"),
                                    excerpt = obj.optString("text", ""),
                                    citation = obj.optString("citation", "")
                                )
                            )
                            importedCount++
                        }
                    }
                }
                allWaqiat = allWaqiat + newItems
                Toast.makeText(context, "کامیابی! $importedCount مزید واقعات امپورٹ ہو گئے!", Toast.LENGTH_LONG).show()
            } catch (e: Exception) {
                Toast.makeText(context, "امپورٹ میں خرابی: ${e.localizedMessage}", Toast.LENGTH_LONG).show()
            }
        }
    }

    LaunchedEffect(Unit) {
        allWaqiat = loadAssetWaqiat(context)
    }

    val bookFilters = listOf("تمام کتب", "مواعظِ شمسیہ", "خطبات فقیر", "خطبات حکیم الاسلام", "خطبات متکلم اسلام", "خطبات ذوالفقار", "تفسیر")
    val sortOptions = listOf("مطابقت", "ترتیب کتب", "طویل ترین", "مختصر ترین")

    val filteredWaqiat = remember(allWaqiat, searchQuery, selectedBook, selectedCategory, selectedSortOrder, showOnlyBookmarked, bookmarkedIds) {
        val queryTokens = searchQuery.trim().lowercase(Locale.ROOT).split("\\s+".toRegex()).filter { it.isNotEmpty() }

        var list = allWaqiat.filter { item ->
            val matchesFav = !showOnlyBookmarked || bookmarkedIds.contains(item.id)

            val searchableText = "${item.title} ${item.excerpt} ${item.bookTitle} ${item.citation} ${item.keyFigures.joinToString(" ")}".lowercase(Locale.ROOT)
            val matchesQuery = queryTokens.isEmpty() || queryTokens.all { searchableText.contains(it) }

            val matchesBook = selectedBook == "تمام کتب" || item.bookTitle.contains(selectedBook, ignoreCase = true)
            val matchesCategory = selectedCategory == "تمام" || item.subject.contains(selectedCategory, ignoreCase = true)

            matchesFav && matchesQuery && matchesBook && matchesCategory
        }

        when (selectedSortOrder) {
            "طویل ترین" -> list.sortedByDescending { it.excerpt.length }
            "مختصر ترین" -> list.sortedBy { it.excerpt.length }
            "ترتیب کتب" -> list.sortedWith(compareBy({ it.bookId }, { it.id }))
            else -> {
                if (queryTokens.isNotEmpty()) {
                    list.sortedByDescending { item ->
                        var score = 0
                        val tLower = item.title.lowercase(Locale.ROOT)
                        val eLower = item.excerpt.lowercase(Locale.ROOT)
                        queryTokens.forEach { token ->
                            if (tLower.contains(token)) score += 10
                            if (eLower.contains(token)) score += 2
                        }
                        score
                    }
                } else {
                    list
                }
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(palette.background)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp, vertical = 10.dp)
        ) {
            // Top Bar: Title, Theme Selector & Settings Button
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "واقعات انسائیکلوپیڈیا",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                        color = palette.textPrimary
                    )
                    Text(
                        text = "${allWaqiat.size} مستند واقعات و ارشادات",
                        fontSize = 12.5.sp,
                        color = palette.accentTeal
                    )
                }

                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    // Settings Icon (Themes & Font Size)
                    IconButton(
                        onClick = { showSettingsSheet = true },
                        modifier = Modifier
                            .background(palette.surface, RoundedCornerShape(8.dp))
                            .border(1.dp, palette.border, RoundedCornerShape(8.dp))
                    ) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = "Display Settings",
                            tint = palette.accentGold,
                            modifier = Modifier.size(20.dp)
                        )
                    }

                    // Bookmarks Toggle
                    IconButton(
                        onClick = { showOnlyBookmarked = !showOnlyBookmarked },
                        modifier = Modifier
                            .background(
                                if (showOnlyBookmarked) palette.accentGold.copy(alpha = 0.2f) else palette.surface,
                                RoundedCornerShape(8.dp)
                            )
                            .border(1.dp, palette.border, RoundedCornerShape(8.dp))
                    ) {
                        Icon(
                            imageVector = if (showOnlyBookmarked) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                            contentDescription = "Show Bookmarked",
                            tint = if (showOnlyBookmarked) palette.accentGold else palette.textSecondary
                        )
                    }

                    // Import Button
                    Button(
                        onClick = { bulkWaqiatLauncher.launch(arrayOf("*/*")) },
                        colors = ButtonDefaults.buttonColors(containerColor = palette.surface, contentColor = palette.textPrimary),
                        shape = RoundedCornerShape(8.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, palette.border),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Icon(Icons.Default.FolderOpen, contentDescription = null, modifier = Modifier.size(15.dp), tint = palette.accentTeal)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("امپورٹ", fontSize = 11.sp)
                    }
                }
            }

            // Search Field
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = { Text("الفاظ، عنوان، شخصیت یا کتاب سے تلاش کریں...", color = palette.textSecondary, fontSize = 13.5.sp) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = palette.accentTeal) },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = "" }) {
                            Icon(Icons.Default.Close, contentDescription = "Clear", tint = palette.textSecondary)
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = palette.accentTeal,
                    unfocusedBorderColor = palette.border,
                    focusedContainerColor = palette.searchBarBg,
                    unfocusedContainerColor = palette.searchBarBg,
                    focusedTextColor = palette.textPrimary,
                    unfocusedTextColor = palette.textPrimary
                )
            )

            // Book Filter Chips Row
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.padding(bottom = 6.dp)
            ) {
                items(bookFilters) { book ->
                    FilterChip(
                        selected = selectedBook == book,
                        onClick = { selectedBook = book },
                        label = { Text(book, fontSize = 11.5.sp) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = palette.accentTeal,
                            selectedLabelColor = Color.White,
                            containerColor = palette.surface,
                            labelColor = palette.textPrimary
                        ),
                        border = FilterChipDefaults.filterChipBorder(
                            enabled = true,
                            selected = selectedBook == book,
                            borderColor = palette.border,
                            selectedBorderColor = palette.accentTeal
                        )
                    )
                }
            }

            // Sorting & Results Count Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "${filteredWaqiat.size} واقعات ملے۔",
                    fontSize = 12.5.sp,
                    color = palette.accentTeal,
                    fontWeight = FontWeight.Bold
                )

                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    sortOptions.forEach { sortOpt ->
                        Text(
                            text = sortOpt,
                            fontSize = 11.5.sp,
                            color = if (selectedSortOrder == sortOpt) palette.accentGold else palette.textSecondary,
                            fontWeight = if (selectedSortOrder == sortOpt) FontWeight.Bold else FontWeight.Normal,
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(if (selectedSortOrder == sortOpt) palette.surfaceVariant else Color.Transparent)
                                .clickable { selectedSortOrder = sortOpt }
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
            }

            // Waqiat List
            if (filteredWaqiat.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = "کوئی واقعہ نہیں ملا۔ سرچ کا معیار یا فلٹر تبدیل کریں۔",
                        color = palette.textSecondary,
                        fontSize = 14.5.sp,
                        textAlign = TextAlign.Center
                    )
                }
            } else {
                LazyColumn(
                    state = listState,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.fillMaxSize()
                ) {
                    items(filteredWaqiat, key = { it.id }) { item ->
                        WaqiatCard(
                            item = item,
                            searchQuery = searchQuery,
                            palette = palette,
                            fontSize = fontSizeSp,
                            isBold = isBoldText,
                            isBookmarked = bookmarkedIds.contains(item.id),
                            onBookmarkToggle = {
                                bookmarkedIds = if (bookmarkedIds.contains(item.id)) {
                                    bookmarkedIds - item.id
                                } else {
                                    bookmarkedIds + item.id
                                }
                            },
                            onOpenPage = { bId, pNo -> onOpenBookPage(bId, pNo) },
                            onCopy = { text ->
                                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                val clip = ClipData.newPlainText("Waqia", text)
                                clipboard.setPrimaryClip(clip)
                                Toast.makeText(context, "متن کاپی ہو گیا!", Toast.LENGTH_SHORT).show()
                            }
                        )
                    }
                }
            }
        }

        // Floating Top / Bottom Quick Navigation Buttons
        Column(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(start = 16.dp, bottom = 20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            FloatingActionButton(
                onClick = {
                    scope.launch {
                        listState.animateScrollToItem(0)
                    }
                },
                modifier = Modifier.size(42.dp),
                containerColor = palette.accentTeal,
                contentColor = Color.White,
                shape = CircleShape
            ) {
                Icon(Icons.Default.KeyboardArrowUp, contentDescription = "Scroll to Top", modifier = Modifier.size(24.dp))
            }

            FloatingActionButton(
                onClick = {
                    scope.launch {
                        if (filteredWaqiat.isNotEmpty()) {
                            listState.animateScrollToItem(filteredWaqiat.size - 1)
                        }
                    }
                },
                modifier = Modifier.size(42.dp),
                containerColor = palette.surface,
                contentColor = palette.accentTeal,
                shape = CircleShape
            ) {
                Icon(Icons.Default.KeyboardArrowDown, contentDescription = "Scroll to Bottom", modifier = Modifier.size(24.dp))
            }
        }

        // Display Settings Bottom Sheet / Dialog
        if (showSettingsSheet) {
            AlertDialog(
                onDismissRequest = { showSettingsSheet = false },
                containerColor = palette.surface,
                title = {
                    Text(
                        text = "⚙️ ڈسپلے و تھیم سیٹنگز",
                        fontWeight = FontWeight.Bold,
                        color = palette.accentGold,
                        fontSize = 18.sp
                    )
                },
                text = {
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        // 1. Theme Selector
                        Text(
                            text = "🎨 رنگ و تھیم منتخب کریں:",
                            fontSize = 13.5.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = palette.textPrimary
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            AppThemeMode.values().forEach { mode ->
                                val isSelected = currentThemeMode == mode
                                Button(
                                    onClick = {
                                        currentThemeMode = mode
                                        prefs.edit().putString("theme_mode", mode.name).apply()
                                    },
                                    colors = ButtonDefaults.buttonColors(
                                        containerColor = if (isSelected) palette.accentTeal else palette.surfaceVariant,
                                        contentColor = if (isSelected) Color.White else palette.textPrimary
                                    ),
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(8.dp),
                                    contentPadding = PaddingValues(vertical = 6.dp)
                                ) {
                                    Text(mode.urduName, fontSize = 12.sp, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal)
                                }
                            }
                        }

                        Divider(color = palette.border)

                        // 2. Font Size Control
                        Text(
                            text = "📏 فانٹ سائز: $fontSizeSp sp",
                            fontSize = 13.5.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = palette.textPrimary
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Button(
                                onClick = {
                                    if (fontSizeSp > 13) {
                                        fontSizeSp -= 2
                                        prefs.edit().putInt("font_size", fontSizeSp).apply()
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = palette.surfaceVariant, contentColor = palette.textPrimary),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Text("A- چھوٹا", fontSize = 12.sp)
                            }

                            Text(
                                text = "نمونہ متن",
                                fontSize = fontSizeSp.sp,
                                fontWeight = if (isBoldText) FontWeight.Bold else FontWeight.Normal,
                                color = palette.textPrimary
                            )

                            Button(
                                onClick = {
                                    if (fontSizeSp < 32) {
                                        fontSizeSp += 2
                                        prefs.edit().putInt("font_size", fontSizeSp).apply()
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = palette.surfaceVariant, contentColor = palette.textPrimary),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Text("A+ بڑا", fontSize = 12.sp)
                            }
                        }

                        Divider(color = palette.border)

                        // 3. Bold Text Switch
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "✍️ متن کی موٹائی (Bold Text):",
                                fontSize = 13.5.sp,
                                color = palette.textPrimary
                            )
                            Switch(
                                checked = isBoldText,
                                onCheckedChange = {
                                    isBoldText = it
                                    prefs.edit().putBoolean("is_bold", it).apply()
                                },
                                colors = SwitchDefaults.colors(
                                    checkedThumbColor = palette.accentTeal,
                                    checkedTrackColor = palette.accentTeal.copy(alpha = 0.5f),
                                    uncheckedThumbColor = palette.textSecondary,
                                    uncheckedTrackColor = palette.surfaceVariant
                                )
                            )
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = { showSettingsSheet = false },
                        colors = ButtonDefaults.buttonColors(containerColor = palette.accentTeal, contentColor = Color.White),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("محفوظ کریں", fontSize = 13.sp)
                    }
                }
            )
        }
    }
}

@Composable
fun WaqiatCard(
    item: WaqiatItem,
    searchQuery: String,
    palette: WaqiatThemeColors,
    fontSize: Int,
    isBold: Boolean,
    isBookmarked: Boolean,
    onBookmarkToggle: () -> Unit,
    onOpenPage: (Int, Int) -> Unit,
    onCopy: (String) -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp)),
        colors = CardDefaults.cardColors(containerColor = palette.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, palette.border),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Header: Title & Bookmark
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = buildHighlightedText("✦ ${item.title}", searchQuery, palette),
                    fontSize = (fontSize + 1).sp,
                    fontWeight = FontWeight.Bold,
                    color = palette.accentGold,
                    modifier = Modifier.weight(1f)
                )
                IconButton(onClick = onBookmarkToggle) {
                    Icon(
                        imageVector = if (isBookmarked) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                        contentDescription = "Bookmark",
                        tint = if (isBookmarked) palette.accentGold else palette.textSecondary
                    )
                }
            }

            // Subject Badge & Book Badge
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Surface(
                    color = palette.accentTeal.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(6.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, palette.accentTeal.copy(alpha = 0.25f))
                ) {
                    Text(
                        text = buildHighlightedText("🏷️ ${item.subject}", searchQuery, palette),
                        fontSize = 11.5.sp,
                        color = palette.accentTeal,
                        modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp)
                    )
                }

                Surface(
                    color = palette.textSecondary.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(6.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, palette.border)
                ) {
                    Text(
                        text = buildHighlightedText("📚 ${item.bookTitle}", searchQuery, palette),
                        fontSize = 11.5.sp,
                        color = palette.textSecondary,
                        modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp)
                    )
                }
            }

            // Excerpt Body with High Contrast & Font Customization
            Text(
                text = buildHighlightedText(item.excerpt, searchQuery, palette),
                fontSize = fontSize.sp,
                fontWeight = if (isBold) FontWeight.Bold else FontWeight.Normal,
                color = palette.textPrimary,
                lineHeight = (fontSize * 1.65).sp,
                textAlign = TextAlign.Justify
            )

            // Footer Actions & Citation
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = buildHighlightedText("📍 ${item.citation}", searchQuery, palette),
                    fontSize = 11.5.sp,
                    color = palette.textSecondary,
                    modifier = Modifier.weight(1f)
                )

                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    IconButton(onClick = { onCopy("واقعہ: ${item.title}\n\n${item.excerpt}\n\nحوالہ: ${item.citation}\n(ماخذ: واقعات انسائیکلوپیڈیا)") }) {
                        Icon(
                            imageVector = Icons.Default.ContentCopy,
                            contentDescription = "Copy",
                            tint = palette.textSecondary,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                    IconButton(onClick = { onOpenPage(item.bookId, item.pageNo) }) {
                        Icon(
                            imageVector = Icons.Default.MenuBook,
                            contentDescription = "Read in Book",
                            tint = palette.accentTeal,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}
