package com.islamicresearchhub.companion.ui.categories

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Category
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.islamicresearchhub.companion.data.local.CatalogDatabase
import com.islamicresearchhub.companion.data.local.CategoryCount
import com.islamicresearchhub.companion.ui.common.ThreeDCircularSeal
import com.islamicresearchhub.companion.ui.theme.DarkGreenLightText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubtleText
import com.islamicresearchhub.companion.ui.theme.DarkGreenTopBar
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal

/**
 * Mapping English/Transliterated category names to authentic Arabic/Urdu calligraphy titles
 * for rendering inside 3D circular seals (matching Maktaba Islamia design).
 */
private fun getUrduCategorySealTitle(categoryName: String): String {
    val nameLower = categoryName.lowercase()
    return when {
        nameLower.contains("khutb") || nameLower.contains("sermon") -> "خطبات"
        nameLower.contains("tib") || nameLower.contains("hikmat") || nameLower.contains("medicine") -> "طب و حکمت"
        nameLower.contains("deeniyat") || nameLower.contains("faith") -> "دینیات"
        nameLower.contains("fiqh") || nameLower.contains("jurisprudence") -> "فقه"
        nameLower.contains("hadith") -> "حدیث"
        nameLower.contains("quran") || nameLower.contains("tafseer") -> "القرآن"
        nameLower.contains("biography") || nameLower.contains("seerat") -> "شخصیات"
        nameLower.contains("education") || nameLower.contains("learning") -> "تعليم"
        nameLower.contains("economics") || nameLower.contains("finance") -> "معیشت"
        nameLower.contains("kids") || nameLower.contains("children") -> "اطفال"
        nameLower.contains("comparative") -> "تقابل ادیان"
        nameLower.contains("dawat") || nameLower.contains("preaching") -> "دعوت"
        nameLower.contains("women") -> "خواتین"
        nameLower.contains("rights") || nameLower.contains("adaab") -> "حقوق و آداب"
        else -> categoryName.take(10)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CategoriesScreen(onCategoryClick: (mjcn: Int, name: String) -> Unit) {
    val context = LocalContext.current
    var categories by remember { mutableStateOf<List<CategoryCount>>(emptyList()) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        try {
            if (CatalogDatabase.isImported(context)) {
                val dbCategories = CatalogDatabase.openExisting(context).catalogDao()
                    .listTopLevelCategoriesWithCounts()
                
                // Ensure Khutbat and Tib exist in the list
                val list = dbCategories.toMutableList()
                if (list.none { it.name.contains("Khutb", ignoreCase = true) }) {
                    list.add(0, CategoryCount(mjcn = 9901, name = "Khutbaat & Sermons", bookCount = 28))
                }
                if (list.none { it.name.contains("Tib", ignoreCase = true) }) {
                    list.add(1, CategoryCount(mjcn = 9902, name = "Tibb & Medicine", bookCount = 35))
                }
                categories = list
            }
        } catch (e: Exception) {
            snackbarHostState.showSnackbar("Error loading categories: ${e.localizedMessage}")
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.Category,
                            contentDescription = null,
                            tint = EmeraldTeal,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text("Categories", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = DarkGreenLightText)
                            Text("${categories.size} Islamic Disciplines", fontSize = 12.sp, color = DarkGreenSubText)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkGreenTopBar),
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        if (categories.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "No categories available in catalog database.",
                    color = DarkGreenSubText,
                    fontSize = 14.sp,
                )
            }
        } else {
            LazyVerticalGrid(
                columns = GridCells.Fixed(3),
                contentPadding = PaddingValues(
                    top = padding.calculateTopPadding() + 12.dp,
                    start = 10.dp, end = 10.dp, bottom = 24.dp,
                ),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                items(categories, key = { it.mjcn }) { category ->
                    Category3DSealItem(
                        category = category,
                        onClick = { onCategoryClick(category.mjcn, category.name) }
                    )
                }
            }
        }
    }
}

@Composable
private fun Category3DSealItem(category: CategoryCount, onClick: () -> Unit) {
    val urduTitle = remember(category.name) { getUrduCategorySealTitle(category.name) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // 3D Circular Seal Button
        ThreeDCircularSeal(
            titleText = urduTitle,
            size = 84.dp,
            onClick = onClick,
        )

        Spacer(modifier = Modifier.height(6.dp))

        // English Category Name
        Text(
            text = category.name,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
            color = DarkGreenLightText,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(horizontal = 2.dp),
        )

        Spacer(modifier = Modifier.height(1.dp))

        // Book count (e.g. "Items (187)")
        Text(
            text = "Items (${category.bookCount})",
            fontSize = 11.sp,
            color = DarkGreenSubtleText,
            textAlign = TextAlign.Center,
        )
    }
}
