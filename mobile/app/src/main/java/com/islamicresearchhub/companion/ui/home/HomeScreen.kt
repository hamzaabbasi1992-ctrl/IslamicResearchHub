package com.islamicresearchhub.companion.ui.home

import android.widget.Toast
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Feedback
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.AppStateDatabase
import com.islamicresearchhub.companion.data.local.RecentlyOpenedEntity
import com.islamicresearchhub.companion.data.local.bulkImportBookFiles
import com.islamicresearchhub.companion.ui.common.AppLanguage
import com.islamicresearchhub.companion.ui.common.LanguageManager
import com.islamicresearchhub.companion.ui.common.ThreeDBadge
import com.islamicresearchhub.companion.ui.theme.DarkGreenBorder
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurface
import com.islamicresearchhub.companion.ui.theme.DarkGreenTopBar
import com.islamicresearchhub.companion.ui.theme.EmeraldGold
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal
import com.islamicresearchhub.companion.ui.theme.Teal3DBorder
import com.islamicresearchhub.companion.ui.theme.Teal3DGradEnd
import com.islamicresearchhub.companion.ui.theme.Teal3DGradStart
import kotlinx.coroutines.launch

private data class GridActionTile(
    val id: String,
    val titleKey: String,
    val subtitle: String? = null,
    val icon: ImageVector,
    val isSpecial: Boolean = false,
    val action: () -> Unit
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onBookClick: (Int, Int) -> Unit,
    onNavigateToAdvancedSearch: () -> Unit,
    onNavigateToDownloads: () -> Unit,
    onNavigateToLibrary: () -> Unit,
    onNavigateToWaqiat: () -> Unit,
    onLanguageChanged: () -> Unit
) {
    val context = LocalContext.current
    var recent by remember { mutableStateOf<List<RecentlyOpenedEntity>>(emptyList()) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    var showLanguageMenu by remember { mutableStateOf(false) }

    // Launcher for Bulk Importing multiple books at once
    val bulkBookLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                Toast.makeText(context, "${uris.size} کتب امپورٹ ہو رہی ہیں...", Toast.LENGTH_SHORT).show()
                val importedCount = bulkImportBookFiles(context, uris)
                Toast.makeText(context, "کامیابی! $importedCount کتب اکٹھا امپورٹ ہو گئیں!", Toast.LENGTH_LONG).show()
                onNavigateToLibrary()
            } catch (e: Exception) {
                Toast.makeText(context, "امپورٹ میں خرابی: ${e.localizedMessage}", Toast.LENGTH_LONG).show()
            }
        }
    }

    LaunchedEffect(Unit) {
        try {
            recent = AppStateDatabase.get(context).appStateDao().listRecent(limit = 10)
        } catch (e: Exception) {
            snackbarHostState.showSnackbar("Error loading recent: ${e.localizedMessage}")
        }
    }

    val actionTiles = remember(LanguageManager.currentLanguage) {
        listOf(
            GridActionTile("waqiat", "واقعات انسائیکلوپیڈیا", "۲,۸۷۰ واقعات", Icons.Default.Star, isSpecial = true, action = onNavigateToWaqiat),
            GridActionTile("bulk_import", "تمام کتب امپورٹ کریں", "ایک ساتھ کتب منتخب کریں", Icons.Default.FolderOpen, isSpecial = true) {
                bulkBookLauncher.launch(arrayOf("*/*"))
            },
            GridActionTile("search", "advanced_search", null, Icons.Default.Book, action = onNavigateToAdvancedSearch),
            GridActionTile("library", "my_library", null, Icons.AutoMirrored.Filled.MenuBook, action = onNavigateToLibrary),
            GridActionTile("downloads", "downloaded_books", null, Icons.Default.Download, action = onNavigateToDownloads),
            GridActionTile("recent", "recent_reading", null, Icons.Default.History) {
                recent.firstOrNull()?.let { onBookClick(it.bookId, it.lastPageNo) }
                    ?: scope.launch { snackbarHostState.showSnackbar("No recent history yet") }
            },
            GridActionTile("favorites", "favorites", null, Icons.Default.Bookmark) {
                scope.launch { snackbarHostState.showSnackbar("Favorites view active") }
            },
            GridActionTile("ai", "ai_summary", null, Icons.Default.AutoAwesome) {
                scope.launch { snackbarHostState.showSnackbar("AI Research Assistant active") }
            }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            modifier = Modifier
                                .size(38.dp)
                                .border(width = 1.dp, color = Teal3DBorder, shape = RoundedCornerShape(10.dp)),
                            shape = RoundedCornerShape(10.dp),
                            color = Teal3DGradStart,
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.Book, contentDescription = null, tint = EmeraldGold, modifier = Modifier.size(22.dp))
                            }
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                LanguageManager.getString("app_title"),
                                fontWeight = FontWeight.Bold,
                                fontSize = 20.sp,
                                color = EmeraldGold,
                            )
                        }
                    }
                },
                actions = {
                    Box {
                        IconButton(onClick = { showLanguageMenu = true }) {
                            Icon(Icons.Default.Language, contentDescription = "Language", tint = EmeraldGold)
                        }
                        DropdownMenu(
                            expanded = showLanguageMenu,
                            onDismissRequest = { showLanguageMenu = false },
                            modifier = Modifier.background(DarkGreenSurface)
                        ) {
                            AppLanguage.values().forEach { lang ->
                                DropdownMenuItem(
                                    text = {
                                        Text(
                                            text = lang.displayName,
                                            color = if (LanguageManager.currentLanguage == lang) EmeraldGold else DarkGreenLightText,
                                            fontWeight = if (LanguageManager.currentLanguage == lang) FontWeight.Bold else FontWeight.Normal
                                        )
                                    },
                                    onClick = {
                                        LanguageManager.setLanguage(context, lang)
                                        showLanguageMenu = false
                                        onLanguageChanged()
                                    }
                                )
                            }
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar),
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        LazyColumn(
            contentPadding = PaddingValues(
                top = padding.calculateTopPadding() + 8.dp,
                start = 16.dp, end = 16.dp, bottom = 24.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Emblem Banner
            item {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(16.dp))
                        .background(
                            brush = Brush.verticalGradient(
                                colors = listOf(Teal3DGradStart, Teal3DGradEnd)
                            )
                        )
                        .border(width = 1.5.dp, color = Teal3DBorder.copy(alpha = 0.7f), shape = RoundedCornerShape(16.dp))
                        .padding(vertical = 18.dp, horizontal = 16.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "مَكْتَبَةُ شَمْس",
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 28.sp,
                            color = EmeraldGold
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "ISLAMIC RESEARCH HUB COMPANION",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = EmeraldTeal,
                            letterSpacing = 2.sp
                        )
                    }
                }
            }

            // 2-Column Grid Action Cards
            item {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    for (i in actionTiles.indices step 2) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            val tile1 = actionTiles[i]
                            ActionGridCard(
                                tile = tile1,
                                modifier = Modifier.weight(1f)
                            )
                            if (i + 1 < actionTiles.size) {
                                val tile2 = actionTiles[i + 1]
                                ActionGridCard(
                                    tile = tile2,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                }
            }

            // Recent Reading Section Header
            item {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    LanguageManager.getString("recent_reading"),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = EmeraldGold,
                )
            }

            if (recent.isNotEmpty()) {
                items(recent, key = { it.bookId }) { entry ->
                    ContinueReadingCard(entry, onClick = { onBookClick(entry.bookId, entry.lastPageNo) })
                }
            } else {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(containerColor = DarkGreenSurface),
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(
                                Icons.AutoMirrored.Filled.MenuBook,
                                contentDescription = null,
                                tint = DarkGreenSubText,
                                modifier = Modifier.size(32.dp),
                            )
                            Spacer(modifier = Modifier.width(14.dp))
                            Text(
                                "No recent reading history. Select a book from your Library or Categories to begin reading.",
                                fontSize = 13.sp,
                                color = DarkGreenSubText,
                                lineHeight = 18.sp,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ActionGridCard(
    tile: GridActionTile,
    modifier: Modifier = Modifier
) {
    val displayTitle = if (tile.titleKey.startsWith("GridActionTile") || tile.titleKey.contains(" ")) {
        tile.titleKey
    } else {
        LanguageManager.getString(tile.titleKey)
    }

    Card(
        modifier = modifier
            .height(115.dp)
            .clickable(onClick = tile.action)
            .border(
                width = if (tile.isSpecial) 1.5.dp else 1.dp,
                color = if (tile.isSpecial) EmeraldTeal else DarkGreenBorder,
                shape = RoundedCornerShape(14.dp)
            ),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (tile.isSpecial) DarkGreenSurface.copy(alpha = 0.9f) else DarkGreenSurface
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                tile.icon,
                contentDescription = null,
                tint = if (tile.isSpecial) EmeraldTeal else EmeraldGold,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = displayTitle,
                fontSize = 13.5.sp,
                fontWeight = FontWeight.Bold,
                color = if (tile.isSpecial) EmeraldTeal else EmeraldGold,
                maxLines = 1
            )
            tile.subtitle?.let { sub ->
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = sub,
                    fontSize = 10.5.sp,
                    color = DarkGreenSubText,
                    maxLines = 1
                )
            }
        }
    }
}

@Composable
private fun ContinueReadingCard(entry: RecentlyOpenedEntity, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .border(width = 1.dp, color = DarkGreenBorder, shape = RoundedCornerShape(14.dp)),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = DarkGreenSurface),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(
                modifier = Modifier
                    .size(44.dp)
                    .border(width = 1.dp, color = Teal3DBorder, shape = RoundedCornerShape(10.dp)),
                shape = RoundedCornerShape(10.dp),
                color = Teal3DGradStart,
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        Icons.Default.PlayArrow,
                        contentDescription = "Resume",
                        tint = DarkGreenLightText,
                        modifier = Modifier.size(24.dp),
                    )
                }
            }
            Spacer(modifier = Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(entry.title, fontWeight = FontWeight.Bold, fontSize = 15.sp, color = DarkGreenLightText)
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    entry.author?.takeIf { it.isNotBlank() } ?: "Islamic Scholar",
                    fontSize = 12.sp,
                    color = DarkGreenSubText,
                )
                Spacer(modifier = Modifier.height(4.dp))
                ThreeDBadge(
                    text = "Page ${entry.lastPageNo}",
                    containerColor = Teal3DGradStart,
                    contentColor = EmeraldGold,
                )
            }
        }
    }
}
