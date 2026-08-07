package com.islamicresearchhub.companion.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One real page's full content, exactly matching
 * `book_package_export_cli.py`'s `Pages` table - `PageID` is a real,
 * synthesized 1-based row number (the desktop source schema has no
 * natural per-row page ID; the export CLI adds one via `ROW_NUMBER()`
 * specifically so Room has a real declared primary key to validate
 * against).
 */
@Entity(tableName = "Pages")
data class PageEntity(
    @PrimaryKey
    @ColumnInfo(name = "PageID")
    val pageId: Int,
    @ColumnInfo(name = "PageNo")
    val pageNo: Int?,
    @ColumnInfo(name = "Content")
    val content: String?,
    @ColumnInfo(name = "HadeesNumber")
    val hadeesNumber: Int?,
    @ColumnInfo(name = "AyahNumber")
    val ayahNumber: Int?,
)
