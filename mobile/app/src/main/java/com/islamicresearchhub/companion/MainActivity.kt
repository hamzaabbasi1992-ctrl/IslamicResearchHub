package com.islamicresearchhub.companion

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Category
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.People
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Mosque
import androidx.compose.material.icons.filled.SelfImprovement
import com.islamicresearchhub.companion.ui.authors.AuthorsScreen
import com.islamicresearchhub.companion.ui.azkaar.AzkaarScreen
import com.islamicresearchhub.companion.ui.bookdetail.BookDetailScreen
import com.islamicresearchhub.companion.ui.catalog.CatalogListScreen
import com.islamicresearchhub.companion.ui.categories.CategoriesScreen
import com.islamicresearchhub.companion.ui.categories.CategoryBooksScreen
import com.islamicresearchhub.companion.ui.common.LanguageManager
import com.islamicresearchhub.companion.ui.common.ProvideLanguageLayout
import com.islamicresearchhub.companion.ui.downloads.DownloadsScreen
import com.islamicresearchhub.companion.ui.hadith.HadithScreen
import com.islamicresearchhub.companion.ui.home.HomeScreen
import com.islamicresearchhub.companion.ui.quran.QuranScreen
import com.islamicresearchhub.companion.ui.reader.BookReaderScreen
import com.islamicresearchhub.companion.ui.reader.ChapterListScreen
import com.islamicresearchhub.companion.ui.search.AdvancedSearchScreen
import com.islamicresearchhub.companion.ui.seerah.SeerahScreen
import com.islamicresearchhub.companion.ui.theme.DarkGreenBottomNav
import com.islamicresearchhub.companion.ui.theme.DarkGreenSubText
import com.islamicresearchhub.companion.ui.theme.EmeraldTeal
import com.islamicresearchhub.companion.ui.theme.EmeraldTealContainer
import com.islamicresearchhub.companion.ui.theme.IslamicResearchHubTheme

import com.islamicresearchhub.companion.ui.waqiat.WaqiatScreen

private data class TopLevelDestination(val route: String, val labelKey: String, val icon: @Composable () -> Unit)

private val TOP_LEVEL_DESTINATIONS = listOf(
    TopLevelDestination("azkaar", "azkaar") { Icon(Icons.Default.SelfImprovement, contentDescription = "Azkaar") },
    TopLevelDestination("hadith", "hadith") { Icon(Icons.Default.AutoAwesome, contentDescription = "Hadith") },
    TopLevelDestination("home", "home") { Icon(Icons.Default.Home, contentDescription = "Home") },
    TopLevelDestination("waqiat", "waqiat") { Icon(Icons.Default.AutoAwesome, contentDescription = "Waqiat") },
    TopLevelDestination("quran", "quran") { Icon(Icons.Default.MenuBook, contentDescription = "Quran") },
    TopLevelDestination("seerah", "seerah") { Icon(Icons.Default.Mosque, contentDescription = "Seerah") },
)

/**
 * Maktaba-Style Companion App Activity with 5 Top-Level Tabs & Multi-Language Support
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        LanguageManager.init(this)
        setContent {
            var languageRecomposeKey by remember { mutableStateOf(0) }
            
            IslamicResearchHubTheme {
                ProvideLanguageLayout {
                    val navController = rememberNavController()
                    val backStackEntry by navController.currentBackStackEntryAsState()
                    val currentRoute = backStackEntry?.destination?.route
                    val showBottomBar = TOP_LEVEL_DESTINATIONS.any { it.route == currentRoute }

                    Scaffold(
                        bottomBar = {
                            if (showBottomBar) {
                                AppBottomNavigationBar(navController, currentRoute)
                            }
                        },
                    ) { padding ->
                        NavHost(
                            navController = navController,
                            startDestination = "home",
                            modifier = Modifier.padding(bottom = padding.calculateBottomPadding()),
                        ) {
                            composable("home") {
                                HomeScreen(
                                    onBookClick = { bookId, page ->
                                        navController.navigate("book/$bookId/reader?page=$page")
                                    },
                                    onNavigateToAdvancedSearch = {
                                        navController.navigate("advanced_search")
                                    },
                                    onNavigateToDownloads = {
                                        navController.navigate("downloads")
                                    },
                                    onNavigateToLibrary = {
                                        navController.navigate("catalog")
                                    },
                                    onNavigateToWaqiat = {
                                        navController.navigate("waqiat")
                                    },
                                    onLanguageChanged = {
                                        languageRecomposeKey++
                                    }
                                )
                            }
                            composable("azkaar") {
                                AzkaarScreen(
                                    onOpenCategory = { _ -> navController.navigate("advanced_search") },
                                    onResumeReading = { navController.navigate("catalog") }
                                )
                            }
                            composable("hadith") {
                                HadithScreen(
                                    onOpenBook = { _ -> navController.navigate("advanced_search") },
                                    onResumeReading = { navController.navigate("catalog") }
                                )
                            }
                            composable("waqiat") {
                                WaqiatScreen(
                                    onOpenBookPage = { bookId, pageNo ->
                                        navController.navigate("book/$bookId/reader?page=$pageNo")
                                    }
                                )
                            }
                            composable("quran") {
                                QuranScreen(
                                    onOpenSurah = { _ -> navController.navigate("advanced_search") },
                                    onResumeReading = { navController.navigate("catalog") }
                                )
                            }
                            composable("seerah") {
                                SeerahScreen(
                                    onOpenBook = { _ -> navController.navigate("advanced_search") },
                                    onResumeReading = { navController.navigate("catalog") }
                                )
                            }
                            composable("advanced_search") {
                                AdvancedSearchScreen(
                                    onBackClick = { navController.popBackStack() },
                                    onOpenPage = { bookId, pageNo ->
                                        navController.navigate("book/$bookId/reader?page=$pageNo")
                                    }
                                )
                            }
                            composable("catalog") {
                                CatalogListScreen(onBookClick = { bookId ->
                                    navController.navigate("book/$bookId")
                                })
                            }
                            composable("categories") {
                                CategoriesScreen(onCategoryClick = { mjcn, name ->
                                    navController.navigate("category/$mjcn/${Uri.encode(name)}")
                                })
                            }
                            composable("authors") {
                                AuthorsScreen(onAuthorClick = { authorName ->
                                    navController.navigate("catalog")
                                })
                            }
                            composable("downloads") {
                                DownloadsScreen(onBookClick = { bookId ->
                                    navController.navigate("book/$bookId")
                                })
                            }
                            composable(
                                "category/{mjcn}/{name}",
                                arguments = listOf(
                                    navArgument("mjcn") { type = NavType.IntType },
                                    navArgument("name") { type = NavType.StringType },
                                ),
                            ) { backStack ->
                                val mjcn = backStack.arguments?.getInt("mjcn") ?: return@composable
                                val name = backStack.arguments?.getString("name") ?: ""
                                CategoryBooksScreen(
                                    mjcn = mjcn,
                                    categoryName = Uri.decode(name),
                                    onBookClick = { navController.navigate("book/$it") },
                                )
                            }
                            composable(
                                "book/{bookId}",
                                arguments = listOf(navArgument("bookId") { type = NavType.IntType }),
                            ) { backStackEntry ->
                                val bookId = backStackEntry.arguments?.getInt("bookId") ?: return@composable
                                BookDetailScreen(
                                    bookId = bookId,
                                    onReadClick = { navController.navigate("book/$it/reader") },
                                    onChaptersClick = { navController.navigate("book/$it/chapters") },
                                )
                            }
                            composable(
                                "book/{bookId}/chapters",
                                arguments = listOf(navArgument("bookId") { type = NavType.IntType }),
                            ) { backStackEntry ->
                                val bookId = backStackEntry.arguments?.getInt("bookId") ?: return@composable
                                ChapterListScreen(
                                    bookId = bookId,
                                    onChapterClick = { pageNo ->
                                        navController.navigate("book/$bookId/reader?page=$pageNo")
                                    },
                                )
                            }
                            composable(
                                "book/{bookId}/reader?page={page}",
                                arguments = listOf(
                                    navArgument("bookId") { type = NavType.IntType },
                                    navArgument("page") {
                                        type = NavType.IntType
                                        defaultValue = -1
                                    },
                                ),
                            ) { backStackEntry ->
                                val bookId = backStackEntry.arguments?.getInt("bookId") ?: return@composable
                                val page = backStackEntry.arguments?.getInt("page") ?: -1
                                BookReaderScreen(bookId = bookId, startPageNo = if (page >= 0) page else null)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AppBottomNavigationBar(navController: NavHostController, currentRoute: String?) {
    NavigationBar(
        containerColor = DarkGreenBottomNav,
        tonalElevation = 12.dp,
    ) {
        TOP_LEVEL_DESTINATIONS.forEach { destination ->
            val isSelected = currentRoute == destination.route
            NavigationBarItem(
                selected = isSelected,
                onClick = {
                    if (currentRoute != destination.route) {
                        navController.navigate(destination.route) {
                            popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                },
                icon = destination.icon,
                label = {
                    Text(
                        LanguageManager.getString(destination.labelKey),
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                    )
                },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = EmeraldTeal,
                    selectedTextColor = EmeraldTeal,
                    indicatorColor = EmeraldTealContainer,
                    unselectedIconColor = DarkGreenSubText,
                    unselectedTextColor = DarkGreenSubText,
                ),
            )
        }
    }
}
