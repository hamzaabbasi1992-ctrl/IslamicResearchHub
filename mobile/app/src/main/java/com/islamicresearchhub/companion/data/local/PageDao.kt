package com.islamicresearchhub.companion.data.local

import androidx.room.Dao
import androidx.room.Query

@Dao
interface PageDao {
    @Query("SELECT * FROM Pages ORDER BY PageNo")
    suspend fun listPages(): List<PageEntity>

    @Query("SELECT * FROM Chapters ORDER BY SortKey, ChapterID")
    suspend fun listChapters(): List<ChapterEntity>

    /** One real book package holds exactly one real book's own row. */
    @Query("SELECT * FROM Books LIMIT 1")
    suspend fun getBook(): BookEntity?
}
