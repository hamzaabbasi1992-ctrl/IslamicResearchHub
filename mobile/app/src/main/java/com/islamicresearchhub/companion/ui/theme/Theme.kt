package com.islamicresearchhub.companion.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val AppColorScheme = darkColorScheme(
    primary = EmeraldTeal,
    onPrimary = EmeraldLightText,
    primaryContainer = EmeraldTealContainer,
    onPrimaryContainer = EmeraldLightText,
    secondary = EmeraldGold,
    onSecondary = EmeraldDarkBackground,
    tertiary = EmeraldSkyBlue,
    onTertiary = EmeraldDarkBackground,
    background = EmeraldDarkBackground,
    onBackground = EmeraldLightText,
    surface = EmeraldDarkSurface,
    onSurface = EmeraldLightText,
    surfaceVariant = EmeraldDarkSurfaceVariant,
    onSurfaceVariant = EmeraldSubText,
    outline = EmeraldDarkSurfaceVariant,
    error = EmeraldError,
    onError = EmeraldLightText,
)

/**
 * The app's one theme - a single dark emerald/gold scheme (no light
 * variant yet, matching every screen's real usage so far) so every
 * screen that reads MaterialTheme.colorScheme gets the same look,
 * instead of each screen hardcoding its own hex values.
 */
@Composable
fun IslamicResearchHubTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AppColorScheme,
        typography = AppTypography,
        content = content,
    )
}
