"""Decrypts Jibreel Desktop's .mjbx files via the app's own SQLite library.

The .mjbx format is the same verified schema as .mjbz, wrapped in
System.Data.SQLite's built-in encryption. The password below was found by
extracting readable strings from the app's own executable (a standard
diagnostic technique, not binary cracking) - see CHANGELOG for the full
investigation, including the second, unidentified password that locks a
minority of files (those simply fail to decrypt and are skipped, not a
crash - see decrypt_all below).

The app's System.Data.SQLite.dll is 32-bit only, so this shells out to
32-bit PowerShell rather than reimplementing SQLite's encryption in
Python - decrypting via the app's own library, the way the app itself
would, is both simpler and more reliable than reverse-engineering the
on-disk format.
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from islamic_research_hub.application.jibreel_desktop_import import DecryptResult

LOGGER = logging.getLogger(__name__)

DEFAULT_PASSWORD = "mjbx_P@ssw0rd"
DEFAULT_POWERSHELL_32BIT = Path(r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe")
SECONDS_PER_JOB = 2
BASE_TIMEOUT_SECONDS = 60

_SCRIPT_PATH = Path(__file__).parent / "scripts" / "decrypt_mjbx.ps1"


class MjbxDecryptorError(Exception):
    """Raised when the decryption batch script itself could not be run."""


class PowerShellMjbxDecryptor:
    """Decrypt .mjbx files via the Jibreel Desktop app's own SQLite library."""

    def __init__(
        self,
        sqlite_dll_path: Path,
        password: str = DEFAULT_PASSWORD,
        powershell_path: Path = DEFAULT_POWERSHELL_32BIT,
    ) -> None:
        self._sqlite_dll_path = sqlite_dll_path
        self._password = password
        self._powershell_path = powershell_path

    def decrypt_all(self, jobs: tuple[tuple[Path, Path], ...]) -> tuple[DecryptResult, ...]:
        """Decrypt each (source, destination) pair, continuing past individual failures.

        A file that fails to decrypt (wrong/unknown password, corrupted
        file, etc.) is reported as `succeeded=False` in the result - it
        does not stop the rest of the batch or raise.
        """
        if not jobs:
            return ()

        with tempfile.TemporaryDirectory() as tmp_dir:
            jobs_file = Path(tmp_dir) / "jobs.json"
            results_file = Path(tmp_dir) / "results.json"
            jobs_file.write_text(
                json.dumps(
                    [{"Source": str(source), "Destination": str(dest)} for source, dest in jobs]
                ),
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
                        "-SqliteDllPath",
                        str(self._sqlite_dll_path),
                        "-Password",
                        self._password,
                        "-ResultsFile",
                        str(results_file),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=len(jobs) * SECONDS_PER_JOB + BASE_TIMEOUT_SECONDS,
                )
            except (subprocess.SubprocessError, OSError) as error:
                LOGGER.exception("Decryption batch script failed to run.")
                raise MjbxDecryptorError("The decryption script could not be run.") from error

            # PowerShell's Out-File -Encoding utf8 writes a UTF-8 BOM; utf-8-sig
            # strips it if present and is otherwise identical to utf-8.
            raw_results = json.loads(results_file.read_text(encoding="utf-8-sig"))

        return tuple(
            DecryptResult(
                source=Path(entry["Source"]),
                destination=Path(entry["Destination"]),
                succeeded=entry["Succeeded"],
            )
            for entry in raw_results
        )
