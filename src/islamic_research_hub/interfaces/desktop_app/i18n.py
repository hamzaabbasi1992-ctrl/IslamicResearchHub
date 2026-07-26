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
        "rail-search": "Search",
        "rail-viewer": "Viewer",
        "rail-import": "Import",
        "rail-settings": "Settings",
        "settings-heading": "Settings",
        "settings-language": "App language",
        "settings-language-note": "Changes the app's own menus, not book content.",
        "settings-reading": "Reading",
        "settings-default-font-size": "Default reading font size",
        "settings-about": "About",
    },
    "ur": {
        "rail-search": "تلاش",
        "rail-viewer": "ریڈر",
        "rail-import": "درآمد",
        "rail-settings": "ترتیبات",
        "settings-heading": "ترتیبات",
        "settings-language": "ایپ کی زبان",
        "settings-language-note": "یہ صرف ایپ کے مینیو بدلتا ہے، کتاب کا مواد نہیں۔",
        "settings-reading": "مطالعہ",
        "settings-default-font-size": "ڈیفالٹ پڑھنے کا فونٹ سائز",
        "settings-about": "تفصیلات",
    },
    "ar": {
        "rail-search": "بحث",
        "rail-viewer": "القارئ",
        "rail-import": "استيراد",
        "rail-settings": "الإعدادات",
        "settings-heading": "الإعدادات",
        "settings-language": "لغة التطبيق",
        "settings-language-note": "يغيّر هذا قوائم التطبيق فقط، وليس محتوى الكتب.",
        "settings-reading": "القراءة",
        "settings-default-font-size": "حجم خط القراءة الافتراضي",
        "settings-about": "حول",
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
