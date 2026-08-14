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
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.islamicresearchhub.companion.ui.bookdetail.BookDetailScreen
import com.islamicresearchhub.companion.ui.categories.CategoriesScreen
import com.islamicresearchhub.companion.ui.categories.CategoryBooksScreen
import com.islamicresearchhub.companion.ui.catalog.CatalogListScreen
import com.islamicresearchhub.companion.ui.downloads.DownloadsScreen
import com.islamicresearchhub.companion.ui.home.HomeScreen
import com.islamicresearchhub.companion.ui.reader.BookReaderScreen
import com.islamicresearchhub.companion.ui.reader.ChapterListScreen
import com.islamicresearchhub.companion.ui.theme.IslamicResearchHubTheme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

private data class TopLevelDestination(val route: String, val label: String, val icon: @Composable () -> Unit)

private val TOP_LEVEL_DESTINATIONS = listOf(
    TopLevelDestination("home", "Home") { Icon(Icons.Default.Home, contentDescription = "Home") },
    TopLevelDestination("catalog", "Library") { Icon(Icons.AutoMirrored.Filled.List, contentDescription = "Library") },
    TopLevelDestination("categories", "Categories") { Icon(Icons.Default.Category, contentDescription = "Categories") },
    TopLevelDestination("downloads", "Downloads") { Icon(Icons.Default.Download, contentDescription = "Downloads") },
)

/**
 * Milestone 3: real bottom-tab navigation (Home / Library / Categories /
 * Downloads) wrapping the four top-level real screens, matching the
 * reference app's structure - the bottom bar hides itself on drill-down
 * screens (book detail, chapters, reader, one category's books), the
 * same show-on-list/hide-on-detail pattern the reference uses.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            IslamicResearchHubTheme {
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
                            HomeScreen(onBookClick = { bookId, page ->
                                navController.navigate("book/$bookId/reader?page=$page")
                            })
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

@Composable
private fun AppBottomNavigationBar(navController: NavHostController, currentRoute: String?) {
    NavigationBar(
        containerColor = MaterialTheme.colorScheme.surface,
        tonalElevation = 8.dp,
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
                        destination.label,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                    )
                },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = MaterialTheme.colorScheme.primary,
                    selectedTextColor = MaterialTheme.colorScheme.primary,
                    indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                    unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                ),
            )
        }
    }
}
