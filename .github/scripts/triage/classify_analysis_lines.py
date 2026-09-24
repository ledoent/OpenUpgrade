#!/usr/bin/env python3
"""TRIAGE TOOL, NOT A GATE. Classify analysis field lines against the database.

The three files in the directory above are gates: they fail a build. This one
answers a question a human then has to act on, so it always exits 0 and is wired
into nothing. It lives here rather than in a scratch directory because the list
it produces was rebuilt from scratch three times before it was written down.

For every field line in the named modules' upgrade_analysis.txt it reads the
MIGRATED database and reports what actually happened to that column. Most lines
settle without a judgment call:

    model holds no rows            a default at creation is the whole story
    model has no table in 20.0     a model-level change, not a field question
    column absent in 20.0          nothing survived to be wrong about
    NEW, empty everywhere          nothing claimed to fill it
    NEW, 20.0 populated it         a compute or a related field did the work
    NEW, uniform at its default    a new setting -- and check_rename_pairs'
                                   rule 2 is what covers the case where that
                                   uniformity is shadowing a DEL sibling
    DEL, column held nothing       there was nothing to carry

and one does not:

    DEL, column STILL HOLDS DATA   the field is gone and its values are still
                                   sitting in the table

That last verdict is a QUESTION, not a finding, and reading it as a finding
would waste a day. The data may already have been carried elsewhere by a script;
the field may simply have MOVED MODULES, which the analysis also reports as a
DEL (sale_timesheet's `so_line` is reported DEL and is alive and well in 20.0);
or it may be a real loss. Over the 20 modules that carry field lines and no
upgrade_analysis_work.txt it separates 60 lines from 445.

Usage:  classify_analysis_lines.py [--db=NAME] [--container=NAME] [MODULE ...]

Run it from the root of an OpenUpgrade series clone. It reaches the database
through `docker exec` on the lab's db container, which is how a migrated
database is reachable locally; the gates beside it take a --dsn instead because
CI runs them with the database already on localhost.
"""

import collections
import glob
import re
import subprocess
import sys

# The 20 modules that have analysis field lines and no upgrade_analysis_work.txt.
DEFAULT_MODULES = """
account_edi_ubl_cii calendar event fleet hr_expense hr_recruitment hr_timesheet
hr_work_entry l10n_th mail maintenance payment_custom portal pos_restaurant
pos_self_order project sale_timesheet website website_blog website_event_track
""".split()

FIELD = re.compile(
    r"^(?P<module>\S+)\s*/\s*(?P<model>[\w.]+)\s*/\s*(?P<field>\S+)\s*"
    r"\((?P<type>[^)]*)\)\s*:\s*(?P<what>.*)$"
)

NEEDS_A_HUMAN = "DEL, column STILL HOLDS DATA"


class Database:
    """Read-only access to the migrated database, memoised.

    One query per column over 3,000 analysis lines is thousands of round trips
    through `docker exec`, and the same tables recur constantly.
    """

    def __init__(self, container, name):
        self.container = container
        self.name = name
        self._cache = {}

    def query(self, sql):
        if sql not in self._cache:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container,
                    "psql",
                    "-U",
                    "odoo",
                    "-d",
                    self.name,
                    "-tAc",
                    sql,
                ],
                capture_output=True,
                text=True,
            )
            self._cache[sql] = (result.stdout.strip(), result.returncode)
        return self._cache[sql]

    def row_count(self, table):
        out, code = self.query(f"SELECT count(*) FROM {table}")
        return None if code else int(out)

    def column(self, table, name):
        """(rows, non-null, distinct) or None when there is no such column."""
        out, code = self.query(
            f"SELECT count(*), count({name}), count(DISTINCT {name}) FROM {table}"
        )
        if code:
            return None
        return tuple(int(value) for value in out.split("|"))


def verdict_for(db, line):
    """What the database says happened to one analysis line, or None to skip."""
    match = FIELD.match(line.strip())
    if not match:
        return None
    parsed = match.groupdict()
    table = parsed["model"].replace(".", "_")

    rows = db.row_count(table)
    if rows is None:
        return "model has no table in 20.0", parsed, None
    if rows == 0:
        return "model holds no rows", parsed, None

    measured = db.column(table, parsed["field"])
    if measured is None:
        return "column absent in 20.0", parsed, None
    _, filled, distinct = measured

    if parsed["what"].startswith("NEW"):
        if distinct > 1:
            return "NEW, 20.0 populated it (varies)", parsed, measured
        if filled == 0:
            return "NEW, empty everywhere", parsed, measured
        return "NEW, uniform at its default", parsed, measured
    if parsed["what"].startswith("DEL"):
        if filled == 0:
            return "DEL, column held nothing", parsed, measured
        return NEEDS_A_HUMAN, parsed, measured
    return "other (selection or type change)", parsed, measured


def main():
    modules = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_MODULES
    options = dict(
        a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a
    )
    db = Database(
        options.get("container", "openupgrade-lab-db-1"),
        options.get("db", "openupgrade_20"),
    )

    analyses = [
        path
        for module in modules
        for path in glob.glob(f"openupgrade_scripts/scripts/{module}/*/*.txt")
        if path.endswith("upgrade_analysis.txt")
    ]
    if not analyses:
        print(
            "no upgrade_analysis.txt found -- run this from the root of an "
            "OpenUpgrade series clone",
            file=sys.stderr,
        )
        return 0

    verdicts = collections.Counter()
    residue = []
    for path in analyses:
        with open(path) as handle:
            for line in handle:
                answer = verdict_for(db, line)
                if answer is None:
                    continue
                name, parsed, measured = answer
                verdicts[name] += 1
                if name == NEEDS_A_HUMAN:
                    residue.append((parsed, measured))

    print(f"{len(analyses)} analyses, {sum(verdicts.values())} field lines\n")
    for name, count in verdicts.most_common():
        print(f"  {count:5}  {name}")

    print(f"\n{len(residue)} line(s) the database cannot settle:")
    for parsed, measured in sorted(
        residue, key=lambda item: (item[0]["module"], item[0]["model"])
    ):
        _, filled, distinct = measured
        print(
            f"  {parsed['module']:22} {parsed['model']}.{parsed['field']}"
            f"  filled={filled} distinct={distinct}"
        )
    print(
        "\nEach of those is a QUESTION: the column still holds its 19.0 values. "
        "It may already have been carried by a script, the field may only have "
        "moved modules, or it may be a real loss. Read it before believing it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
