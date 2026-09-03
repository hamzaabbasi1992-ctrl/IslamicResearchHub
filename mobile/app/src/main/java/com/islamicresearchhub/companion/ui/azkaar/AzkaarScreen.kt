package com.islamicresearchhub.companion.ui.azkaar

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.ui.quran.QuranQuickActionButton
import com.islamicresearchhub.companion.ui.theme.*

data class AzkaarGridItem(
    val id: Int,
    val titleUrdu: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AzkaarScreen(
    onOpenCategory: (categoryId: Int) -> Unit,
    onResumeReading: () -> Unit
) {
    val azkaarItems = remember {
        listOf(
            AzkaarGridItem(1, "صبح کے مسنون اذکار"),
            AzkaarGridItem(2, "شام کے مسنون اذکار"),
            AzkaarGridItem(3, "رات کے مسنون اذکار"),
            AzkaarGridItem(4, "دیگر مسنون اذکار"),
            AzkaarGridItem(5, "روزمرہ کی سنتیں"),
            AzkaarGridItem(6, "روزمرہ کی دعائیں"),
            AzkaarGridItem(7, "اسمائے حسنیٰ"),
            AzkaarGridItem(8, "۱۰۰۰ مسنون اعمال"),
            AzkaarGridItem(9, "درود و سلام"),
            AzkaarGridItem(10, "قرآنی دعائیں"),
            AzkaarGridItem(11, "طہارت کے مسائل"),
            AzkaarGridItem(12, "جنازے کے مسائل")
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Azkaar", color = DarkGreenLightText, fontWeight = FontWeight.Bold) },
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
                // Top Quick Actions Panel (Image #3)
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
                    }
                }

                // 2-Column Grid Options (Image #3)
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = 8.dp, bottom = 80.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(azkaarItems) { item ->
                        Surface(
                            color = DarkGreenSurface,
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(72.dp)
                                .clickable { onOpenCategory(item.id) },
                            border = androidx.compose.foundation.BorderStroke(1.dp, DarkGreenBorder)
                        ) {
                            Box(
                                modifier = Modifier.fillMaxSize().padding(12.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = item.titleUrdu,
                                    color = DarkGreenLightText,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 16.sp,
                                    textAlign = TextAlign.Center
                                )
                            }
                        }
                    }
                }
            }

            // Floating Action Chip: Resume Zikr Reading
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
                        text = "Resume Zikr Reading",
                        color = EmeraldTeal,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }
        }
    }
}
