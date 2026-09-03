package com.islamicresearchhub.companion.ui.quran

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.ui.common.LanguageManager
import com.islamicresearchhub.companion.ui.theme.*

data class SurahItem(
    val number: Int,
    val nameEnglish: String,
    val nameArabic: String,
    val type: String, // "Meccan" or "Medinan"
    val versesCount: Int
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuranScreen(
    onOpenSurah: (surahNumber: Int) -> Unit,
    onResumeReading: () -> Unit
) {
    var searchQuery by remember { mutableStateOf("") }
    var activeTab by remember { mutableStateOf("Surah") }

    val surahList = remember {
        listOf(
            SurahItem(1, "Al-Faatiha", "الفاتحة", "Meccan", 7),
            SurahItem(2, "Al-Baqara", "البقرة", "Medinan", 286),
            SurahItem(3, "Aal-i-Imraan", "آل عمران", "Medinan", 200),
            SurahItem(4, "An-Nisaa", "النساء", "Medinan", 176),
            SurahItem(5, "Al-Maaida", "المائدة", "Medinan", 120),
            SurahItem(6, "Al-An'aam", "الأنعام", "Meccan", 165),
            SurahItem(7, "Al-A'raaf", "الأعراف", "Meccan", 206),
            SurahItem(8, "Al-Anfaal", "الأنفال", "Medinan", 75),
            SurahItem(9, "At-Tawba", "التوبة", "Medinan", 129),
            SurahItem(10, "Yunus", "يونس", "Meccan", 109),
            SurahItem(11, "Hud", "هود", "Meccan", 123),
            SurahItem(12, "Yusuf", "يوسف", "Meccan", 111),
            SurahItem(13, "Ar-Ra'd", "الرعد", "Medinan", 43),
            SurahItem(14, "Ibrahim", "إبراهيم", "Meccan", 52),
            SurahItem(15, "Al-Hijr", "الحجر", "Meccan", 99),
            SurahItem(16, "An-Nahl", "النحل", "Meccan", 128),
            SurahItem(17, "Al-Israa", "الإسراء", "Meccan", 111),
            SurahItem(18, "Al-Kahf", "الكهف", "Meccan", 110)
        )
    }

    val filteredSurahs = surahList.filter {
        searchQuery.isBlank() ||
                it.number.toString() == searchQuery.trim() ||
                it.nameEnglish.contains(searchQuery, ignoreCase = true) ||
                it.nameArabic.contains(searchQuery)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Quran", color = DarkGreenLightText, fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar)
            )
        },
        containerColor = DarkGreenBackground
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Column(modifier = Modifier.fillMaxSize()) {
                // Top Quick Actions Panel (Image #4)
                Surface(
                    color = DarkGreenSurface,
                    modifier = Modifier.fillMaxWidth().padding(8.dp),
                    shape = RoundedCornerShape(12.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, DarkGreenBorder)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceAround
                        ) {
                            QuranQuickActionButton(Icons.Default.PinDrop, "Find Ayah")
                            QuranQuickActionButton(Icons.Default.Search, "Search")
                            QuranQuickActionButton(Icons.Default.Bookmark, "Bookmarks")
                            QuranQuickActionButton(Icons.Default.EditNote, "Notes")
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceAround
                        ) {
                            QuranQuickActionButton(Icons.Default.MenuBook, "Surah Qirat")
                            QuranQuickActionButton(Icons.Default.Book, "Parah")
                            QuranQuickActionButton(Icons.Default.BookmarkBorder, "Ruku")
                            QuranQuickActionButton(Icons.Default.Headphones, "Audio")
                        }
                    }
                }

                // Search Filter Input Box
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    placeholder = { Text("Filter Surah List by Number or Name", color = DarkGreenSubText, fontSize = 14.sp) },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = EmeraldTeal) },
                    singleLine = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = DarkGreenSurface,
                        unfocusedContainerColor = DarkGreenSurface,
                        focusedBorderColor = EmeraldTeal,
                        unfocusedBorderColor = DarkGreenBorder,
                        focusedTextColor = DarkGreenLightText,
                        unfocusedTextColor = DarkGreenLightText
                    ),
                    shape = RoundedCornerShape(10.dp)
                )

                // Surah Rows List
                LazyColumn(
                    contentPadding = PaddingValues(start = 12.dp, end = 12.dp, bottom = 80.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    itemsIndexed(filteredSurahs) { _, item ->
                        Surface(
                            color = DarkGreenSurface,
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onOpenSurah(item.number) },
                            border = androidx.compose.foundation.BorderStroke(1.dp, DarkGreenBorder)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "${item.number}",
                                    color = EmeraldTeal,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 18.sp,
                                    modifier = Modifier.width(36.dp)
                                )
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = item.nameEnglish,
                                        color = DarkGreenLightText,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 16.sp
                                    )
                                    Text(
                                        text = "${item.type} - ${item.versesCount} Verses",
                                        color = DarkGreenSubText,
                                        fontSize = 12.sp
                                    )
                                }
                                Text(
                                    text = item.nameArabic,
                                    color = EmeraldGold,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 20.sp
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Icon(
                                    Icons.Default.PlayCircleOutline,
                                    contentDescription = "Play",
                                    tint = EmeraldTeal,
                                    modifier = Modifier.size(24.dp)
                                )
                            }
                        }
                    }
                }
            }

            // Floating Action Chip: Resume Quran Reading
            Surface(
                color = DarkGreenSurface,
                shape = RoundedCornerShape(24.dp),
                shadowElevation = 6.dp,
                border = androidx.compose.foundation.BorderStroke(1.dp, EmeraldTeal),
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 16.dp)
                    .clickable { onResumeReading() }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.History, contentDescription = null, tint = EmeraldTeal)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Resume Quran Reading",
                        color = EmeraldTeal,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }
        }
    }
}

@Composable
fun QuranQuickActionButton(icon: ImageVector, label: String) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.width(70.dp)
    ) {
        Icon(icon, contentDescription = label, tint = EmeraldGold, modifier = Modifier.size(26.dp))
        Spacer(modifier = Modifier.height(4.dp))
        Text(label, color = DarkGreenLightText, fontSize = 11.sp)
    }
}
