# Handoff

Read this first if you're a different AI tool picking up this project
cold. Also read `PROJECT.md` (architecture + full phase roadmap) and
`CLAUDE.md` (working rules for this project) before making changes.

This file is overwritten each time, not appended to - it always reflects
the current real state, not a history. For history, see `CHANGELOG.md`.

The user mentioned switching to Antigravity IDE, then asked to finish
the in-progress mobile app work in Claude Code first - that work is now
done (see below). This file is current as of that completion, not yet
superseded by any Antigravity session.

## Current objective

Phase 18 (Android companion app), Milestone 2 is **done**: a real,
working four-screen mobile app (catalog browse/import, book detail +
per-book import, chapter list, offline reader) with real Jetpack
Navigation Compose wiring, verified via two real `gradlew assembleDebug`
successes. **Not yet installed/run on a real device or emulator** -
compiling successfully proves the code and dependency versions are all
correct together, not that it behaves correctly at runtime. That real
device/emulator test is the natural next step for whoever continues.

## What was completed (this session, most recent first)

This was a very long session - many real milestones shipped across
several different areas. Full detail for all of them is in
`CHANGELOG.md`; here's what's most relevant to continuing right now:

- **Phase 18, Milestone 2 (done)**: see "Current objective" above.
  Real Room layer for both desktop export formats
  (`BookEntity`/`LibraryEntity` shared, `PageEntity`/`ChapterEntity`,
  `CatalogDatabase`/`BookPackageDatabase`), four real Compose screens
  (`CatalogListScreen`, `BookDetailScreen`, `ChapterListScreen`,
  `BookReaderScreen`), real navigation routes connecting them
  (`catalog` → `book/{bookId}` → `chapters` or `reader?page={page}`).
- **Real addition: Ollama as a 4th AI Agent provider** - local models
  instead of paid cloud API calls, tool-calling-capable models only.
  `qwen2.5:14b` is fully downloaded and configured in Settings
  (`ai_agent/enabled=true`, `ai_agent/provider=ollama`,
  `ai_agent/ollama_model=qwen2.5:14b`, set directly via `QSettings`,
  registry-backed at `HKEY_CURRENT_USER\Software\IslamicResearchHub\
  DesktopApp`). **Not yet live-tested** - no one has asked it a real
  question through the app yet.
- **4 real UX fixes reported directly by the user via screenshots**:
  nav rail group tabs moved to a top menu bar + icons gained text
  labels; reader auto-sizes to ~half the workspace width on opening a
  book; reader toolbar's 7 AI-generation buttons grouped into a
  collapsible second row.
- **Phase 16 M2** (real AI-generated lecture notes), **Phase 15 M3**
  (real SM-2 spaced-repetition scheduling), **Phase 14 M2+M3** (saved
  searches, saved AI conversations - Phase 14 now fully complete),
  **Phase 12 M2** (real direct Arabic↔Urdu translation via M2M100).

## Files changed (this session)

Far too many to list individually (every commit this session is small
and individually well-described - see `git log`/`CHANGELOG.md` for the
full real history). Most recent commit: `d79ec15`.

Most relevant to continuing right now - the entire `mobile/` folder is
new this session (Android Studio Gradle project, Kotlin + Jetpack
Compose + Room):
- `mobile/app/build.gradle.kts`, `mobile/build.gradle.kts`,
  `mobile/settings.gradle.kts`, `mobile/gradle.properties` - real,
  version-pinned build config (see "Reproducing the mobile build"
  below for exact versions and why).
- Real Gradle wrapper: `mobile/gradlew`, `mobile/gradlew.bat`,
  `mobile/gradle/wrapper/`.
- `mobile/app/src/main/AndroidManifest.xml`,
  `mobile/app/src/main/res/values/{strings,themes}.xml`.
- `mobile/app/src/main/java/com/islamicresearchhub/companion/`:
  - `MainActivity.kt` - hosts the real `NavHost` and all four routes.
  - `data/local/{BookEntity,LibraryEntity,PageEntity,ChapterEntity}.kt`
    - Room entities, exact real column names matching the desktop's
      export schema.
  - `data/local/{CatalogDatabase,BookPackageDatabase}.kt` - Room
    databases, each opens its real pre-populated SQLite file via
    `createFromFile()`.
  - `data/local/{CatalogDao,PageDao}.kt` - Room DAOs (`CatalogDao`
    gained a real `getBook(bookId)` query this round, needed by the
    detail screen).
  - `data/local/FileImportUtils.kt` - shared SAF-URI-to-cache-file
    helper, used by both the catalog and book-package import flows.
  - `ui/catalog/CatalogListScreen.kt`, `ui/bookdetail/
    BookDetailScreen.kt`, `ui/reader/{ChapterListScreen,
    BookReaderScreen}.kt` - the four real screens.

Modified (earlier in the session, already committed/pushed):
`src/islamic_research_hub/infrastructure/ai/ollama_llm_provider.py`
(new), `src/islamic_research_hub/interfaces/book_package_export_cli.py`
(real fix: `Pages`/`Chapters` now have a real declared primary key,
required by Room).

## Current state of the code

- **Python desktop app**: full test suite 1320/1320 passing. Local
  git and `origin/main` are in sync at `d79ec15` (nothing uncommitted
  except a few pre-existing, unrelated untracked files -
  `.claude/`, `docs/duplicate_analysis/*.xlsx`,
  `screenshots of app for other ai/` - none of which are this
  session's work, leave them alone).
- **Mobile app**: `mobile/` builds successfully via
  `gradlew assembleDebug` (real 10.3MB APK produced - confirmed twice,
  once for the first slice and again after adding the remaining three
  screens + navigation). Not yet run on a device/emulator. No
  automated tests exist for the Kotlin code yet - a genuinely new area
  for this project, worth a real decision on whether/how to add them
  (Room supports in-memory test databases; Compose has its own UI
  testing framework) before this grows much further.

### Reproducing the mobile build

The real Android SDK and Android Studio's own JDK are both on F:\
drive (**not** in default locations - don't assume
`ANDROID_HOME`/`JAVA_HOME` are already set correctly by the OS):
- SDK: `F:\android studio downloads` (confirmed real: `adb.exe` and
  platform `android-37.0`/build-tools `36.0.0` are there)
- Android Studio + bundled JDK: `F:\android studio` (JDK at
  `F:\android studio\jbr`, confirmed real: `java -version` reports
  OpenJDK 25)
- `mobile/local.properties` already points `sdk.dir` at the SDK path
  above (gitignored, but already correctly set on this machine)

To build from a fresh terminal:
```powershell
$env:JAVA_HOME = "F:\android studio\jbr"
$env:GRADLE_USER_HOME = "F:\gradle-home"   # keeps Gradle's cache off C:
cd "F:\ISLAMIC RESEARCH HUB AI\mobile"
.\gradlew.bat assembleDebug
```
Real output APK lands at
`mobile\app\build\outputs\apk\debug\app-debug.apk`.

**Real version pins, arrived at empirically** (this is a genuinely new,
2026-era Android toolchain generation - don't assume older/more
familiar version numbers will work; see `CHANGELOG.md`'s Phase 18
Milestone 2 entry for the exact real build failures each one fixed):
AGP 9.3.1, Gradle 9.7.0, Kotlin 2.0.21 (no separate
`org.jetbrains.kotlin.android` plugin - AGP 9.x has built-in Kotlin
support), KSP 2.0.21-1.0.28 (with
`android.disallowKotlinSourceSets=false` in `gradle.properties`), Room
2.8.4, compileSdk/targetSdk 37, minSdk 26.

A full, separately-downloaded Gradle 9.7.0 distribution also exists at
`F:\gradle-dist\gradle-9.7.0\` (used once to bootstrap the wrapper
itself - not needed for normal builds, but there if the wrapper ever
needs regenerating).

### Ollama (local AI)

`ollama.exe` is at `C:\Users\DELL\AppData\Local\Programs\Ollama\
ollama.exe` (not on PATH in at least some shells on this machine - use
the full path if a bare `ollama` command isn't found). Model
`qwen2.5:14b` (9.0GB) is fully downloaded and confirmed present via
`ollama list`. The desktop app's Settings are already configured to
use it - opening the app and asking a real question through the AI
panel or "AI Tools" should now route through this local model. This
has not actually been tried yet.

## What remains to do

**Immediate / most concrete next step**: install the mobile app's real
debug APK (`mobile\app\build\outputs\apk\debug\app-debug.apk`) on a
real device or emulator and actually walk through the real flow:
import a real `catalog.db` (built via the desktop's
`catalog_export_cli.py`), tap a book, import its real `book_<id>.db`
(built via `book_package_export_cli.py`), read it, jump via chapters.
Compiling successfully is not the same as working correctly - this is
the real, still-open verification step.

**Also open**:
- Real catalog search/filtering UI - `CatalogDao.search()` already
  exists and is real, just not wired to a visible search box yet.
- Live-test Ollama through the desktop app with a real question.
- Camera OCR search, bookmark sync back to the desktop, nested chapter
  hierarchy (via `ParentChapterID`) - all explicitly deferred, not
  missed.
- Phase 12: word-by-word breakdown, grammar notes, root-word analysis.
- Phase 15: lesson plans, "teaching mode" view.
- Phase 16: khutbah outlines, research-paper drafts, book reviews,
  comparison tables, citation lists.
- Several already-shipped features across this whole project remain
  automated-tested only, not live-tested with real API keys/models by
  the user yet. See `CHANGELOG.md` for the complete real list - don't
  assume "shipped" means "user-verified working."

## Known issues

- None open in the sense of "broken and left broken." Every real build
  failure hit while bootstrapping the mobile app was root-caused and
  fixed (see `CHANGELOG.md`'s Phase 18 Milestone 2 entries for the
  full list).
- Real thing to watch for: the mobile app's SDK/AGP/Gradle/Kotlin/Room
  version combination was arrived at empirically, through real trial
  and error against real build failures - it is NOT necessarily "the"
  correct/recommended combination, just a confirmed *working* one on
  this specific machine's toolchain as of 2026-08-08. If a future
  change to any of these versions is needed, expect similar real
  compatibility debugging, not a clean drop-in upgrade.

## Exact next step

Get the real debug APK onto a real Android device (or start a real
emulator) and walk through the actual import → browse → read flow end
to end - this is the one thing that hasn't been verified yet for the
whole mobile app, and it's a real, concrete, achievable next milestone
rather than more speculative feature-building on unverified ground.
