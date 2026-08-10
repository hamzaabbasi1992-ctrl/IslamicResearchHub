package com.islamicresearchhub.companion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.islamicresearchhub.companion.ui.bookdetail.BookDetailScreen
import com.islamicresearchhub.companion.ui.catalog.CatalogListScreen
import com.islamicresearchhub.companion.ui.reader.BookReaderScreen
import com.islamicresearchhub.companion.ui.reader.ChapterListScreen
import com.islamicresearchhub.companion.ui.theme.IslamicResearchHubTheme

/**
 * Milestone 2 (Phase 18): real navigation between the four real screens
 * - catalog browse (import a real catalog.db), book detail (import a
 * real book_<id>.db to read it offline), chapter list, and the offline
 * reader itself. Every screen's real data comes from local Room over
 * the desktop's exported SQLite files - no network call anywhere.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            IslamicResearchHubTheme {
                val navController = rememberNavController()
                NavHost(navController = navController, startDestination = "catalog") {
                    composable("catalog") {
                        CatalogListScreen(onBookClick = { bookId ->
                            navController.navigate("book/$bookId")
                        })
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
