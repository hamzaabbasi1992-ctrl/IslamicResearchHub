"""Live theme (palette + font-scale + density) switching, applied at the
QApplication level.

Wired into the app at startup (`__main__.py`) and live from Settings
(`settings_screen.py`'s Appearance block calls `set_theme`/
`set_font_scale`/`set_density`, each of which persists to `QSettings`
and re-applies the stylesheet to the whole running `QApplication`
immediately - no restart needed).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

from islamic_research_hub.interfaces.desktop_app.theme import (
    DARK,
    DENSITY_COMFORTABLE,
    HIGH_CONTRAST,
    LIGHT,
    Palette,
    build_stylesheet,
)

THEME_KEY = "appearance/theme"
FONT_SCALE_KEY = "appearance/font_scale"
DENSITY_KEY = "appearance/density"
DEFAULT_THEME = "light"
DEFAULT_FONT_SCALE = 1.0
DEFAULT_DENSITY = DENSITY_COMFORTABLE

THEMES: dict[str, Palette] = {"light": LIGHT, "dark": DARK, "high_contrast": HIGH_CONTRAST}


class ThemeController(QObject):
    """Owns the active palette/font-scale/density, persists them, and
    re-applies the global stylesheet to the whole running application
    when any of them changes.
    """

    theme_changed = Signal(str)
    density_changed = Signal(float)

    def __init__(self, settings: QSettings, parent: QObject | None = None) -> None:
        """Load the persisted theme/font-scale/density, falling back to
        light/1.0x/comfortable."""
        super().__init__(parent)
        self._settings = settings
        theme_name = str(settings.value(THEME_KEY, DEFAULT_THEME))
        self._theme_name = theme_name if theme_name in THEMES else DEFAULT_THEME
        try:
            self._font_scale = float(settings.value(FONT_SCALE_KEY, DEFAULT_FONT_SCALE))
        except (TypeError, ValueError):
            self._font_scale = DEFAULT_FONT_SCALE
        try:
            self._density = float(settings.value(DENSITY_KEY, DEFAULT_DENSITY))
        except (TypeError, ValueError):
            self._density = DEFAULT_DENSITY

    @property
    def theme_name(self) -> str:
        """The active theme's key (`"light"`, `"dark"`, or `"high_contrast"`)."""
        return self._theme_name

    @property
    def font_scale(self) -> float:
        """The active app-chrome font-size multiplier."""
        return self._font_scale

    @property
    def density(self) -> float:
        """The active app-chrome spacing multiplier (Compact Research Mode)."""
        return self._density

    def palette(self) -> Palette:
        """The active theme's `Palette`."""
        return THEMES[self._theme_name]

    def set_theme(self, theme_name: str) -> None:
        """Switch the active theme, persist it, and re-apply the stylesheet."""
        if theme_name not in THEMES:
            raise ValueError(f"Unknown theme: {theme_name}")
        self._theme_name = theme_name
        self._settings.setValue(THEME_KEY, theme_name)
        self._apply()

    def set_font_scale(self, font_scale: float) -> None:
        """Change the app-chrome font-size multiplier, persist it, and re-apply."""
        self._font_scale = font_scale
        self._settings.setValue(FONT_SCALE_KEY, font_scale)
        self._apply()

    def set_density(self, density: float) -> None:
        """Change the app-chrome spacing multiplier, persist it, and re-apply.

        Independent of the accessibility font-scale/high-contrast theme -
        any theme x any density x any font-scale composes freely.
        """
        self._density = density
        self._settings.setValue(DENSITY_KEY, density)
        self._apply()
        self.density_changed.emit(density)

    def stylesheet(self) -> str:
        """The full global stylesheet for the current theme/font-scale/density."""
        return build_stylesheet(self.palette(), self._font_scale, self._density)

    def _apply(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(self.stylesheet())
        self.theme_changed.emit(self._theme_name)
