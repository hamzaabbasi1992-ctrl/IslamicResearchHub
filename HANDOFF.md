# Handoff

Read this first if you're a different AI tool (or a fresh chat) picking up this project cold. Also read `PROJECT.md` (architecture + full phase roadmap) and `CLAUDE.md` (working rules for this project) before making changes.

This file is overwritten each time, not appended to - it always reflects the current real state, not a history. For history, see `CHANGELOG.md`.

## ⚠️ MACHINE SWITCH IN PROGRESS - read this section first

As of 2026-08-12, the user is moving this project to a **new Windows 11 laptop**. This session ran on the old machine (drives `F:` and `J:` below).

**Explicit decision made this session: the user does NOT want `F:`'s 157GB `books.db` copied to `J:` (or anywhere else) as part of this handoff.** An attempt to robocopy it from `F:` to `J:` was started and the user immediately interrupted it ("NO NO DONT COPY 157 GB THERE") - it was stopped mid-copy, the partial file deleted, and `J:`'s own original `books.db` (which had been renamed aside as a safety backup first) was restored byte-for-byte. **Do not re-attempt copying the full `F:` database anywhere without the user asking for it again.** When asked afterward how they *did* want the 66-row extraction (Volumes 1-3) carried to the new laptop, the user chose: **"Skip the DB for now" - start the new laptop with just the code + this HANDOFF.md from git, and deal with the database (re-extract, or bring it over some other way) later, separately.**

Practical consequence for whoever picks this up on the new laptop: **assume the new laptop's `books.db` does NOT contain the Volumes 1-3 `EventCandidates` rows** (14 + 17 + 35 = 66 total) unless the user says otherwise. Don't silently start Volume 4 assuming Volumes 1-3's data is present - check first (`SELECT COUNT(*) FROM EventCandidates WHERE BookID IN (322,418,474)`), and if it's empty, ask the user whether they still have `F:`'s copy accessible (old laptop, external drive, etc.) before deciding whether to re-run Volumes 1-3's extraction from scratch or wait for them to bring the data over.

What *did* carry over cleanly via git (pushed to `origin`, `https://github.com/hamzaabbasi1992-ctrl/IslamicResearchHub.git`, branch `handoff/waqiat-encyclopedia-session` - a plain `git clone`/`git pull` on the new laptop gets all of this with no extra steps):
- The source code and this HANDOFF.md.
- `Waqiat_Encyclopedia_Deliverables/` (new folder in the repo root) - the small Volume 1-3 `.docx`/`.html` output files (a few MB total, copied over from the old machine's Desktop) - these are just the already-generated encyclopedia documents, not the underlying database, but they're a readable/shareable record of what was extracted even before the database itself makes the trip.

Still not carried over, and will need separate handling whenever the user is ready:
- `F:\ISLAMIC RESEARCH HUB AI\data\books.db` (~157GB, the authoritative one, holds all 66 `EventCandidates` rows) - deliberately NOT copied this session, see above.
- `J:\ISLAMIC RESEARCH HUB AI\data\books.db` (~25GB) - a separate, older, smaller copy from a *different* prior laptop; left untouched/restored to its original state. Do not confuse it with the F: copy. See "Note on J: vs F: drive" below (now a 3-way question: F: laptop, J: laptop, new Win11 laptop).
- MCP server config - the `islamic-research-hub` MCP server's configured database path (pointing at `F:\...\data\books.db` on the old machine) will need re-pointing once/if a database lands on the new laptop.
- `maktaba://` protocol handler - a per-machine Windows registry entry (`HKCU\Software\Classes\maktaba`, see rule #9 below); will need re-registering on the new laptop before those links work there.

## Current Objective: Waqiat Encyclopedia from اصلاحی خطبات (Islahi Khutbat)

The user is building a "Waqiat Encyclopedia" (انسائیکلوپیڈیا) - every real anecdote/incident (واقعہ) narrated inside Mufti Muhammad Taqi Usmani's 18-volume **اصلاحی خطبات** (book_ids 322, 418, 474, 479, 532, 546, 548, 571, 678, 746, 829, 933, 1040, 1103, 1210, 1320, 1704, 1705 in `F:\ISLAMIC RESEARCH HUB AI\data\books.db`, Maktaba Jibreel Mobile), pulled out into structured entries with citations.

**Explicit instruction: no paid LLM API calls.** The assistant reads the real page text itself (via direct SQLite queries or the `islamic-research-hub` MCP server) and does the extraction by hand, in-conversation. This was a deliberate correction from the user after an initial plan to batch-call a paid API - do not revert to that.

### Rules established so far (apply to every remaining volume)

1. **Output language: fully Urdu, no English.** Title, subject, bayan name, citation, everything - only the `matn` (full quoted text) was ever in Urdu anyway, but labels/headings must be Urdu too.
2. **Every entry must have:** `title` (عنوان), `subject` (موضوع - the topic/theme), `bayan` (بیان کا نام - which sermon/lecture within the volume it was told in, found via the `<urh1>...ضبط و ترتیب...</urh1>` chapter-marker pages), `citation` (book + page), `figures` (کردار/راوی), and `matn`.
3. **`matn` must be the COMPLETE verbatim waqia, copied in full from the real page text - never a truncated excerpt or a paraphrased summary.** This was a hard correction from the user ("copy paste complete waqia not a para only"). Read enough page context around a keyword hit to find the real start/end of the story before extracting it.
4. **Include EVERYTHING, including well-known/Qur'anic stories** (e.g. Ibrahim & Isma'il's sacrifice) - do not skip a real waqia just because it's already famous. (This is a change from the Volume 1/2 pass below, which *did* skip a few for exactly that reason - those two volumes need a re-pass to add what was skipped.)
5. **Mark recurring waqiat.** This shaykh retells some stories across multiple volumes (already confirmed: the Abu Bakr/Umar "loud vs quiet tahajjud recitation" hadith appears in both Vol 1 pages 220-222 and Vol 2 pages 141-142; Dr. Abdul Hai's "if the head of state summoned you" motivation story appears in both Vol 1 pages 78-79 and Vol 2 pages 252-253). Going forward, **do not silently skip a repeat** - include it as its own entry, but add a note stating exactly where else (volume + page) and how many times it has appeared before. Volumes 1 and 2 below need a re-pass to add this cross-referencing (Vol 2's pass silently dropped the repeats instead of noting them - fix this).
6. **Extraction method per volume:** find bayan (chapter) boundaries via pages containing `ضبط و ترتیب` (or the equivalent title-page pattern), find candidate pages via `SELECT PageNo, Content FROM Pages WHERE BookID=? AND Content REGEXP-like 'واقع(ہ|ات|ے|ہات)'` (Python re, not SQL - see pattern in the build scripts), then read each hit ±2 pages of real context before writing the entry.
7. **Storage:** every entry gets inserted into the app's own `EventCandidates` table (`BookID, ChunkStartPage, ChunkEndPage, Title, ExtractedDataJson, Status='pending'`) in `F:\ISLAMIC RESEARCH HUB AI\data\books.db` - this is the *same* table/schema the app's built-in (never-yet-used) "Extract Events" feature uses, so results show up in the app's own Event Manager screen for the user to confirm/dismiss. Re-running a volume's build script does `DELETE FROM EventCandidates WHERE BookID=?` first, so it's safe to re-run.
8. **Deliverables per volume:** (a) a Word doc `واقعات انسائیکلوپیڈیا - اصلاحی خطبات جلد X.docx` on the Desktop (RTL, Arial, one section per waqia: title/subject/bayan/citation/figures/full matn), and (b) a full-book verification HTML `مکمل جلد X - تصدیق و مکمل مطالعہ.html` on the Desktop, showing literally every real page of that volume (fetched fresh from the DB) with the extracted waqia's pages highlighted - lets the user manually confirm nothing was missed. Both link to each other.
9. **Deep links: use `maktaba://open?book=<id>&page=<n>`, not a `file://` workaround.** The desktop app already has a real, working `maktaba://` protocol handler (`shared/maktaba_link.py`, registered in `HKCU\Software\Classes\maktaba` -> `open_maktaba_link.bat` -> `python -m islamic_research_hub.interfaces.desktop_app <link>` -> `MainWindow.open_book_at_page()`). Every waqia's Word-doc entry should carry a `maktaba://` hyperlink to its start page, in addition to the full-book HTML link. **Not yet visually confirmed to actually open the app** - the sandboxed tool environment can't see a GUI window opening. Ask the user to click one and confirm before trusting it further.
10. Build scripts live in the scratchpad (session-specific temp dir, will not survive to a new chat) - the *data* they produce (EventCandidates rows in `books.db`, and the Desktop docx/HTML files) is what persists. A new chat will need to recreate the Python build scripts using the conventions above, not reuse the old scratchpad files.

### Newly available MCP tools (user just registered ~20 more on the `islamic-research-hub` server) - worth using instead of hand-rolled scripts going forward

- **Collections**: `create_collection`, `add_to_collection`, `remove_from_collection`, `list_collections`, `list_collection_items`, `rename_collection`, `delete_collection`, and critically **`export_collection_to_docx`** - the app already has a built-in "save a collection of book/page items as a real cited .docx" feature. This may be a cleaner way to produce the per-volume Word doc than the custom python-docx script used for Volumes 1-2 - worth evaluating first in the new chat rather than defaulting back to the custom script.
- **Notes/quotations**: `create_note_document`, `save_quotation` (append a quotation+citation to a note doc), `list_note_documents`, `find_notes_mentioning_book`.
- **Bookmarks**: `add_bookmark`, `remove_bookmark`, `list_bookmarked_pages`, `list_recent_bookmarks`.
- **Citation candidates** (unrelated to this task, pre-existing app feature): `list_citation_candidates`, `count_citation_candidates`, `dismiss_citation_candidate`.
- **Export**: `export_answer_to_docx`, `export_article_to_docx` (sections+sources -> docx), `export_collection_to_docx`.
- **`get_open_link`**: returns the `maktaba://` link for a book_id+page_number (confirmed matches `shared/maktaba_link.py::build_maktaba_link` exactly).

Worth a deliberate evaluation pass at the start of the new chat: does `export_collection_to_docx` already produce something as good as (or better than) the custom Urdu RTL docx builder? If so, switch to it and stop maintaining the custom script.

### Progress

- **Volume 1** (book_id 322, 241 pages): 14 waqiat extracted and saved (EventCandidates + Desktop docx/HTML). Built under the *old, narrower* rules (skipped a couple of borderline/Qur'anic items, silently dropped nothing duplicate since none were found yet at that point).
- **Volume 2** (book_id 418, 263 pages): 17 waqiat extracted and saved. Built after the "complete verbatim + Urdu-only" rules were established, but *before* the "include everything" and "mark recurring waqiat" rules (#4 and #5 above) - it silently skipped the Ibrahim/Isma'il qurbani narrative and silently dropped the two repeat stories instead of cross-referencing them. **Needs a re-pass** to add those back in under the current rules.
- **Volume 3** (book_id 474, 254 pages): **done**, 35 waqiat extracted and saved (EventCandidates rows inserted + Desktop docx/HTML built), under the *current, full* rule set (include-everything + would-cross-reference-repeats-if-found). No repeats of the two known Vol1/Vol2 recurring stories (Abu Bakr/Umar tahajjud; Dr. Abdul Hai "head of state") turned up in this volume, and no internal (within-Vol3) repeats were found either, so no cross-reference notes were needed this time. Bayan boundaries, all 35 titles/citations, and the full extraction reasoning (including the ~9 borderline items deliberately excluded as general habits/doctrinal teaching rather than discrete incidents) are preserved in this session's transcript, not just here - re-derive from the DB with the same `ضبط و ترتیب` + regex method if picking this up fresh.
- **Volumes 4-18**: not started.

### Immediate next steps for the new chat

1. Confirm with the user whether the `maktaba://` link actually opened the app when they clicked it (rule #9) - still not confirmed as of the Volume 3 session.
2. `export_collection_to_docx` was evaluated during the Volume 3 session and rejected as a replacement for the custom docx builder: it dumps raw per-page content for each collection item, not the curated title/subject/bayan/citation/figures/matn structure this task needs - keep using the custom python-docx script (its exact paragraph/style/hyperlink structure was reverse-engineered from the Volume 2 docx and should be reused as-is for consistency).
3. Re-pass Volumes 1 and 2 to add previously-skipped Qur'anic/well-known waqiat, and to add explicit cross-reference notes on the two known repeats (Abu Bakr/Umar tahajjud story; Dr. Abdul Hai's "head of state" story) plus any others found.
4. Continue with Volume 4 (book_id 479, page count not yet checked) onward, same method as Volume 3.

---

## Prior Objective (completed, unrelated to the above)

All v1.0 core engine phases (1-7) and post-v1.0 roadmap phases (8 through 20) are **complete, tested, and verified** - see full detail previously in this file, now summarized:

- Phase 20 (Scholarly Review), Phase 18 (Android Companion App, APK built), Phase 16 (AI Content Generators), Phase 12 (Translation & Linguistics), Phase 15 (Educational Features), Phase 10 (Knowledge Graph/Encyclopedia builder/Contradiction detector), Phase 8.5 (Data Quality Diagnostics), Phase 19 (Developer Public API), and PySide6 Desktop GUI Background Workers are all complete.
- Python Desktop Suite: 1,375/1,375 tests passing. Android JVM unit tests passing; Gradle debug build succeeded.
- Still open from that phase of work: Android live-device install/test (`adb install` the debug APK), and live local-AI/cloud-AI prompting test.

## Note on J: vs F: drive (now a 3-way question with the new laptop)

This session ran primarily against **F:\ISLAMIC RESEARCH HUB AI** (books.db there is 157GB, has the mcp_server module, has the newer `maktaba_link.py`/protocol-handler code). The working directory the harness opened is **J:\ISLAMIC RESEARCH HUB AI** (25GB books.db, no mcp_server module - it's an older copy from a different laptop, per the user). These are two different git repos (different `.git`, different volume) on the *same* old machine. This was flagged to the user earlier but never resolved/merged.

Now that a **third** copy is about to exist (whatever ends up on the new Win11 laptop, per the section above), don't just repeat the same unresolved ambiguity a third time - ask the user directly, before touching source code again, which copy is meant to be canonical going forward (most likely: bring `F:`'s newer code + a copy of `F:`'s books.db over to the new laptop and retire both old copies, but confirm rather than assume).
