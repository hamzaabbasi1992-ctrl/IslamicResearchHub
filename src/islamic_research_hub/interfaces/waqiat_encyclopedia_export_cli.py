"""Command-line interface to build and export Waqiat Encyclopedia volumes.

Merges, deduplicates, and groups confirmed `EventCandidates` by taxonomy subject
dimensions into rendered encyclopedia entries and export formats.
"""

import argparse
import json
import logging
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

from islamic_research_hub.application.encyclopedia_builder import (
    EncyclopediaEntry,
    LinkedSourceReference,
    build_encyclopedia_entry,
)

LOGGER = logging.getLogger(__name__)


def build_waqiat_encyclopedia(
    database_path: Path,
    output_dir: Path,
    status_filter: str = "confirmed",
    subject_filter: str | None = None,
    export_format: str = "json",
) -> dict[str, Any]:
    """Process EventCandidates & taxonomy from `database_path` and export to `output_dir`.

    Returns summary metrics of the export operation.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as conn:
        conn.row_factory = sqlite3.Row

        # Check tables existence
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "EventCandidates" not in tables:
            return {"status": "empty", "total_candidates": 0, "exported_volumes": 0}

        # Query candidates
        query = "SELECT EventCandidateID, BookID, ChunkStartPage, ChunkEndPage, Title, ExtractedDataJson, Status FROM EventCandidates"
        params: list[Any] = []
        if status_filter != "all":
            query += " WHERE Status = ?"
            params.append(status_filter)

        candidates = conn.execute(query, params).fetchall()

        if not candidates:
            return {"status": "no_candidates", "total_candidates": 0, "exported_volumes": 0}

        # Parse candidates
        parsed_entries: list[dict[str, Any]] = []
        for row in candidates:
            c_id = row["EventCandidateID"]
            book_id = row["BookID"]
            start_p = row["ChunkStartPage"]
            end_p = row["ChunkEndPage"]
            raw_json = row["ExtractedDataJson"]

            extracted_data = {}
            if raw_json:
                try:
                    extracted_data = json.loads(raw_json)
                except json.JSONDecodeError:
                    pass

            title = row["Title"] or extracted_data.get("title", f"Waqia #{c_id}")
            gist = extracted_data.get("gist", "")
            excerpt = extracted_data.get("quoted_excerpt", "")
            personality = extracted_data.get("personality", "")

            # Get attached taxonomy terms if table exists
            terms: list[str] = []
            if "EventCandidateTaxonomyTerms" in tables and "TaxonomyTermNames" in tables:
                term_rows = conn.execute(
                    "SELECT n.Name FROM EventCandidateTaxonomyTerms t "
                    "JOIN TaxonomyTermNames n ON t.TermID = n.TermID "
                    "WHERE t.EventCandidateID = ?",
                    (c_id,),
                ).fetchall()
                terms = [r["Name"] for r in term_rows if r["Name"]]

            parsed_entries.append(
                {
                    "candidate_id": c_id,
                    "book_id": book_id,
                    "start_page": start_p,
                    "end_page": end_p,
                    "title": title,
                    "gist": gist,
                    "excerpt": excerpt,
                    "personality": personality,
                    "terms": terms,
                }
            )

        # Filter by subject if specified
        if subject_filter:
            parsed_entries = [
                e for e in parsed_entries if any(subject_filter.lower() in t.lower() for t in e["terms"])
            ]

        # Group into encyclopedia entries
        entries_by_id: dict[int, EncyclopediaEntry] = {}
        for item in parsed_entries:
            linked_book = {
                "book_id": item["book_id"],
                "title": f"Book #{item['book_id']}",
                "page_no": item["start_page"],
                "snippet": item["gist"] or item["excerpt"][:150],
            }
            enc_entry = build_encyclopedia_entry(
                term_id=item["candidate_id"],
                term_name=item["title"],
                dimension="Waqia",
                linked_books=[linked_book],
                related_terms=item["terms"],
            )
            entries_by_id[item["candidate_id"]] = enc_entry

        # Export output
        json_output_path = output_dir / "waqiat_encyclopedia_export.json"
        export_data = {
            "total_candidates": len(parsed_entries),
            "entries": [
                {
                    "term_id": e.term_id,
                    "title": e.term_name,
                    "description": e.description,
                    "sources": [
                        {
                            "book_id": s.book_id,
                            "page_no": s.page_no,
                            "snippet": s.snippet,
                        }
                        for s in e.sources
                    ],
                    "related_terms": list(e.related_terms),
                }
                for e in entries_by_id.values()
            ],
        }

        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return {
            "status": "success",
            "total_candidates": len(parsed_entries),
            "exported_entries": len(entries_by_id),
            "output_path": str(json_output_path),
        }


def main(args: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Export Waqiat Encyclopedia from EventCandidates data.")
    parser.add_argument("--database", type=Path, required=True, help="Path to SQLite database")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to save exports")
    parser.add_argument(
        "--status", default="confirmed", choices=["confirmed", "pending", "all"], help="Filter by candidate status"
    )
    parser.add_argument("--subject", type=str, default=None, help="Filter by subject taxonomy name")
    parser.add_argument("--format", default="json", choices=["json", "both"], help="Export format")

    parsed = parser.parse_args(args)

    if not parsed.database.exists():
        print(f"Error: Database file not found: {parsed.database}", file=sys.stderr)
        return 1

    result = build_waqiat_encyclopedia(
        database_path=parsed.database,
        output_dir=parsed.output_dir,
        status_filter=parsed.status,
        subject_filter=parsed.subject,
        export_format=parsed.format,
    )

    print("Waqiat Encyclopedia Export Complete:")
    print(f"  Total Candidates Processed: {result.get('total_candidates', 0)}")
    print(f"  Exported Entries: {result.get('exported_entries', 0)}")
    print(f"  Output Saved To: {result.get('output_path', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
