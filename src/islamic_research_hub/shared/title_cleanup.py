"""Cosmetic cleanup for titles derived from raw filenames.

Some libraries (Maknoon, the Jibreel PDF Archive) have no real cataloged
title, only the source file's name (e.g. "KHUTBAAT_E_ALI_MIYAN_VOL_8").
This does not recover a real title - it only makes an all-caps,
underscore-separated filename more readable, leaving already-readable
mixed-case titles untouched.
"""


def clean_filename_title(raw_title: str) -> str:
    """Return a more readable title for an all-caps, underscore-style filename."""
    cleaned = " ".join(raw_title.replace("_", " ").split())
    letters = [character for character in raw_title if character.isalpha()]
    if letters and all(character.isupper() for character in letters):
        cleaned = cleaned.title()
    return cleaned
