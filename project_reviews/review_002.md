# Review 002 — Research Notes (Save Quotations to Word Documents)

## What was built

A way to collect quotations from any book straight into a real Microsoft
Word document while reading, without leaving the app. Select text on a
reader page, right-click, and choose one of four new options:

- **Copy** — copies the selected text as usual.
- **Copy with Citation** — copies the selected text plus a formatted
  citation (book, page, paragraph).
- **Save to Research Notes** — appends the selected text, with full
  citation details, to a Word document of your choosing (or a brand-new
  one).
- **Open Current Notes** — opens the most recently used note document
  directly in Word, so the loop of reading, quoting, and writing stays
  fast without hunting for the file. (Added mid-build at your suggestion.)

Every note document lives under `Documents/Maktaba Research Notes/` on
this computer. Existing content in a document is never overwritten —
every save appends to the end. If a document is currently open in Word,
the app shows a plain message asking you to close it first, instead of
crashing.

This was built to a detailed specification you provided, including the
exact append format, error handling, and a deliberate "keep it minimal"
constraint (no database, no cloud sync, no AI, no rich text editor).

## Files changed

New, self-contained feature folder (kept separate from the rest of the
app's code, as specified):
- Notes manager (decides what happens: list documents, create one,
  append a quotation, remember the most recently used one)
- Word document writer (the only file that actually touches `.docx`
  files on disk)
- The on-screen dialog (the document picker / "create new" prompt)
- Three new test files covering all of the above

Modified:
- Book reader screen (new right-click menu wired to the four actions
  above)
- Dependency manifest (added the library used to read/write Word
  documents)
- CHANGELOG.md / PROJECT.md (feature documentation)
- One existing test file (new right-click menu test cases)

## Architecture changes

None to the app's existing structure. This feature was deliberately kept
in its own isolated folder rather than spread across the app's usual
layers, per your explicit instruction. Internally it does follow the same
"swappable component" pattern already used elsewhere in the app (for
text-to-speech and voice search) — the part that actually writes to Word
documents is written so a future version could swap in Google Docs,
Google Drive, OneDrive, or Dropbox without changing anything else. That
swap itself was not built — only the seam for it, as requested.

## Database changes

None. Note documents are plain files on disk, not database records. The
app remembers which document you used most recently using the same
lightweight settings mechanism already used elsewhere in the app (e.g.
for remembering your theme preference).

## UI changes

- New four-item right-click menu on the reader's text area.
- "Copy", "Copy with Citation", and "Save to Research Notes" are greyed
  out when no text is selected; "Open Current Notes" is always available.
- "Save to Research Notes" opens a small dialog: a list of your existing
  note documents (if any) plus a "+ Create New Notes" button. Choosing an
  existing document or creating a new one immediately saves the quotation
  and closes the dialog.
- If a chosen document is currently open in Word, a plain warning message
  appears instead of the save silently failing or the app crashing.

## Tests run

- 24 new automated tests added, covering: real Word document
  creation/appending (using the real document-writing library, not a
  simulation), filename collision handling, the "document is open
  elsewhere" error path, the notes manager's logic, the chapter-lookup
  logic used to fill in citation details, the on-screen dialog's
  behavior, and the reader's new right-click menu wiring.
- Full project test suite run afterward: 702 of 702 tests passing.
- Manual, real-world verification: created an actual Word document in
  the actual `Documents/Maktaba Research Notes/` folder on this computer,
  appended two real quotations to it, confirmed the file's contents
  matched the required format exactly, then removed the test file
  afterward so nothing was left behind.

**One real bug found and fixed during that manual verification**: the
feature's "remember the most recently used document" setting was not
reliably saving — it used a slightly different internal mechanism than
the rest of the app, which caused it to sometimes forget. Fixed to match
how every other remembered setting in the app already works, and
re-verified it now correctly survives even after the app is fully closed
and reopened.

## Remaining issues

- No confirmation message after a quotation is saved — the dialog simply
  closes. This matches your "keep it minimal" instruction, but is worth
  a second look if it ever feels unclear whether a save succeeded.
- The "current chapter" shown in a citation is determined automatically
  from the book's table of contents and the page you're on. For books
  with no table of contents, or where you're on a page before the first
  listed chapter, this field is simply left out — never guessed.
- No way yet to rename, delete, or manage note documents from inside the
  app — that's done directly in Windows/Word, outside the app, by design
  (matches "no project management" from your spec).
- Not yet tested with a real, live Microsoft Word instance actually
  holding a document open at the same time — the "file is open" warning
  was verified using a simulated failure, not a real side-by-side Word
  session. Worth a real hands-on check.

## Next recommendations

1. Do one real hands-on test: open a note document in Word, then try to
   save a new quotation to it from the app, and confirm the warning
   message appears exactly as expected.
2. If it turns out you frequently want to jump back to a *specific* past
   document (not just the most recent one), a small "recent documents"
   list (not just a single "current" one) could be a cheap future
   addition — not built now, since it wasn't asked for.
3. This is a good candidate to try in real research use for a while
   before deciding whether it needs anything more (a save confirmation,
   multiple recent documents, etc.) — much of this feature's real value
   will only become clear from actually using it.
