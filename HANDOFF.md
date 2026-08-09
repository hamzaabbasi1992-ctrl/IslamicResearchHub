# Handoff

Read this first if you're a different AI tool picking up this project cold. Also read `PROJECT.md` (architecture + full phase roadmap) and `CLAUDE.md` (working rules for this project) before making changes.

This file is overwritten each time, not appended to - it always reflects the current real state, not a history. For history, see `CHANGELOG.md`.

## Current Objective & Project State

All v1.0 core engine phases (1–7) and post-v1.0 roadmap phases (8 through 20) are **complete, tested, and verified**:
- **Phase 20 (Scholarly Review & Hard Constraints)**: **Complete**. Hard-constraint validation engine (`scholarly_review.py`) auditing AI research outputs against mandatory paragraph citation grounding (`P-XXXXX`), confidence thresholds, and Hadith authentication rules.
- **Phase 18 (Android Companion App)**: **Complete & Audited**. 4 Compose screens (`CatalogListScreen`, `BookDetailScreen`, `ChapterListScreen`, `BookReaderScreen`) with Room SQLite storage (`CatalogDatabase`, `BookPackageDatabase`). Features title/author search UI, structured metadata card overview, parent-child chapter tree hierarchy, RTL reader with page progress counter, jump dialog, and scroll position memory per book. Verified via JVM unit tests (`ModelUnitTest`) and Gradle (`app-debug.apk` built successfully at `mobile/app/build/outputs/apk/debug/app-debug.apk`).
- **Phase 16 (AI Content Generators)**: Complete. Includes Khutbah outlines (`khutbah_extraction.py`), Book reviews (`book_review_extraction.py`), Comparison tables (`comparison_table_extraction.py`), Citation bibliographies (`citation_list_extraction.py`), Lecture notes, Slide decks, Flashcards, MCQs, and Podcasts.
- **Phase 12 (Translation & Linguistics)**: Complete. Direct Arabic ↔ Urdu M2M100 engine, MarianMT English engine, and word-by-word morphological & root-word grammar breakdown module (`grammar_breakdown.py`).
- **Phase 15 (Educational Features)**: Complete. SM-2 spaced repetition, Flashcards, MCQ Quiz Mode, and Educational Lesson Plan Generator (`lesson_plan_generator.py`).
- **Phase 10 (Knowledge Graph)**: Complete. Permanent paragraph citation IDs (`P-XXXXX`), Paragraph Knowledge Graph Network Builder (`knowledge_graph_builder.py`), Encyclopedia entry auto-assembly (`encyclopedia_builder.py`), and Contradiction/variance evidence detector (`contradiction_detector.py`).
- **Phase 8.5 (Data Quality & Diagnostics)**: Complete. Series volume sequence consistency diagnostics (`series_diagnostics.py`).
- **Phase 19 (Developer Public APIs)**: Complete. Programmatic Python API facade (`IslamicResearchHubAPI` in `public_api.py`).
- **PySide6 Desktop GUI Background Workers**: Complete. Non-blocking `QThread` / `Signal` workers (`KhutbahGenerationWorker`, `BookReviewWorker`, `ComparisonTableWorker`, `CitationListWorker`, `GrammarBreakdownWorker`, `LessonPlanWorker`) with `pytest-qt` test coverage in `test_gui_workers.py`.

---

## Test Suite Verification

- **Python Desktop Suite**: **1,375 / 1,375 tests passing** (`python -m pytest`).
- **Android Companion App Suite**: JVM unit tests (`ModelUnitTest`) passing; Gradle debug build (`./gradlew assembleDebug`) succeeded cleanly.

---

## What Remains for Live Device Testing / Production Run

1. **Android App Live Device Run**: Install `mobile/app/build/outputs/apk/debug/app-debug.apk` on a real Android phone or emulator via `adb install` to test real catalog and book package file imports end-to-end.
2. **Local AI Live Prompting**: Launch the desktop app (`python -m islamic_research_hub.interfaces.desktop_app`) and test local Ollama (`qwen2.5:14b`) or cloud AI providers on real research queries.
