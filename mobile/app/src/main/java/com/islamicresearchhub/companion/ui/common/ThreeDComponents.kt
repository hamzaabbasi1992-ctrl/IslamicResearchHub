package com.islamicresearchhub.companion.ui.common

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarHalf
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.ui.theme.DarkGreenBorder
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubtleText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSurface
import com.islamicresearchhub.companion.ui.theme.EmeraldGold
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal
import com.islamicresearchhub.companion.ui.theme.Teal3DBorder
import com.islamicresearchhub.companion.ui.theme.Teal3DGradEnd
import com.islamicresearchhub.companion.ui.theme.Teal3DGradStart
import com.islamicresearchhub.companion.ui.theme.Teal3DShadow

/**
 * Custom 3D Circular Seal component matching the Maktaba Islamia category seals.
 * Features double embossed ring border, deep teal radial-like gradient, and bold text inside.
 */
@Composable
fun ThreeDCircularSeal(
    titleText: String,
    modifier: Modifier = Modifier,
    size: Dp = 80.dp,
    onClick: () -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(if (isPressed) 0.94f else 1.0f, label = "sealScale")

    Box(
        modifier = modifier
            .scale(scale)
            .clickable(interactionSource = interactionSource, indication = null, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        // 3D Outer Drop Shadow Circle
        Box(
            modifier = Modifier
                .size(size)
                .offset(y = 3.dp)
                .clip(CircleShape)
                .background(Teal3DShadow.copy(alpha = 0.8f))
        )

        // Main 3D Seal Circle with Embossed Metallic Ring
        Box(
            modifier = Modifier
                .size(size)
                .clip(CircleShape)
                .background(
                    brush = Brush.verticalGradient(
                        colors = listOf(Teal3DGradStart, Teal3DGradEnd)
                    )
                )
                .border(width = 3.dp, color = Teal3DBorder.copy(alpha = 0.7f), shape = CircleShape)
                .border(width = 1.dp, color = Color.White.copy(alpha = 0.3f), shape = CircleShape)
                .padding(6.dp),
            contentAlignment = Alignment.Center,
        ) {
            // Inner Seal Ring
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(CircleShape)
                    .border(width = 1.5.dp, color = Teal3DBorder.copy(alpha = 0.5f), shape = CircleShape)
                    .background(
                        brush = Brush.radialGradient(
                            colors = listOf(
                                Teal3DGradStart.copy(alpha = 0.9f),
                                Teal3DGradEnd
                            )
                        )
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = titleText,
                    color = DarkGreenLightText,
                    fontSize = if (titleText.length > 8) 12.sp else 14.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(horizontal = 4.dp),
                )
            }
        }
    }
}

/**
 * Tactile 3D Elevated Button with gradient top surface and bottom shadow offset.
 */
@Composable
fun ThreeDButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    backgroundColor: Color = EmeraldTeal,
    textColor: Color = DarkGreenLightText,
    icon: (@Composable () -> Unit)? = null,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val offsetY by animateFloatAsState(if (isPressed) 2f else 0f, label = "buttonYOffset")

    Box(
        modifier = modifier
            .clickable(interactionSource = interactionSource, indication = null, onClick = onClick)
    ) {
        // 3D Shadow layer
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(44.dp)
                .offset(y = 3.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(Teal3DShadow.copy(alpha = 0.7f))
        )

        // Top Elevated Button Surface
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .height(44.dp)
                .offset(y = offsetY.dp)
                .clip(RoundedCornerShape(12.dp))
                .border(width = 1.dp, color = Color.White.copy(alpha = 0.2f), shape = RoundedCornerShape(12.dp)),
            color = backgroundColor,
            shape = RoundedCornerShape(12.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        brush = Brush.verticalGradient(
                            colors = listOf(
                                backgroundColor.copy(alpha = 1.0f),
                                backgroundColor.copy(alpha = 0.8f)
                            )
                        )
                    )
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (icon != null) {
                    icon()
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Text(
                    text = text,
                    color = textColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                )
            }
        }
    }
}

/**
 * 5-Star Rating component matching reference book details.
 */
@Composable
fun StarRatingBar(
    rating: Float = 4.5f,
    maxStars: Int = 5,
    starSize: Dp = 14.dp,
    modifier: Modifier = Modifier,
) {
    Row(modifier = modifier, verticalAlignment = Alignment.CenterVertically) {
        for (i in 1..maxStars) {
            val starIcon = when {
                i <= rating -> Icons.Filled.Star
                i - 0.5f <= rating -> Icons.Outlined.StarHalf
                else -> Icons.Outlined.StarOutline
            }
            Icon(
                imageVector = starIcon,
                contentDescription = null,
                tint = EmeraldGold,
                modifier = Modifier.size(starSize)
            )
        }
    }
}

/**
 * 3D Badge Pill component for view counts ("Views 404") or tags.
 */
@Composable
fun ThreeDBadge(
    text: String,
    modifier: Modifier = Modifier,
    containerColor: Color = Teal3DGradStart,
    contentColor: Color = DarkGreenSubText,
) {
    Surface(
        modifier = modifier
            .border(width = 1.dp, color = Teal3DBorder.copy(alpha = 0.4f), shape = RoundedCornerShape(8.dp)),
        shape = RoundedCornerShape(8.dp),
        color = containerColor,
    ) {
        Text(
            text = text,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color = contentColor,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}
