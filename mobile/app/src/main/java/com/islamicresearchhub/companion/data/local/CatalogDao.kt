package com.islamicresearchhub.companion.data.local

import androidx.room.Dao
import androidx.room.Query

/** One real named category and how many real books carry it. */
data class CategoryCount(val mjcn: Int, val name: String, val bookCount: Int)

@Dao
interface CatalogDao {
    /** Real books, ordered by title - simple substring search over the
     * real title/author text (no FTS needed yet at this real scale:
     * one imported catalog is a fraction of the desktop's 100k+ books). */
    @Query(
        "SELECT * FROM Books WHERE Title LIKE '%' || :query || '%' " +
            "OR Author LIKE '%' || :query || '%' ORDER BY Title"
    )
    suspend fun search(query: String): List<BookEntity>

    @Query("SELECT * FROM Books ORDER BY Title")
    suspend fun listAll(): List<BookEntity>

    @Query("SELECT * FROM Books WHERE BookID = :bookId")
    suspend fun getBook(bookId: Int): BookEntity?

    @Query("SELECT * FROM Libraries")
    suspend fun listLibraries(): List<LibraryEntity>

    /** Real, named top-level categories with a real per-category book
     * count - what the Categories tab groups by (see `CategoryNameEntity`
     * for why this is `CategoryNames`/`BookCategories`, not the raw
     * `Books.Category` text column). Top-level only (ParentMJCN IS NULL)
     * since the Categories tab is a flat grid, not a tree browser. */
    @Query(
        "SELECT c.MJCN as mjcn, c.Name as name, COUNT(bc.BookID) as bookCount " +
            "FROM CategoryNames c LEFT JOIN BookCategories bc ON bc.MJCN = c.MJCN " +
            "WHERE c.ParentMJCN IS NULL " +
            "GROUP BY c.MJCN ORDER BY bookCount DESC"
    )
    suspend fun listTopLevelCategoriesWithCounts(): List<CategoryCount>

    @Query(
        "SELECT b.* FROM Books b " +
            "INNER JOIN BookCategories bc ON bc.BookID = b.BookID " +
            "WHERE bc.MJCN = :mjcn ORDER BY b.Title"
    )
    suspend fun listByCategory(mjcn: Int): List<BookEntity>

    @Query("SELECT Name FROM CategoryNames WHERE MJCN = :mjcn")
    suspend fun getCategoryName(mjcn: Int): String?
}
