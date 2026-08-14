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
@Database(
    entities = [
        BookEntity::class,
        LibraryEntity::class,
        CategoryNameEntity::class,
        BookCategoryEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
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
                .fallbackToDestructiveMigration()
                .build()
        }

        /** Whether a real catalog is available (true out-of-the-box via bundled assets). */
        fun isImported(context: Context): Boolean {
            return true
        }

        /** Reopen the catalog, copying from bundled asset catalog.db on first launch if needed.
         * Self-healing: If an existing DB file is corrupt or has an old schema mismatch,
         * it resets the file and re-copies fresh from assets. */
        fun openExisting(context: Context): CatalogDatabase {
            val dbFile = context.getDatabasePath(DATABASE_NAME)
            fun buildDb(forceAssetCopy: Boolean = false): CatalogDatabase {
                if (forceAssetCopy || !dbFile.exists()) {
                    dbFile.delete()
                    File(dbFile.path + "-shm").delete()
                    File(dbFile.path + "-wal").delete()
                }
                val builder = Room.databaseBuilder(context, CatalogDatabase::class.java, DATABASE_NAME)
                    .fallbackToDestructiveMigration()
                if (forceAssetCopy || !dbFile.exists()) {
                    builder.createFromAsset("catalog.db")
                }
                return builder.build()
            }

            return try {
                val instance = buildDb(forceAssetCopy = false)
                // Touch database to verify schema on open
                instance.openHelper.writableDatabase
                instance
            } catch (e: Exception) {
                buildDb(forceAssetCopy = true)
            }
        }
    }
}
