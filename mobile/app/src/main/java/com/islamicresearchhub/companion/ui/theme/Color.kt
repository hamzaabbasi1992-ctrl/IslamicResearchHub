package com.islamicresearchhub.companion.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Three High-Contrast, Crystal-Clear Color Palettes:
 * 1. Dark Green (Islamic Emerald Night)
 * 2. Off White (Warm Cream Paper)
 * 3. Sunny (Golden Amber Warmth)
 */
enum class AppThemeMode(val urduName: String) {
    DARK_GREEN("سبز ڈارک"),
    OFF_WHITE("آف وائٹ"),
    SUNNY("سنہری دھوپ")
}

data class WaqiatThemeColors(
    val background: Color,
    val surface: Color,
    val surfaceVariant: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val accentGold: Color,
    val accentTeal: Color,
    val border: Color,
    val highlightBg: Color,
    val highlightText: Color,
    val searchBarBg: Color
)

val DarkGreenPalette = WaqiatThemeColors(
    background = Color(0xFF031612),
    surface = Color(0xFF082721),
    surfaceVariant = Color(0xFF0F3B32),
    textPrimary = Color(0xFFFFFFFF),       // Pure crisp white for 100% legibility
    textSecondary = Color(0xFF86EFAC),     // Crisp Light Mint
    accentGold = Color(0xFFFBBF24),        // Glowing Amber Gold
    accentTeal = Color(0xFF34D399),        // Radiant Emerald Teal
    border = Color(0xFF144D42),
    highlightBg = Color(0xFFFDE047),       // Radiant Yellow
    highlightText = Color(0xFF000000),     // Jet Black Bold
    searchBarBg = Color(0xFF06201B)
)

val OffWhitePalette = WaqiatThemeColors(
    background = Color(0xFFF5F2EB),       // Warm Soft Paper
    surface = Color(0xFFFFFFFF),          // Pure White Card
    surfaceVariant = Color(0xFFEBE6DC),
    textPrimary = Color(0xFF111827),      // Deep Charcoal Black (Maximum Contrast)
    textSecondary = Color(0xFF4B5563),    // Slate Grey
    accentGold = Color(0xFFB45309),       // Deep Ochre Gold
    accentTeal = Color(0xFF047857),       // Deep Emerald Green
    border = Color(0xFFD1D5DB),
    highlightBg = Color(0xFFFEF08A),      // Soft Highlighter Yellow
    highlightText = Color(0xFF1E1B4B),
    searchBarBg = Color(0xFFEFECE4)
)

val SunnyPalette = WaqiatThemeColors(
    background = Color(0xFFFFFBEB),       // Warm Amber Sunshine
    surface = Color(0xFFFEF3C7),          // Soft Golden Linen Card
    surfaceVariant = Color(0xFFFDE68A),
    textPrimary = Color(0xFF1C1917),      // Deep Warm Espresso Black
    textSecondary = Color(0xFF78350F),    // Warm Amber Brown
    accentGold = Color(0xFFD97706),       // Amber Gold
    accentTeal = Color(0xFF059669),       // Forest Teal
    border = Color(0xFFFCD34D),
    highlightBg = Color(0xFFFDE047),      // Sunshine Yellow
    highlightText = Color(0xFF000000),
    searchBarBg = Color(0xFFFEF08A)
)

fun getThemePalette(mode: AppThemeMode): WaqiatThemeColors {
    return when (mode) {
        AppThemeMode.DARK_GREEN -> DarkGreenPalette
        AppThemeMode.OFF_WHITE -> OffWhitePalette
        AppThemeMode.SUNNY -> SunnyPalette
    }
}

// Legacy Default Fallbacks
val DarkGreenBackground = DarkGreenPalette.background
val DarkGreenSurface = DarkGreenPalette.surface
val DarkGreenSurfaceVariant = DarkGreenPalette.surfaceVariant
val DarkGreenTopBar = Color(0xFF072822)
val DarkGreenBottomNav = Color(0xFF06221E)
val EmeraldTeal = DarkGreenPalette.accentTeal
val EmeraldTealContainer = Color(0xFF064E3B)
val Teal3DGradStart = Color(0xFF0F5A4D)
val Teal3DGradEnd = Color(0xFF05312B)
val Teal3DBorder = Color(0xFF1BE0A0)
val Teal3DShadow = Color(0xFF021714)
val EmeraldGold = DarkGreenPalette.accentGold
val EmeraldGoldContainer = Color(0xFF78350F)
val Gold3DBorder = Color(0xFFFBBF24)
val DarkGreenLightText = DarkGreenPalette.textPrimary
val DarkGreenSubText = DarkGreenPalette.textSecondary
val DarkGreenSubtleText = Color(0xFF5EEAD4)
val DarkGreenBorder = DarkGreenPalette.border
val DarkGreenError = Color(0xFFEF4444)
val DarkGreenErrorContainer = Color(0xFF7F1D1D)
