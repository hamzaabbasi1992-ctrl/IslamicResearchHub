package com.islamicresearchhub.companion.ui.authors

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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.People
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.ui.theme.DarkGreenBorder
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubtleText
import com.islamicresearchhub.companion.ui.theme.DarkGreenTopBar
import com.islamicresearchhub.companion.ui.theme.EmeraldGold
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal
import com.islamicresearchhub.companion.ui.theme.Teal3DBorder
import com.islamicresearchhub.companion.ui.theme.Teal3DGradEnd
import com.islamicresearchhub.companion.ui.theme.Teal3DGradStart

import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

data class AuthorInfo(
    val name: String,
    val titleOrLocation: String,
    val bookCount: Int,
    val initial: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuthorsScreen(onAuthorClick: (authorName: String) -> Unit) {
    val context = LocalContext.current
    var authors by remember {
        mutableStateOf<List<AuthorInfo>>(
            listOf(
                AuthorInfo("الإمام البخاري", "محدث / المكس", 42, "ب"),
                AuthorInfo("الإمام مسلم", "محدث / نيسابور", 28, "م"),
                AuthorInfo("الإمام أبو داود", "محدث / سجستان", 35, "د"),
                AuthorInfo("الإمام الترمذي", "محدث / ترمذ", 31, "ت"),
                AuthorInfo("الإمام النسائي", "محدث / نسا", 29, "ن"),
                AuthorInfo("الإمام ابن ماجه", "محدث / قزوين", 24, "م"),
                AuthorInfo("الإمام مالك بن أنس", "فقيه / المدينة المنورة", 38, "م"),
                AuthorInfo("الحافظ ابن كثير", "مفسر / دمشق", 45, "ك"),
                AuthorInfo("الإمام الغزالي", "عالم / طوس", 50, "غ"),
                AuthorInfo("الإمام ابن قيم الجوزية", "محدث / دمشق", 62, "ق"),
                AuthorInfo("الإمام النووي", "فقيه / نوى", 48, "ن"),
                AuthorInfo("الشيخ صفي الرحمن المباركفوري", "مؤرخ / الهند", 18, "م"),
                AuthorInfo("مفتی محمد شفیع رحمہ اللہ", "مفسر / پاکستان", 25, "ش"),
                AuthorInfo("مولانا محمد تقی عثمانی", "فقيه / پاکستان", 55, "ع"),
            )
        )
    }

    LaunchedEffect(Unit) {
        withContext(Dispatchers.IO) {
            try {
                val db = CatalogDatabase.openExisting(context)
                val dbAuthors = db.catalogDao().listAuthors()
                if (dbAuthors.isNotEmpty()) {
                    authors = dbAuthors.take(120).map { a ->
                        val cleanName = a.authorName.trim()
                        val initialChar = if (cleanName.isNotEmpty()) cleanName.take(1) else "A"
                        AuthorInfo(
                            name = cleanName,
                            titleOrLocation = "تصانيف و کتب",
                            bookCount = a.bookCount,
                            initial = initialChar
                        )
                    }
                }
            } catch (e: Exception) {
                // Keep default Islamic scholars list on fallback
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.People,
                            contentDescription = null,
                            tint = EmeraldTeal,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text("Authors", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = DarkGreenLightText)
                            Text("${authors.size} Renowned Scholars", fontSize = 12.sp, color = DarkGreenSubText)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        LazyVerticalGrid(
            columns = GridCells.Fixed(3),
            contentPadding = PaddingValues(
                top = padding.calculateTopPadding() + 12.dp,
                start = 12.dp, end = 12.dp, bottom = 24.dp,
            ),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            items(authors, key = { it.name }) { author ->
                AuthorGridItem(author = author, onClick = { onAuthorClick(author.name) })
            }
        }
    }
}

@Composable
private fun AuthorGridItem(author: AuthorInfo, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Circular Avatar with 3D Emerald Ring Border
        Box(
            modifier = Modifier
                .size(76.dp)
                .clip(CircleShape)
                .background(
                    brush = Brush.verticalGradient(
                        colors = listOf(Teal3DGradStart, Teal3DGradEnd)
                    )
                )
                .border(width = 2.5.dp, color = Teal3DBorder, shape = CircleShape)
                .padding(4.dp),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(CircleShape)
                    .background(DarkGreenTopBar),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = author.initial,
                    fontWeight = FontWeight.ExtraBold,
                    fontSize = 26.sp,
                    color = EmeraldGold,
                )
            }
        }

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = author.name,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
            color = DarkGreenLightText,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            lineHeight = 15.sp,
        )

        Spacer(modifier = Modifier.height(2.dp))

        Text(
            text = author.titleOrLocation,
            fontSize = 10.sp,
            color = DarkGreenSubtleText,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
