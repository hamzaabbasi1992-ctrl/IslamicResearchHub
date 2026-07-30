"""Tests for the post-import processing orchestrator.

Each real step (migrations, backfills, taxonomy, indexing) already has
its own dedicated test file - these tests are about the orchestration
itself (order, opt-in/skip behavior, resilience to one step failing),
so every step is replaced with a lightweight recording fake rather than
exercising its full real behavior again here.
"""

from pathlib import Path

import islamic_research_hub.interfaces.process_all_cli as process_all_cli
from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def _make_database(path: Path) -> None:
    """Create a real, minimal master database by importing one book."""
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(path, (book,), (path.parent / "source.mjbz",))


class _RecordingSteps:
    """Records every step call, in order, standing in for every real sub-CLI/step."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def migrate(self, arguments):
        self.calls.append("migrate")
        return 0

    def jibreel_hint(self, arguments):
        self.calls.append("jibreel_hint")
        return 0

    def publish_year(self, arguments):
        self.calls.append("publish_year")
        return 0

    def structure(self, arguments):
        self.calls.append("structure")
        return 0

    def pdf_match(self, database_path):
        self.calls.append("pdf_match")
        return 0

    def taxonomy(self, arguments):
        self.calls.append("taxonomy")
        return 0

    def semantic_index(self, arguments):
        self.calls.append("semantic_index")
        return 0


def _patch_all_steps(monkeypatch, recorder: _RecordingSteps) -> None:
    """Patch every always-imported step. Deliberately excludes semantic_index_cli -
    it's imported lazily inside main() only when --run-semantic-index is passed
    (see process_all_cli's own comment on why: a real ~20s sentence-transformers/
    torch import cost otherwise paid unconditionally) - only the one test that
    actually passes that flag needs to patch it, via _patch_semantic_index below."""
    monkeypatch.setattr(process_all_cli.migrate_database_cli, "main", recorder.migrate)
    monkeypatch.setattr(process_all_cli.jibreel_pdf_hint_backfill_cli, "main", recorder.jibreel_hint)
    monkeypatch.setattr(
        process_all_cli.shamila_urdu_publish_year_backfill_cli, "main", recorder.publish_year
    )
    monkeypatch.setattr(
        process_all_cli.shamila_urdu_structure_backfill_cli, "main", recorder.structure
    )
    monkeypatch.setattr(process_all_cli, "_run_pdf_match_detection", recorder.pdf_match)
    monkeypatch.setattr(process_all_cli.taxonomy_population_cli, "main", recorder.taxonomy)


def _patch_semantic_index(monkeypatch, recorder: _RecordingSteps) -> None:
    """Inject a fake module rather than importing the real one.

    process_all_cli's lazy `from islamic_research_hub.interfaces import
    semantic_index_cli` (inside main(), only reached with --run-semantic-index)
    resolves against sys.modules like any import - importing the real module
    just to patch its `main` would defeat the whole point of it being lazy,
    paying the real ~20s sentence-transformers/torch cost this is designed
    to avoid. Confirmed for real: doing it that way made this one test take
    23s alone.

    Patching only sys.modules is not enough: `from package import name`
    resolves via `getattr(package, name)` first, falling back to sys.modules
    only when that attribute doesn't exist - and it *does* exist here once
    any other test in the same run (e.g. test_semantic_index_cli.py) has
    really imported this module, since Python sets it as a package attribute
    as an import side effect. Confirmed for real: this test passed in
    isolation but silently ran the real model when the full suite ran first.
    Both must be patched to be robust to import order.
    """
    import sys
    import types

    import islamic_research_hub.interfaces as interfaces_package

    fake_module = types.ModuleType("islamic_research_hub.interfaces.semantic_index_cli")
    fake_module.main = recorder.semantic_index
    monkeypatch.setitem(
        sys.modules, "islamic_research_hub.interfaces.semantic_index_cli", fake_module
    )
    monkeypatch.setattr(interfaces_package, "semantic_index_cli", fake_module, raising=False)


def test_runs_every_always_on_step_in_order(tmp_path: Path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "books.db"
    _make_database(database_path)
    recorder = _RecordingSteps()
    _patch_all_steps(monkeypatch, recorder)

    exit_code = process_all_cli.main(["--database", str(database_path)])

    assert exit_code == 0
    assert recorder.calls == ["migrate", "publish_year", "structure", "pdf_match", "taxonomy"]


def test_jibreel_step_skipped_without_credentials(tmp_path: Path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "books.db"
    _make_database(database_path)
    recorder = _RecordingSteps()
    _patch_all_steps(monkeypatch, recorder)

    process_all_cli.main(["--database", str(database_path)])

    captured = capsys.readouterr()
    assert "jibreel_hint" not in recorder.calls
    assert "skipped" in captured.out
    assert "--jibreel-books-folder" in captured.out


def test_jibreel_step_runs_when_both_credentials_given(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "books.db"
    _make_database(database_path)
    recorder = _RecordingSteps()
    _patch_all_steps(monkeypatch, recorder)

    process_all_cli.main(
        [
            "--database", str(database_path),
            "--jibreel-books-folder", str(tmp_path / "books"),
            "--jibreel-sqlite-dll", str(tmp_path / "sqlite.dll"),
        ]
    )

    assert "jibreel_hint" in recorder.calls


def test_semantic_index_skipped_by_default(tmp_path: Path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "books.db"
    _make_database(database_path)
    recorder = _RecordingSteps()
    _patch_all_steps(monkeypatch, recorder)

    process_all_cli.main(["--database", str(database_path)])

    captured = capsys.readouterr()
    assert "semantic_index" not in recorder.calls
    assert "--run-semantic-index" in captured.out


def test_semantic_index_runs_when_opted_in(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "books.db"
    _make_database(database_path)
    recorder = _RecordingSteps()
    _patch_all_steps(monkeypatch, recorder)
    _patch_semantic_index(monkeypatch, recorder)

    process_all_cli.main(["--database", str(database_path), "--run-semantic-index"])

    assert "semantic_index" in recorder.calls


def test_a_failing_step_does_not_stop_the_remaining_steps(tmp_path: Path, monkeypatch) -> None:
    """One step raising doesn't abort the run - matches the real resilience
    pattern jibreel_desktop_import_cli.py already uses for individual files."""
    database_path = tmp_path / "books.db"
    _make_database(database_path)
    recorder = _RecordingSteps()
    _patch_all_steps(monkeypatch, recorder)

    def _broken_migrate(arguments):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(process_all_cli.migrate_database_cli, "main", _broken_migrate)

    exit_code = process_all_cli.main(["--database", str(database_path)])

    assert exit_code == 0
    assert recorder.calls == ["publish_year", "structure", "pdf_match", "taxonomy"]


def test_missing_database_fails_clearly(tmp_path: Path) -> None:
    exit_code = process_all_cli.main(["--database", str(tmp_path / "does_not_exist.db")])

    assert exit_code == 1
