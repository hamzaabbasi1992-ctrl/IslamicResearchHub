package com.islamicresearchhub.companion.ui.seerah

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

data class SeerahBookItem(
    val id: Int,
    val titleUrdu: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SeerahScreen(
    onOpenBook: (bookId: Int) -> Unit,
    onResumeReading: () -> Unit
) {
    var searchQuery by remember { mutableStateOf("") }

    val seerahBooks = remember {
        listOf(
            SeerahBookItem(1, "شمائل نبویہ ﷺ"),
            SeerahBookItem(2, "الرحيق المختوم"),
            SeerahBookItem(3, "سيرت خاتم الانبياء محمد مصطفىٰ ﷺ"),
            SeerahBookItem(4, "حضرت ابو بكر صديقؓ"),
            SeerahBookItem(5, "حضرت عمر بن الخطابؓ"),
            SeerahBookItem(6, "حضرت عثمان بن عفانؓ"),
            SeerahBookItem(7, "حضرت علی بن ابی طالبؓ"),
            SeerahBookItem(8, "حضرت حسن و حسینؓ")
        )
    }

    val filteredBooks = seerahBooks.filter {
        searchQuery.isBlank() || it.titleUrdu.contains(searchQuery)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Seerah", color = DarkGreenLightText, fontWeight = FontWeight.Bold) },
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
                // Top Quick Actions Panel (Image #2)
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
                        QuranQuickActionButton(Icons.Default.PinDrop, "Find Page")
                        QuranQuickActionButton(Icons.Default.Search, "Search")
                        QuranQuickActionButton(Icons.Default.Bookmark, "Bookmarks")
                        QuranQuickActionButton(Icons.Default.Headphones, "Audio")
                    }
                }

                // Search Filter Input Box
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    placeholder = { Text("عنوان کے ذریعے تلاش کریں", color = DarkGreenSubText, fontSize = 14.sp) },
                    trailingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = EmeraldTeal) },
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

                // Seerah Books List
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
                                    .padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = item.titleUrdu,
                                    color = DarkGreenLightText,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 18.sp,
                                    modifier = Modifier.weight(1f)
                                )
                                Text(
                                    text = "${index + 1}",
                                    color = EmeraldTeal,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 18.sp
                                )
                            }
                        }
                    }
                }
            }

            // Floating Action Chip: Resume Seerah Reading
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
                        text = "Resume Seerah Reading",
                        color = EmeraldTeal,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }
        }
    }
}
