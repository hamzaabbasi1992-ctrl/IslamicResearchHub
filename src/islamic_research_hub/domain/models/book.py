"""Typed models extracted from one verified Jibreel Mobile database."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Category:
    """One node in the complete Jibreel category hierarchy."""

    mjcn: int | None
    name: str | None
    parent_mjcn: int | None
    sort_key: int | None
    children: tuple["Category", ...] = ()


@dataclass(frozen=True, slots=True)
class Chapter:
    """One node in the complete table-of-contents hierarchy."""

    title_id: int | None
    title: str | None
    page_number: int | None
    parent_id: int | None
    sort_key: int | None
    children: tuple["Chapter", ...] = ()


@dataclass(frozen=True, slots=True)
class Page:
    """One content record from the verified Content table."""

    content_id: int | None
    page_number: int | None
    content_f: str | None
    content_p: str | None
    footnote: str | None = None
    hadees_number: str | None = None
    """Real hadith number, from Shamila Urdu's `Hadith/` collections only."""
    ayah_number: str | None = None
    """Real ayah number, from Shamila Urdu's `Quran/` collection only."""


@dataclass(frozen=True, slots=True)
class Book:
    """All metadata and page content extracted from one .mjbz book."""

    information: dict[str, str | None]
    categories: tuple[Category, ...]
    table_of_contents: tuple[Chapter, ...]
    pages: tuple[Page, ...]
