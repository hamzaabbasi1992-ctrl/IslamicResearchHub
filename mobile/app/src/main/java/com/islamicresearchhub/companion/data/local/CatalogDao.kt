package com.islamicresearchhub.companion.data.local

import androidx.room.Dao
import androidx.room.Query

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

    @Query("SELECT * FROM Libraries")
    suspend fun listLibraries(): List<LibraryEntity>
}
