package com.islamicresearchhub.companion.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One real library row, exactly matching `catalog_export_cli.py`'s
 * `Libraries` table - this database is written by that desktop tool,
 * not by Room, so every column name here must match the real exported
 * schema exactly (Room validates this on open).
 */
@Entity(tableName = "Libraries")
data class LibraryEntity(
    @PrimaryKey
    @ColumnInfo(name = "LibraryID")
    val libraryId: Int,
    @ColumnInfo(name = "Name")
    val name: String,
)
