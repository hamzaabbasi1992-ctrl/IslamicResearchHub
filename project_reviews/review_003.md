# Review 003 — AI Agent, Milestone 1 (Q&A, Search Shortcuts, Summarization)

## What was built

A real AI assistant, not a placeholder. The "Assistant" panel that's
always been part of the app now actually works: type a real question
about your library, and it searches your books, reads the real relevant
pages, and answers grounded in what it actually found — with a real
citation to the book and page, never a made-up reference. The same
capability lets you type a request in plain language instead of using
the search filters ("find hadith about patience"), and lets you ask for
a summary of a book or chapter on demand.

You choose which AI service does the thinking — Anthropic's Claude,
OpenAI's ChatGPT, or Google's Gemini — from a dropdown in Settings, and
each one remembers its own separate key, so switching between them
doesn't make you re-enter anything. This is off by default, since it's
the first feature in the app that costs real money per use (a cloud AI
subscription/API key, not a one-time local download like the
text-to-speech or voice search features) — you turn it on deliberately
in Settings and provide your own key.

Two real safety limits were built in from the start, since an AI
"reading" an entire book in one go could otherwise run up a large real
cost or simply fail: reading a book is capped at 20 pages per request
(it will ask again for the next 20 if needed), and the whole back-and-
forth of "search, read, answer" is capped at 8 real steps before it
gives you an honest partial answer instead of running indefinitely.

## Files changed

New:
- The AI provider contract (what any AI service needs to support)
- The tool layer connecting the AI to your library's real search and
  book-reading capabilities
- The core question-answering/summarizing logic (the "agent loop")
- Three separate connector files, one per AI service (Anthropic, OpenAI,
  Google)
- A background worker so asking a question never freezes the app while
  waiting for a real response

Modified:
- The Assistant panel (real question box, Ask button, answer area, and a
  label showing which searches it actually ran)
- Settings screen (enable/disable toggle, AI service picker, API key
  field per service, with a plain-language warning that the key is
  stored on your computer without encryption)
- Main window (wires the new setting into the Assistant panel at startup)
- Translation files (English/Urdu/Arabic labels for the new settings)
- Dependency manifest (three new optional packages, one per AI service)

## Architecture changes

None to the app's existing design. This follows the exact same pattern
already used for local text-to-speech and voice search — a clean,
swappable "adapter" for each AI service behind one shared interface — so
adding a fourth AI service later (or a future local/offline option) is a
contained addition, not a rework.

## Database changes

None. This feature only *reads* your existing library data (via search
you already have) — it doesn't add, change, or store anything in the
database itself.

## UI changes

- The Assistant panel's question box is now enabled and functional
  (previously a disabled "coming soon" placeholder).
- New "Ask" button, and pressing Enter in the question box also submits.
- New answer area showing the AI's real response.
- New small label showing which real searches the AI performed for that
  answer (transparency into what it actually did, not a black box).
- Settings gained a new "AI Agent" section: an enable toggle, a provider
  dropdown (Claude / ChatGPT / Gemini), an API key field, and a plain
  disclosure about how that key is stored.

## Tests run

- 77 new automated tests covering: the tool layer, the core agent loop
  (using a scripted fake AI so tests are fast and don't cost real money),
  each of the three AI service connectors' real message formatting
  (checked directly against each service's actual software library, not
  guessed), and the Settings/panel wiring.
- Full project test suite run after every change: 781 of 781 tests
  passing.
- Manually verified: with the feature turned on but no API key entered,
  the app shows a real, clear "unavailable" message instead of crashing
  — confirmed directly, not assumed. Also confirmed all three AI service
  connectors build successfully.
- **Not yet done**: an actual real question asked to a real AI service.
  That requires a real API key, which only you can provide (see below).

## Remaining issues

- **The most important one**: nobody has actually asked it a real
  question yet. Everything is verified as far as possible without
  spending real money on a real API call — the actual "does this give me
  a good, correctly-cited answer" test still needs to happen with your
  own API key.
- No cost or usage limit exists yet beyond the two safety caps described
  above — a heavy day of use could run up a real bill on whichever AI
  service you choose. Worth keeping an eye on until real usage patterns
  are clear.
- Summarizing works one chapter/page-range at a time; there's no "give me
  the whole book" one-click summary yet (deliberately — a whole book
  could be hundreds of pages, too much for one request).
- The API key is stored in plain, unencrypted form on your computer (in
  the same place other app settings live). Anyone else with access to
  your Windows account could read it. This was a deliberate, disclosed
  tradeoff for now, not an oversight — a more secure storage option is a
  real future improvement, not built yet.

## Next recommendations

1. **Try it for real.** Get an API key from whichever service you'd
   rather use (Anthropic, OpenAI, or Google all offer them), enter it in
   Settings, and ask it something real about your library. This is the
   one thing that can't be verified without you.
2. Once you've used it a bit, decide whether a "how much have I spent /
   used" indicator is worth adding — right now there's genuinely no
   visibility into that from inside the app.
3. If the answers feel too slow, or you want it to sound different, or
   you find it's calling the wrong searches for certain questions — bring
   specific examples back and I can tune the instructions it's given.
