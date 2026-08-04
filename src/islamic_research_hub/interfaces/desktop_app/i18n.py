"""App-chrome language switching (English/Urdu/Arabic) with real RTL/LTR layout.

Only the app's own menus translate - book content always stays in its
original script, exactly like the earlier design preview promised.
Persisted via QSettings so the choice survives a restart.
"""

from PySide6.QtCore import QObject, QSettings, Qt, Signal

SETTINGS_ORGANIZATION = "IslamicResearchHub"
SETTINGS_APPLICATION = "DesktopApp"
LANGUAGE_KEY = "language"
DEFAULT_LANGUAGE = "en"

LANGUAGES: dict[str, str] = {"en": "English", "ur": "اردو", "ar": "العربية"}

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "rail-home": "Home",
        "rail-search": "Search",
        "rail-libraries": "Libraries",
        "rail-duplicates": "Duplicates",
        "rail-taxonomy": "Taxonomy",
        "rail-logs": "Logs",
        "rail-settings": "Settings",
        "settings-heading": "Settings",
        "settings-language": "App language",
        "settings-language-note": "Changes the app's own menus, not book content.",
        "settings-reading": "Reading",
        "settings-default-font-size": "Default reading font size",
        "settings-default-font-family": "Default reading font",
        "settings-tts-enabled": "Read pages aloud",
        "settings-voice-search-enabled": "Search by speaking",
        "settings-appearance": "Appearance",
        "settings-ai-agent": "AI Agent",
        "settings-ai-agent-enabled": "Enable AI Agent (uses a paid cloud API)",
        "settings-ai-agent-provider": "Provider",
        "settings-ai-agent-api-key": "API key",
        "settings-ai-agent-disclosure": "Stored locally on this device, unencrypted. Anyone with access to this Windows account can read it.",
        "settings-theme": "Theme",
        "theme-light": "Light",
        "theme-dark": "Dark",
        "theme-high-contrast": "High contrast",
        "settings-font-scale": "Interface text size",
        "settings-density": "Layout density",
        "settings-shortcuts": "Keyboard shortcuts",
        "settings-about": "About",
        "tagline": "Master Library",
        "stat-books": "books",
        "stat-libraries": "libraries",
        "stat-authors": "authors",
        "stat-categories": "categories",
        "stat-series": "series",
        "tab-categories": "Categories",
        "tab-authors": "Authors",
        "pane-libraries": "Libraries",
        "all-libraries": "All libraries",
        "add-library": "Add new library",
        "library-sources": "Library sources",
        "duplicate-review": "Duplicate review",
        "folder-to-scan": "Folder to scan",
        "browse": "Browse...",
        "format": "Format",
        "library-name": "Library name",
        "scan-import": "Scan && import",
    },
    "ur": {
        "rail-home": "ہوم",
        "rail-search": "تلاش",
        "rail-libraries": "مکاتب",
        "rail-duplicates": "نقول",
        "rail-taxonomy": "درجہ بندی",
        "rail-logs": "لاگز",
        "rail-settings": "ترتیبات",
        "settings-heading": "ترتیبات",
        "settings-language": "ایپ کی زبان",
        "settings-language-note": "یہ صرف ایپ کے مینیو بدلتا ہے، کتاب کا مواد نہیں۔",
        "settings-reading": "مطالعہ",
        "settings-default-font-size": "ڈیفالٹ پڑھنے کا فونٹ سائز",
        "settings-default-font-family": "ڈیفالٹ پڑھنے کا فونٹ",
        "settings-tts-enabled": "صفحہ بلند آواز میں پڑھیں",
        "settings-voice-search-enabled": "آواز سے تلاش کریں",
        "settings-appearance": "ظاہری شکل",
        "settings-ai-agent": "اے آئی ایجنٹ",
        "settings-ai-agent-enabled": "اے آئی ایجنٹ فعال کریں (ادا شدہ کلاؤڈ اے پی آئی استعمال کرتا ہے)",
        "settings-ai-agent-provider": "فراہم کنندہ",
        "settings-ai-agent-api-key": "اے پی آئی کی",
        "settings-ai-agent-disclosure": "اس ڈیوائس پر مقامی طور پر، بغیر خفیہ کاری کے محفوظ ہے۔ اس ونڈوز اکاؤنٹ تک رسائی رکھنے والا کوئی بھی اسے پڑھ سکتا ہے۔",
        "settings-theme": "تھیم",
        "theme-light": "ہلکا",
        "theme-dark": "گہرا",
        "theme-high-contrast": "زیادہ تضاد",
        "settings-font-scale": "انٹرفیس متن کا سائز",
        "settings-density": "ترتیب کی کثافت",
        "settings-shortcuts": "کی بورڈ شارٹ کٹس",
        "settings-about": "تفصیلات",
        "tagline": "مرکزی لائبریری",
        "stat-books": "کتابیں",
        "stat-libraries": "مکاتب",
        "stat-authors": "مصنفین",
        "stat-categories": "موضوعات",
        "stat-series": "سلسلے",
        "tab-categories": "موضوعات",
        "tab-authors": "مصنفین",
        "pane-libraries": "مکاتب",
        "all-libraries": "تمام مکاتب",
        "add-library": "نئی لائبریری شامل کریں",
        "library-sources": "لائبریری ذرائع",
        "duplicate-review": "نقل کا جائزہ",
        "folder-to-scan": "اسکین کرنے کے لیے فولڈر",
        "browse": "براؤز...",
        "format": "فارمیٹ",
        "library-name": "لائبریری کا نام",
        "scan-import": "اسکین اور درآمد",
    },
    "ar": {
        "rail-home": "الرئيسية",
        "rail-search": "بحث",
        "rail-libraries": "مكتبات",
        "rail-duplicates": "التكرارات",
        "rail-taxonomy": "التصنيف",
        "rail-logs": "السجلات",
        "rail-settings": "الإعدادات",
        "settings-heading": "الإعدادات",
        "settings-language": "لغة التطبيق",
        "settings-language-note": "يغيّر هذا قوائم التطبيق فقط، وليس محتوى الكتب.",
        "settings-reading": "القراءة",
        "settings-default-font-size": "حجم خط القراءة الافتراضي",
        "settings-default-font-family": "خط القراءة الافتراضي",
        "settings-tts-enabled": "قراءة الصفحات بصوت عالٍ",
        "settings-voice-search-enabled": "البحث بالصوت",
        "settings-appearance": "المظهر",
        "settings-ai-agent": "الوكيل الذكي",
        "settings-ai-agent-enabled": "تفعيل الوكيل الذكي (يستخدم واجهة برمجة سحابية مدفوعة)",
        "settings-ai-agent-provider": "المزوّد",
        "settings-ai-agent-api-key": "مفتاح API",
        "settings-ai-agent-disclosure": "مخزّن محليًا على هذا الجهاز، غير مشفّر. يمكن لأي شخص لديه وصول إلى حساب ويندوز هذا قراءته.",
        "settings-theme": "السمة",
        "theme-light": "فاتح",
        "theme-dark": "داكن",
        "theme-high-contrast": "تباين عالٍ",
        "settings-font-scale": "حجم نص الواجهة",
        "settings-density": "كثافة التخطيط",
        "settings-shortcuts": "اختصارات لوحة المفاتيح",
        "settings-about": "حول",
        "tagline": "المكتبة المركزية",
        "stat-books": "كتب",
        "stat-libraries": "مكتبات",
        "stat-authors": "مؤلفين",
        "stat-categories": "مواضيع",
        "stat-series": "سلاسل",
        "tab-categories": "مواضيع",
        "tab-authors": "مؤلفين",
        "pane-libraries": "مكتبات",
        "all-libraries": "كل المكتبات",
        "add-library": "إضافة مكتبة جديدة",
        "library-sources": "مصادر المكتبة",
        "duplicate-review": "مراجعة التكرار",
        "folder-to-scan": "مجلد للفحص",
        "browse": "استعراض...",
        "format": "الصيغة",
        "library-name": "اسم المكتبة",
        "scan-import": "فحص واستيراد",
    },
}

_RTL_LANGUAGES = frozenset({"ur", "ar"})


class Translator(QObject):
    """Holds the current app language, persists it, and notifies listeners."""

    language_changed = Signal(str)

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        self._language = self._settings.value(LANGUAGE_KEY, DEFAULT_LANGUAGE)
        if self._language not in LANGUAGES:
            self._language = DEFAULT_LANGUAGE

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        """Change the app language, persist it, and notify listeners."""
        if language not in LANGUAGES or language == self._language:
            return
        self._language = language
        self._settings.setValue(LANGUAGE_KEY, language)
        self.language_changed.emit(language)

    def tr(self, key: str) -> str:
        """Return the current-language text for a key, falling back to English."""
        return _TRANSLATIONS[self._language].get(key, _TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key))

    @property
    def layout_direction(self) -> Qt.LayoutDirection:
        """Return the correct overall layout direction for the current language."""
        if self._language in _RTL_LANGUAGES:
            return Qt.LayoutDirection.RightToLeft
        return Qt.LayoutDirection.LeftToRight
