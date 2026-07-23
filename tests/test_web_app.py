"""Tests for the local web app (search, PDF opening, in-app reading)."""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.web_app import create_app


def _seed_database(database_path: Path) -> None:
    """Import one Jibreel-style book (no PDF) and one PDF-Archive-style book."""
    jibreel_book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(
            Page(1, 1, "First page about jurisprudence", "Plain"),
            Page(2, 2, "Second page about jurisprudence in detail", "Plain"),
        ),
    )
    MasterBookRepository().import_books(
        database_path,
        (jibreel_book,),
        (database_path.parent / "book.mjbz",),
        library_name="Maktaba Jibreel (Mobile)",
    )

    pdf_book = Book(
        information={"Name": "A PDF Book"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 3, "Content extracted about jurisprudence", None),),
    )
    MasterBookRepository().import_books(
        database_path,
        (pdf_book,),
        (database_path.parent / "A PDF Book.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )


def _make_client(tmp_path: Path):
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    app = create_app(
        database_path, maknoon_pdf_folder=tmp_path / "maknoon_pdfs", enable_semantic=False
    )
    return app.test_client(), database_path


def test_index_loads_with_empty_query(tmp_path: Path) -> None:
    """The bare search page loads successfully with the library dropdown populated."""
    client, _ = _make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert b"Islamic Research Hub" in response.data
    assert "Maktaba Jibreel (Mobile)".encode() in response.data


def test_search_shows_read_link_for_book_with_no_pdf(tmp_path: Path) -> None:
    """A Jibreel-style match (no PDF available) gets a Read link, not a PDF link."""
    client, _ = _make_client(tmp_path)

    response = client.get("/?q=jurisprudence")

    assert response.status_code == 200
    assert b"Book of Fiqh" in response.data
    assert b"/read/1?page=1" in response.data or b"/read/1" in response.data
    assert b"Read" in response.data


def test_search_shows_pdf_link_when_pdf_file_exists(tmp_path: Path) -> None:
    """A PDF Archive match with a real, existing source file gets an Open PDF link."""
    database_path = tmp_path / "books.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    (database_path.parent / "A PDF Book.pdf").write_bytes(b"%PDF-1.4 fake pdf content")
    _seed_database(database_path)
    app = create_app(
        database_path, maknoon_pdf_folder=tmp_path / "maknoon_pdfs", enable_semantic=False
    )
    client = app.test_client()

    response = client.get("/?q=extracted")

    assert response.status_code == 200
    assert b"A PDF Book" in response.data
    assert b"Open PDF" in response.data


def test_search_with_no_matches_shows_message(tmp_path: Path) -> None:
    """A query with no hits shows a clear no-results message."""
    client, _ = _make_client(tmp_path)

    response = client.get("/?q=nonexistentterm")

    assert response.status_code == 200
    assert b"No matches found" in response.data


def test_read_book_renders_pages_and_marks_jump_target(tmp_path: Path) -> None:
    """The reading view shows all pages and marks the requested page for scrolling."""
    client, _ = _make_client(tmp_path)

    response = client.get("/read/1?page=2")

    assert response.status_code == 200
    assert "Book of Fiqh".encode() in response.data
    assert "Second page about jurisprudence in detail".encode() in response.data
    assert b'id="jump"' in response.data


def test_read_book_404_for_unknown_book(tmp_path: Path) -> None:
    """Requesting a nonexistent book id returns 404."""
    client, _ = _make_client(tmp_path)

    response = client.get("/read/9999")

    assert response.status_code == 404


def test_open_pdf_serves_file_when_it_exists(tmp_path: Path) -> None:
    """/pdf/<id> streams the real PDF file when it can be resolved."""
    database_path = tmp_path / "books.db"
    pdf_path = database_path.parent / "A PDF Book.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake pdf content")
    _seed_database(database_path)
    app = create_app(
        database_path, maknoon_pdf_folder=tmp_path / "maknoon_pdfs", enable_semantic=False
    )
    client = app.test_client()

    response = client.get("/pdf/2")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_open_pdf_404_when_book_has_no_pdf(tmp_path: Path) -> None:
    """/pdf/<id> returns 404 for a book from a library with no PDFs (e.g. Jibreel Mobile)."""
    client, _ = _make_client(tmp_path)

    response = client.get("/pdf/1")

    assert response.status_code == 404
