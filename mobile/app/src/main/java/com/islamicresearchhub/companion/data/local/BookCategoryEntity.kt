package com.islamicresearchhub.companion.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity

/**
 * One real book<->category membership link, exactly matching
 * `catalog_export_cli.py`'s `BookCategories` table (itself sourced from
 * the desktop's per-book `Categories` table, restricted to MJCNs that
 * resolved to a real name in `CategoryTaxonomy`).
 */
@Entity(tableName = "BookCategories", primaryKeys = ["BookID", "MJCN"])
data class BookCategoryEntity(
    @ColumnInfo(name = "BookID")
    val bookId: Int,
    @ColumnInfo(name = "MJCN")
    val mjcn: Int,
)
