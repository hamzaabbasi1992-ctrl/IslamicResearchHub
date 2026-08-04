# Handoff

Read this first if you're a different AI tool picking up this project
cold. Also read `PROJECT.md` (architecture + full phase roadmap) and
`CLAUDE.md` (working rules for this project) before making changes.

This file is overwritten each time, not appended to - it always reflects
the current real state, not a history. For history, see `CHANGELOG.md`
and `project_reviews/review_00X.md`.

## Current objective

AI Agent, Milestone 1 is code-complete, tested, and pushed
(`origin/main`, commit `b31a85e`). One real step remains before it can be
called fully done: live end-to-end verification with a real API key,
which only the user can provide.

## What was completed (most recent session)

- **AI Agent, Milestone 1**: `AiAssistantPanel`'s question box now
  answers real questions grounded in real book content with real
  citations, via a real tool-calling loop over the app's existing
  search/retrieval (not a generic chatbot). Same loop covers natural-
  language search shortcuts and on-demand book/chapter summarization.
  Multi-provider from day one - Anthropic Claude, OpenAI ChatGPT, or
  Google Gemini, chosen in Settings, each with its own separately-stored
  API key. Off by default (first feature making a paid external API
  call). Real safety caps (20 pages per fetch, 8 tool-loop iterations)
  prevent runaway cost on open-ended requests.
- Real screenshots of every major screen captured and saved to
  `screenshots of app for other ai/` (untracked, not committed) for
  external UI review, plus my own written critique in that folder's
  `SUGGESTIONS.md`.
- UI Polish Pass 3: Taxonomy Browser's empty states now use the app's own
  centered `EmptyStateLabel` treatment; Duplicate Manager's table claims
  its real available height; Home dashboard cards share a consistent
  minimum height.
- Fixed three real bugs reported against the running app in an earlier
  pass this session (reader toolbar controls squeezed invisible, raw
  `<urh1>` markup in reader headings, no save confirmation in Research
  Notes) - see CHANGELOG for full detail on both passes.

## Files changed (most recent session)

New:
- `src/islamic_research_hub/application/llm_provider.py`
- `src/islamic_research_hub/application/agent_tools.py`
- `src/islamic_research_hub/application/ai_agent_service.py`
- `src/islamic_research_hub/infrastructure/ai/anthropic_llm_provider.py`
- `src/islamic_research_hub/infrastructure/ai/openai_llm_provider.py`
- `src/islamic_research_hub/infrastructure/ai/gemini_llm_provider.py`
- `src/islamic_research_hub/interfaces/desktop_app/ai_agent_worker.py`

Modified: `ai_panel_screen.py`, `settings_screen.py`, `main_window.py`,
`i18n.py`, `pyproject.toml` (new `agent` extra), plus the UI-polish files
(`taxonomy_browser_screen.py`, `duplicate_manager_screen.py`,
`home_screen.py`) and matching test files under `tests/`.

## Current state of the code

- Full test suite: 781/781 passing.
- Local git and `origin/main` are in sync (nothing uncommitted, nothing
  unpushed) as of this handoff.
- No known failing tests, no known broken features.
- `AnthropicLlmProvider`/`OpenAiLlmProvider`/`GeminiLlmProvider` are
  verified only at the translation-logic level (real SDK shapes
  confirmed directly) and construction level (all three build without
  error given a fake key) - **no real live API call has been made yet**.

## What remains to do

- **Immediate**: live end-to-end verification of the AI Agent - the user
  needs to enter a real API key (any of the three providers) in Settings
  and ask a real question. Watch for: a real grounded answer with a real
  citation, the tool-call transparency label showing real tool names,
  and confirm summarization works on a real chapter-sized page range.
- `PROJECT.md`'s remaining Phase 9 items (English-language books via
  islamhouse.com - blocked on the user registering an API key there;
  multi-voice audio-overview discussions; visual reports).
- UI Polish Pass 3 candidates not yet done: nothing queued - the three
  items agreed on were all completed this pass.
- Research Notes real hands-on test with an actual Word instance holding
  a file open (only simulated so far - see `project_reviews/review_002.md`).

## Known issues

- None open. (If you find one, note it here before switching tools, not
  just in chat.)

## Exact next step

Wait for the user to test the AI Agent with a real API key and report
back what happened - do not mark this milestone done until that real
verification succeeds.
