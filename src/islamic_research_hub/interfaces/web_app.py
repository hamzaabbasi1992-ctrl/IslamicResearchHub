"""Local web app for searching and browsing the book corpus.

Requires the optional "web" dependency group (`pip install -e .[web]`).
Semantic search is used automatically when the "ai" extra is also
installed and its index is populated; otherwise falls back to
keyword-only search, same as the CLI tools.
"""

import logging
import re
from pathlib import Path

from flask import Flask, abort, render_template, request, send_file
from markupsafe import Markup, escape

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.hybrid_search import HybridSearchService
from islamic_research_hub.domain.models.hybrid_search_result import HybridSearchResult
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    SqliteBookSearchRepository,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_LIMIT = 20
PDF_ARCHIVE_LIBRARY = "Maktaba Jibreel (PDF Archive)"
MAKNOON_LIBRARY = "Maktaba Al-Maknoon"
DEFAULT_MAKNOON_PDF_FOLDER = Path(
    r"F:\Maknoon Mufahris Almakhtotaat (Search Able Urdu Pdf books Library)\PDF Data"
)

_BOLD_MARKER = re.compile(r"\*\*(.+?)\*\*")


def create_app(
    database_path: Path = DEFAULT_DATABASE_PATH,
    maknoon_pdf_folder: Path = DEFAULT_MAKNOON_PDF_FOLDER,
    enable_semantic: bool = True,
) -> Flask:
    """Build and configure the Flask application.

    `enable_semantic=False` skips loading the (slow) embedding model
    entirely, useful for tests that don't need semantic search.
    """
    configure_logging()
    app = Flask(__name__)

    browser = BookBrowserRepository(database_path)
    keyword_service = BookSearchService(SqliteBookSearchRepository(database_path))
    semantic_service = _build_semantic_service(database_path) if enable_semantic else None
    search_service = HybridSearchService(keyword_service, semantic_service)

    def resolve_pdf_path(library: str | None, source: str) -> Path | None:
        """Return the real PDF path for a book, or None if it has no PDF available."""
        if library == PDF_ARCHIVE_LIBRARY:
            path = Path(source)
            return path if path.is_file() else None
        if library == MAKNOON_LIBRARY:
            candidate = maknoon_pdf_folder / Path(source).stem  # "X.pdf.txt" -> "X.pdf"
            return candidate if candidate.is_file() else None
        return None

    def build_result_view(hit: HybridSearchResult) -> dict:
        """Attach an open-link (PDF or in-app read view) and highlighted excerpt to one hit."""
        source = browser.get_book_source(hit.book_id)
        pdf_path = resolve_pdf_path(source[1], source[0]) if source else None
        if pdf_path is not None:
            fragment = f"#page={hit.page_number}" if hit.page_number else ""
            open_url = f"/pdf/{hit.book_id}{fragment}"
            open_label = "Open PDF"
        else:
            query_string = f"?page={hit.page_number}" if hit.page_number else ""
            open_url = f"/read/{hit.book_id}{query_string}"
            open_label = "Read"
        return {
            "result": hit,
            "excerpt_html": _highlight_excerpt(hit.excerpt),
            "open_url": open_url,
            "open_label": open_label,
        }

    @app.route("/")
    def index():
        query = request.args.get("q", "").strip()
        library = request.args.get("library") or None
        results = []
        if query:
            hits = search_service.search(query, DEFAULT_LIMIT, library)
            results = [build_result_view(hit) for hit in hits]
        return render_template(
            "search.html",
            query=query,
            library=library,
            libraries=browser.list_libraries(),
            results=results,
            semantic_available=semantic_service is not None,
        )

    @app.route("/pdf/<int:book_id>")
    def open_pdf(book_id: int):
        source = browser.get_book_source(book_id)
        pdf_path = resolve_pdf_path(source[1], source[0]) if source else None
        if pdf_path is None:
            abort(404)
        return send_file(pdf_path, mimetype="application/pdf")

    @app.route("/read/<int:book_id>")
    def read_book(book_id: int):
        detail = browser.get_book_detail(book_id)
        if detail is None:
            abort(404)
        title, author, pages = detail
        jump_page = request.args.get("page", type=int)
        return render_template(
            "read.html", title=title, author=author, pages=pages, jump_page=jump_page
        )

    return app


def _build_semantic_service(database_path: Path):
    """Build the semantic search service, or None if the ai extra isn't installed."""
    try:
        from islamic_research_hub.application.semantic_book_search import (
            SemanticBookSearchService,
        )
        from islamic_research_hub.infrastructure.ai.sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )
        from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (
            SqlitePageEmbeddingRepository,
        )
    except ImportError:
        LOGGER.info("Semantic search unavailable (install .[ai]); running keyword-only.")
        return None
    return SemanticBookSearchService(
        SentenceTransformerEmbedder(), SqlitePageEmbeddingRepository(database_path)
    )


def _highlight_excerpt(excerpt: str) -> Markup:
    """Convert **term** snippet markers into safe HTML <mark> tags."""
    parts = []
    last_end = 0
    for match in _BOLD_MARKER.finditer(excerpt):
        parts.append(escape(excerpt[last_end : match.start()]))
        parts.append(Markup("<mark>") + escape(match.group(1)) + Markup("</mark>"))
        last_end = match.end()
    parts.append(escape(excerpt[last_end:]))
    return Markup("").join(parts)


if __name__ == "__main__":
    create_app().run(debug=False)
