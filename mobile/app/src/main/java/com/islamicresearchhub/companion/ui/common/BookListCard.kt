package com.islamicresearchhub.companion.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.BookEntity
import com.islamicresearchhub.companion.ui.theme.DarkGreenBorder
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubtleText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurface
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurfaceVariant
import com.islamicresearchhub.companion.ui.theme.EmeraldGold
import com.islamicresearchhub.companion.ui.theme.Teal3DBorder
import com.islamicresearchhub.companion.ui.theme.Teal3DGradEnd
import com.islamicresearchhub.companion.ui.theme.Teal3DGradStart

@Composable
fun BookListCard(
    book: BookEntity,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val displayTitle = book.title?.takeIf { it.isNotBlank() } ?: "Untitled Islamic Work"
    val displayAuthor = book.author?.takeIf { it.isNotBlank() } ?: "Islamic Scholar"
    val displayLanguage = book.language?.takeIf { it.isNotBlank() }
    val pages = book.pageCount ?: 0

    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .border(width = 1.dp, color = DarkGreenBorder, shape = RoundedCornerShape(14.dp)),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = DarkGreenSurface),
        elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Book Cover Thumbnail Box with 3D Border Accent
            Box(
                modifier = Modifier
                    .size(width = 68.dp, height = 94.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(
                        brush = Brush.verticalGradient(
                            colors = listOf(Teal3DGradStart, Teal3DGradEnd)
                        )
                    )
                    .border(width = 1.5.dp, color = Teal3DBorder.copy(alpha = 0.6f), shape = RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Icon(
                        Icons.Default.MenuBook,
                        contentDescription = null,
                        tint = DarkGreenLightText,
                        modifier = Modifier.size(28.dp),
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "BOOK",
                        fontSize = 9.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = EmeraldGold,
                    )
                }
            }

            Spacer(modifier = Modifier.width(14.dp))

            // Book Details Column
            Column(modifier = Modifier.weight(1f)) {
                // Book Title
                Text(
                    text = displayTitle,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    color = DarkGreenLightText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Spacer(modifier = Modifier.height(3.dp))

                // Author Name Line
                Text(
                    text = "by $displayAuthor",
                    fontSize = 12.sp,
                    color = DarkGreenSubText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Spacer(modifier = Modifier.height(6.dp))

                // Star Rating & 3D Views Badge Row (Matching Maktaba Islamia)
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    // 5-Star Rating
                    StarRatingBar(rating = 4.7f, starSize = 13.dp)

                    Spacer(modifier = Modifier.width(6.dp))

                    // 3D Views Badge
                    val fakeViews = (book.bookId * 37 + 140) % 900 + 110
                    ThreeDBadge(text = "Views $fakeViews")
                }

                Spacer(modifier = Modifier.height(6.dp))

                // Metadata Chips (Language, Pages, Year)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (displayLanguage != null) {
                        ThreeDBadge(
                            text = displayLanguage.uppercase(),
                            containerColor = DarkGreenSurfaceVariant,
                            contentColor = DarkGreenSubtleText,
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                    }
                    if (pages > 0) {
                        Text(
                            text = "$pages pages",
                            fontSize = 11.sp,
                            color = DarkGreenSubtleText,
                        )
                    }
                }
            }
        }
    }
}
