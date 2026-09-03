package com.islamicresearchhub.companion.ui.hadith

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.ui.quran.QuranQuickActionButton
import com.islamicresearchhub.companion.ui.theme.*

data class HadithBookItem(
    val id: Int,
    val titleEnglish: String,
    val titleUrdu: String,
    val count: Int
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HadithScreen(
    onOpenBook: (bookId: Int) -> Unit,
    onResumeReading: () -> Unit
) {
    var searchQuery by remember { mutableStateOf("") }

    val hadithBooks = remember {
        listOf(
            HadithBookItem(1, "Sahih Bukhari", "صحيح بخارى", 7563),
            HadithBookItem(2, "Sahih Muslim", "صحيح مسلم", 7563),
            HadithBookItem(3, "Abu Dawood", "سنن ابوداؤد", 5274),
            HadithBookItem(4, "Sunan Nasai", "سنن نسائى", 5761),
            HadithBookItem(5, "Jame' Tirmidhi", "جامع ترمذى", 3956),
            HadithBookItem(6, "Ibn-e-Majah", "سنن ابن ماجه", 4341),
            HadithBookItem(7, "Mishkaat", "مشكوٰة المصابيح", 6294),
            HadithBookItem(8, "Muatta Imam Malik", "مؤطا امام مالك", 1740)
        )
    }

    val filteredBooks = hadithBooks.filter {
        searchQuery.isBlank() ||
                it.titleEnglish.contains(searchQuery, ignoreCase = true) ||
                it.titleUrdu.contains(searchQuery)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Hadith", color = DarkGreenLightText, fontWeight = FontWeight.Bold) },
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
                // Top Quick Actions Panel (Image #5)
                Surface(
                    color = DarkGreenSurface,
                    modifier = Modifier.fillMaxWidth().padding(8.dp),
                    shape = RoundedCornerShape(12.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, DarkGreenBorder)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(14.dp),
                        horizontalArrangement = Arrangement.SpaceAround
                    ) {
                        QuranQuickActionButton(Icons.Default.PinDrop, "Find Hadith")
                        QuranQuickActionButton(Icons.Default.Search, "Search")
                        QuranQuickActionButton(Icons.Default.Bookmark, "Bookmarks")
                        QuranQuickActionButton(Icons.Default.EditNote, "Notes")
                    }
                }

                // Search Filter Input Box
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    placeholder = { Text("Filter Book List by Number or Name", color = DarkGreenSubText, fontSize = 14.sp) },
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

                // Hadith Books List
                LazyColumn(
                    contentPadding = PaddingValues(start = 12.dp, end = 12.dp, bottom = 80.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    itemsIndexed(filteredBooks) { index, item ->
                        Surface(
                            color = DarkGreenSurface,
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onOpenBook(item.id) },
                            border = androidx.compose.foundation.BorderStroke(1.dp, DarkGreenBorder)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "${index + 1}",
                                    color = EmeraldTeal,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 18.sp,
                                    modifier = Modifier.width(36.dp)
                                )
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = item.titleEnglish,
                                        color = DarkGreenLightText,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 16.sp
                                    )
                                    Text(
                                        text = "Ahadith: ${item.count}",
                                        color = DarkGreenSubText,
                                        fontSize = 12.sp
                                    )
                                }
                                Text(
                                    text = item.titleUrdu,
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

            // Floating Action Chip: Resume Hadith Reading
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
                        text = "Resume Hadith Reading",
                        color = EmeraldTeal,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }
        }
    }
}
