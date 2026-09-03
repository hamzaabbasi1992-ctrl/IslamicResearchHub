"""Tests for `waqiat_encyclopedia_export_cli.py`."""

import json
import sqlite3
from pathlib import Path

from islamic_research_hub.interfaces.waqiat_encyclopedia_export_cli import (
    build_waqiat_encyclopedia,
    main,
)


def test_build_waqiat_encyclopedia_with_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "test_books.db"
    out_dir = tmp_path / "output"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE EventCandidates (EventCandidateID INTEGER PRIMARY KEY, BookID INT, ChunkStartPage INT, ChunkEndPage INT, Title TEXT, ExtractedDataJson TEXT, Status TEXT)"
        )
        conn.execute(
            "INSERT INTO EventCandidates VALUES (1, 100, 10, 12, 'Test Waqia', ?, 'confirmed')",
            (json.dumps({"title": "Test Waqia", "gist": "A test anecdote gist", "personality": "Abu Bakr (RA)"}),),
        )

    result = build_waqiat_encyclopedia(db_path, out_dir, status_filter="confirmed")

    assert result["status"] == "success"
    assert result["total_candidates"] == 1
    assert result["exported_entries"] == 1

    export_file = out_dir / "waqiat_encyclopedia_export.json"
    assert export_file.exists()

    data = json.loads(export_file.read_text(encoding="utf-8"))
    assert data["total_candidates"] == 1
    assert data["entries"][0]["title"] == "Test Waqia"


def test_main_cli(tmp_path: Path) -> None:
    db_path = tmp_path / "test_books.db"
    out_dir = tmp_path / "output"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE EventCandidates (EventCandidateID INTEGER PRIMARY KEY, BookID INT, ChunkStartPage INT, ChunkEndPage INT, Title TEXT, ExtractedDataJson TEXT, Status TEXT)"
        )
        conn.execute(
            "INSERT INTO EventCandidates VALUES (1, 101, 1, 2, 'Sample Waqia', ?, 'confirmed')",
            (json.dumps({"gist": "Sample"}),),
        )

    ret = main(["--database", str(db_path), "--output-dir", str(out_dir)])
    assert ret == 0
    assert (out_dir / "waqiat_encyclopedia_export.json").exists()
