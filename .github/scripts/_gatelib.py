#!/usr/bin/env python3
"""The two pieces every gate in this directory needs, in one place.

Each check here reads the same two sources -- the generated analysis for WHERE
to look, and the migrated database for WHAT happened -- so each had grown its
own copy of the connection helper and of the regex that parses an analysis field
line. Four copies of `connect` and three of the regex is three chances for them
to drift, and a gate whose parser drifts reports a clean run over lines it
silently failed to read.

Imported as a plain module rather than a package: CI runs each gate as
`python3 .github/scripts/<gate>.py`, and Python puts the script's own directory
on sys.path, so `from _gatelib import ...` resolves without any packaging.
"""

import re

# "module / model / field (type) : NEW|DEL ..." as the analysis writes it.
FIELD = re.compile(
    r"^(?P<module>\S+)\s*/\s*(?P<model>[\w.]+)\s*/\s*(?P<field>\S+)\s*"
    r"\((?P<type>[^)]*)\)\s*:\s*(?P<what>.*)$"
)


def connect(dsn):
    """A connection to the migrated database, or None having said why.

    Returning None rather than raising is what lets each gate exit 2 --
    "could not check" -- distinctly from exit 1, "checked and found something".
    A gate that cannot reach the database must never report a clean run.
    """
    try:
        import psycopg2
    except ImportError:
        print("::error::psycopg2 is needed to read the migrated database")
        return None
    try:
        return psycopg2.connect(dsn) if dsn else psycopg2.connect("")
    except Exception as exc:  # noqa: BLE001 - any failure here is fatal alike
        print(f"::error::cannot reach the migrated database: {exc}")
        return None
