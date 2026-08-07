# Handoff

Read this first if you're a different AI tool picking up this project
cold. Also read `PROJECT.md` (architecture + full phase roadmap) and
`CLAUDE.md` (working rules for this project) before making changes.

This file is overwritten each time, not appended to - it always reflects
the current real state, not a history. For history, see `CHANGELOG.md`.

The user is switching AI tools now (moving to Antigravity IDE) - this
handoff was written specifically for that switch, mid-way through
Phase 18's mobile app work, at a genuine "build succeeds" checkpoint.

## Current objective

Phase 18 (Android companion app), Milestone 2: the Kotlin/Compose/Room
mobile app itself. A real, minimal first slice (catalog import + browse,
via Room reading a desktop-exported SQLite file) is built and verified
via a real `gradlew assembleDebug` success - a real 10.2MB debug APK
was produced. **Not yet installed/run on a real device or emulator** -
compiling successfully proves the code and dependency versions are all
correct together, not that the app behaves correctly at runtime.

## What was completed (this session, most recent first)

This was a very long session - many real milestones shipped across
several different areas. Full detail for all of them is in
`CHANGELOG.md`; here's what's most relevant to continuing right now:

- **Phase 18, Milestone 2 (in progress, real checkpoint reached)**: see
  "Current objective" above and "What remains to do" below.
- **Real addition: Ollama as a 4th AI Agent provider** - local models
  instead of paid cloud API calls, tool-calling-capable models only
  (the whole AI Agent architecture depends on real tool-calling for
  grounded citations). `qwen2.5:14b` was chosen for the user's real
  hardware (Quadro T1000, 4GB VRAM, 32GB RAM) and is fully downloaded
  and configured - Settings already has `ai_agent/enabled=true`,
  `ai_agent/provider=ollama`, `ai_agent/ollama_model=qwen2.5:14b` (set
  directly via the app's own `QSettings` API, registry-backed at
  `HKEY_CURRENT_USER\Software\IslamicResearchHub\DesktopApp`). **Not
  yet live-tested** - the user hasn't asked it a real question through
  the app yet.
- **4 real UX fixes reported directly by the user via screenshots**:
  nav rail group tabs moved to a top menu bar + icons gained text
  labels (matching Shamila/Jibreel's convention); reader auto-sizes to
  ~half the workspace width on opening a book; reader toolbar's 7
  AI-generation buttons grouped into a collapsible second row (a real
  `QMenu`/`QWidgetAction` attempt was tried and reverted - it broke
  every visibility test, since Qt reports widgets inside an unshown
  popup as `isHidden()` regardless of their own explicit state; used a
  real sibling `QWidget` toggle instead, mirroring the nav rail's
  already-proven pattern).
- **Phase 16, Milestone 2**: real AI-generated lecture notes (chunked
  generation, mirrors Slide Deck's architecture, exports to `.docx`).
- **Phase 15, Milestone 3**: real SM-2 spaced-repetition scheduling for
  flashcards (`application/spaced_repetition.py`, pure/DB-free).
- **Phase 14, Milestones 2+3**: saved searches, saved AI conversations
  - Phase 14 is now fully complete.
- **Phase 12, Milestone 2**: real direct Arabic↔Urdu translation via
  `facebook/m2m100_418M` (no English pivot).

## Files changed (this session)

Far too many to list individually (see `git log` and `CHANGELOG.md` for
the full real history - every commit this session is small and
individually well-described). Most recent commit: `5f1188d`.

New this session, most relevant to continuing right now:
- `mobile/` - the entire new Android Studio Gradle project (Kotlin +
  Jetpack Compose + Room). Real files: `mobile/app/build.gradle.kts`,
  `mobile/build.gradle.kts`, `mobile/settings.gradle.kts`,
  `mobile/gradle.properties`, the real Gradle wrapper (`gradlew`,
  `gradlew.bat`, `gradle/wrapper/`), `mobile/app/src/main/
  AndroidManifest.xml`, `mobile/app/src/main/res/values/{strings,
  themes}.xml`, and the Kotlin sources under `mobile/app/src/main/
  java/com/islamicresearchhub/companion/`:
  - `MainActivity.kt` - the one real screen so far (catalog import +
    browse).
  - `data/local/{BookEntity,LibraryEntity,PageEntity,ChapterEntity}.kt`
    - Room entities, exact real column names matching the desktop's
      export schema.
  - `data/local/{CatalogDatabase,BookPackageDatabase}.kt` - Room
    databases, each opens its real pre-populated SQLite file via
    `createFromFile()`.
  - `data/local/{CatalogDao,PageDao}.kt` - Room DAOs.
- `src/islamic_research_hub/infrastructure/ai/ollama_llm_provider.py` -
  the Ollama LLM provider adapter (reuses `openai_llm_provider.py`'s
  translation logic - Ollama speaks the identical OpenAI-compatible
  wire format).
- `mobile/local.properties` (gitignored, real machine-specific SDK
  path - already correctly set to `F:\android studio downloads`, no
  action needed unless this exact machine's SDK location changes).

Modified: `src/islamic_research_hub/interfaces/book_package_export_cli.py`
(real fix: `Pages`/`Chapters` now have a real declared primary key,
required by Room - was previously a real gap, undetected until the
Kotlin Room entities were written against it), plus the usual
`.gitignore`/`PROJECT.md`/`CHANGELOG.md`/`i18n.py` updates that
accompany every real milestone in this project.

## Current state of the code

- **Python desktop app**: full test suite 1320/1320 passing. Local
  git and `origin/main` are in sync (nothing uncommitted except a few
  pre-existing, unrelated untracked files - `.claude/`,
  `docs/duplicate_analysis/*.xlsx`, `screenshots of app for other ai/`
  - none of which are this session's work, leave them alone).
- **Mobile app**: `mobile/` builds successfully via
  `gradlew assembleDebug` (real APK produced, see below for the exact
  environment variables needed to reproduce this). Not yet run on a
  device/emulator. No automated tests exist for the Kotlin code yet
  (matches this project's own precedent of not unit-testing thin
  adapter/UI layers where a real external dependency - here, a real
  Android runtime - would be needed to test meaningfully; this is a
  genuinely new area for this project, worth a real decision on
  whether/how to add Kotlin tests going forward).

### Reproducing the mobile build

The real Android SDK and Android Studio's own JDK are both on F:\
drive (**not** in default locations - this matters, don't assume
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

A full, separately-downloaded Gradle 9.7.0 distribution also exists at
`F:\gradle-dist\gradle-9.7.0\` (used once to bootstrap the wrapper
itself - the project's own `gradlew` is now self-sufficient and this
extra copy isn't needed for normal builds, but it's there if the
wrapper ever needs regenerating).

### Ollama (local AI)

`ollama.exe` is at `C:\Users\DELL\AppData\Local\Programs\Ollama\
ollama.exe` (not on PATH in at least some shells on this machine - use
the full path if a bare `ollama` command isn't found). Model
`qwen2.5:14b` (9.0GB) is fully downloaded and confirmed present via
`ollama list`. The Islamic Research Hub desktop app's Settings are
already configured to use it (see above) - opening the app and asking
a real question through the AI panel or "AI Tools" should now route
through this local model. This has not actually been tried yet.

## What remains to do

**Immediate / most concrete next step**: build the remaining Compose
screens for the mobile app - `BookDetailScreen.kt`, `BookReaderScreen.kt`,
`ChapterListScreen.kt` (per the original plan, still describes the
intended shape even though its exact file wasn't carried into this
repo - see "Design notes" below for the essentials). The Room layer
for book packages (`BookPackageDatabase`/`PageDao`) is already built
and ready; only the UI to call it is missing. After adding real
navigation (Jetpack Navigation Compose is already a dependency:
`androidx.navigation:navigation-compose`), re-run
`gradlew assembleDebug` to confirm it still builds, the same real way
this session's slice was verified.

**Also open**:
- Install/run the mobile app on a real device or emulator - never done
  yet, only compilation has been verified.
- Live-test Ollama through the desktop app with a real question.
- Phase 12: word-by-word breakdown, grammar notes, root-word analysis
  (Arabic morphology) - still open within that phase.
- Phase 15: lesson plans, "teaching mode" view - still open.
- Phase 16: khutbah outlines, research-paper drafts, book reviews,
  comparison tables, citation lists - other AI-generated document
  types, still open.
- Several already-shipped features across this whole project remain
  automated-tested only, not live-tested with real API keys/models by
  the user yet (Gemini/OpenAI/Anthropic-backed AI Agent features, TTS,
  MarianMT/M2M100 translation). See `CHANGELOG.md` for the complete,
  real list - don't assume "shipped" means "user-verified working."

### Design notes for the remaining mobile screens

Real schema each screen needs to work against (both databases share
`Books`/`Libraries`; `book_<id>.db` additionally has `Pages`/`Chapters`):
- `BookDetailScreen`: shown after tapping a book in the catalog list.
  Needs an "Import this book" action (SAF picker again, same pattern
  as `MainActivity.kt`'s catalog import) that calls
  `BookPackageDatabase.open(context, bookId, sourceFile)`, or, if
  `BookPackageDatabase.isImported(context, bookId)` is already true,
  goes straight to the reader.
- `ChapterListScreen`: `PageDao.listChapters()` - a real, flat list for
  now (nested/parent-child chapter hierarchy via `ParentChapterID` is a
  real "nice to have," not required for a first working version) -
  tapping a chapter jumps the reader to its `PageNo`.
- `BookReaderScreen`: `PageDao.listPages()` ordered by `PageNo`,
  displayed as scrollable real page content. Real Arabic/Urdu RTL text
  needs `LayoutDirection.Rtl` applied at the text-composable level
  (matches how the desktop app's own reader already handles this -
  see `viewer_screen.py`'s `RTL_TEXT_STYLE` for the equivalent desktop
  pattern, though the mobile implementation will obviously be Compose-
  native, not a literal port).

## Known issues

- None open in the sense of "broken and left broken." Every real build
  failure hit while bootstrapping the mobile app was root-caused and
  fixed (see `CHANGELOG.md`'s Phase 18 Milestone 2 entry for the full
  list of version-compatibility issues found and fixed - AGP/Kotlin/
  KSP/Room versions all needed real bumps past what older training
  data would assume, since this is a genuinely new, 2026-era Android
  toolchain generation).
- Real thing to watch for: this SDK/AGP/Gradle/Kotlin/Room version
  combination was arrived at empirically, through real trial and
  error against real build failures - it is NOT necessarily "the"
  correct/recommended combination, just a confirmed *working* one on
  this specific machine's toolchain as of 2026-08-07. If a future
  change to any of these versions is needed, expect similar real
  compatibility debugging, not a clean drop-in upgrade.

## Exact next step

Build `BookDetailScreen.kt`/`BookReaderScreen.kt`/`ChapterListScreen.kt`
with real Navigation Compose wiring from `MainActivity.kt`'s catalog
list, using the already-built `BookPackageDatabase`/`PageDao`. Verify
with a real `gradlew assembleDebug` after, the same way this session's
slice was verified - don't skip that step even for what looks like a
straightforward addition, given how many real version-compatibility
surprises this exact toolchain generation produced already.
