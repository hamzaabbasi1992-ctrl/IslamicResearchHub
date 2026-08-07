package com.islamicresearchhub.companion.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One real book's catalog metadata (no page content - the catalog file
 * is deliberately lightweight enough to ship whole to a phone), exactly
 * matching `catalog_export_cli.py`'s `Books` table.
 */
@Entity(tableName = "Books")
data class BookEntity(
    @PrimaryKey
    @ColumnInfo(name = "BookID")
    val bookId: Int,
    @ColumnInfo(name = "LibraryID")
    val libraryId: Int?,
    @ColumnInfo(name = "Title")
    val title: String?,
    @ColumnInfo(name = "Author")
    val author: String?,
    @ColumnInfo(name = "Publisher")
    val publisher: String?,
    @ColumnInfo(name = "Language")
    val language: String?,
    @ColumnInfo(name = "Category")
    val category: String?,
    @ColumnInfo(name = "PageCount")
    val pageCount: Int?,
    @ColumnInfo(name = "ChapterCount")
    val chapterCount: Int?,
    @ColumnInfo(name = "PublishYear")
    val publishYear: String?,
    @ColumnInfo(name = "SeriesID")
    val seriesId: Int?,
    @ColumnInfo(name = "VolumeNumber")
    val volumeNumber: Int?,
)
