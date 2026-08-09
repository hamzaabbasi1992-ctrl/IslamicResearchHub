"""Unit tests for public_api.py."""

from unittest.mock import MagicMock

from islamic_research_hub.interfaces.public_api import (
    ApiBookDetails,
    ApiSearchResult,
    IslamicResearchHubAPI,
)


def test_public_api_search() -> None:
    mock_repo = MagicMock()
    mock_search = MagicMock()

    mock_search_item = MagicMock()
    mock_search_item.book_id = 1
    mock_search_item.book_title = "Sahih Bukhari"
    mock_search_item.author = "Imam Bukhari"
    mock_search_item.page_no = 5
    mock_search_item.snippet = "Sample search snippet"

    mock_search.search_content.return_value = [mock_search_item]

    api = IslamicResearchHubAPI(
        repository=mock_repo,
        search_service=mock_search,
    )

    results = api.search("Bukhari")
    assert len(results) == 1
    assert isinstance(results[0], ApiSearchResult)
    assert results[0].book_id == 1
    assert results[0].book_title == "Sahih Bukhari"


def test_public_api_book_details() -> None:
    mock_repo = MagicMock()
    mock_detail = MagicMock()
    mock_detail.book_id = 42
    mock_detail.title = "Al-Mawardi"
    mock_detail.author = "Al-Mawardi"
    mock_detail.publisher = "Dar"
    mock_detail.language = "Arabic"
    mock_detail.category = "Political Science"
    mock_detail.page_count = 300
    mock_detail.chapter_count = 15

    mock_repo.get_book_detail.return_value = mock_detail

    api = IslamicResearchHubAPI(repository=mock_repo)
    details = api.get_book_details(42)

    assert details is not None
    assert isinstance(details, ApiBookDetails)
    assert details.book_id == 42
    assert details.title == "Al-Mawardi"


def test_public_api_format_citation() -> None:
    mock_repo = MagicMock()
    mock_detail = MagicMock()
    mock_detail.title = "Riyad as-Salihin"
    mock_detail.author = "Imam Nawawi"
    mock_repo.get_book_detail.return_value = mock_detail

    api = IslamicResearchHubAPI(repository=mock_repo)
    citation = api.format_paragraph_citation(
        book_id=10, page_no=25, paragraph_id="1234"
    )

    assert "Riyad as-Salihin by Imam Nawawi" in citation
    assert "Page 25" in citation
    assert "(P-1234)" in citation
