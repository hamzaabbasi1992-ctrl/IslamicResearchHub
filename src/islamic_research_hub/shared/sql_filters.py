"""Small shared SQL-fragment builders used by more than one repository,
so a filter that needs to support both a single value and several
values at once (the multi-library search scope picker) isn't
implemented twice with two different bugs."""


def library_filter_clause(
    column_expression: str, library: str | tuple[str, ...] | None
) -> tuple[str, list[object]]:
    """Return (SQL fragment, parameters) for filtering by one or more
    library names against `column_expression` (e.g. "Libraries.Name").

    `None` returns no filter at all (unchanged pre-existing behavior for
    every caller written before multi-library selection existed). A
    plain `str` returns the exact same `= ?` fragment those same callers
    already produced - this is purely additive, not a behavior change,
    for anyone who never passes a tuple. A `tuple`/`list` of more than
    one name returns a real `IN (...)` fragment.
    """
    if library is None:
        return "", []
    if isinstance(library, str):
        return f" AND {column_expression} = ?", [library]
    names = tuple(library)
    if not names:
        return "", []
    if len(names) == 1:
        return f" AND {column_expression} = ?", [names[0]]
    placeholders = ", ".join("?" for _ in names)
    return f" AND {column_expression} IN ({placeholders})", list(names)
