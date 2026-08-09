# UI Screenshots — My Own Review Notes

Captured directly from the real running app against the real production
database (offscreen rendering, so Arabic/Urdu text shows as placeholder
boxes here — a limitation of this capture environment only, not a real
app bug; the real app on your machine renders real glyphs, as your own
screenshots earlier already showed).

| File | Screen |
|---|---|
| `01_workspace_search_reader_assistant.png` | Search + Reader + Assistant, combined |
| `02_reader_with_real_book.png` | Reader alone, a real page loaded |
| `03_settings.png` | Settings |
| `04_home.png` | Home dashboard |
| `05_duplicate_manager.png` | Duplicate Manager |
| `06_taxonomy_browser.png` | Taxonomy Browser |
| `07_logs.png` | Logs |

## What I'd flag, screen by screen

**Duplicate Manager & Taxonomy Browser** — both leave a large amount of
empty gray background on a wide window: the real content (a table, a
tree) sits in a fixed-width region and nothing fills the rest. On a
normal desktop monitor this will look unfinished, not intentionally
spacious. Worth either capping+centering the content column (like the
reader's own `MAX_READING_COLUMN_WIDTH` treatment) or letting the table/
detail pane genuinely stretch to fill available width.

**Taxonomy Browser's detail pane has no empty state at all** — it's
just blank when nothing is selected. This app already has a real,
established empty-state pattern (`EmptyStateLabel`, used for Bookmarks,
TOC, the Recent tab) — this is the one place I found that doesn't use
it. A one-line "Select a category to see its books" would match the
rest of the app.

**Home dashboard's card grid is visually uneven** — card heights vary a
lot (some are a single line, others much taller) with no consistent
rhythm, so the grid doesn't read as a grid. Normalizing a minimum card
height, or grouping short/tall cards more deliberately, would tighten it.

**Reader's left nav panel stacks three lists (Contents, Bookmarks,
Research Notes) in fixed-height boxes** — on a shorter window each gets
cramped with its own internal scrollbar close together. This was a
deliberate, scoped addition this session (Research Notes list is new),
not revisited for vertical space since — worth a look if it feels tight
in real use.

**Toolbar scroll fix confirmed working** — the reader toolbar (font
combo, Contents/Copy Citation buttons) is visibly the full-size,
horizontally-scrollable row from the recent bug fix, not squeezed. No
action needed, just confirming it holds up in a real capture.

## What I'd leave alone

Settings, the combined Search+Reader+Assistant workspace, and the reader
toolbar's own layout already look structurally sound — organized into
clear sections, nothing obviously broken. The Logs screen's blank body
is expected here (no real log content was loaded in this capture
context) — check it against a real log file before judging it.

## Using these with another AI

These are plain PNG files — attach them directly wherever you're getting
a second opinion. If you want a written brief instead of raw images,
this file plus a one-line "here's my Islamic research library app,
built with PySide6 (Qt), give me UI feedback" is enough context for
another AI to work from.
