#!/usr/bin/env python3
"""Write a first upgrade_analysis_work.txt for a module that has none.

A BOOTSTRAP, not a build step. It runs once per module to turn the generated
analysis into an annotated work file; from then on the file is hand-edited like
any other, and re-running this would clobber that. Nothing calls it
automatically and no Makefile target rebuilds it.

Every marker it writes is derived, and the derivation is stated so a reader can
re-check it rather than trust it:

  * An XML-record line is classified from ITS OWN TEXT. Whether a record carries
    `(noupdate)`, whether the line is NEW or DEL, and whether it is an ir.access
    replacing an ir.model.access or ir.rule, is all right there -- these are
    classifications, not judgements about data.
  * A FIELD line is classified from the MIGRATED DATABASE: how many rows the
    model has, whether the column exists, whether it is empty, uniform, or
    varies. Same measurement classify_analysis_lines.py reports.
  * A field line the database cannot settle gets no generated marker at all. It
    is left bare on purpose, so that `grep -c 'NEEDS A VERDICT'` counts exactly
    the lines still owed a human, and the file never pretends otherwise.

Usage:  bootstrap_work_file.py MODULE [MODULE ...] [--db NAME] [--container NAME]
        bootstrap_work_file.py --check MODULE   # print the plan, write nothing

Run from the root of an OpenUpgrade series clone. Refuses a module that already
has a work file.
"""

import collections
import glob
import os
import re
import subprocess
import sys

FIELD = re.compile(
    r"^(?P<module>\S+)\s*/\s*(?P<model>[\w.]+)\s*/\s*(?P<field>\S+)\s*"
    r"\((?P<type>[^)]*)\)\s*:\s*(?P<what>.*)$"
)
XML_RECORD = re.compile(r"^(?P<verb>NEW|DEL) (?P<model>[\w.]+): (?P<xmlid>\S+)")

NEEDS_A_VERDICT = "# NEEDS A VERDICT: the database cannot settle this one"

ACCESS_MODELS = {"ir.access", "ir.model.access", "ir.rule"}


def classify_model(line):
    """A marker for a model line, read off the line itself.

    The analysis writes one of `new model X` or `obsolete model X`, optionally
    tagged [abstract], [transient] or [sql_view], optionally noting a rename.
    Each of those says what to do without asking the database.
    """
    stripped = line.strip()
    if not stripped.startswith(("new model", "obsolete model")):
        return None
    if "renamed to" in stripped or "renamed from" in stripped:
        return (
            "# NOTHING TO DO: a model rename, which apriori declares and base's "
            "update_module_names performs -- the table and its rows are carried"
        )
    if "[abstract]" in stripped:
        return "# NOTHING TO DO: an abstract model has no table"
    if "[transient]" in stripped:
        return "# NOTHING TO DO: a transient model holds no persistent data"
    if "[sql_view]" in stripped:
        return "# NOTHING TO DO: a SQL view holds no rows of its own"
    if stripped.startswith("new model"):
        return (
            "# NOTHING TO DO: the ORM creates the table; there are no 19.0 rows "
            "to carry into a model that did not exist"
        )
    return (
        "# NOTHING TO DO: the table is left in place for database_cleanup rather "
        "than dropped during an upgrade, which is the anti-pattern upstream "
        "rejected in #5630-5632"
    )


def classify_xml(line):
    """A marker for an XML-record line, read off the line itself."""
    noupdate = "(noupdate)" in line
    if "noupdate switched" in line:
        return (
            "# NOTHING TO DO: only the noupdate flag changed, the definition is "
            "the same"
        )
    m = XML_RECORD.match(line.strip())
    if not m:
        if "ir.model.constraint" in line:
            return (
                "# NOTHING TO DO: a constraint the ORM applies itself; the "
                "constraint gate reports any it could not"
            )
        return None
    if m["model"] in ACCESS_MODELS:
        return (
            "# NOTHING TO DO: base folds ir.model.access and ir.rule into "
            "ir.access, keeping the xml_ids"
        )
    if m["verb"] == "NEW":
        return (
            "# NOTHING TO DO: the record is not noupdate, so the module update "
            "creates it"
        )
    if noupdate:
        return (
            "# NOTHING TO DO: left alone. _process_end only removes a stale row "
            "whose noupdate is false, and writing an orphan cleanup is the "
            "anti-pattern upstream rejected in #5630-5632"
        )
    return (
        "# NOTHING TO DO: the record is not noupdate, so the module update removes it"
    )


class Database:
    """Read-only, memoised access to the migrated database."""

    def __init__(self, container, name):
        self.container, self.name, self._cache = container, name, {}

    def query(self, sql):
        if sql not in self._cache:
            out = subprocess.run(
                # fmt: off
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
                # fmt: on
                capture_output=True,
                text=True,
            )
            self._cache[sql] = (out.stdout.strip(), out.returncode)
        return self._cache[sql]

    def column(self, model, field):
        table = model.replace(".", "_")
        out, code = self.query(f"SELECT count(*) FROM {table}")
        if code:
            return None
        rows = int(out)
        out, code = self.query(
            f"SELECT count({field}), count(DISTINCT {field}) FROM {table}"
        )
        if code:
            return (rows, None, None)
        filled, distinct = (int(x) for x in out.split("|"))
        return (rows, filled, distinct)


def _selection_marker(db, match, removed):
    """A removed selection key is answerable: does any row still hold one?

    check_selection_values.py gates exactly this across the whole database, so
    the only thing left to say per line is what THIS column holds -- which is a
    count, not a judgement.
    """
    keys = [k.strip().strip("'\"") for k in removed.split(",") if k.strip()]
    table = match["model"].replace(".", "_")
    field = match["field"]
    quoted = ", ".join("'" + k.replace("'", "''") + "'" for k in keys)
    if not keys:
        return None
    out, code = db.query(
        f"SELECT count(*) FROM {table} WHERE {field}::text IN ({quoted})"
    )
    if code:
        return None
    if out == "0":
        return (
            f"# NOTHING TO DO: no row holds {' or '.join(keys)} any more, so the "
            f"key 20.0 dropped left nothing behind -- and check_selection_values "
            f"gates that across every stored selection"
        )
    return None  # rows still hold a dropped key: that is a finding, not a note


def classify_field(db, line):
    """A marker for a field line, measured; None when it needs a human."""
    m = FIELD.match(line.strip())
    if not m:
        return None
    what = m["what"]
    if "module is now" in what or "previously in module" in what:
        return (
            "# NOTHING TO DO: the field only changed owning module, the column "
            "is the same"
        )
    keys_removed = re.search(r"selection_keys removed: \[([^\]]*)\]", what)
    if keys_removed:
        return _selection_marker(db, m, keys_removed.group(1))
    if "selection_keys added" in what:
        return (
            "# NOTHING TO DO: keys were added to the selection, so every stored "
            "value stays valid"
        )
    measured = db.column(m["model"], m["field"])
    if measured is None:
        return (
            f"# NOTHING TO DO: 20.0 has no table for {m['model']}, so no column "
            f"survived to hold a wrong value"
        )
    rows, filled, distinct = measured
    if filled is None:
        return (
            f"# NOTHING TO DO: 20.0 has no {m['field']} column on "
            f"{m['model']}, so nothing was left behind"
        )
    if rows == 0:
        return (
            f"# NOTHING TO DO: {m['model']} holds no rows carried from 19.0, so "
            f"a default applies at creation and there is nothing to carry"
        )
    if what.startswith("NEW") or "is now stored" in what:
        if filled == 0:
            return (
                f"# NOTHING TO DO: empty on all {rows} rows -- nothing claimed "
                f"to fill it, so a NULL is what 19.0 knew"
            )
        if distinct > 1:
            return (
                f"# NOTHING TO DO: 20.0 filled it itself -- {distinct} distinct "
                f"values over {filled} of {rows} rows, so a compute or a related "
                f"field did the work"
            )
        return None  # uniform on a populated table: the defaulted-columns gate's
    if what.startswith("DEL"):
        if filled == 0:
            return (
                f"# NOTHING TO DO: the column held nothing on any of the {rows} "
                f"rows, so its removal carries nothing away"
            )
        return None  # still holds data: a question, not a finding
    return None


def annotate(db, path, verdicts):
    """The analysis, verbatim, with a marker after each line or run of lines."""
    lines = open(path).read().splitlines()
    out, markers = [], []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("---"):
            marker = None
        else:
            # A hand-written verdict WINS over a mechanical one. Both are true,
            # but "moved to res.company, where the value already is" tells a
            # reader more than "the column held nothing".
            marker = None
            field = FIELD.match(stripped)
            if field:
                key = f"{field['module']}:{field['model']}.{field['field']}"
                marker = verdicts.get(key)
            if marker is None:
                marker = (
                    classify_field(db, line)
                    or classify_xml(line)
                    or classify_model(line)
                )
            if marker is None and field:
                marker = NEEDS_A_VERDICT
        markers.append((line, marker))

    # Emit one marker per RUN of consecutive lines sharing it, which is how the
    # hand-written files read -- a marker repeated per line is noise.
    for i, (line, marker) in enumerate(markers):
        out.append(line)
        nxt = markers[i + 1][1] if i + 1 < len(markers) else object()
        if marker is not None and marker != nxt:
            out.extend(marker.splitlines())
    return "\n".join(out) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(
        a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a
    )
    check_only = "--check" in sys.argv
    if not args:
        print(__doc__)
        return 2
    db = Database(
        opts.get("container", "openupgrade-lab-db-1"),
        opts.get("db", "openupgrade_20_test"),
    )
    verdicts = load_verdicts()
    total = collections.Counter()
    for module in args:
        found = glob.glob(
            f"openupgrade_scripts/scripts/{module}/*/upgrade_analysis.txt"
        )
        if not found:
            print(f"::error::no analysis for {module}")
            return 2
        path = found[0]
        work = os.path.join(os.path.dirname(path), "upgrade_analysis_work.txt")
        if os.path.exists(work):
            print(f"::error::{module} already has a work file; refusing to overwrite")
            return 2
        text = annotate(db, path, verdicts)
        owed = text.count(NEEDS_A_VERDICT)
        total["lines"] += len(text.splitlines())
        total["owed"] += owed
        if check_only:
            print(f"{module}: {len(text.splitlines())} lines, {owed} needing a verdict")
            continue
        with open(work, "w") as handle:
            handle.write(text)
        print(f"wrote {work}: {len(text.splitlines())} lines, {owed} needing a verdict")
    print(f"\ntotal {total['lines']} lines, {total['owed']} still owed a verdict")
    return 0


VERDICT_FILE = "work_file_verdicts.txt"


def load_verdicts():
    """Hand-written verdicts, read from work_file_verdicts.txt beside this script.

    These are the lines the database cannot settle -- a DEL field whose column
    still holds its 19.0 values, or a NEW one uniform on a populated table. Each
    was read against 20.0's source, and the reason says what was FOUND rather
    than that somebody looked.

    They live in a data file rather than in this source for two reasons: they are
    prose, which reads badly as Python string literals, and a reviewer should be
    able to read the verdicts without reading the generator.

    Format -- a key on its own line, then its marker lines, then a blank line:

        module:model.field
        # NOTHING TO DO: ...
        # ... continued

    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), VERDICT_FILE)
    if not os.path.exists(path):
        return {}
    out, key, lines = {}, None, []
    for raw in open(path).read().splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("##"):
            if key and lines:
                out[key] = "\n".join(lines)
            key, lines = None, []
            continue
        if line.startswith("#"):
            lines.append(line)
        else:
            key = line.strip()
    if key and lines:
        out[key] = "\n".join(lines)
    return out


if __name__ == "__main__":
    sys.exit(main())
