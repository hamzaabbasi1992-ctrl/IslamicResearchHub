package com.islamicresearchhub.companion.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

/**
 * This app's own local state - currently just "which books has this
 * device actually opened, and when" (`RecentlyOpenedBooks`, backing the
 * Home screen's Continue Reading row). Unlike `CatalogDatabase`/
 * `BookPackageDatabase`, Room creates and owns this schema itself from
 * an empty file on first launch - no prepackaged asset/file import, so
 * none of the `PRAGMA user_version` mismatch that broke those two
 * applies here.
 */
@Database(entities = [RecentlyOpenedEntity::class], version = 1, exportSchema = false)
abstract class AppStateDatabase : RoomDatabase() {
    abstract fun appStateDao(): AppStateDao

    companion object {
        @Volatile
        private var instance: AppStateDatabase? = null

        fun get(context: Context): AppStateDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppStateDatabase::class.java,
                    "app_state.db",
                ).build().also { instance = it }
            }
        }
    }
}
