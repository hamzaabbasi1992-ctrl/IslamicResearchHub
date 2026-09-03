package com.islamicresearchhub.companion.ui.common

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection

enum class AppLanguage(val code: String, val displayName: String, val isRtl: Boolean) {
    URDU("ur", "اردو", true),
    ENGLISH("en", "English", false),
    ARABIC("ar", "العربية", true)
}

object LanguageManager {
    private const val PREFS_NAME = "app_lang_prefs"
    private const val KEY_LANG = "selected_language"

    var currentLanguage by mutableStateOf(AppLanguage.URDU)
        private set

    fun init(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val code = prefs.getString(KEY_LANG, AppLanguage.URDU.code) ?: AppLanguage.URDU.code
        currentLanguage = AppLanguage.values().firstOrNull { it.code == code } ?: AppLanguage.URDU
    }

    fun setLanguage(context: Context, language: AppLanguage) {
        currentLanguage = language
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_LANG, language.code).apply()
    }

    fun getString(key: String): String {
        return when (currentLanguage) {
            AppLanguage.URDU -> urduTranslations[key] ?: key
            AppLanguage.ENGLISH -> englishTranslations[key] ?: key
            AppLanguage.ARABIC -> arabicTranslations[key] ?: key
        }
    }

    private val urduTranslations = mapOf(
        "app_title" to "مکتبہ شمس",
        "home" to "ہوم",
        "library" to "لائبریری",
        "azkaar" to "اذکار",
        "hadith" to "حدیث",
        "quran" to "قرآن",
        "seerah" to "سیرت",
        "waqiat" to "واقعات انسائیکلوپیڈیا",
        "bulk_import" to "تمام کتب امپورٹ کریں",
        "categories" to "زمرہ جات",
        "authors" to "مصنفین",
        "downloads" to "ڈاؤنلوڈز",
        "advanced_search" to "تفصیلی تلاش",
        "downloaded_books" to "ڈاؤنلوڈ کتب",
        "my_library" to "میری لائبریری",
        "recent_reading" to "حالیہ مطالعہ",
        "favorites" to "پسندیدہ",
        "feedback" to "شکایات و آراء",
        "online_corpus" to "آن لائن مطالعہ",
        "ai_summary" to "اے آئی سے خلاصہ",
        "search_placeholder" to "مطلوبہ الفاظ لکھیں",
        "how_to_search" to "کیسے تلاش کریں",
        "search_in_title" to "عنوان",
        "search_in_full" to "مکمل کتاب",
        "what_to_search" to "کیا تلاش کریں",
        "all_words" to "تمام الفاظ",
        "any_word" to "کوئی بھی لفظ",
        "exact_match" to "مکمل مطابقت",
        "ordered_match" to "ترتیب",
        "ignore_hamza" to "عربی ہمزہ یا ی وغیرہ کو نظر انداز",
        "select_category_scope" to "تلاش کا دائرہ کار منتخب کریں",
        "select_categories" to "منتخب کریں",
        "ok" to "ٹھیک ہے",
        "cancel" to "منسوخ",
        "search_results" to "نتائج",
        "in_book_search" to "کتاب میں تلاش"
    )

    private val englishTranslations = mapOf(
        "app_title" to "Maktaba Shams",
        "home" to "Home",
        "library" to "Library",
        "azkaar" to "Azkaar",
        "hadith" to "Hadith",
        "quran" to "Quran",
        "seerah" to "Seerah",
        "waqiat" to "Waqiat",
        "categories" to "Categories",
        "authors" to "Authors",
        "downloads" to "Downloads",
        "advanced_search" to "Detailed Search",
        "downloaded_books" to "Downloaded Books",
        "my_library" to "My Library",
        "recent_reading" to "Recent Reading",
        "favorites" to "Favorites",
        "feedback" to "Feedback & Support",
        "online_corpus" to "Online Corpus",
        "ai_summary" to "AI Summary",
        "search_placeholder" to "Type search keywords...",
        "how_to_search" to "Search Scope",
        "search_in_title" to "Title Only",
        "search_in_full" to "Full Book Content",
        "what_to_search" to "Match Mode",
        "all_words" to "All Words (AND)",
        "any_word" to "Any Word (OR)",
        "exact_match" to "Exact Phrase",
        "ordered_match" to "Ordered Terms",
        "ignore_hamza" to "Ignore Hamza & Alef variants",
        "select_category_scope" to "Select Category Scope",
        "select_categories" to "Select Categories",
        "ok" to "OK",
        "cancel" to "Cancel",
        "search_results" to "Search Results",
        "in_book_search" to "Search in Book"
    )

    private val arabicTranslations = mapOf(
        "app_title" to "مكتبة شمس",
        "home" to "الرئيسية",
        "library" to "المكتبة",
        "categories" to "التصنيفات",
        "authors" to "المؤلفون",
        "downloads" to "التنزيلات",
        "advanced_search" to "البحث التفصيلي",
        "downloaded_books" to "الكتب المحملة",
        "my_library" to "مكتبتي",
        "recent_reading" to "القراءة الحديثة",
        "favorites" to "المفضلة",
        "feedback" to "الآراء والملاحظات",
        "online_corpus" to "القراءة المباشرة",
        "ai_summary" to "ملخص الذكاء الاصطناعي",
        "search_placeholder" to "اكتب الكلمات المطلوبة",
        "how_to_search" to "طريقة البحث",
        "search_in_title" to "العنوان",
        "search_in_full" to "الكتاب الكامل",
        "what_to_search" to "نوع المطابقة",
        "all_words" to "جميع الكلمات",
        "any_word" to "أي كلمة",
        "exact_match" to "مطابقة تامة",
        "ordered_match" to "ترتيب",
        "ignore_hamza" to "تجاهل الهمزة والياء",
        "select_category_scope" to "تحديد نطاق البحث",
        "select_categories" to "اختر التصنيفات",
        "ok" to "موافق",
        "cancel" to "إلغاء",
        "search_results" to "نتائج البحث",
        "in_book_search" to "البحث في الكتاب"
    )
}

@Composable
fun ProvideLanguageLayout(content: @Composable () -> Unit) {
    val layoutDirection = if (LanguageManager.currentLanguage.isRtl) {
        LayoutDirection.Rtl
    } else {
        LayoutDirection.Ltr
    }
    CompositionLocalProvider(LocalLayoutDirection provides layoutDirection) {
        content()
    }
}
