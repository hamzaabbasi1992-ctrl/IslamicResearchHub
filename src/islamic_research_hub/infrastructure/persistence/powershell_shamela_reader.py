"""Reads Maktaba Shamela's .mdb files (Jet 3/Access-97 format) via ADODB.

Every modern ACE-based provider (ODBC, DAO, `Microsoft.ACE.OLEDB.12.0`)
refuses to open these files ("Cannot open a database created with a
previous version"). The older `Microsoft.Jet.OLEDB.4.0` provider opens
them correctly, but is 32-bit only - the same "32-bit-only DLL" shape
already solved for Jibreel Desktop's `.mjbx` decryption
(`powershell_mjbx_decryptor.py`), so this follows that exact
shell-out-to-32-bit-PowerShell architecture: a JSON jobs file in, a JSON
results file out, per-file error isolation inside the PowerShell script
itself so one bad file never aborts the batch.

Each real book's `.mdb` has exactly two tables - "book" (page content)
and "title" (table-of-contents headings) - but the "book" table's real
column set varies between files (confirmed directly: some carry a
"seal" column, others carry "hno"/"Sora"/"Aya"/"na" instead), so rows
are read back as flexible `dict`s rather than a fixed shape.
"""

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_POWERSHELL_32BIT = Path(r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe")
SECONDS_PER_JOB = 2
BASE_TIMEOUT_SECONDS = 60

_SCRIPT_PATH = Path(__file__).parent / "scripts" / "read_shamela_mdb.ps1"

RawRow = dict[str, str | int | float | None]


@dataclass(frozen=True)
class ShamelaRawBook:
    """One .mdb file's raw, unprocessed rows - not yet a domain `Book`."""

    path: Path
    succeeded: bool
    error: str | None
    book_rows: tuple[RawRow, ...]
    title_rows: tuple[RawRow, ...]


class ShamelaReaderError(Exception):
    """Raised when the read batch script itself could not be run."""


class PowerShellShamelaReader:
    """Read a batch of real Shamela `.mdb` files via `Microsoft.Jet.OLEDB.4.0`."""

    def __init__(self, powershell_path: Path = DEFAULT_POWERSHELL_32BIT) -> None:
        self._powershell_path = powershell_path

    def read_all(self, paths: tuple[Path, ...]) -> tuple[ShamelaRawBook, ...]:
        """Read each `.mdb` file, continuing past individual failures.

        A file that fails to open/read (missing, corrupted, an
        unexpected schema) is reported with `succeeded=False` and a real
        `error` message - it does not stop the rest of the batch or raise.
        """
        if not paths:
            return ()

        with tempfile.TemporaryDirectory() as tmp_dir:
            jobs_file = Path(tmp_dir) / "jobs.json"
            results_file = Path(tmp_dir) / "results.json"
            jobs_file.write_text(
                json.dumps([{"Path": str(path)} for path in paths]),
                encoding="utf-8",
            )

            try:
                subprocess.run(
                    [
                        str(self._powershell_path),
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(_SCRIPT_PATH),
                        "-JobsFile",
                        str(jobs_file),
                        "-ResultsFile",
                        str(results_file),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=len(paths) * SECONDS_PER_JOB + BASE_TIMEOUT_SECONDS,
                )
            except (subprocess.SubprocessError, OSError) as error:
                LOGGER.exception("Shamela read batch script failed to run.")
                raise ShamelaReaderError("The Shamela read script could not be run.") from error

            try:
                raw_results = _read_ndjson(results_file)
            except (OSError, json.JSONDecodeError) as error:
                LOGGER.exception("Shamela read batch produced an unreadable results file.")
                raise ShamelaReaderError(
                    "The Shamela read script's results could not be read."
                ) from error

            if not raw_results:
                # Real bug found and fixed: a large batch could make
                # PowerShell's ConvertTo-Json throw OutOfMemoryException
                # while still exiting 0 - the results file ends up empty
                # with no other signal anything went wrong. Jobs were
                # submitted, so zero results back is never legitimate.
                LOGGER.error(
                    "Shamela read batch returned no results for %d submitted file(s).",
                    len(paths),
                )
                raise ShamelaReaderError(
                    f"The Shamela read script returned no results for {len(paths)} file(s)."
                )

        return tuple(
            ShamelaRawBook(
                path=Path(entry["Path"]),
                succeeded=entry["Succeeded"],
                error=entry["Error"],
                book_rows=_as_row_tuple(entry["BookRows"]),
                title_rows=_as_row_tuple(entry["TitleRows"]),
            )
            for entry in raw_results
        )


def _read_ndjson(results_file: Path) -> list[dict]:
    """Parse the results file as newline-delimited JSON (one compact
    object per file processed) - streamed by the PowerShell side rather
    than written as one giant JSON array, so a single very large batch
    can't exhaust 32-bit PowerShell's limited address space serializing
    everything in one `ConvertTo-Json` call (a real crash found and
    fixed - see `read_shamela_mdb.ps1`'s docstring).

    PowerShell's `StreamWriter` with `UTF8Encoding` writes a UTF-8 BOM;
    `utf-8-sig` strips it if present and is otherwise identical to utf-8.
    """
    text = results_file.read_text(encoding="utf-8-sig")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _as_row_tuple(rows: RawRow | list[RawRow] | None) -> tuple[RawRow, ...]:
    """Normalize PowerShell's JSON output: a single row isn't wrapped in a
    list, and no rows serializes as null rather than an empty list."""
    if rows is None:
        return ()
    if isinstance(rows, dict):
        return (rows,)
    return tuple(rows)
