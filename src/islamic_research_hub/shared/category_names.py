"""Display-name translations for the real, named Islamic subject
categories recovered from this corpus's `CategoryTaxonomy` (see
`book_browser_repository.get_category_tree()`).

Keyed by the canonical `CategoryTaxonomy.Name` text (the raw label the
corpus stores, and the same value used as the real filter key for
`list_books_in_category()`) - translation is display-only, the
canonical name stays the real lookup key everywhere else, same
separation `LANGUAGE_CANONICAL_NAMES` already uses for `Books.Language`.
"""

CATEGORY_NAME_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Aqeedah": {"en": "Creed (Aqeedah)", "ur": "عقیدہ", "ar": "العقيدة"},
    "aqeeda": {"en": "Creed (Aqeedah)", "ur": "عقیدہ", "ar": "العقيدة"},
    "Azkaar-Duain": {"en": "Adhkar & Duas", "ur": "اذکار و دعائیں", "ar": "الأذكار والأدعية"},
    "Dawat-o-tableegh": {"en": "Dawah & Tableegh", "ur": "دعوت و تبلیغ", "ar": "الدعوة والتبليغ"},
    "Fiqh": {"en": "Fiqh (Jurisprudence)", "ur": "فقہ", "ar": "الفقه"},
    "fiqh-wa-usool-fiqh": {"en": "Fiqh & Usul al-Fiqh", "ur": "فقہ و اصول فقہ", "ar": "الفقه وأصول الفقه"},
    "Hadith": {"en": "Hadith", "ur": "حدیث", "ar": "الحديث"},
    "hadisiyaat": {"en": "Hadith Studies", "ur": "حدیثیات", "ar": "علوم الحديث"},
    "Inkar-e-Hadith": {"en": "Hadith Denial (Inkar-e-Hadith)", "ur": "انکارِ حدیث", "ar": "إنكار الحديث"},
    "Mazahib-Wa-Adyan": {"en": "Sects & Religions", "ur": "مذاہب و ادیان", "ar": "المذاهب والأديان"},
    "Quran": {"en": "Quran", "ur": "قرآن", "ar": "القرآن"},
    "quraniyat": {"en": "Quranic Studies", "ur": "قرآنیات", "ar": "الدراسات القرآنية"},
    "Seerah": {"en": "Seerah (Prophetic Biography)", "ur": "سیرت", "ar": "السيرة"},
    "seerat": {"en": "Seerah (Prophetic Biography)", "ur": "سیرت", "ar": "السيرة"},
    "seerat-o-sawanih": {"en": "Biography & Life History", "ur": "سیرت و سوانح", "ar": "السيرة والسير الذاتية"},
    "Tafseer": {"en": "Tafseer (Quranic Exegesis)", "ur": "تفسیر", "ar": "التفسير"},
    "ahkaam": {"en": "Rulings (Ahkaam)", "ur": "احکام", "ar": "الأحكام"},
    "akhlaq-adaab": {"en": "Ethics & Manners", "ur": "اخلاق و آداب", "ar": "الأخلاق والآداب"},
    "al-bayan": {"en": "Al-Bayan (Elucidation)", "ur": "البیان", "ar": "البيان"},
    "fatawa": {"en": "Fatawa (Verdicts)", "ur": "فتاویٰ", "ar": "الفتاوى"},
    "islah": {"en": "Islah (Reform)", "ur": "اصلاح", "ar": "الإصلاح"},
    "khutbaat-o-maqalaat": {"en": "Khutbaat & Articles", "ur": "خطبات و مقالات", "ar": "الخطب والمقالات"},
    "maeeshat": {"en": "Economy & Livelihood", "ur": "معیشت", "ar": "الاقتصاد والمعيشة"},
    "mahnama-mohaddis": {"en": "Monthly Muhaddith (Magazine)", "ur": "ماہنامہ محدث", "ar": "مجلة المحدث الشهرية"},
    "mahnama-rushad": {"en": "Monthly Rushad (Magazine)", "ur": "ماہنامہ رُشد", "ar": "مجلة الرشد الشهرية"},
    "manaqib": {"en": "Manaqib (Virtues)", "ur": "مناقب", "ar": "المناقب"},
    "mutafareqaat": {"en": "Miscellaneous", "ur": "متفرقات", "ar": "متفرقات"},
    "radd-e-fitan": {"en": "Refutation of Fitna", "ur": "رد فتن", "ar": "الرد على الفتن"},
    "rudood": {"en": "Refutations (Rudood)", "ur": "ردود", "ar": "الردود"},
    "tareekh": {"en": "History", "ur": "تاریخ", "ar": "التاريخ"},
    "tibb-wa-hikmat": {"en": "Medicine & Wisdom", "ur": "طب و حکمت", "ar": "الطب والحكمة"},
    "zuhd": {"en": "Zuhd (Asceticism)", "ur": "زہد", "ar": "الزهد"},
}


def translated_category_name(canonical_name: str, language_code: str) -> str:
    """Return the display name for a category in the given app language,
    falling back to the raw canonical name if no translation is recorded."""
    return CATEGORY_NAME_TRANSLATIONS.get(canonical_name, {}).get(language_code, canonical_name)
