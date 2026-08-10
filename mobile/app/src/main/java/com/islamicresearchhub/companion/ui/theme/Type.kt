package com.islamicresearchhub.companion.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * Material3's default type scale, with just the weights the app's own
 * screens actually lean on (bold titles, readable long-form page text)
 * nudged - not a full custom font, this app has no branded typeface yet.
 */
val AppTypography = Typography().let { base ->
    base.copy(
        titleLarge = base.titleLarge.copy(fontWeight = FontWeight.Bold),
        titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
        bodyLarge = base.bodyLarge.copy(lineHeight = 28.sp),
    )
}
