"""Typed models for the general multi-dimensional taxonomy system."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaxonomyTerm:
    """One real term within a taxonomy dimension (e.g. one subject, one region)."""

    term_id: int
    dimension_code: str
    parent_term_id: int | None
    stable_key: str | None
    names: dict[str, str]
    """Language code -> primary display name in that language."""

    children: tuple["TaxonomyTerm", ...] = ()
