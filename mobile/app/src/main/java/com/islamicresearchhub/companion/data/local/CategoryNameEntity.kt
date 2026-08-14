package com.islamicresearchhub.companion.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One real, named category from the desktop's cross-library
 * `CategoryTaxonomy`, exactly matching `catalog_export_cli.py`'s
 * `CategoryNames` table. Deliberately not derived from `Books.Category`
 * (that free-text column is mostly empty, and where populated is often
 * a bare MJCN number or a library-internal slug - see that export
 * script's own docstring for the real numbers behind this decision).
 */
@Entity(tableName = "CategoryNames")
data class CategoryNameEntity(
    @PrimaryKey
    @ColumnInfo(name = "MJCN")
    val mjcn: Int,
    @ColumnInfo(name = "Name")
    val name: String,
    @ColumnInfo(name = "ParentMJCN")
    val parentMjcn: Int?,
)
