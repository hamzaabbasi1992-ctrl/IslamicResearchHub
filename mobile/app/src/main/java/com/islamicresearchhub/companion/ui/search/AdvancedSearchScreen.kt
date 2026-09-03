package com.islamicresearchhub.companion.ui.search

import android.content.Context
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.BookPackageDatabase
import com.islamicresearchhub.companion.ui.common.LanguageManager
import com.islamicresearchhub.companion.ui.theme.DarkGreenBorder
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurface
import com.islamicresearchhub.companion.ui.theme.DarkGreenTopBar
import com.islamicresearchhub.companion.ui.theme.EmeraldGold
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class AdvancedSearchResult(
    val bookId: Int,
    val bookTitle: String,
    val pageNo: Int,
    val snippet: String,
    val matchQuery: String,
    val matchRank: Int = 1
)

data class GroupedBookResults(
    val bookId: Int,
    val bookTitle: String,
    val totalMatches: Int,
    val items: List<AdvancedSearchResult>,
    val bestRank: Int = 1
)

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

/** Mirrors shared/arabic_text_normalization.py's pair list so mobile and
 * desktop search treat the same spellings as equivalent. */
private fun normalizeUrduArabicText(text: String): String {
    return text
        .replace("ً", "")
        .replace("ٌ", "")
        .replace("ٍ", "")
        .replace("َ", "")
        .replace("ُ", "")
        .replace("ِ", "")
        .replace("ّ", "")
        .replace("ْ", "")
        .replace("ٓ", "")
        .replace("ٔ", "")
        .replace("ٕ", "")
        .replace("ٰ", "")
        .replace("ـ", "")
        .replace('أ', 'ا')
        .replace('إ', 'ا')
        .replace('آ', 'ا')
        .replace('ٱ', 'ا')
        .replace('ى', 'ي')
        .replace('ی', 'ي')
        .replace('ئ', 'ي')
        .replace('ؤ', 'و')
        .replace('ة', 'ه')
        .replace('ۃ', 'ه')
        .replace('ک', 'ك')
        .replace('ہ', 'ه')
        .replace('ھ', 'ه')
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdvancedSearchScreen(
    onBackClick: () -> Unit,
    onOpenPage: (bookId: Int, pageNo: Int) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var searchQuery by remember { mutableStateOf("") }
    var searchScope by remember { mutableStateOf("Title") }
    var matchMode by remember { mutableStateOf("AllWords") }
    var ignoreHamza by remember { mutableStateOf(true) }
    var showCategoryModal by remember { mutableStateOf(false) }
    var showBookModal by remember { mutableStateOf(false) }
    var selectedBookIds by remember { mutableStateOf<Set<Int>>(emptySet()) }
    var installedBookMap by remember { mutableStateOf<Map<Int, String>>(emptyMap()) }
    var bookSearchFilter by remember { mutableStateOf("") }

    val allCategories = remember {
        listOf(
            "قرآن کریم", "حدیث شریف", "سیرت", "فقہ", "فتاوی",
            "درس نظامی", "اصلاحی کتب", "زبان و ادب", "تاریخ جغرافیہ و ممالک"
        )
    }
    var selectedCategories by remember { mutableStateOf(allCategories.toSet()) }
    var recentSearchChips by remember { mutableStateOf(listOf("احیاء العلوم", "بخاري", "سيرت", "فتاوى")) }
    var isSearching by remember { mutableStateOf(false) }
    var searchResultsGrouped by remember { mutableStateOf<List<GroupedBookResults>>(emptyList()) }
    var totalMatchesCount by remember { mutableStateOf(0) }
    var totalBooksCount by remember { mutableStateOf(0) }
    var hasSearched by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        withContext(Dispatchers.IO) {
            val installedIds = getInstalledBookIds(context)
            val map = mutableMapOf<Int, String>()
            for (bId in installedIds) {
                if (BookPackageDatabase.isImported(context, bId)) {
                    try {
                        val db = BookPackageDatabase.openExisting(context, bId)
                        val title = db.pageDao().getBook()?.title ?: "Book #$bId"
                        map[bId] = title
                    } catch (_: Exception) {}
                }
            }
            withContext(Dispatchers.Main) {
                installedBookMap = map
            }
        }
    }

    fun performSearch() {
        val query = searchQuery.trim()
        if (query.isBlank()) return

        if (!recentSearchChips.contains(query)) {
            recentSearchChips = (listOf(query) + recentSearchChips).take(6)
        }

        isSearching = true
        hasSearched = true

        scope.launch(Dispatchers.IO) {
            val installedIds = getInstalledBookIds(context)
            val resultsList = mutableListOf<AdvancedSearchResult>()
            val expandedTerms = CrossLanguageTranslator.expandQuery(context, query)
            val allQueries = (listOf(query) + expandedTerms).distinct()

            for (bookId in installedIds) {
                if (selectedBookIds.isNotEmpty() && !selectedBookIds.contains(bookId)) continue
                if (!BookPackageDatabase.isImported(context, bookId)) continue
                try {
                    val db = BookPackageDatabase.openExisting(context, bookId)
                    val bookMeta = db.pageDao().getBook()
                    val bookTitle = bookMeta?.title ?: "Book #$bookId"
                    val pages = db.pageDao().listPages()

                    for (page in pages) {
                        val content = page.content ?: continue
                        val normContent = if (ignoreHamza) normalizeUrduArabicText(content) else content

                        var matchedQuery: String? = null
                        var matchedRank = 99

                        for ((idx, q) in allQueries.withIndex()) {
                            val targetQuery = if (ignoreHamza) normalizeUrduArabicText(q) else q
                            val isMatch = when (matchMode) {
                                "Exact" -> normContent.contains(targetQuery, ignoreCase = true)
                                "AnyWord" -> targetQuery.split(" ").any { word ->
                                    word.isNotBlank() && normContent.contains(word, ignoreCase = true)
                                }
                                else -> targetQuery.split(" ").all { word ->
                                    word.isNotBlank() && normContent.contains(word, ignoreCase = true)
                                }
                            }
                            if (isMatch) {
                                matchedQuery = q
                                matchedRank = if (idx == 0) 1 else 2
                                break
                            }
                        }

                        if (matchedQuery != null) {
                            val cleanContent = content.replace(Regex("""</?[a-zA-Z0-9]+[^>]*>"""), "").trim()
                            val snippetText = cleanContent.take(140) + if (cleanContent.length > 140) "..." else ""
                            resultsList.add(
                                AdvancedSearchResult(
                                    bookId = bookId,
                                    bookTitle = bookTitle,
                                    pageNo = page.pageNo ?: 1,
                                    snippet = snippetText,
                                    matchQuery = matchedQuery,
                                    matchRank = matchedRank
                                )
                            )
                        }
                    }
                } catch (_: Exception) {}
            }

            val grouped = resultsList
                .groupBy { it.bookId }
                .map { (bId, items) ->
                    val sortedItems = items.sortedWith(compareBy({ it.matchRank }, { it.pageNo }))
                    GroupedBookResults(
                        bookId = bId,
                        bookTitle = items.first().bookTitle,
                        totalMatches = items.size,
                        items = sortedItems,
                        bestRank = sortedItems.minOf { it.matchRank }
                    )
                }
                .sortedWith(compareBy({ it.bestRank }, { -it.totalMatches }, { it.bookTitle }))

            withContext(Dispatchers.Main) {
                searchResultsGrouped = grouped
                totalMatchesCount = resultsList.size
                totalBooksCount = grouped.size
                isSearching = false
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        LanguageManager.getString("advanced_search"),
                        color = EmeraldGold,
                        fontWeight = FontWeight.Bold,
                        fontSize = 20.sp
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = EmeraldTeal)
                    }
                },
                actions = {
                    if (hasSearched) {
                        IconButton(onClick = {
                            hasSearched = false
                            searchResultsGrouped = emptyList()
                        }) {
                            Icon(Icons.Default.Close, contentDescription = "Clear Results", tint = DarkGreenSubText)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar)
            )
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            if (!hasSearched) {
                // Search Input Field
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    placeholder = {
                        Text(
                            LanguageManager.getString("search_placeholder"),
                            color = DarkGreenSubText
                        )
                    },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = EmeraldTeal) },
                    trailingIcon = {
                        if (searchQuery.isNotEmpty()) {
                            IconButton(onClick = { searchQuery = "" }) {
                                Icon(Icons.Default.Close, contentDescription = null, tint = DarkGreenSubText)
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

                if (recentSearchChips.isNotEmpty()) {
                    LazyRow(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(recentSearchChips) { chipText ->
                            AssistChip(
                                onClick = {
                                    searchQuery = chipText
                                    performSearch()
                                },
                                label = { Text(chipText, color = EmeraldTeal, fontSize = 13.sp) },
                                colors = AssistChipDefaults.assistChipColors(
                                    containerColor = DarkGreenSurface,
                                    labelColor = EmeraldTeal
                                ),
                                border = BorderStroke(1.dp, DarkGreenBorder)
                            )
                        }
                    }
                }

                HorizontalDivider(color = DarkGreenBorder)

                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .padding(horizontal = 16.dp, vertical = 12.dp)
                ) {
                    // Section 1: How to Search (Scope)
                    item {
                        Text(
                            text = LanguageManager.getString("how_to_search"),
                            color = EmeraldGold,
                            fontWeight = FontWeight.Bold,
                            fontSize = 17.sp,
                            modifier = Modifier.padding(bottom = 6.dp)
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(
                                selected = searchScope == "Title",
                                onClick = { searchScope = "Title" },
                                colors = RadioButtonDefaults.colors(selectedColor = EmeraldTeal)
                            )
                            Text(
                                LanguageManager.getString("search_in_title"),
                                color = DarkGreenLightText,
                                fontSize = 15.sp,
                                modifier = Modifier.clickable { searchScope = "Title" }
                            )
                            Spacer(modifier = Modifier.width(20.dp))
                            RadioButton(
                                selected = searchScope == "Full",
                                onClick = { searchScope = "Full" },
                                colors = RadioButtonDefaults.colors(selectedColor = EmeraldTeal)
                            )
                            Text(
                                LanguageManager.getString("search_in_full"),
                                color = DarkGreenLightText,
                                fontSize = 15.sp,
                                modifier = Modifier.clickable { searchScope = "Full" }
                            )
                        }
                        Spacer(modifier = Modifier.height(16.dp))
                    }

                    // Section 2: What to Search (Match Mode)
                    item {
                        Text(
                            text = LanguageManager.getString("what_to_search"),
                            color = EmeraldGold,
                            fontWeight = FontWeight.Bold,
                            fontSize = 17.sp,
                            modifier = Modifier.padding(bottom = 6.dp)
                        )
                        val modes = listOf(
                            "AllWords" to LanguageManager.getString("all_words"),
                            "AnyWord" to LanguageManager.getString("any_word"),
                            "Exact" to LanguageManager.getString("exact_match"),
                            "Ordered" to LanguageManager.getString("ordered_match")
                        )
                        modes.forEach { (modeKey, label) ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 2.dp)
                            ) {
                                RadioButton(
                                    selected = matchMode == modeKey,
                                    onClick = { matchMode = modeKey },
                                    colors = RadioButtonDefaults.colors(selectedColor = EmeraldTeal)
                                )
                                Text(
                                    text = label,
                                    color = DarkGreenLightText,
                                    fontSize = 15.sp,
                                    modifier = Modifier.clickable { matchMode = modeKey }
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(16.dp))
                    }

                    // Section 3: Hamza Checkbox
                    item {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp)
                        ) {
                            Checkbox(
                                checked = ignoreHamza,
                                onCheckedChange = { ignoreHamza = it },
                                colors = CheckboxDefaults.colors(checkedColor = EmeraldTeal)
                            )
                            Text(
                                text = LanguageManager.getString("ignore_hamza"),
                                color = DarkGreenLightText,
                                fontSize = 14.sp,
                                modifier = Modifier.clickable { ignoreHamza = !ignoreHamza }
                            )
                        }
                        Spacer(modifier = Modifier.height(20.dp))
                    }

                    // Section 4: Category & Specific Book Selection Scope Buttons
                    item {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Button(
                                onClick = { showCategoryModal = true },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = DarkGreenSurface,
                                    contentColor = DarkGreenLightText
                                ),
                                shape = RoundedCornerShape(10.dp),
                                modifier = Modifier
                                    .weight(1f)
                                    .height(48.dp)
                                    .border(width = 1.dp, color = DarkGreenBorder, shape = RoundedCornerShape(10.dp))
                            ) {
                                Icon(Icons.Default.FilterList, contentDescription = null, tint = EmeraldTeal)
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(LanguageManager.getString("select_category_scope"), fontSize = 12.sp)
                            }

                            Button(
                                onClick = { showBookModal = true },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = DarkGreenSurface,
                                    contentColor = DarkGreenLightText
                                ),
                                shape = RoundedCornerShape(10.dp),
                                modifier = Modifier
                                    .weight(1f)
                                    .height(48.dp)
                                    .border(width = 1.dp, color = DarkGreenBorder, shape = RoundedCornerShape(10.dp))
                            ) {
                                Icon(Icons.Default.FilterList, contentDescription = null, tint = EmeraldGold)
                                Spacer(modifier = Modifier.width(4.dp))
                                val bookCountLabel = if (selectedBookIds.isEmpty()) "All Books" else "${selectedBookIds.size} Selected"
                                Text("Books ($bookCountLabel)", fontSize = 12.sp)
                            }
                        }
                        Spacer(modifier = Modifier.height(24.dp))
                    }

                    // Perform Search Action Button
                    item {
                        Button(
                            onClick = { performSearch() },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = EmeraldTeal,
                                contentColor = DarkGreenLightText
                            ),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(52.dp)
                        ) {
                            Icon(Icons.Default.Search, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                LanguageManager.getString("advanced_search"),
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            } else {
                // Results Screen View matching Screenshot #3
                Column(modifier = Modifier.fillMaxSize()) {
                    // Summary Banner Bar
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        color = DarkGreenTopBar
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "$totalBooksCount کتب میں $totalMatchesCount.0 نتائج حاصل ہوئے",
                                color = EmeraldGold,
                                fontWeight = FontWeight.Bold,
                                fontSize = 16.sp
                            )
                        }
                    }

                    if (isSearching) {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("البحث جاري...", color = DarkGreenSubText, fontSize = 16.sp)
                        }
                    } else if (searchResultsGrouped.isEmpty()) {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("لم يتم العثور على نتائج.", color = DarkGreenSubText, fontSize = 16.sp)
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(12.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            items(searchResultsGrouped) { group ->
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = CardDefaults.cardColors(containerColor = DarkGreenSurface),
                                    shape = RoundedCornerShape(12.dp)
                                ) {
                                    Column(modifier = Modifier.padding(14.dp)) {
                                        // Book Title Header
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Text(
                                                text = group.bookTitle,
                                                color = EmeraldGold,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 16.sp,
                                                modifier = Modifier.weight(1f)
                                            )
                                            Text(
                                                text = "${group.totalMatches} نتائج",
                                                color = DarkGreenSubText,
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.Bold
                                            )
                                        }

                                        HorizontalDivider(
                                            color = DarkGreenBorder,
                                            modifier = Modifier.padding(vertical = 8.dp)
                                        )

                                        // Snippet Items
                                        group.items.forEach { item ->
                                            Row(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .clickable { onOpenPage(item.bookId, item.pageNo) }
                                                    .padding(vertical = 6.dp),
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Text(
                                                    text = "${item.pageNo}",
                                                    color = EmeraldTeal,
                                                    fontSize = 14.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    modifier = Modifier.width(36.dp)
                                                )
                                                Text(
                                                    text = buildAnnotatedString {
                                                        append(item.snippet)
                                                        val idx = item.snippet.indexOf(item.matchQuery, ignoreCase = true)
                                                        if (idx >= 0) {
                                                            addStyle(
                                                                style = SpanStyle(color = EmeraldGold, fontWeight = FontWeight.ExtraBold),
                                                                start = idx,
                                                                end = idx + item.matchQuery.length
                                                            )
                                                        }
                                                    },
                                                    color = DarkGreenLightText,
                                                    fontSize = 14.sp,
                                                    modifier = Modifier.weight(1f)
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

    // Category Scope Selection Modal (Image #2)
    if (showCategoryModal) {
        AlertDialog(
            onDismissRequest = { showCategoryModal = false },
            title = {
                Text(
                    LanguageManager.getString("select_categories"),
                    color = EmeraldTeal,
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp
                )
            },
            text = {
                Column {
                    allCategories.forEach { cat ->
                        val isChecked = selectedCategories.contains(cat)
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    selectedCategories = if (isChecked) {
                                        selectedCategories - cat
                                    } else {
                                        selectedCategories + cat
                                    }
                                }
                                .padding(vertical = 4.dp)
                        ) {
                            Text(
                                text = cat,
                                color = DarkGreenLightText,
                                fontSize = 15.sp,
                                modifier = Modifier.weight(1f)
                            )
                            Checkbox(
                                checked = isChecked,
                                onCheckedChange = { checked ->
                                    selectedCategories = if (checked) {
                                        selectedCategories + cat
                                    } else {
                                        selectedCategories - cat
                                    }
                                },
                                colors = CheckboxDefaults.colors(checkedColor = EmeraldTeal)
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showCategoryModal = false }) {
                    Text(LanguageManager.getString("ok"), color = EmeraldTeal, fontWeight = FontWeight.Bold)
                }
            },
            containerColor = DarkGreenSurface
        )
    }

    // Specific Book Selection Modal
    if (showBookModal) {
        AlertDialog(
            onDismissRequest = { showBookModal = false },
            title = {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "Select Specific Books",
                        color = EmeraldGold,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp
                    )
                    TextButton(onClick = {
                        selectedBookIds = if (selectedBookIds.size == installedBookMap.size) emptySet() else installedBookMap.keys.toSet()
                    }) {
                        Text(
                            if (selectedBookIds.size == installedBookMap.size) "Deselect All" else "Select All",
                            color = EmeraldTeal,
                            fontSize = 13.sp
                        )
                    }
                }
            },
            text = {
                Column {
                    OutlinedTextField(
                        value = bookSearchFilter,
                        onValueChange = { bookSearchFilter = it },
                        placeholder = { Text("Filter books...", color = DarkGreenSubText) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = DarkGreenSurface,
                            unfocusedContainerColor = DarkGreenSurface,
                            focusedBorderColor = EmeraldTeal,
                            unfocusedBorderColor = DarkGreenBorder,
                            focusedTextColor = DarkGreenLightText,
                            unfocusedTextColor = DarkGreenLightText
                        )
                    )
                    LazyColumn(modifier = Modifier.height(260.dp)) {
                        val filteredBooks = installedBookMap.entries.filter {
                            bookSearchFilter.isBlank() || it.value.contains(bookSearchFilter, ignoreCase = true)
                        }
                        items(filteredBooks) { (bId, bTitle) ->
                            val isChecked = selectedBookIds.contains(bId)
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        selectedBookIds = if (isChecked) selectedBookIds - bId else selectedBookIds + bId
                                    }
                                    .padding(vertical = 4.dp)
                            ) {
                                Checkbox(
                                    checked = isChecked,
                                    onCheckedChange = {
                                        selectedBookIds = if (it) selectedBookIds + bId else selectedBookIds - bId
                                    },
                                    colors = CheckboxDefaults.colors(checkedColor = EmeraldGold)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(text = bTitle, color = DarkGreenLightText, fontSize = 14.sp)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showBookModal = false }) {
                    Text(LanguageManager.getString("ok"), color = EmeraldTeal, fontWeight = FontWeight.Bold)
                }
            },
            containerColor = DarkGreenTopBar
        )
    }
}
