package com.islamicresearchhub.companion.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import java.io.File

/**
 * Wraps the real catalog.db the desktop's `catalog_export_cli.py`
 * produces. Opened via `createFromFile()` rather than letting Room
 * create/migrate a schema of its own - this file is already real,
 * complete, and populated by the time the user imports it; Room's job
 * here is only to query it, never to own its schema evolution.
 */
@Database(entities = [BookEntity::class, LibraryEntity::class], version = 1, exportSchema = false)
abstract class CatalogDatabase : RoomDatabase() {
    abstract fun catalogDao(): CatalogDao

    companion object {
        private const val DATABASE_NAME = "catalog.db"

        /** Build a real Room database over a real, already-imported
         * catalog file at `sourceFile` - copies it into this app's
         * private storage under Room's own managed name on first open. */
        fun open(context: Context, sourceFile: File): CatalogDatabase {
            return Room.databaseBuilder(context, CatalogDatabase::class.java, DATABASE_NAME)
                .createFromFile(sourceFile)
                .build()
        }

        /** Whether a real catalog has already been imported into this
         * app's private storage (survives app restarts). */
        fun isImported(context: Context): Boolean {
            return context.getDatabasePath(DATABASE_NAME).exists()
        }

        /** Reopen the already-imported real catalog without needing the
         * original source file again. */
        fun openExisting(context: Context): CatalogDatabase {
            return Room.databaseBuilder(context, CatalogDatabase::class.java, DATABASE_NAME).build()
        }
    }
}
