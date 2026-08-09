import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication

# Add src path
sys.path.insert(0, str(Path("src").resolve()))

from islamic_research_hub.interfaces.desktop_app.main_window import MainWindow

output_dir = Path("screenshots of app for other ai/ui_matrix")
output_dir.mkdir(parents=True, exist_ok=True)


def capture_all() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    db_path = Path("data/books.db").resolve()
    maknoon_path = Path("F:/MAKBATA AL MAKOON PDF").resolve()

    window = MainWindow(database_path=db_path, maknoon_pdf_folder=maknoon_path)
    window.show()
    app.processEvents()

    languages = [("en", "English"), ("ur", "Urdu"), ("ar", "Arabic")]
    screens = [
        (0, "01_Search"),
        (1, "02_Taxonomy"),
        (2, "03_Viewer"),
        (3, "04_Import"),
        (4, "05_Duplicates"),
        (5, "06_Settings"),
        (6, "07_Logs"),
        (7, "08_AI_Assistant"),
    ]

    for lang_code, lang_name in languages:
        print(f"\n--- Capturing UI Matrix for Language: {lang_name} ({lang_code}) ---")
        window._on_language_changed(lang_code)
        app.processEvents()
        time.sleep(0.3)

        # 1. Normal Window State (1280x800)
        window.showNormal()
        window.resize(1280, 800)
        app.processEvents()
        time.sleep(0.3)

        for screen_idx, screen_name in screens:
            try:
                window._nav_rail.buttons[screen_idx].click()
            except Exception:
                pass
            app.processEvents()
            time.sleep(0.2)
            shot_path = output_dir / f"{lang_code}_normal_{screen_name}.png"
            pixmap = window.grab()
            pixmap.save(str(shot_path))
            print(f"Captured: {shot_path.name}")

        # 2. Maximized Window State
        window.showMaximized()
        app.processEvents()
        time.sleep(0.4)

        for screen_idx, screen_name in screens[:4]:  # Key screens in maximized
            try:
                window._nav_rail.buttons[screen_idx].click()
            except Exception:
                pass
            app.processEvents()
            time.sleep(0.2)
            shot_path = output_dir / f"{lang_code}_maximized_{screen_name}.png"
            pixmap = window.grab()
            pixmap.save(str(shot_path))
            print(f"Captured: {shot_path.name}")

        # 3. Full Screen Window State
        window.showFullScreen()
        app.processEvents()
        time.sleep(0.4)

        for screen_idx, screen_name in screens[:3]:  # Key screens in fullscreen
            try:
                window._nav_rail.buttons[screen_idx].click()
            except Exception:
                pass
            app.processEvents()
            time.sleep(0.2)
            shot_path = output_dir / f"{lang_code}_fullscreen_{screen_name}.png"
            pixmap = window.grab()
            pixmap.save(str(shot_path))
            print(f"Captured: {shot_path.name}")

    window.showNormal()
    window.close()
    print("\nUI Matrix Screenshot Capture Complete!")


if __name__ == "__main__":
    capture_all()
