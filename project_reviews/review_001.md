# Review 001 — Phase 9, Milestone 2: Local Voice Search

## What was built

Speak a search query instead of typing it. A mic button in the Search
screen's query row records a short spoken query, transcribes it locally
(no cloud service), and feeds the transcript into the app's existing
keyword search pipeline — same results a typed query would produce. Off
by default; a user must opt in via a Settings toggle, since it implies an
optional local model download.

Follows the same design pattern already established by semantic search
and text-to-speech (Milestone 1): a background thread does the slow work
(model load + transcription) so the UI never freezes, and any failure
(missing dependency, model load error, no microphone) degrades gracefully
— typed search keeps working unaffected, nothing crashes.

While verifying the feature end-to-end against the real production
database (not just isolated tests), three real bugs were found and fixed:

1. An already-shipped bug in the text-to-speech feature (Milestone 1)
   that would have prevented a brand-new install from ever downloading
   its voice models — only masked, in prior testing, by models already
   being cached from earlier work.
2. A pre-existing crash in title search (unrelated to voice search) that
   any punctuated query — typed or spoken — could trigger.
3. Voice transcripts carrying automatic punctuation (added by the speech
   model) that defeated search entirely even after the crash above was
   fixed, since the search engine treats certain punctuation as special
   syntax.

## Files changed

New:
- Voice transcription application service (query validation + delegation)
- Local speech-to-text adapter (faster-whisper integration)
- Microphone audio format conversion helper
- Background worker thread for transcription
- Two new test files covering the above

Modified:
- Search screen (mic button, recording flow, wiring to the worker)
- Settings screen (new toggle, persisted preference)
- Main window (wires the setting into the search screen at startup)
- Translation strings (English/Urdu/Arabic, new setting label)
- Icon set (new microphone icon)
- Theme (new color export for the "recording" visual state)
- Text-to-speech adapter (bug fix, see above)
- Title search repository (crash fix, see above)
- Dependency manifest (new optional install group for this feature)
- CHANGELOG.md / PROJECT.md (milestone documentation)

## Architecture changes

None. Voice search follows the exact same layered pattern already used
by semantic search and text-to-speech: an application-layer service
behind a swappable interface, a concrete local-model adapter, and a
background-thread worker in the desktop UI layer. No new architectural
concept was introduced.

## Database changes

None.

## UI changes

- New microphone button in the Search screen's query row, visible only
  when the feature is enabled in Settings.
- Three visual states: idle, recording (red-tinted icon), transcribing
  (button disabled).
- Status text area now also reports "Listening..." and "Transcribing..."
  during a voice search, reusing the existing status label.
- New "Search by speaking" checkbox in Settings, off by default.

## Tests run

- 19 new automated tests added (application-layer transcription logic,
  audio format conversion, and desktop UI wiring/behavior).
- Full project test suite run after every change: 676 of 676 tests
  passing.
- Manual end-to-end verification against the real, live production
  database (not a test fixture): synthesized speech in English, Arabic,
  and Urdu was fed through the fully-wired Search screen and produced
  real search results with no crashes in any language.

## Remaining issues

- Speech recognition accuracy for short Arabic/Urdu phrases is
  noticeably weaker than for English or for longer phrases, using the
  current (smaller, faster) model. This matches an earlier finding from
  this same investigation and was an accepted, stated tradeoff, not an
  oversight — but it means very short spoken queries in Arabic/Urdu may
  need a repeat attempt.
- No confirm-before-searching step — a successful transcript searches
  immediately. Intentional for this milestone, matching how text-to-speech
  auto-plays once ready, but worth revisiting if users find it too eager.
- No hands-free/continuous listening — press-to-record only.
- Voice search is not available inside the book reader/viewer, only on
  the main Search screen.
- Cloud speech-to-text (as a faster/more accurate optional upgrade) was
  not built — local-only for now, consistent with this project's
  default-to-local AI policy.

## Next recommendations

1. Get real human-spoken (not synthesized) test recordings in each
   language before considering this feature "field tested" — everything
   verified so far used synthesized speech round-tripped through the
   text-to-speech feature, which is a reasonable stand-in but not the
   same as a real voice, accent, or background noise.
2. If Arabic/Urdu accuracy on short queries proves frustrating in real
   use, evaluate the next-larger speech model — slower per query, but
   meaningfully more accurate per earlier testing.
3. Decide whether the previously-discussed "AI Agent" (natural-language
   query understanding, tool-calling, multi-provider AI support) work
   should begin next, per the direction already agreed: voice search was
   the explicit prerequisite to finish first.
4. Push the completed, committed work to GitHub when ready — it is
   currently committed locally only.
