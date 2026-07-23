"""Tests for planning which .mjbx files need decrypting."""

from pathlib import Path

from islamic_research_hub.application.jibreel_desktop_import import (
    JibreelDesktopImportPlanner,
    find_new_files,
)


def test_find_new_files_excludes_already_imported_ids(tmp_path: Path) -> None:
    """A file whose stem matches an existing source book id is excluded."""
    (tmp_path / "10.mjbx").touch()
    (tmp_path / "20.mjbx").touch()
    (tmp_path / "30.mjbx").touch()

    new_files = find_new_files(tmp_path, existing_source_book_ids=frozenset({"20"}))

    assert [path.name for path in new_files] == ["10.mjbx", "30.mjbx"]


def test_find_new_files_ignores_non_mjbx_files(tmp_path: Path) -> None:
    """Only .mjbx files are considered, regardless of other files present."""
    (tmp_path / "10.mjbx").touch()
    (tmp_path / "readme.txt").touch()

    new_files = find_new_files(tmp_path, existing_source_book_ids=frozenset())

    assert [path.name for path in new_files] == ["10.mjbx"]


def test_planner_maps_sources_to_staging_destinations(tmp_path: Path) -> None:
    """Each new file gets a destination in the staging folder with a .mjbz extension."""
    app_folder = tmp_path / "app"
    app_folder.mkdir()
    (app_folder / "42.mjbx").touch()
    staging = tmp_path / "staging"

    jobs = JibreelDesktopImportPlanner(staging).plan(app_folder, frozenset())

    assert len(jobs) == 1
    source, destination = jobs[0]
    assert source == app_folder / "42.mjbx"
    assert destination == staging / "42.mjbz"


def test_planner_returns_nothing_when_all_files_already_imported(tmp_path: Path) -> None:
    """No jobs are planned when every file's id is already in the database."""
    app_folder = tmp_path / "app"
    app_folder.mkdir()
    (app_folder / "42.mjbx").touch()

    jobs = JibreelDesktopImportPlanner(tmp_path / "staging").plan(
        app_folder, frozenset({"42"})
    )

    assert jobs == ()
