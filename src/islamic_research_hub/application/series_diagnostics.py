"""Analyze series integrity, volume sequence gaps, and database quality.

Phase 8.5 feature: checks book records across multi-volume series to detect missing
volumes, duplicate volume numbers, or unassigned series identifiers defensively.
"""

import logging
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SeriesQualityIssue:
    """One diagnostic issue found in a book series sequence."""

    book_id: int
    title: str
    series_id: int | None
    volume_number: int | None
    issue_type: str
    description: str


def analyze_series_consistency(
    books: list[dict[str, Any]],
) -> tuple[SeriesQualityIssue, ...]:
    """Analyze a list of book records for series volume sequence anomalies.

    Identifies:
    - `MISSING_VOLUME`: Gap in volume numbers within a series.
    - `DUPLICATE_VOLUME`: Multiple volumes assigned the same volume number in a series.
    - `ORPHAN_VOLUME`: Volume number assigned without a valid SeriesID.
    """
    issues: list[SeriesQualityIssue] = []
    series_groups: dict[int, list[dict[str, Any]]] = {}

    for b in books:
        book_id = b.get("book_id") or b.get("BookID")
        title = str(b.get("title") or b.get("Title") or "Untitled")
        series_id = b.get("series_id") or b.get("SeriesID")
        vol_num = b.get("volume_number") or b.get("VolumeNumber")

        if book_id is None:
            continue

        if series_id is None and vol_num is not None:
            issues.append(
                SeriesQualityIssue(
                    book_id=int(book_id),
                    title=title,
                    series_id=None,
                    volume_number=int(vol_num),
                    issue_type="ORPHAN_VOLUME",
                    description=f"Book '{title}' has VolumeNumber={vol_num} but no SeriesID.",
                )
            )
            continue

        if series_id is not None:
            series_groups.setdefault(int(series_id), []).append(b)

    for s_id, group in series_groups.items():
        vols: list[int] = []
        for b in group:
            v_num = b.get("volume_number") or b.get("VolumeNumber")
            if v_num is not None:
                vols.append(int(v_num))

        if not vols:
            continue

        # Check duplicate volume numbers
        seen: set[int] = set()
        for b in group:
            v_num = b.get("volume_number") or b.get("VolumeNumber")
            if v_num is not None:
                v_int = int(v_num)
                if v_int in seen:
                    b_id = int(b.get("book_id") or b.get("BookID") or 0)
                    t_name = str(b.get("title") or b.get("Title") or "")
                    issues.append(
                        SeriesQualityIssue(
                            book_id=b_id,
                            title=t_name,
                            series_id=s_id,
                            volume_number=v_int,
                            issue_type="DUPLICATE_VOLUME",
                            description=f"Series {s_id} has duplicate VolumeNumber={v_int}.",
                        )
                    )
                else:
                    seen.add(v_int)

        # Check sequence gaps
        min_vol, max_vol = min(vols), max(vols)
        for expected in range(min_vol, max_vol + 1):
            if expected not in seen:
                first_book = group[0]
                b_id = int(first_book.get("book_id") or first_book.get("BookID") or 0)
                t_name = str(first_book.get("title") or first_book.get("Title") or "")
                issues.append(
                    SeriesQualityIssue(
                        book_id=b_id,
                        title=t_name,
                        series_id=s_id,
                        volume_number=expected,
                        issue_type="MISSING_VOLUME",
                        description=f"Series {s_id} is missing Volume {expected} (range {min_vol}-{max_vol}).",
                    )
                )

    return tuple(issues)
