---
name: islamic-research-hub-tools
description: Access and execute all 20+ Islamic Research Hub research capabilities, including full-text corpus search, bookmarks, collections, citations, research notes (.docx), and Word exports.
---

# Islamic Research Hub Tools (MCP Skill)

Use this skill whenever performing Islamic research tasks, searching the book library, extracting quotes, adding bookmarks/collections, or generating `.docx` exports.

## Available Tools & CLI Invocation

All 20+ research tools exposed in the MCP server can be executed via `.venv\Scripts\python.exe scripts/mcp_tool_runner.py <tool_name> --kwargs '<json_string>'`.

### 1. Full-Text Corpus Search & Navigation
- **`search_text`**: Search full text of library books.
  - `python scripts/mcp_tool_runner.py search_text --kwargs '{"query": "Hadith title", "limit": 10}'`
- **`get_citation`**: Format citation for a book page.
  - `python scripts/mcp_tool_runner.py get_citation --kwargs '{"book_id": 1, "page_number": 5, "paragraph_index": 0}'`
- **`get_open_link`**: Generate `maktaba://` protocol link to open page in Desktop GUI.
  - `python scripts/mcp_tool_runner.py get_open_link --kwargs '{"book_id": 1, "page_number": 5}'`

### 2. Bookmarks & Collections
- **`add_bookmark`** / **`list_recent_bookmarks`**
- **`create_collection`** / **`add_to_collection`** / **`list_collections`** / **`list_collection_items`**

### 3. Research Notes & Word Exports (.docx)
- **`create_note_document`**: Create a `.docx` note file in user documents.
- **`save_quotation`**: Append quote and citation details to `.docx` note.
- **`export_answer_to_docx`**: Save Q&A with citations to a styled `.docx`.
- **`export_article_to_docx`**: Export full structured article to `.docx`.

### 4. System & Health Check
- **`health_check`**: Verify database connection (`data/books.db`).
