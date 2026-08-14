package com.islamicresearchhub.companion.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface AppStateDao {
    /** Plain REPLACE-on-conflict insert, not `@Upsert` - `@Upsert`
     * compiles to `INSERT ... ON CONFLICT DO UPDATE`, SQL that needs
     * SQLite 3.24+; the bundled SQLite on some real devices near this
     * app's `minSdk = 26` floor predates that and would throw at
     * runtime on the first call, a failure compilation can't catch.
     * `OnConflictStrategy.REPLACE` has been supported forever and gives
     * the exact same insert-or-update behavior here since `bookId` is
     * the only conflict target (the primary key). */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun recordOpened(entry: RecentlyOpenedEntity)

    @Query("SELECT * FROM RecentlyOpenedBooks ORDER BY openedAtEpochMillis DESC LIMIT :limit")
    suspend fun listRecent(limit: Int = 10): List<RecentlyOpenedEntity>
}
