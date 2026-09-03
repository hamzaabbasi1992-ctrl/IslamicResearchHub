package com.islamicresearchhub.companion.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val AppColorScheme = darkColorScheme(
    primary = EmeraldTeal,
    onPrimary = DarkGreenLightText,
    primaryContainer = EmeraldTealContainer,
    onPrimaryContainer = DarkGreenLightText,
    secondary = EmeraldGold,
    onSecondary = DarkGreenBackground,
    tertiary = DarkGreenSubText,
    onTertiary = DarkGreenBackground,
    background = DarkGreenBackground,
    onBackground = DarkGreenLightText,
    surface = DarkGreenSurface,
    onSurface = DarkGreenLightText,
    surfaceVariant = DarkGreenSurfaceVariant,
    onSurfaceVariant = DarkGreenSubText,
    outline = DarkGreenBorder,
    error = DarkGreenError,
    onError = DarkGreenLightText,
)

/**
 * Islamic Research Hub Dark Greenish Theme
 */
@Composable
fun IslamicResearchHubTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AppColorScheme,
        typography = AppTypography,
        content = content,
    )
}
