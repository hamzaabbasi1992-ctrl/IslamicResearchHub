package com.islamicresearchhub.companion.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import java.io.File

/**
 * Wraps one real, self-contained book package the desktop's
 * `book_package_export_cli.py` produces - real pages, chapters, and
 * this one book's own metadata, everything the offline reader needs
 * from a single file. Reuses `BookEntity`/`LibraryEntity` as-is (same
 * real columns as `CatalogDatabase`'s copy of those two tables) rather
 * than duplicating near-identical entity classes.
 */
@Database(
    entities = [BookEntity::class, LibraryEntity::class, PageEntity::class, ChapterEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class BookPackageDatabase : RoomDatabase() {
    abstract fun pageDao(): PageDao

    companion object {
        private fun databaseName(bookId: Int) = "book_$bookId.db"

        /** Import a real book package file, keyed by its own real BookID
         * so multiple offline books coexist in this app's private storage. */
        fun open(context: Context, bookId: Int, sourceFile: File): BookPackageDatabase {
            return Room.databaseBuilder(
                context, BookPackageDatabase::class.java, databaseName(bookId)
            )
                .createFromFile(sourceFile)
                .build()
        }

        fun isImported(context: Context, bookId: Int): Boolean {
            return context.getDatabasePath(databaseName(bookId)).exists()
        }

        fun openExisting(context: Context, bookId: Int): BookPackageDatabase {
            return Room.databaseBuilder(
                context, BookPackageDatabase::class.java, databaseName(bookId)
            ).build()
        }
    }
}
