# Handoff

Read this first if you're a different AI tool picking up this project
cold. Also read `PROJECT.md` (architecture + full phase roadmap) and
`CLAUDE.md` (working rules for this project) before making changes.

This file is overwritten each time, not appended to - it always reflects
the current real state, not a history. For history, see `CHANGELOG.md`
and `project_reviews/review_00X.md`.

## Current objective

None in progress. All work requested so far is complete, tested, and
pushed to GitHub (`origin/main`, commit `b3d8ebd`). Waiting on the next
task from the user.

## What was completed (most recent session)

- Fixed three real bugs reported against the running app: reader
  toolbar controls squeezed to invisible width, raw `<urh1>` markup
  showing literally in reader headings, no confirmation after saving a
  Research Notes quotation.
- Added a maximize control (alongside each existing collapse toggle) to
  the AI panel, the reader's Contents panel, and the Search screen's
  detail panel.
- Bookmarks now show full detail (book title, volume, page) instead of
  just "Page N".
- The reader's nav panel lists Research Notes documents that have a
  quotation saved from the currently open book.

## Files changed (most recent session)

- `src/islamic_research_hub/interfaces/desktop_app/viewer_screen.py`
- `src/islamic_research_hub/interfaces/desktop_app/search_screen.py`
- `src/islamic_research_hub/interfaces/desktop_app/workspace_screen.py`
- `src/islamic_research_hub/interfaces/desktop_app/ai_panel_screen.py`
- `src/islamic_research_hub/interfaces/desktop_app/icons.py`
- `src/islamic_research_hub/interfaces/desktop_app/panel_toggle.py` (new)
- `src/islamic_research_hub/research_notes/docx_writer.py`
- `src/islamic_research_hub/research_notes/research_notes_manager.py`
- Matching test files under `tests/`

## Current state of the code

- Full test suite: 726/726 passing.
- Local git and `origin/main` are in sync (nothing uncommitted, nothing
  unpushed) as of this handoff.
- No known failing tests, no known broken features.

## What remains to do

Nothing committed to yet. Candidates raised in conversation but not
started:

- `PROJECT.md`'s Phase 9 remaining items (English-language books,
  community feedback beyond ratings, NotebookLM-style AI research
  workspace).
- The "AI Agent" vision (natural-language queries, tool-calling,
  multi-provider LLM support) - explicitly deferred earlier until other
  work finished; not yet scoped or planned.
- Research Notes real hands-on test with an actual Word instance holding
  a file open (only simulated so far - see `project_reviews/review_002.md`).

## Known issues

- None open. (If you find one, note it here before switching tools, not
  just in chat.)

## Exact next step

Ask the user what they want worked on next - there is no queued task.
