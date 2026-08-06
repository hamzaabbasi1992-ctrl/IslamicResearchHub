"""Tests for AgentToolExecutor - real search/retrieval delegation, real
JSON shapes, and the safety limits that keep an agentic loop honest."""

import json
from pathlib import Path

from islamic_research_hub.application.agent_tools import (
    MAX_PAGES_PER_CALL,
    AgentToolExecutor,
)
from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.domain.models.book import Book, Chapter, Page
from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


class FakeSearchIndex:
    def __init__(self, results: tuple[SearchResult, ...] = ()) -> None:
        self._results = results
        self.last_query: str | None = None

    def search(self, query, limit, library=None, author=None, category=None, exact=False, scope="content"):
        self.last_query = query
        return self._results


class FakeSemanticSearchIndex:
    def __init__(self, results: tuple[SemanticSearchResult, ...] = ()) -> None:
        self._results = results

    def search(self, embedding, limit, library=None, query_language=None):
        return self._results


class FakeEmbedder:
    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((0.1, 0.2) for _ in texts)


def _seed_database_with_chapter(database_path: Path) -> int:
    """Import one real book with a real chapter and multiple pages -
    returns its book_id (always 1, the first import)."""
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(
            Chapter(title_id=1, title="Chapter One", page_number=1, parent_id=None, sort_key=1),
        ),
        pages=tuple(
            Page(i, i, f"<urh1>Heading {i}</urh1> Real page content {i}", "Plain")
            for i in range(1, 31)
        ),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )
    return 1


def _executor(database_path: Path, semantic: SemanticBookSearchService | None = None) -> AgentToolExecutor:
    book_search = BookSearchService(FakeSearchIndex())
    browser = BookBrowserRepository(database_path)
    return AgentToolExecutor(book_search, semantic, browser)


def test_unknown_tool_returns_a_real_error_not_a_crash(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_chapter(database_path)
    executor = _executor(database_path)

    content, is_error = executor.execute("not_a_real_tool", {})

    assert is_error is True
    assert "not_a_real_tool" in content


def test_search_books_delegates_and_includes_a_real_citation(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_chapter(database_path)
    fake_index = FakeSearchIndex(
        (SearchResult(book_id=1, title="Book of Fiqh", author="Author One", page_number=5, excerpt="..."),)
    )
    book_search = BookSearchService(fake_index)
    executor = AgentToolExecutor(book_search, None, BookBrowserRepository(database_path))

    content, is_error = executor.execute("search_books", {"query": "fiqh"})

    assert is_error is False
    results = json.loads(content)
    assert results[0]["book_id"] == 1
    assert results[0]["citation"] == "Book Book of Fiqh, Page 5, Paragraph 1"


def test_semantic_search_books_omitted_when_unavailable(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_chapter(database_path)
    executor = _executor(database_path, semantic=None)

    names = {tool.name for tool in executor.tool_definitions()}

    assert "semantic_search_books" not in names
    assert "search_books" in names


def test_semantic_search_books_present_and_works_when_available(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_chapter(database_path)
    fake_index = FakeSemanticSearchIndex(
        (
            SemanticSearchResult(
                book_id=1, title="Book of Fiqh", author="Author One",
                page_number=5, excerpt="...", similarity=0.9,
            ),
        )
    )
    semantic = SemanticBookSearchService(FakeEmbedder(), fake_index)
    executor = _executor(database_path, semantic=semantic)

    names = {tool.name for tool in executor.tool_definitions()}
    content, is_error = executor.execute("semantic_search_books", {"query": "patience"})

    assert "semantic_search_books" in names
    assert is_error is False
    results = json.loads(content)
    assert results[0]["similarity"] == 0.9


def test_get_book_metadata_returns_real_data(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_database_with_chapter(database_path)
    executor = _executor(database_path)

    content, is_error = executor.execute("get_book_metadata", {"book_id": book_id})

    assert is_error is False
    data = json.loads(content)
    assert data["title"] == "Book of Fiqh"
    assert data["author"] == "Author One"


def test_get_book_metadata_unknown_book_id_is_a_real_error(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_chapter(database_path)
    executor = _executor(database_path)

    content, is_error = executor.execute("get_book_metadata", {"book_id": 999})

    assert is_error is False  # a handled, honest "not found" JSON payload, not a crash
    assert "error" in json.loads(content)


def test_list_chapters_returns_the_real_toc(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_database_with_chapter(database_path)
    executor = _executor(database_path)

    content, is_error = executor.execute("list_chapters", {"book_id": book_id})

    assert is_error is False
    chapters = json.loads(content)
    assert chapters[0]["title"] == "Chapter One"
    assert chapters[0]["page_number"] == 1


def test_get_book_pages_strips_raw_markup(tmp_path: Path) -> None:
    """Real bug already found once this session (reader headings) - the
    agent must not feed raw '<urh1>' markup to the model either."""
    database_path = tmp_path / "books.db"
    book_id = _seed_database_with_chapter(database_path)
    executor = _executor(database_path)

    content, is_error = executor.execute(
        "get_book_pages", {"book_id": book_id, "start_page": 1, "end_page": 1}
    )

    assert is_error is False
    data = json.loads(content)
    page_text = data["pages"][0]["text"]
    assert "<" not in page_text
    assert "urh1" not in page_text
    assert "Heading 1" in page_text
    assert "Real page content 1" in page_text


def test_get_book_pages_caps_at_the_real_limit_and_says_so(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_database_with_chapter(database_path)  # 30 real pages
    executor = _executor(database_path)

    content, is_error = executor.execute(
        "get_book_pages", {"book_id": book_id, "start_page": 1, "end_page": 30}
    )

    assert is_error is False
    data = json.loads(content)
    assert len(data["pages"]) == MAX_PAGES_PER_CALL
    assert data["truncated"] is True
    assert "truncation_note" in data
    assert str(MAX_PAGES_PER_CALL + 1) in data["truncation_note"]


def test_get_book_pages_not_truncated_within_the_cap(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_database_with_chapter(database_path)
    executor = _executor(database_path)

    content, is_error = executor.execute(
        "get_book_pages", {"book_id": book_id, "start_page": 1, "end_page": 5}
    )

    assert is_error is False
    data = json.loads(content)
    assert len(data["pages"]) == 5
    assert data["truncated"] is False
    assert "truncation_note" not in data


def test_get_book_pages_unknown_book_id_is_a_real_error(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_chapter(database_path)
    executor = _executor(database_path)

    content, is_error = executor.execute(
        "get_book_pages", {"book_id": 999, "start_page": 1, "end_page": 5}
    )

    assert is_error is False
    assert "error" in json.loads(content)
