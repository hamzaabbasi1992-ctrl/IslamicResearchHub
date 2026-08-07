package com.islamicresearchhub.companion.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One real chapter/table-of-contents entry, exactly matching
 * `book_package_export_cli.py`'s `Chapters` table - `ChapterID` reuses
 * the desktop source database's own real chapter ID (a genuine, already
 * globally-unique value there), now declared as a real Room primary key.
 */
@Entity(tableName = "Chapters")
data class ChapterEntity(
    @PrimaryKey
    @ColumnInfo(name = "ChapterID")
    val chapterId: Int,
    @ColumnInfo(name = "ParentChapterID")
    val parentChapterId: Int?,
    @ColumnInfo(name = "Title")
    val title: String?,
    @ColumnInfo(name = "PageNo")
    val pageNo: Int?,
    @ColumnInfo(name = "SortKey")
    val sortKey: Int?,
)
