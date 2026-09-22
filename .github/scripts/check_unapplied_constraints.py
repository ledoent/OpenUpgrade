#!/usr/bin/env python3
"""Fail when the upgrade could not establish a constraint the new version declares.

When migrated data does not satisfy a constraint, Odoo logs one INFO line and
carries on:

    Constraint not added: column "provider_id" of relation "payment_method"
    contains null values

The upgrade still exits 0, so neither the migration job nor checklog-odoo, which
only reacts to WARNING and above, notices. Every such line is a 20.0 invariant
the database does not hold -- a field the migration should have filled, a rename
it should have performed, or rows it should have reconciled. On the run that
first exited 0 there were twelve, and behind one of them was every company but
one losing its payment methods.

The log line alone is not the verdict. It is written while the table is being
reshaped, which is *before* post-migration and end-migration run, so a script
that repairs the data cannot stop the line being emitted. Reading the log and
nothing else would report a fixed defect as broken for ever, and the natural
reaction -- allowlist it -- would blind the check to a real regression later.

So the log only says which constraints to look at; the database says whether
they hold now. All three shapes Odoo reports are answerable from the schema:

  * "contains null values" -- count the nulls that are left.
  * "check constraint N ... is violated by some row" -- ask whether N exists.
  * "could not create unique index N" -- ask whether N exists.

The last two matter more than they look. A module that owns a stricter rule than
the one being attempted replaces it a moment later in the same run, and the
replacement succeeds: `account` cannot build its broad account_move_unique_name
while LATAM vendor bills are present, and then l10n_latam_invoice_document
installs the narrower index that is the real rule. The log records the first
attempt; only the schema knows how it ended.

ALLOWED is a last resort for a constraint that is genuinely absent and genuinely
acceptable. It should stay empty; an entry needs a reason saying why the database
is correct without the constraint, never merely to quiet a failure.

Usage:  check_unapplied_constraints.py <migration-log> [--dsn DSN]

The connection comes from --dsn, else from the standard libpq environment
(PGHOST, PGDATABASE, PGUSER, ...). It is required: a run that cannot reach the
database fails rather than degrading to a log-only check, because a check that
quietly gets weaker is indistinguishable from one that passes.
"""

import argparse
import re
import sys

PATTERN = re.compile(r"Constraint not added: (.+?)\s*$", re.MULTILINE)
NULL_COLUMN = re.compile(
    r'^column "(?P<column>[^"]+)" of relation "(?P<table>[^"]+)" contains null values$'
)
CHECK_CONSTRAINT = re.compile(
    r'^check constraint "(?P<name>[^"]+)" of relation "(?P<table>[^"]+)" '
    r"is violated by some row$"
)
UNIQUE_INDEX = re.compile(r'^could not create unique index "(?P<name>[^"]+)"$')

# Message payload -> why it is acceptable that the constraint is genuinely
# absent. Keep this empty if at all possible.
ALLOWED = {}


def connect(dsn):
    try:
        import psycopg2
    except ImportError:
        print("::error::psycopg2 is needed to verify the migrated database")
        return None
    try:
        return psycopg2.connect(dsn) if dsn else psycopg2.connect("")
    except Exception as exc:  # noqa: BLE001 - any failure here is fatal alike
        print(f"::error::cannot reach the migrated database: {exc}")
        return None


def count_nulls(cur, table, column):
    """Rows still holding NULL, or None when the column no longer exists.

    A missing column is not "no nulls": it means the upgrade went somewhere this
    check does not understand, and saying so beats reporting a pass.
    """
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    if not cur.fetchone():
        return None
    cur.execute(f'SELECT count(*) FROM "{table}" WHERE "{column}" IS NULL')
    return cur.fetchone()[0]


def constraint_exists(cur, table, name):
    cur.execute(
        """
        SELECT 1 FROM pg_constraint
        WHERE conname = %s AND conrelid = %s::regclass
        """,
        (name, table),
    )
    return bool(cur.fetchone())


def index_exists(cur, name):
    cur.execute("SELECT 1 FROM pg_indexes WHERE indexname = %s", (name,))
    return bool(cur.fetchone())


def verdict(cur, payload):
    """(resolved?, why) for one 'Constraint not added' payload."""
    match = NULL_COLUMN.match(payload)
    if match:
        table, column = match.group("table"), match.group("column")
        nulls = count_nulls(cur, table, column)
        if nulls is None:
            return False, f"{table}.{column} does not exist after the upgrade"
        if nulls:
            return False, f"{nulls} row(s) still NULL"
        return True, "0 rows NULL after the full run"

    match = CHECK_CONSTRAINT.match(payload)
    if match:
        table, name = match.group("table"), match.group("name")
        if constraint_exists(cur, table, name):
            return True, "the constraint is present in the final schema"
        return False, "the constraint is absent from the final schema"

    match = UNIQUE_INDEX.match(payload)
    if match:
        name = match.group("name")
        if index_exists(cur, name):
            return True, "the index is present in the final schema"
        return False, "the index is absent from the final schema"

    if payload in ALLOWED:
        return True, ALLOWED[payload]
    return False, "unrecognised message and not allowlisted"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="the migration log to read")
    parser.add_argument(
        "--dsn",
        help="libpq connection string; defaults to the PG* environment",
    )
    opts = parser.parse_args()
    dsn = opts.dsn

    try:
        with open(opts.log, encoding="utf-8", errors="replace") as fobj:
            log = fobj.read()
    except OSError as exc:
        print(f"::error::cannot read the migration log: {exc}")
        return 2

    # A log with no upgrade in it must not pass for lack of findings.
    if "Modules loaded." not in log:
        print(
            "::error::the log has no 'Modules loaded.' line, so no upgrade ran "
            "and this check proves nothing"
        )
        return 2

    found = []
    for match in PATTERN.finditer(log):
        payload = match.group(1)
        if payload not in found:
            found.append(payload)
    if not found:
        print("OK: the upgrade applied every constraint it declares.")
        return 0

    conn = connect(dsn)
    if conn is None:
        return 2

    resolved, failures = [], []
    with conn, conn.cursor() as cur:
        for payload in found:
            ok, why = verdict(cur, payload)
            (resolved if ok else failures).append((payload, why))

    for payload, why in resolved:
        print(f"resolved: {payload}\n          -> {why}")

    if not failures:
        print(f"\nOK: {len(resolved)} reported, all resolved by the end of the run.")
        return 0

    print()
    for payload, why in failures:
        print(f"::error::{payload} -- {why}")
    print(
        f"\n{len(failures)} constraint(s) the new version declares are missing from "
        f"the migrated database, and the data still does not satisfy them. Each one "
        f"is data the migration should have produced and did not."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
