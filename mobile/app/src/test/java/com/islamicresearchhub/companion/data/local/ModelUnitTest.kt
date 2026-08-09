package com.islamicresearchhub.companion.data.local

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class ModelUnitTest {

    @Test
    fun testBookEntityFields() {
        val book = BookEntity(
            bookId = 101,
            libraryId = 1,
            title = "Sahih al-Bukhari",
            author = "Imam al-Bukhari",
            publisher = "Darussalam",
            language = "Arabic",
            category = "Hadith",
            pageCount = 7563,
            chapterCount = 99,
            publishYear = "1400",
            seriesId = 5,
            volumeNumber = 1
        )

        assertEquals(101, book.bookId)
        assertEquals("Sahih al-Bukhari", book.title)
        assertEquals("Imam al-Bukhari", book.author)
        assertEquals(7563, book.pageCount)
        assertEquals(99, book.chapterCount)
        assertEquals(1, book.volumeNumber)
    }

    @Test
    fun testLibraryEntityFields() {
        val library = LibraryEntity(libraryId = 1, name = "Shamela Library")
        assertEquals(1, library.libraryId)
        assertEquals("Shamela Library", library.name)
    }

    @Test
    fun testPageEntityFields() {
        val page = PageEntity(
            pageId = 1,
            pageNo = 15,
            content = "Sample Arabic page content",
            hadeesNumber = 1001,
            ayahNumber = null
        )

        assertEquals(1, page.pageId)
        assertEquals(15, page.pageNo)
        assertEquals(1001, page.hadeesNumber)
        assertNull(page.ayahNumber)
    }

    @Test
    fun testChapterHierarchyDepthCalculation() {
        val ch1 = ChapterEntity(chapterId = 1, parentChapterId = null, title = "Book of Faith", pageNo = 1, sortKey = 1)
        val ch2 = ChapterEntity(chapterId = 2, parentChapterId = 1, title = "Chapter on Belief", pageNo = 5, sortKey = 2)
        val ch3 = ChapterEntity(chapterId = 3, parentChapterId = 2, title = "Section on Intentions", pageNo = 8, sortKey = 3)

        val chapters = listOf(ch1, ch2, ch3)
        val byId = chapters.associateBy { it.chapterId }
        val depths = mutableMapOf<Int, Int>()

        fun getDepth(id: Int): Int {
            depths[id]?.let { return it }
            val ch = byId[id] ?: return 0
            val parentId = ch.parentChapterId
            val d = if (parentId != null && parentId != 0 && parentId in byId) {
                1 + getDepth(parentId)
            } else {
                0
            }
            depths[id] = d
            return d
        }

        chapters.forEach { getDepth(it.chapterId) }

        assertEquals(0, depths[1])
        assertEquals(1, depths[2])
        assertEquals(2, depths[3])
    }
}
