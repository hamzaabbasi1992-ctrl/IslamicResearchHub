package com.islamicresearchhub.companion.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * One real record of this device opening one real book in the reader -
 * powers the Home screen's "Continue Reading" row. Lives in
 * `AppStateDatabase`, an app-owned database Room creates and manages
 * itself from scratch (never a `createFromAsset`/`createFromFile` copy
 * of an externally-written file), so it carries none of the prepackaged-
 * database version risk `CatalogDatabase`/`BookPackageDatabase` do.
 */
@Entity(tableName = "RecentlyOpenedBooks")
data class RecentlyOpenedEntity(
    @PrimaryKey
    val bookId: Int,
    val title: String,
    val author: String?,
    val lastPageNo: Int,
    val openedAtEpochMillis: Long,
)
